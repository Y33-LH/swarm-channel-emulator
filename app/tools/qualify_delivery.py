"""Sequential physical-board suite with immutable image/test receipts.

Do not run concurrently with the UI serial worker. Every child failure stops
the suite; a receipt records completed checks without claiming release success.
"""
import argparse,datetime,hashlib,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SHA=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
PLAN=[('acceptance.py',[]),('mixed_node_acceptance.py',[]),('ack_deadline_acceptance.py',[]),('modem_extension_acceptance.py',[]),('full_phy_acceptance.py',[]),
      ('noise_acceptance.py',[]),('product_scene_acceptance.py',['--board','COM4']),
      ('product_preset_acceptance.py',[]),('product_control_acceptance.py',[]),
      ('product_serial_interrupt.py',[]),('receiver_study.py',[]),
      ('capacity_acceptance.py',[]),('operation_comparison.py',[]),('product_scenarios.py',['--resume'])]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--from-test');args=parser.parse_args()
    plan=PLAN
    if args.from_test:plan=PLAN[next(i for i,x in enumerate(PLAN) if x[0]==args.from_test):]
    out=ROOT/'results'/time.strftime('qualification_%Y%m%d_%H%M%S');out.mkdir()
    release=json.loads((ROOT/'release.json').read_text())
    images={k:SHA(ROOT/release[k]) for k in ('bit','elf','init')}
    report=dict(started=datetime.datetime.now().isoformat(),images=images,completed=False,checks=[])
    for name,argv in plan:
        script=ROOT/'tests'/name;test_hash=SHA(script);start=time.time()
        print('QUALIFY_START',name,flush=True)
        with (out/(name+'.log')).open('w',encoding='utf-8') as log:
            proc=subprocess.Popen([sys.executable,'-X','utf8','-B',str(script),*argv],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            code=proc.wait()
        evidence=[dict(path=p.relative_to(ROOT).as_posix(),sha256=SHA(p)) for p in (ROOT/'results').rglob('*.json')
                  if p.stat().st_mtime>=start and p.parent!=out and (p.name=='acceptance.json' or 'acceptance' in p.name)]
        assert SHA(script)==test_hash,'Test was edited while it was running'
        report['checks'].append(dict(test=name,test_sha256=test_hash,exit_code=code,wall_seconds=time.time()-start,evidence=evidence))
        assert images=={k:SHA(ROOT/release[k]) for k in images},'Programmed artifact changed during qualification'
        (out/'receipt.json').write_text(json.dumps(report,indent=2))
        print('QUALIFY_RESULT',name,code,round(time.time()-start,2),str(out),flush=True)
        if code:raise SystemExit(code)
    report.update(completed=True,finished=datetime.datetime.now().isoformat())
    (out/'receipt.json').write_text(json.dumps(report,indent=2));print('QUALIFICATION_SUITE_PASS',out,flush=True)
if __name__=='__main__':main()
