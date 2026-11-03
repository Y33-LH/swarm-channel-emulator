"""Executed altitude commands must change ARM geometry and replay, including PL nodes."""
import sys,json,time,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps'),str(ROOT/'reference')]
import serial
from serial_json import JsonSerial
from product_config import validate,encode
from product_scene import position
from truth_track import track
from firmware_contract import VERSION,PROTOCOL

def run(port):
 out=ROOT/'results'/time.strftime('runtime_scene_%Y%m%d_%H%M%S');out.mkdir();snaps=[]
 config=validate({'environment':1,'formation':1,'faults':0,'jitter_percent':0});seed=20261101
 with serial.Serial(port,230400,timeout=.2,write_timeout=5) as uart,(out/'uart.jsonl').open('w') as log:
  uart.reset_input_buffer();client=JsonSerial(uart,max_line=32768)
  def cmd(s):
   r=client.request(s,60);log.write(json.dumps(dict(command=s,response=r))+'\n');log.flush();assert r.get('ok')==1,(s,r);return r
  ping=cmd('PING');assert ping['protocol']==PROTOCOL and ping['version']==VERSION
  cmd('NETSTOP');cmd('SCENECFG '+encode(config).hex());cmd('MEDIACLEAR 0 0');cmd('NETLOAD 0');cmd('NETFEC 1');cmd('LINKOBS 1');cmd('NETSTART 20 '+str(seed)+' 1')
  assert cmd('SCENERUNTIME')['runtime']['altitude']==[]
  for cid,node,height in ((501,16,450),(502,9,480)):
   cmd('GCOMMAND '+struct.pack('<5I',cid,node,5,height,10000).hex())
  for _ in range(40):
   s=cmd('NETSTEP 5');r=cmd('SCENERUNTIME');assert r['run_id']==s['run_id'] and r['model_ms']==s['round']*100
   s['scene_runtime']=r['runtime'];snaps.append(s)
   for row in s['nodes']:
    expected=position(row[0],s['round']/10,seed,config,PROTOCOL,r['runtime'])
    assert max(abs(x-round(y*1000)) for x,y in zip(row[1:4],expected))<=1,(row,expected)
  final=cmd('CMDSTATUS');assert all(row[4]==2 for row in final['commands']),final
  assert snaps[-1]['nodes'][8][3]==480000 and snaps[-1]['nodes'][15][3]==450000
  states=snaps[-1]['scene_runtime'];assert len(states['altitude'])==2
  for node,target in ((9,480000),(16,450000)):
   values={s['nodes'][node-1][3] for s in snaps};assert len(values)>10 and max(values)==target
  # Dense replay and all recorded ARM source positions agree, including mid-ramp.
  for s in snaps:
   dense=track(snaps,config,seed,20,PROTOCOL,s['round']/10,2)
   for node in (9,16):assert max(abs(x*1000-y) for x,y in zip(dense['samples'][0][node-1],s['nodes'][node-1][1:4]))<=1
  for node,old,new,at in states['altitude']:
   before=position(node,max(0,at-1e-6),seed,config,PROTOCOL,states)
   assert abs(before[2]-400)<1e-6
  trace=cmd('CMDTRACE');assert all(n==1 for _,n in trace['executions'])
  cmd('NETSTART 1 7 1');assert cmd('SCENERUNTIME')['runtime']['altitude']==[];cmd('NETSTOP')
  memory=cmd('MEMORY');assert memory['stack_guard_ok'] and not memory['heap_failures']
 (out/'acceptance.json').write_text(json.dumps(dict(passed=True,ping=ping,commands=final,trace=trace,snapshots=snaps,memory=memory,
  scope='Actual reverse-link PL command execution, virtual and hardware-node height ramps; ARM telemetry and dense historical map coordinates agree within 1 mm. Model geometry, not real aircraft movement.'),indent=2))
 print('RUNTIME_SCENE_PASS',out,flush=True)
if __name__=='__main__':run(sys.argv[1])
