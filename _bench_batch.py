"""对比不同遥测批次(batch)下的回传帧数与墙钟开销，用于确定流畅度与耗时的平衡点。
只读实验，不改工程源码；结果写入 _bench_batch_result.json。
"""
import json, time, urllib.request, sys
from pathlib import Path

BASE = 'http://127.0.0.1:18878'
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def get(p):
    with OP.open(BASE + p, timeout=20) as r:
        return json.load(r)

def post(p, b):
    req = urllib.request.Request(BASE + p, json.dumps(b).encode(), {'Content-Type': 'application/json'})
    with OP.open(req, timeout=30) as r:
        return json.load(r)

CONFIG = dict(schema=1, environment=4, weather=0, formation=8, spacing_m=300, altitude_m=400,
              center_x_m=5000, center_y_m=5000, speed_mmps=12000, heading_deg=0,
              reference_snr_cdb=3400, faults=0, jitter_percent=100, carrier_mhz=2400,
              external_node=0, reserved=0)
SECONDS = 90
SEED = 20261023

print('connect:', post('/api/connect', {'port': 'COM4'}))
for _ in range(120):
    st = get('/api/state')
    if st.get('task') is None and st['status'] in ('idle', 'complete', 'error'):
        break
    time.sleep(0.5)
if get('/api/state').get('error'):
    print('连接失败'); sys.exit(1)

results = []
for batch in (50, 20):
    print('\n=== batch =', batch, '===')
    post('/api/start', {'seconds': SECONDS, 'ideal': 0, 'seed': SEED, 'config': CONFIG,
                        'telemetry_rounds': batch})
    t0 = time.monotonic()
    pc_elapsed = None
    while time.monotonic() - t0 < 400:
        st = get('/api/state')
        if st.get('error'):
            print('  ERROR:', st['error']); break
        if st['status'] in ('complete', 'idle') and st.get('task') is None:
            pc_elapsed = round(time.monotonic() - t0, 2)
            break
        time.sleep(0.4)
    st = get('/api/state')
    snaps = st.get('snapshots') or []
    snap = st.get('snapshot') or {}
    rec = {'batch': batch, 'frames': len(snaps),
           'board_wall_ms': snap.get('wall_ms'),
           'pc_elapsed_s': pc_elapsed,
           'generated': snap.get('generated'), 'delivered': snap.get('delivered'),
           'record_id': st.get('record_id'),
           'rounds': [s.get('round') for s in snaps]}
    results.append(rec)
    print('  帧数:', rec['frames'], '| 板内墙钟:', rec['board_wall_ms'], 'ms | PC 侧耗时:', rec['pc_elapsed_s'], 's')
    print('  生成/送达:', rec['generated'], '/', rec['delivered'])
    print('  rounds:', rec['rounds'][:12], '...' if len(rec['rounds']) > 12 else '')
    time.sleep(1.0)

Path(r'D:/Swarm_20261023_step29/_bench_batch_result.json').write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print('\n=== 汇总 ===')
for r in results:
    fps = (r['frames'] / (r['board_wall_ms'] / 1000)) if r['board_wall_ms'] else 0
    print('batch %3d -> %2d 帧, 板内 %6d ms, PC %5s s, 观感帧率 %.2f 帧/秒'
          % (r['batch'], r['frames'], r['board_wall_ms'] or 0, r['pc_elapsed_s'], fps))
