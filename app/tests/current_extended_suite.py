"""Current-image endurance and boundary studies, sequential serial ownership.

Every child has its own stated scope; success is not universal receiver success.
"""
from pathlib import Path
import sys,json,time,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from firmware_contract import BUILD,VERSION_HEX,PROTOCOL
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(port):
 out=ROOT/'results'/time.strftime('extended_suite_%Y%m%d_%H%M%S');out.mkdir()
 images={n:sha(ROOT/'ready'/n) for n in ('system_wrapper.bit','swarm_app.elf','ps7_init.tcl')}
 report=dict(complete=False,arm_build=BUILD,version=VERSION_HEX,protocol=PROTOCOL,images=images,checks=[])
 for name,args in [('current_network_stability.py',[port]),('terrain_headroom_acceptance.py',['--board',port]),('noise_acceptance.py',['--port',port]),('receiver_study.py',['--port',port])]:
  print('EXTENDED_BEGIN',name,str(out),flush=True);start=time.time();script=ROOT/'tests'/name;digest=sha(script)
  with (out/(name+'.log')).open('w',encoding='utf-8') as log:
   p=subprocess.run([sys.executable,'-X','utf8',str(script),*args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
  assert images=={n:sha(ROOT/'ready'/n) for n in images}
  assert digest==sha(script)
  evidence=[dict(path=f.relative_to(ROOT).as_posix(),sha256=sha(f)) for f in (ROOT/'results').rglob('acceptance.json') if f.stat().st_mtime>=start]
  report['checks'].append(dict(test=name,test_sha256=digest,returncode=p.returncode,wall_s=time.time()-start,evidence=evidence))
  (out/'receipt.json').write_text(json.dumps(report,indent=2))
  print('EXTENDED_END',name,p.returncode,flush=True)
  if p.returncode:
   print((out/(name+'.log')).read_text('utf-8')[-3000:],flush=True);return p.returncode
 report['complete']=True;(out/'receipt.json').write_text(json.dumps(report,indent=2));print('CURRENT_EXTENDED_SUITE_PASS',out,flush=True);return 0
if __name__=='__main__':sys.exit(main(sys.argv[1]))
