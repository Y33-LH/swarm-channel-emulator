"""跑一组"极恶劣"对照实验，确认业务指标出现明显可观测退化。
运行期间不要修改工程文件（会触发发布完整性校验）。
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

SEVERE = dict(schema=1, environment=4, weather=7, formation=8, spacing_m=1100, altitude_m=600,
              center_x_m=5000, center_y_m=5000, speed_mmps=16000, heading_deg=0,
              reference_snr_cdb=1800, faults=1, jitter_percent=200, carrier_mhz=2400,
              external_node=0, reserved=0)

print('connect:', post('/api/connect', {'port': 'COM4'}))
for _ in range(120):
    st = get('/api/state')
    if st.get('task') is None and st['status'] in ('idle', 'complete', 'error'):
        break
    time.sleep(0.5)
if get('/api/state').get('error'):
    print('连接失败:', get('/api/state')['error']); sys.exit(1)

print('start:', post('/api/start', {'seconds': 90, 'ideal': 0, 'seed': 20261023,
                                    'config': SEVERE, 'telemetry_rounds': 20}))
# 先等任务真正起来，避免读到上一次的残留状态
t0 = time.monotonic()
while time.monotonic() - t0 < 60:
    st = get('/api/state')
    if st.get('task') == 'network' or st.get('busy'):
        break
    if st.get('error'):
        print('ERROR:', st['error']); sys.exit(1)
    time.sleep(0.3)
print('任务已启动，用时 %.1f s' % (time.monotonic() - t0))

t0 = time.monotonic()
while time.monotonic() - t0 < 500:
    st = get('/api/state')
    if st.get('error'):
        print('ERROR:', st['error']); sys.exit(1)
    if not st.get('busy') and st.get('task') is None and st['status'] in ('complete', 'idle'):
        break
    time.sleep(0.4)

st = get('/api/state')
snaps = st.get('snapshots') or []
s = st.get('snapshot') or {}
m = st.get('metrics') or {}
print('帧数:', len(snaps), '| 墙钟:', s.get('wall_ms'), 'ms')
print('生成/送达:', s.get('generated'), '/', s.get('delivered'))
print('及时率:', m.get('timely_delivery'), '| 积压:', s.get('pending'))
print('队列丢:', s.get('queue_drops'), '| 重传丢:', s.get('retry_drops'))
print('最大时延: %.1f ms' % ((s.get('delay_max_ns') or 0) / 1e6))
print('记录:', st.get('record_id'))
Path(r'D:/Swarm_20261023_step29/_severe_result.json').write_text(json.dumps(
    dict(record_id=st.get('record_id'), frames=len(snaps), wall_ms=s.get('wall_ms'),
         generated=s.get('generated'), delivered=s.get('delivered'),
         timely=m.get('timely_delivery'), pending=s.get('pending'),
         queue_drops=s.get('queue_drops'), retry_drops=s.get('retry_drops')),
    ensure_ascii=False, indent=2), encoding='utf-8')
