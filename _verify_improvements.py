"""验证两组改进：(1) 细粒度回传的帧数与墙钟；(2) 恶劣场景是否产生可观测的业务变化。
只调用既有 API 跑实板实验，不改任何工程源码。运行期间请勿修改工程文件（会触发发布校验）。
"""
import json, time, urllib.request, sys
from pathlib import Path

BASE = 'http://127.0.0.1:18878'
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def get(p):
    with OP.open(BASE + p, timeout=25) as r:
        return json.load(r)

def post(p, b):
    req = urllib.request.Request(BASE + p, json.dumps(b).encode(), {'Content-Type': 'application/json'})
    with OP.open(req, timeout=40) as r:
        return json.load(r)

BASE_CFG = dict(schema=1, environment=1, weather=0, formation=0, spacing_m=300, altitude_m=400,
                center_x_m=5000, center_y_m=5000, speed_mmps=12000, heading_deg=0,
                reference_snr_cdb=3400, faults=1, jitter_percent=100, carrier_mhz=2400,
                external_node=0, reserved=0)
HARSH_CFG = dict(schema=1, environment=4, weather=4, formation=8, spacing_m=800, altitude_m=400,
                 center_x_m=5000, center_y_m=5000, speed_mmps=12000, heading_deg=0,
                 reference_snr_cdb=2200, faults=1, jitter_percent=150, carrier_mhz=2400,
                 external_node=0, reserved=0)

print('connect:', post('/api/connect', {'port': 'COM4'}))
for _ in range(120):
    st = get('/api/state')
    if st.get('task') is None and st['status'] in ('idle', 'complete', 'error'):
        break
    time.sleep(0.5)
if get('/api/state').get('error'):
    print('连接失败:', get('/api/state')['error']); sys.exit(1)

def run(tag, cfg, batch, seconds=90, seed=20261023):
    print('\n=== %s (batch=%d) ===' % (tag, batch))
    post('/api/start', {'seconds': seconds, 'ideal': 0, 'seed': seed, 'config': cfg,
                        'telemetry_rounds': batch})
    t0 = time.monotonic()
    while time.monotonic() - t0 < 500:
        st = get('/api/state')
        if st.get('error'):
            print('  ERROR:', st['error']); return None
        if st['status'] in ('complete', 'idle') and st.get('task') is None:
            break
        time.sleep(0.4)
    st = get('/api/state')
    snaps = st.get('snapshots') or []
    s = st.get('snapshot') or {}
    m = st.get('metrics') or {}
    rec = dict(tag=tag, batch=batch, frames=len(snaps),
               board_wall_ms=s.get('wall_ms'), pc_s=round(time.monotonic() - t0, 2),
               generated=s.get('generated'), delivered=s.get('delivered'),
               timely=m.get('timely_delivery'), pending=s.get('pending'),
               queue_drops=s.get('queue_drops'), retry_drops=s.get('retry_drops'),
               delay_max_ms=(s.get('delay_max_ns') or 0) / 1e6,
               record_id=st.get('record_id'))
    print('  帧数 %d | 墙钟 %s ms | PC %s s' % (rec['frames'], rec['board_wall_ms'], rec['pc_s']))
    print('  生成 %s / 送达 %s / 及时率 %s' % (rec['generated'], rec['delivered'], rec['timely']))
    print('  积压 %s | 队列丢 %s | 重传丢 %s | 最大时延 %.1f ms'
          % (rec['pending'], rec['queue_drops'], rec['retry_drops'], rec['delay_max_ms']))
    print('  记录:', rec['record_id'])
    time.sleep(1.0)
    return rec

out = []
out.append(run('基准 · 细粒度', BASE_CFG, 20))
out.append(run('城市大雨 · 细粒度', HARSH_CFG, 20))
Path(r'D:/Swarm_20261023_step29/_verify_improvements.json').write_text(
    json.dumps([r for r in out if r], ensure_ascii=False, indent=2), encoding='utf-8')
print('\n=== 对比 ===')
for r in out:
    if not r:
        continue
    fps = r['frames'] / (r['board_wall_ms'] / 1000) if r['board_wall_ms'] else 0
    loss = (r['generated'] - r['delivered']) if r['generated'] else 0
    print('%s: %d 帧 (%.2f 帧/秒), 未送达 %d, 积压 %s' % (r['tag'], r['frames'], fps, loss, r['pending']))
