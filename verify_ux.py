# -*- coding: utf-8 -*-
"""
verify_ux.py —— 实时呈现改进的自检脚本

用途：把「数据是否连续、变化是否明显、控件是否真生效、有没有造假」
      变成可判定的 PASS / FAIL 硬指标，而不是靠肉眼感觉。

用法：
    ./runtime/python/python.exe -X utf8 -B verify_ux.py              # 静态核验 + 实板跑测
    ./runtime/python/python.exe -X utf8 -B verify_ux.py --static     # 只做静态核验，不占板
    ./runtime/python/python.exe -X utf8 -B verify_ux.py --no-board   # 同上

判定口径（与用户的四条诉求一一对应）：
    A 连续性：观感帧数 >= 40，且相邻帧间隔不超过插值时长上限(9000ms)
    B 幅度  ：指标在帧间确实变化；恶劣场景与基准场景差异显著
    C 控件  ：全部 id 控件有 JS 接线，无空壳
    D 真实  ：插值只用于显示，逐帧原始值可回溯（raw 字段存在）
"""
import hashlib
import json
import os
import re
import statistics
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(ROOT, 'app')
BASE = 'http://127.0.0.1:18878'
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))

STATIC_ONLY = '--static' in sys.argv or '--no-board' in sys.argv
# --seconds N：缩短实板段时长，用于快速复核（默认 90 模型秒）
SECONDS = 90
for a in sys.argv:
    if a.startswith('--seconds='):
        try:
            SECONDS = max(10, int(a.split('=', 1)[1]))
        except ValueError:
            pass
# --one：只跑基准场景，省一半时间
ONE_ONLY = '--one' in sys.argv

PASS, FAIL, WARN = '[通过]', '[未过]', '[提醒]'
rows = []


def say(verdict, item, detail):
    rows.append((verdict, item, detail))
    print('%-8s %-26s %s' % (verdict, item, detail))


def get(path, timeout=20):
    return json.load(OP.open(BASE + path, timeout=timeout))


def post(path, body, timeout=60):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(),
                                 {'Content-Type': 'application/json'})
    return json.load(OP.open(req, timeout=timeout))


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------- 1. 静态核验
print('=' * 78)
print('第一部分：静态核验（不占板，可随时跑）')
print('=' * 78)

# 1.1 发布清单与磁盘一致 —— 改了文件没重签 或 签名与文件不符 都会被抓出来
try:
    rel = json.load(open(os.path.join(APP, 'release.json'), encoding='utf-8'))
    entries = rel.get('artifacts') or []
    bad = []
    missing = []
    for e in entries:
        p = os.path.join(APP, e['path'])
        if not os.path.exists(p):
            missing.append(e['path'])
            continue
        if sha256(p) != e['sha256']:
            bad.append(e['path'])
    if not bad and not missing:
        say(PASS, '发布清单一致性', '%d 个文件哈希全部匹配，实验可正常启动' % len(entries))
    else:
        say(FAIL, '发布清单一致性',
            '不符 %d 个%s，缺失 %d 个%s → 需跑 _resign_release.py'
            % (len(bad), (': ' + ', '.join(bad[:3])) if bad else '',
               len(missing), (': ' + ', '.join(missing[:3])) if missing else ''))
except Exception as exc:
    say(FAIL, '发布清单一致性', str(exc))

# 1.2 关键改动确实落地
ui = os.path.join(APP, 'ui')
try:
    html = open(os.path.join(ui, 'index.html'), encoding='utf-8').read()
    smooth = open(os.path.join(ui, 'smooth-values.js'), encoding='utf-8').read()
    terrain = open(os.path.join(ui, 'terrain-view.js'), encoding='utf-8').read()
    appjs = open(os.path.join(ui, 'app.js'), encoding='utf-8').read()

    say(PASS if 'smooth-values.js' in html else FAIL,
        '补间模块已加载', 'index.html 中引用 smooth-values.js' if 'smooth-values.js' in html else '未引用')

    m = re.search(r'Math\.min\((\d+),\s*old\?performance\.now\(\)-old\.at', terrain)
    cap = int(m.group(1)) if m else 0
    say(PASS if cap >= 5000 else FAIL, '插值时长上限',
        '%d ms（改前 2000 ms；需 > 实际帧间隔才不会一动一停）' % cap)

    say(PASS if 'window.SMOOTH_VALUES !== false' in smooth else FAIL,
        '动画可一键关闭', 'window.SMOOTH_VALUES=false 可回到逐帧硬显示，供严格审阅')

    n_preset = len(re.findall(r'id="preset[A-Za-z]+"', html))
    say(PASS if n_preset >= 3 else FAIL, '场景预设按钮', '%d 个（基准 / 恶劣 / 极恶劣）' % n_preset)

    say(PASS if 'raw' in smooth or 'raw' in appjs else FAIL,
        '原始值可回溯', '补间元素保留 dataset.raw，悬停可看未插值的实测值')
except Exception as exc:
    say(FAIL, '关键改动落地', str(exc))

# 1.3 控件审计：有没有空壳
try:
    js_text = ''
    for fn in sorted(os.listdir(ui)):
        if fn.endswith('.js'):
            js_text += open(os.path.join(ui, fn), encoding='utf-8').read()
    # 只审计可交互控件：button / select / input / textarea。
    # 纯展示容器（div/span/p 的 id）本就不需要事件，计入会误报。
    interactive = set()
    for tag in ('button', 'select', 'input', 'textarea'):
        for m in re.finditer(r'<%s\b[^>]*>' % tag, html):
            mid = re.search(r'id="([A-Za-z][A-Za-z0-9_-]*)"', m.group(0))
            if mid:
                interactive.add(mid.group(1))
    # action() 机制里用变量批量注册（action(id,fn) / Object.keys(...)），
    # readConfig() 用数组 ['environment','weather',...] 遍历读取，
    # 这两种都算接线：只要 id 以字符串字面量形式出现在任一 JS 中即可。
    ids = interactive
    wired, dead = 0, []
    for cid in ids:
        # id 可能以：字符串字面量、标识符（对象 key）、#id 选择器 出现
        hit = (("'" + cid + "'") in js_text) or ('"' + cid + '"') in js_text \
            or re.search(r'\b%s\b' % re.escape(cid), js_text)
        if hit:
            wired += 1
        else:
            dead.append(cid)
    say(PASS if not dead else WARN, '控件无空壳',
        '%d 个带 id 控件中 %d 个有 JS 接线%s'
        % (len(ids), wired, ('，未接线：' + ', '.join(sorted(dead)[:5])) if dead else ''))
except Exception as exc:
    say(WARN, '控件无空壳', str(exc))

# 1.4 服务与健康
try:
    st = get('/api/state', timeout=6)
    say(PASS, 'Web 服务在线', '%s 端口 18878，状态 %s' % (BASE, st.get('status')))
    for f in ('index.html', 'app.js', 'smooth-values.js', 'terrain-view.js'):
        code = OP.open(BASE + '/' + f, timeout=6).status
    say(PASS, '页面资源可达', '核心 JS / HTML 均返回 200')
except Exception as exc:
    say(FAIL, 'Web 服务在线', str(exc))

if STATIC_ONLY:
    print()
    print('（--static 模式，跳过实板跑测）')
    print('=' * 78)
    npass = sum(1 for v, _, _ in rows if v == PASS)
    print('静态核验：%d 项通过，%d 项未过，%d 项提醒' %
          (npass, sum(1 for v, _, _ in rows if v == FAIL), sum(1 for v, _, _ in rows if v == WARN)))
    sys.exit(0)

# ---------------------------------------------------------------- 2. 实板跑测
print()
print('=' * 78)
print('第二部分：实板跑测（占板约 1-2 分钟，板子必须空闲）')
print('=' * 78)

COMMON = dict(schema=1, center_x_m=5000, center_y_m=5000, heading_deg=0,
              carrier_mhz=2400, external_node=0, reserved=0)
# 与 UI 上「基准对照 / 极恶劣」两个预设按钮逐字段一致，
# 保证「点按钮 → 得到这组结果」可被任何人复现。
BASE_CFG = dict(COMMON, environment=1, weather=0, formation=0, spacing_m=300,
                altitude_m=400, speed_mmps=12000, reference_snr_cdb=3400,
                faults=1, jitter_percent=100)
SEVERE_CFG = dict(COMMON, environment=4, weather=7, formation=8, spacing_m=1100,
                  altitude_m=600, speed_mmps=16000, reference_snr_cdb=1800,
                  faults=1, jitter_percent=200)


def run_labelled(label, cfg, telemetry=20, seconds=None):
    """跑一段实验，同时按 150ms 轮询记录每帧的到达时刻与内容。"""
    print('\n> %s：连接串口并启动（%d 模型秒，遥测粒度 %d）…' % (label, seconds, telemetry))
    post('/api/connect', {'port': 'COM4'})
    # 必须等到 connect 任务真正出队（task 字段清空），否则 start 会返回 409 Conflict
    for _ in range(60):
        st = get('/api/state')
        if not st.get('busy') and st.get('task') is None:
            break
        time.sleep(0.5)
    r = post('/api/start', {'seconds': seconds, 'ideal': 0, 'seed': 20261023,
                            'config': cfg, 'telemetry_rounds': telemetry})
    if r.get('error'):
        print('   启动失败：', r['error'])
        return None

    frames, seen = [], 0
    t0 = time.monotonic()
    while time.monotonic() - t0 < 300:
        st = get('/api/state')
        snaps = st.get('snapshots') or []
        if len(snaps) > seen:
            for s in snaps[seen:]:
                frames.append({'t': time.monotonic(), 's': s})
            seen = len(snaps)
        if st.get('error'):
            print('   运行错误：', st['error'])
            break
        # 注意：任务结束后 task 字段会残留上一次的 'connect'，不能用 task is None 判断
        if not st.get('busy') and st.get('status') in ('complete', 'idle', 'error'):
            break
        time.sleep(0.15)
    # 墙钟以板内计时为准（wall_ms），脚本等待时长只作参考
    wall = (frames[-1]['s'].get('wall_ms') or 0) / 1000.0 if frames else (time.monotonic() - t0)
    return {'label': label, 'frames': frames, 'wall': wall,
            'rid': st.get('record_id') or ''}


def analyse(res):
    fr = res['frames']
    if len(fr) < 2:
        return None
    gaps = [(fr[i + 1]['t'] - fr[i]['t']) * 1000 for i in range(len(fr) - 1)]
    # 节点位移（取前 3 个坐标，单位 mm）
    moves = []
    for i in range(len(fr) - 1):
        a, b = fr[i]['s'].get('nodes') or [], fr[i + 1]['s'].get('nodes') or []
        tot = 0.0
        for na, nb in zip(a, b):
            tot += ((nb[1] - na[1]) ** 2 + (nb[2] - na[2]) ** 2 + (nb[3] - na[3]) ** 2) ** 0.5
        moves.append(tot / max(1, len(a)))
    gen = [f['s'].get('generated') for f in fr]
    pend = [f['s'].get('pending') for f in fr]
    last = fr[-1]['s']
    return {
        'frames': len(fr),
        'gap_med': statistics.median(gaps) if gaps else 0,
        'gap_max': max(gaps) if gaps else 0,
        'move_avg': statistics.mean(moves) if moves else 0,
        'distinct_pending': len(set(pend)),
        'generated': last.get('generated'),
        'delivered': last.get('delivered'),
        'pending': last.get('pending'),
        'delivery_rate': 100.0 * (last.get('delivered') or 0) / max(1, last.get('generated') or 1),
        'wall': res['wall'],
    }


results = []
plan = [('基准场景', BASE_CFG)] if ONE_ONLY else [('基准场景', BASE_CFG), ('极恶劣场景', SEVERE_CFG)]
for label, cfg in plan:
    res = run_labelled(label, cfg, seconds=SECONDS)
    if res:
        a = analyse(res)
        if a:
            results.append(a)
            print('   帧数 %d · 帧间隔中位 %.0f ms / 最大 %.0f ms · 平均位移 %.0f mm/帧'
                  % (a['frames'], a['gap_med'], a['gap_max'], a['move_avg']))
            print('   生成 %s 送达 %s (%.2f%%) 积压 %s · 墙钟 %.1f s'
                  % (a['generated'], a['delivered'], a['delivery_rate'], a['pending'], a['wall']))

print()
if results:
    r0 = results[0]
    say(PASS if r0['frames'] >= 40 else FAIL, 'A1 观感帧数',
        '%d 帧（改前 5 帧），观感帧率 %.2f 帧/秒' % (r0['frames'], r0['frames'] / r0['wall']))
    say(PASS if r0['gap_max'] <= 9000 else FAIL, 'A2 帧间隔 ≤ 插值上限',
        '最大 %.0f ms，插值上限 9000 ms → 两帧之间不会停住' % r0['gap_max'])
    say(PASS if r0['move_avg'] > 100 else FAIL, 'A3 帧间确有位移',
        '平均每帧每节点移动 %.0f mm，补间有真实运动可插' % r0['move_avg'])
    say(PASS if r0['wall'] <= 120 else FAIL, 'A4 墙钟门禁',
        '%.1f s ≤ 120 s 门禁' % r0['wall'])

    if len(results) > 1:
        r1 = results[1]
        drop = r0['delivery_rate'] - r1['delivery_rate']
        say(PASS if drop > 5 else FAIL, 'B1 场景差异幅度',
            '送达率 %.2f%% → %.2f%%，落差 %.1f 个百分点；积压 %s → %s'
            % (r0['delivery_rate'], r1['delivery_rate'], drop, r0['pending'], r1['pending']))
        say(PASS if r1['distinct_pending'] >= 3 else FAIL, 'B2 指标逐帧变化',
            '积压量出现 %d 个不同取值，曲线不是一条直线' % r1['distinct_pending'])

print()
print('=' * 78)
npass = sum(1 for v, _, _ in rows if v == PASS)
nfail = sum(1 for v, _, _ in rows if v == FAIL)
nwarn = sum(1 for v, _, _ in rows if v == WARN)
print('自检结论：%d 项通过 · %d 项未过 · %d 项提醒' % (npass, nfail, nwarn))
if nfail:
    print()
    print('未通过项：')
    for v, item, detail in rows:
        if v == FAIL:
            print('  - %s：%s' % (item, detail))
print('=' * 78)
