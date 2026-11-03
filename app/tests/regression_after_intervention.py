from pathlib import Path
import sys,time,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from network_acceptance import run
out=ROOT/'results'/time.strftime('network_regression_%Y%m%d_%H%M%S')
r,_=run(output=out,strict=True)
assert r['final']['delivered']/r['final']['generated']>.99
assert r['all_media_complete'] and r['final']['slot_misses']==0
print('CURRENT_ARM_FULL_NETWORK_REGRESSION_PASS',str(out),json.dumps(r['performance_gates']),flush=True)
