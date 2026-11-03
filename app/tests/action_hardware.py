"""Exercise user actions, returned acknowledgements, workload effects and replay on board."""
from pathlib import Path
import sys,time,json
R=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(R/'tools'),str(R/'reference'),str(R/'tests')]
from network_acceptance import run
from intervention_session import Session,record,save
import network_intervention as ni
import action_observation as ao

def main():
 parent=R/'results'/time.strftime('action_qualification_%Y%m%d_%H%M%S');parent.mkdir()
 p=ni.plan(dict(link=4,seconds=120,seed=20261021,config={'environment':1,'faults':0}))
 def progress(s,session):
  if session.phase!='waiting':return
  t=s['round'];print('WINDOW',t/10,[(x['id'],x['status'],x['verdict']) for x in ao.commands(session.snapshots,session.events)],flush=True)
  a={100:dict(kind='command',command=dict(target=5,opcode=4,value=1,ttl_ms=10000),window_s=10),
     200:dict(kind='command',command=dict(target=5,opcode=4,value=5,ttl_ms=10000),window_s=10),
     300:dict(kind='command',command=dict(target=9,opcode=2,value=2000,ttl_ms=10000),window_s=10),
     400:dict(kind='change',gain_permille=50,sigma=8192,window_s=10),
     500:dict(kind='command',command=dict(target=5,opcode=3,value=1,ttl_ms=10000),window_s=15),
     650:dict(kind='restore',window_s=10),
     750:dict(kind='command',command=dict(target=5,opcode=3,value=0,ttl_ms=10000),window_s=10)}.get(t,dict(kind='finish'))
  a['observed_round']=t;session.submit(a,session.id)
 out=parent/'original';out.mkdir();session=Session('original',out,p,progress,lambda:False)
 report=session.run(run,(sys.argv[1] if len(sys.argv)>1 else 'COM9'));actions=report['actions']
 assert actions[0]['status']=='confirmed' and actions[0]['readback']['media_rate']==1
 s20=[s for s in session.snapshots if s['round']<=200]
 limit=ao.commands(s20,session.events)[0]
 assert limit['after']['generated_fragments_per_s']==1,limit
 s30=[s for s in session.snapshots if s['round']<=300]
 restored=ao.commands(s30,session.events)[1]
 assert restored['after']['generated_fragments_per_s']==5,restored
 assert actions[2]['status']=='confirmed' and actions[2]['readback']['heartbeat_ms']==2000
 blocked=ao.commands([s for s in session.snapshots if s['round']<=650],session.events)[3]
 assert blocked['status']=='unconfirmed' and blocked['confirmed_ms'] is None,blocked
 assert all(x['executions']==1 for x in actions),actions
 assert report['all_media_complete']
 out2=parent/'recomputed';out2.mkdir();replay=Session('recomputed',out2,p,lambda s,x:None,lambda:False,record(out))
 repeated=replay.run(run,(sys.argv[1] if len(sys.argv)>1 else 'COM9'));assert repeated['reproduction']['exact_match'],repeated['reproduction']
 save(parent/'acceptance.json',dict(pass_actions=True,limited_window=limit,restored_window=restored,
   blocked_receipt=blocked,actions=actions,reproduction=repeated['reproduction'],image_hashes=report['image_hashes'],
   scope='UART commands traverse actual FPGA multi-hop downlink, execution receipt returns uplink; both source rate and received byte rate observed; no claim of improvement when not congested'))
 print('ACTION_HARDWARE_PASS',parent,flush=True)
if __name__=='__main__':main()
