import json,sys,time,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
case=sys.argv[1] if len(sys.argv)>1 else 'all'
out=root/('results/recovery_20261102_'+case);out.mkdir(exist_ok=True)
def api(path,d=None):
 req=urllib.request.Request('http://127.0.0.1:18878'+path,data=json.dumps(d).encode() if d is not None else None,headers={'Content-Type':'application/json'})
 try:return json.load(op.open(req,timeout=15))
 except urllib.error.HTTPError as e:raise RuntimeError(e.read().decode())
def state():return api('/api/state')
def wait(fn,timeout=50):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  s=state()
  if s.get('error'):raise RuntimeError(s['error'])
  if fn(s):return s
  time.sleep(.6)
 raise RuntimeError('condition timed out')
def text_command(text,s):
 p=api('/api/recovery/parse',{'text':text})['plan']
 if p['kind']=='restore':return api('/api/intervene',dict(link=p['link'],enabled=0,gain_permille=1000,sigma=0))
 return api('/api/command',dict(record_id=s['network_record_id'],run_id=s['snapshot']['run_id'],confirm=True,action=p['action']))
try:
 s0=state()
 if not s0['busy']:
  api('/api/connect',{'port':s0['port']});wait(lambda s:not s['busy'])
 s0=state()
 if s0['busy'] and s0['task']!='network':wait(lambda s:not s['busy'],120)
 cfg=json.loads((root/'results/network_20261101_220319_018454/config.json').read_text())['config'];cfg.update(faults=0,environment=1)
 start=time.monotonic()
 if not state()['busy']:api('/api/start',dict(seconds=60,ideal=0,seed=20261009,config=cfg,telemetry_rounds=10))
 s=wait(lambda s:(s.get('snapshot') or {}).get('round',0)>=100)
 results=dict(record_id=s['network_record_id'],baseline=s['snapshot']['recovery'],cases=[])
 assert s['snapshot']['recovery']['healthy'],s['snapshot']['recovery']
 for kind,inject,restore in [('heartbeat','节点 2 心跳间隔 10000 毫秒','节点 2 心跳间隔 1000 毫秒'),('congestion','节点 5 媒体速率 12','节点 5 媒体速率 1'),('link',None,'恢复链路 4')]:
  if case not in ('all',kind):continue
  t=time.monotonic();s=state()
  if inject:text_command(inject,s)
  else:api('/api/watch',{'link':4});api('/api/intervene',dict(link=4,enabled=1,gain_permille=10,sigma=8193))
  fault=wait(lambda s:any(x['kind']==kind for x in s['snapshot']['recovery']['issues']),30)
  print('FAULT',kind,fault['snapshot']['recovery'],flush=True)
  (out/(kind+'_fault.json')).write_text(json.dumps(fault,ensure_ascii=False))
  # Allow a user review interval; recovery is exclusively from a subsequent command.
  time.sleep(3)
  receipt=text_command(restore,fault)
  recovered=wait(lambda s:s['snapshot']['round']>fault['snapshot']['round']+30 and s['snapshot']['recovery']['healthy'],50)
  elapsed=time.monotonic()-t
  results['cases'].append(dict(kind=kind,elapsed=elapsed,receipt=receipt,fault=fault['snapshot']['recovery'],recovered=recovered['snapshot']['recovery']))
  (out/'progress.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
  print('RECOVERED',kind,round(elapsed,2),flush=True)
 end=wait(lambda s:not s['busy'],120);results['wall_total']=time.monotonic()-start;results['report']=end.get('report');results['pass']=all(x['elapsed']<=50 for x in results['cases']) and results['wall_total']<=130
 (out/'acceptance.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('DONE',results['pass'],results['wall_total'],flush=True)
except Exception as e:
 (out/'failure.json').write_text(json.dumps(dict(error=str(e),state=state()),ensure_ascii=False));print('FAILED',str(e),flush=True);raise
