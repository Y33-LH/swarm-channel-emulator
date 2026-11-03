"""Real-board session beyond the old 900 s limit, repeated media, >64 commands.

Uses actual protocol acknowledgements and archived receiver bytes. Continuous
mode is stopped explicitly; the unfinished tail clip stays incomplete.
"""
import sys,time,json,struct,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'reference'),str(ROOT/'tests')]
from network_acceptance import run
from firmware_contract import BUILD

def main(port):
 out=ROOT/'results'/time.strftime('continuous_board_%Y%m%d_%H%M%S');out.mkdir();issued=[]
 def control(cmd,s):
  if not s:return
  t=s['round']//10
  # One command every ten model seconds. The buffer must retire old entries,
  # never lose an unexpired operation or execute a repeated command twice.
  if t<=800 and t%10==0:
   cid=t//10;node=5;op=1;value=0
   if t in (60,90):op=3;value=int(t==60)
   if t in (120,180):op=4;value=1 if t==120 else 5
   if t in (240,250,260,270):node=9 if t<260 else 13;op=2;value=2000 if t%20==0 else 1000
   r=cmd('GCOMMAND '+struct.pack('<5I',cid,node,op,value,10000).hex())
   issued.append(dict(id=cid,model_s=t,node=node,opcode=op,value=value,receipt=r))
   if t in (650,800):
    rejected=cmd('GCOMMAND '+struct.pack('<5I',1,5,1,0,10000).hex(),allow_reject=True)
    assert rejected['ok']==0 and rejected['error'] in ('COMMAND_ID_REUSED','COMMAND_ID_NOT_INCREASING')
 def progress(s):
  if s['round']%1000==0:print('CONTINUOUS',s['round']/10,s['media_archive_count'],s['running'],flush=True)
 report,_=run(port,0,1,20261101,output=out,config={'environment':1,'formation':7,'faults':0},control=control,
  progress=progress,batch=100,strict=False,continuous=True,repeat_media=True,stop_round=9100)
 snapshots=[json.loads(x) for x in (out/'snapshots.jsonl').read_text().splitlines()]
 by={x['round']//10:x for x in snapshots}
 assert by[900]['running']==1 and report['stop_round']==9100 and not report['final']['running']
 assert report['arm_build']==BUILD
 results={c[0]:c for s in snapshots for c in s['command_results']}
 assert len(issued)==80 and set(results)==set(range(1,81))
 assert all(c[4]==2 for c in results.values()),results
 def generated(t,kind):return next(x[1] for x in by[t]['business_counts'] if x[0]==kind)
 assert generated(90,4)==generated(70,4),'Paused video kept generating'
 assert generated(120,4)>generated(100,4),'Video did not resume'
 low=(generated(170,4)-generated(130,4))/40
 high=(generated(230,4)-generated(190,4))/40
 assert .7<=low<=1.1 and high>low*2,(low,high)
 objects=report['media_objects'];assert len(objects)>10 and all(x['complete'] for x in objects)
 assert len({(x['kind'],x['object_id']) for x in objects})==len(objects)
 assert all(by[b]['media_totals'][k]>=by[a]['media_totals'][k] for a,b in zip(sorted(by),sorted(by)[1:]) for k in range(4))
 assert report['memory_after']['stack_guard_ok'] and not report['memory_after']['heap_failures']
 result=dict(passed=True,arm_build=BUILD,evidence=str(out),commands_confirmed=len(results),objects=len(objects),
  rate_before_restore=low,rate_after_restore=high,stop_round=report['stop_round'],tdma=report['final']['tdma'],
  memory=report['memory_after'],images=report['image_hashes'],
  scope='910 model seconds, explicit stop, 80 actual returned command confirmations, media pause/rate/resume and independent repeated RX objects; no RF/live camera claim')
 (out/'qualification.json').write_text(json.dumps(result,indent=2));print('CONTINUOUS_BOARD_PASS',out,flush=True)
if __name__=='__main__':main(sys.argv[1])
