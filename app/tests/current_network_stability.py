"""Three current-image complete runs, with the NEW scene-derived Rician taps.

Wall-time target is explicitly deferred by the user, never silently declared met.
All 9000 communication rounds still execute on the board.
"""
import sys,json,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
from network_acceptance import run
from firmware_contract import VERSION_HEX,PROTOCOL
from product_config import validate
import channel_config

def main(port):
 out=ROOT/'results'/time.strftime('current_network_stability_%Y%m%d_%H%M%S');out.mkdir();rows=[]
 images={k:hashlib.sha256((ROOT/'ready'/k).read_bytes()).hexdigest() for k in ('system_wrapper.bit','swarm_app.elf','ps7_init.tcl')}
 cfg=validate({'channel':channel_config.validate({'mode':1,'fading':2,'tap_count':0})})
 for i in range(3):
  dest=out/f'run_{i+1}';report,_=run(port,900,0,20261009,output=dest,config=cfg,batch=100,strict=True)
  final=report['final'];ratio=final['delivered']/final['generated']
  assert ratio>=.99 and final['pending']==0 and final['slot_misses']==0
  limited=[s['round'] for s in map(json.loads,(dest/'snapshots.jsonl').read_text().splitlines())
           if s.get('observation') and s['observation'].get('coefficient_limited',0)]
  assert not limited,('Observed coefficient limitation',limited)
  assert images=={k:hashlib.sha256((ROOT/'ready'/k).read_bytes()).hexdigest() for k in images}
  rows.append(dict(evidence=str(dest),delivery=ratio,media=report['media'],memory=report['memory_after'],
   wall_s=report['wall_total_seconds'],timely=final['timely_delivered']/final['generated'],max_delay_ms=final['delay_max_ns']/1e6))
  (out/'progress.json').write_text(json.dumps(rows,indent=2));print('CURRENT_NETWORK_REPEAT',i+1,ratio,flush=True)
 (out/'acceptance.json').write_text(json.dumps(dict(passed=True,version=VERSION_HEX,protocol=PROTOCOL,images=images,config=cfg,
  runs=rows,performance_gate_deferred_by_user=True,
  scope='Three complete 900-second new scene/Rician 16-node experiments, same seed and images; media byte integrity, fault recovery, memory, >=99% final delivery and no slot misses. Timely delivery separately reported; not all user configurations.'),indent=2))
 print('CURRENT_NETWORK_STABILITY_PASS',out,flush=True)
if __name__=='__main__':main(sys.argv[1])
