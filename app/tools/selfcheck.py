# -*- coding: utf-8 -*-
"""
selfcheck.py —— 静态自检（供界面上的「系统自检」按钮调用）

只做只读检查，不触碰串口、不启动任务，因此任何时刻都能安全执行：
  1. 发布清单一致性：改了 UI 却忘了重签，这里立刻暴露
  2. 关键改动是否真的落地：补间模块、插值上限、场景预设
  3. 控件审计：有没有点了没反应的空壳按钮

返回结构全部是可直接渲染的判定结果（verdict 取 PASS / FAIL / WARN）。
"""
import hashlib
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
UI = BASE / 'ui'


def _sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _read(p):
    try:
        return p.read_text(encoding='utf-8')
    except Exception:
        return ''


def release_integrity():
    """逐文件比对 release.json 里的 sha256 与磁盘实际内容。"""
    try:
        manifest = __import__('json').loads((BASE / 'release.json').read_text(encoding='utf-8-sig'))
    except Exception as e:
        return dict(verdict='FAIL', total=0, mismatched=[], missing=[], note='清单读取失败：%s' % e)
    items = manifest.get('artifacts') or []
    mismatched, missing = [], []
    for it in items:
        p = BASE / it['path']
        if not p.is_file():
            missing.append(it['path'])
        elif _sha256(p) != it['sha256']:
            mismatched.append(it['path'])
    ok = not mismatched and not missing
    note = ('%d 个文件哈希全部匹配' % len(items)) if ok else \
        ('%d 个文件与清单不符，需重新签名' % (len(mismatched) + len(missing)))
    return dict(verdict='PASS' if ok else 'FAIL', total=len(items),
                mismatched=mismatched[:8], missing=missing[:8], note=note)


def features():
    """确认流畅性相关的改动确实在页面里生效。"""
    html = _read(UI / 'index.html')
    smooth = _read(UI / 'smooth-values.js')
    terrain = _read(UI / 'terrain-view.js')

    loaded = 'smooth-values.js' in html
    m = re.search(r'Math\.min\((\d+),\s*old\?performance\.now\(\)-old\.at', terrain)
    cap = int(m.group(1)) if m else 0
    presets = len(re.findall(r'id="preset[A-Za-z]+"', html))
    closable = 'window.SMOOTH_VALUES !== false' in smooth
    # 插值上限必须大于实际帧间隔，否则动画跑完会停住等下一帧
    verdict = 'PASS' if (loaded and cap >= 5000 and presets >= 3 and closable) else 'FAIL'
    return dict(verdict=verdict, smooth_loaded=loaded, interp_cap_ms=cap,
                presets=presets, animation_closable=closable,
                note='插值上限 %d ms，预设 %d 个' % (cap, presets))


def controls():
    """审计可交互控件，抓出没有任何 JS 引用的空壳。"""
    html = _read(UI / 'index.html')
    js = ''
    for p in sorted(UI.glob('*.js')):
        js += _read(p)

    ids = set()
    for tag in ('button', 'select', 'input', 'textarea'):
        for m in re.finditer(r'<%s\b[^>]*>' % tag, html):
            mid = re.search(r'id="([A-Za-z][A-Za-z0-9_-]*)"', m.group(0))
            if mid:
                ids.add(mid.group(1))

    dead = []
    for cid in ids:
        # id 可能以：字符串字面量 / 对象 key（无引号）/ #id 选择器 出现
        hit = (("'" + cid + "'") in js) or ('"' + cid + '"') in js \
            or re.search(r'\b%s\b' % re.escape(cid), js)
        if not hit:
            dead.append(cid)
    total, wired = len(ids), len(ids) - len(dead)
    return dict(verdict='PASS' if not dead else 'WARN', total=total, wired=wired,
                dead=sorted(dead)[:8],
                note='%d 个控件中 %d 个有 JS 接线' % (total, wired))


def evidence_quality():
    """实质检查：静态检查全部 PASS 也可能一无所获，这一节看的是实验证据本身。

    过去的自检只回答「文件齐不齐、控件接没接线」，从来不敢回答「信道参数
    到底有没有用」。用户调了半天旋钮结果纹丝不动，自检还在旁边报 PASS——
    这比没有自检更危险。这一节补上：

      1. 参数多样性 —— 最近完成的一批实验里，信道相关配置有没有变化过。
         全部一样说明从未做过对照，信道的有效性就没有实验证据。
      2. PHY 证据 —— 最新记录里有没有纠错前/后 BER、σ 回读、EVM 这些读数。
      3. 溢出哨兵 —— 节点遥测里出现 2^31 量级的哨兵值会污染导出数据。
      4. 内存证据区分度 —— 前后完全相同的内存统计等于没测。
    """
    import json
    results = BASE / 'results'
    dims = ('environment', 'weather', 'spacing_m', 'reference_snr_cdb', 'jitter_percent', 'formation')
    seen, latest_fin, latest_dir = {}, None, None
    try:
        rows = sorted([p for p in results.iterdir()
                       if p.is_dir() and p.name.startswith('network_')
                       and (p / 'acceptance.json').exists()],
                      key=lambda p: p.name, reverse=True)[:30]
    except Exception:
        rows = []
    for p in rows:
        try:
            rep = json.loads((p / 'acceptance.json').read_text(encoding='utf-8'))
        except Exception:
            continue
        if not rep.get('pass'):
            continue
        cfg = rep.get('config') or {}
        key = tuple(cfg.get(d) for d in dims)
        seen[key] = seen.get(key, 0) + 1
        if latest_fin is None:
            latest_fin, latest_dir = rep.get('final') or {}, p.name

    problems, warnings = [], []
    # 1. 参数多样性
    if not seen:
        problems.append('results 里找不到任何完整的实板网络实验记录')
    elif len(seen) == 1:
        problems.append('最近 %d 次完成的实验全部是同一套信道配置（环境/天气/间距/SNR/抖动/编队无一变化），'
                        '从未做过参数对照——「信道参数有效」这一结论目前没有任何实验证据。'
                        '请至少用两套不同配置各跑一次再对比。' % sum(seen.values()))
    # 2. PHY 证据
    if latest_fin:
        links = latest_fin.get('links') or []
        applied = latest_fin.get('applied_links') or []
        bits = sum(l[7] for l in links) if links else 0
        pre = sum(l[13] for l in links) if links else 0
        if not links:
            problems.append('最新记录的遥测里没有链路级 PHY 统计（links），纠错前后 BER 无从谈起')
        if not applied:
            warnings.append('最新记录没有 applied_links 回读，σ/增益没有「板卡确认收到」的证据')
        # 3. 溢出哨兵：直接查最后一行 snapshot
        try:
            snaps = (latest_dir and (results / latest_dir / 'snapshots.jsonl').exists()
                     and (results / latest_dir / 'snapshots.jsonl').read_text(encoding='utf-8').strip().splitlines() or [])
            last = json.loads(snaps[-1]) if snaps else {}
            bad_nodes = [n[0] for n in last.get('nodes', []) if any(isinstance(v, int) and v >= 2 ** 31 for v in n)]
            if bad_nodes:
                warnings.append('节点 %s 的遥测里存在 2^31 量级的溢出哨兵值，会原样进入 JSON/CSV 导出，'
                                '请在导出前清洗' % bad_nodes)
        except Exception:
            pass
        # 4. 内存证据
        mb = rep.get('memory_before') or {}
        ma = rep.get('memory_after') or {}
        if mb and ma and mb == ma:
            warnings.append('memory_before 与 memory_after 完全相同，这条「内存证据」没有区分度，'
                            '报告里建议不要当证据使用')
        if links and bits == 0:
            problems.append('最新记录 links 里 bits=0（没有累计任何编码位统计）')
    verdict = 'FAIL' if problems else ('WARN' if warnings else 'PASS')
    notes = problems + warnings
    return dict(verdict=verdict,
                variants=len(seen),
                runs=sum(seen.values()),
                problems=problems[:4], warnings=warnings[:4],
                note='；'.join(notes[:3]) or
                     ('最近 %d 次完成实验覆盖 %d 种信道配置，最新记录含 PHY 与回读证据'
                      % (sum(seen.values()), len(seen))))


def static_report():
    """汇总静态自检，附带一个总判定。"""
    parts = dict(release=release_integrity(), features=features(), controls=controls(),
                 evidence=evidence_quality())
    failed = [k for k, v in parts.items() if v['verdict'] == 'FAIL']
    parts['verdict'] = 'FAIL' if failed else 'PASS'
    parts['failed'] = failed
    return parts
