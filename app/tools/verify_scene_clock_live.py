import sys,time,json,math,urllib.request
from pathlib import Path
sys.path[:0]=['tools','reference']
from product_scene import position
root=Path.cwd();out=root/'results/scene_clock_live';out.mkdir(exist_ok=True)
op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def req(path,data=None):
 r=urllib.request.Request('http://127.0.0.1:18878'+path,None if data is None else json.dumps(data).encode(),{'Content-Type':'application/json'})
 with op.open(r,timeout=15) as f:return json.load(f)
old=json.loads((root/'results/network_20261101_154002_9df8e8/config.json').read_text()) if (root/'results/network_20261101_154002_9df8e8/config.json').exists() else None
if old and 'config' in old:old=old['config']
if not old:
 from product_config import validate
 from channel_config import validate as cv
 old=validate(dict(environment=6,formation=7,spacing_m=450,altitude_m=400,speed_mmps=20000,carrier_mhz=2500,faults=0,channel=cv(dict(mode=1,tap_count=7,fading=2,rician_k_cdb=1500,reserved0=1))))
c={**old,'spacing_m':900,'speed_mmps':20000,'reserved':16,'faults':0,'center_x_m':5000,'center_y_m':5000}
(out/'request.json').write_text(json.dumps(c,indent=2))
print(req('/api/start',dict(seconds=0,seed=20261009,ideal=0,config=c,telemetry_rounds=10)),flush=True)
t0=time.monotonic();first=None;last=-1;prev=None;turn=0;rows=[];maxerr=0;cross=None
with (out/'snapshots.jsonl').open('w') as f:
 while time.monotonic()-t0<185:
  s=req('/api/state');a=s.get('snapshot');wall=time.monotonic()-t0
  if s.get('error'):raise RuntimeError(s['error'])
  if a and a.get('protocol')==22 and a.get('round')!=last:
   last=a['round'];ct=last/10;assert a['scene_ms']==a['communication_ms']*16
   if first is None:first=wall
   for n in a['nodes']:
    truth=position(n[0],ct,a['seed'],c,22,a.get('scene_runtime'))
    maxerr=max(maxerr,math.dist(truth,[v/1000 for v in n[1:4]]))
   x=sum(n[1]/1000 for n in a['nodes'])/16-5000;y=sum(n[2]/1000 for n in a['nodes'])/16-5000
   angle=math.atan2(y,x)
   if prev is not None:turn+=math.atan2(math.sin(angle-prev),math.cos(angle-prev))
   prev=angle;laps=abs(turn)/math.tau
   row=dict(wall_s=wall,live_s=wall-first,laps=laps,snapshot=a);rows.append(row);f.write(json.dumps(row)+'\n');f.flush()
   if cross is None and laps>=2:cross=wall-first;print('TWO_ORBITS',cross,flush=True)
   if last%100==0:print(json.dumps(dict(wall_s=round(wall,2),communication_s=ct,scene_s=a['scene_ms']/1000,laps=round(laps,3),max_error_m=maxerr,delivered=a.get('delivered'))),flush=True)
  if cross is not None and wall-first>=max(140,cross+3):break
  time.sleep(.5)
summary=dict(record_id=s.get('network_record_id'),two_orbits_wall_s=cross,final_laps=rows[-1]['laps'],max_position_reference_error_m=maxerr,snapshot_count=len(rows),scene_scale=16,config=c,pass_geometry=maxerr<.002,pass_time=cross is not None and 120<=cross<=150)
(out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)

