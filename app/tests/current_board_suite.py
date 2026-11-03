"""Serial, fail-fast gates against one explicitly loaded firmware pair.

This suite proves only the gates listed here; it is not the 54-item product audit.
It never substitutes a historical acceptance report for a current board run.
"""
from pathlib import Path
import sys, time, json, subprocess, hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from firmware_contract import VERSION_HEX, PROTOCOL

def run(port):
    out=ROOT/'results'/time.strftime('board_suite_%Y%m%d_%H%M%S')
    out.mkdir()
    gates=[
        ('multitap','multitap_board_acceptance.py',[port]),
        ('geometry','product_scene_acceptance.py',['--board',port]),
        ('full_phy','full_phy_acceptance.py',['--port',port]),
        ('same_frame','coherent_board_acceptance.py',[port]),
        ('mixed_nodes','mixed_node_acceptance.py',[port]),
        ('ack_deadline','ack_deadline_acceptance.py',[port]),
        ('metric_extension','modem_extension_acceptance.py',[port]),
        ('capacity','capacity_acceptance.py',['--port',port]),
    ]
    report=dict(complete=False,version=VERSION_HEX,protocol=PROTOCOL,port=port,gates=[],
        scope='Eight named hardware gates only; complete network repetition, model limits, UI and all audit items require separate evidence.',
        images={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'ready').iterdir() if p.is_file()})
    def save(): (out/'report.json').write_text(json.dumps(report,indent=2))
    save()
    for name,file,args in gates:
        print('GATE_BEGIN',name,flush=True);started=time.monotonic()
        with (out/(name+'.log')).open('w',encoding='utf-8') as log:
            child=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tests'/file),*args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        report['gates'].append(dict(name=name,passed=child.returncode==0,returncode=child.returncode,wall_s=time.monotonic()-started,log=name+'.log'))
        save();print('GATE_END',name,child.returncode,str(out),flush=True)
        if child.returncode:
            print((out/(name+'.log')).read_text(encoding='utf-8')[-4000:],flush=True)
            return 1
    report['complete']=True;save();print('CURRENT_BOARD_SUITE_PASS',out,flush=True);return 0

if __name__=='__main__':sys.exit(run(sys.argv[1]))
