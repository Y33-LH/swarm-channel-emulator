"""Final exact-image gate: interrupted run, recovery, three complete real runs."""
import sys,json,time,hashlib,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps'),str(ROOT/'tests')]
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX
import serial
from serial_json import JsonSerial
from network_acceptance import run as network_run
from product_config import DEFAULT,encode
def run(port='COM4'):
 out=ROOT/'results'/time.strftime('release_stability_%Y%m%d_%H%M%S');out.mkdir()
 manifest=json.loads((ROOT/'release.json').read_text(encoding='utf-8-sig'))
 image_hashes={k:hashlib.sha256((ROOT/manifest[k]).read_bytes()).hexdigest() for k in ('bit','elf','init')}
 def interruption():
  with serial.Serial(port,230400,timeout=.2,write_timeout=5) as s,(out/'recovery.jsonl').open('w') as log:
   s.reset_input_buffer();client=JsonSerial(s)
   def cmd(t):
    r=client.request(t,20);log.write(json.dumps(dict(command=t,response=r))+'\n');log.flush();assert r.get('ok')==1,(t,r);return r
   assert cmd('PING')['version']==VERSION
   cmd('NETSTOP');cmd('SCENECFG '+encode(DEFAULT).hex());cmd('MEDIACLEAR 0 0');cmd('NETFEC 1');cmd('NETLOAD 0');cmd('NETACKDROP 0');cmd('NETSTART 900 20261009 0')
   r=cmd('NETSTEP 100');assert r['running'] and r['round']==100
   cmd('NETSTOP');stopped=cmd('NETSTATUS');assert not stopped['running'] and stopped['round']==100
   assert cmd('STATUS')['status']&1==0
   # Must start a different run from round zero after the abort.
   cmd('NETSTART 2 20261010 1');r=cmd('NETSTEP 20');assert r['round']==20 and r['delivered']==r['generated']==32
   return dict(pass_recovery=True,stopped=stopped,restarted=r,memory=cmd('MEMORY'))
 recovery=interruption();rows=[]
 for i in range(3):
  dest=ROOT/'results'/(time.strftime('network_%Y%m%d_%H%M%S_')+f'{i+1:06x}')
  dest.mkdir();(dest/'metadata.json').write_text(json.dumps(dict(id=dest.name,kind='network',source='hardware_uart',board_version=VERSION_HEX,release_sha256=hashlib.sha256((ROOT/'release.json').read_bytes()).hexdigest())))
  report,path=network_run(port,900,0,20261009,output=dest)
  row=dict(evidence=str(path),wall=report['wall_total_seconds'],delivery=report['final']['delivered']/report['final']['generated'],gates=report['performance_gates'],memory=report['memory_after'])
  rows.append(row);(out/'progress.json').write_text(json.dumps(rows,indent=2))
  assert all(row['gates'].values()),row
  assert report['final']['pending']==0 and report['final']['slot_misses']==0
  assert all(hashlib.sha256((ROOT/manifest[k]).read_bytes()).hexdigest()==v for k,v in image_hashes.items())
 final=dict(**{'pass':True},version=VERSION_HEX,source='three_consecutive_physical_board_runs',images=image_hashes,recovery=recovery,runs=rows)
 (out/'acceptance.json').write_text(json.dumps(final,indent=2));print('RELEASE_STABILITY_PASS '+str(out));return final
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',default='COM4');a=p.parse_args();run(a.port)
