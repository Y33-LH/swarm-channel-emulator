"""Current-image technical audit. Historical tests with wrong version are not reused as passes."""
from pathlib import Path
import subprocess,sys,time,json,hashlib
R=Path(__file__).resolve().parents[1]
out=R/'results'/time.strftime('specialty_audit_%Y%m%d_%H%M%S');out.mkdir()
stages=[('combined_channel','full_phy_acceptance.py',[]),('modem_extension','modem_extension_acceptance.py',[]),
 ('mixed_nodes','mixed_node_acceptance.py',[]),('downlink_protocol','product_control_acceptance.py',[]),
 ('scene_consistency','product_scene_acceptance.py',['--board',(sys.argv[1] if len(sys.argv)>1 else 'COM9')]),('controlled_operation','operation_comparison.py',[]),('capacity','capacity_acceptance.py',[]),
 ('receiver_range','receiver_study.py',[])]
rows=[]
for name,script,args in stages:
 print('AUDIT_BEGIN',name,flush=True);start=time.time()
 sys.path[:0]=[str(R/'tools'),str(R/'tools/python_deps')]
 import serial
 from serial_json import JsonSerial
 with serial.Serial((sys.argv[1] if len(sys.argv)>1 else 'COM9'),230400,timeout=.2,write_timeout=5) as uart:
  uart.reset_input_buffer();client=JsonSerial(uart)
  for command in ('NETSTOP','LINKOBS 0'):
   response=client.request(command,20);assert response['ok'],response
 with (out/(name+'.log')).open('w',encoding='utf-8') as f:
  p=subprocess.run([sys.executable,'-B',str(R/'tests'/script),*args],cwd=R,stdout=f,stderr=subprocess.STDOUT)
 rows.append(dict(area=name,script=script,exit_code=p.returncode,seconds=time.time()-start,log=str(out/(name+'.log'))))
 (out/'status.json').write_text(json.dumps(dict(complete=False,rows=rows),indent=2))
 print('AUDIT_END',name,p.returncode,flush=True)
 if p.returncode:break
report=dict(complete=len(rows)==len(stages),all_pass=all(x['exit_code']==0 for x in rows) and len(rows)==len(stages),rows=rows,
 image_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (R/'ready').iterdir() if p.suffix in ('.elf','.bit')},
 note='Passing means declared tests and measured boundaries, not arbitrary reception or universal superiority. Capacity is fixed topology/ideal-channel workload capacity.')
(out/'acceptance.json').write_text(json.dumps(report,indent=2));print('AUDIT_DONE',out,flush=True)
