"""驱动一次短实板实验：连接 -> 启动 90 模型秒 -> 轮询 -> 保存记录摘要。不修改工程源码。"""
import json, time, urllib.request, sys
from pathlib import Path

BASE = 'http://127.0.0.1:18878'
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def get(path):
    with OP.open(BASE + path, timeout=20) as r:
        return json.load(r)

def post(path, body):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(),
                                 {'Content-Type': 'application/json'})
    with OP.open(req, timeout=30) as r:
        return json.load(r)

print('connect:', post('/api/connect', {'port': 'COM4'}))
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    st = get('/api/state')
    if st.get('task') is None and st['status'] in ('idle', 'done', 'error'):
        break
    if st.get('error'):
        break
    time.sleep(0.5)
st = get('/api/state')
print('after connect:', json.dumps({k: st.get(k) for k in ('status', 'connected', 'error', 'task')}, ensure_ascii=False))
if st.get('error'):
    print('连接失败，终止'); sys.exit(1)

CONFIG = dict(schema=1, environment=4, weather=0, formation=8, spacing_m=300, altitude_m=400,
              center_x_m=5000, center_y_m=5000, speed_mmps=12000, heading_deg=0,
              reference_snr_cdb=3400, faults=0, jitter_percent=100, carrier_mhz=2400,
              external_node=0, reserved=0)
print('start:', post('/api/start', {'seconds': 90, 'ideal': 0, 'seed': 20261023,
                                    'config': CONFIG, 'telemetry_rounds': 200}))

t0 = time.monotonic()
last = None
while time.monotonic() - t0 < 300:
    st = get('/api/state')
    snap = st.get('snapshot') or {}
    msg = (st['status'], st.get('task'), st.get('record_id'),
           (snap.get('model_ms') or snap.get('round') or 0))
    if msg != last:
        print(' ', msg, flush=True)
        last = msg
    if st['status'] in ('done', 'idle') and st.get('task') is None:
        break
    if st.get('error'):
        print('  ERROR:', st['error'])
        break
    time.sleep(1.0)
print('elapsed wall:', round(time.monotonic() - t0, 1), 's')
st = get('/api/state')
print('final status:', st['status'], 'record:', st.get('record_id'), 'error:', st.get('error'))
if st.get('record_id'):
    rec = get('/api/record?id=' + st['record_id'])
    out = Path(r'D:/Swarm_20261023_step29/_last_run.json')
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding='utf-8')
    print('saved ->', out)
    fin = (rec.get('report') or {}).get('final') or rec.get('final') or {}
    print('final keys:', list(fin)[:30])
