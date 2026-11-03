"""Current-image serial regression; failures and every child transcript are retained."""
from pathlib import Path
import sys, subprocess, json, hashlib, time, datetime, traceback
R = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(R/'tools'), str(R/'tools/python_deps')]
import serial
from serial_json import JsonSerial
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
PLAN = [('acceptance.py', []), ('mixed_node_acceptance.py', []), ('ack_deadline_acceptance.py', []),
        ('modem_extension_acceptance.py', []), ('full_phy_acceptance.py', []), ('noise_acceptance.py', []),
        ('product_scene_acceptance.py', ['--board', 'COM4']), ('product_preset_acceptance.py', []),
        ('product_control_acceptance.py', []), ('product_serial_interrupt.py', []),
        ('receiver_study.py', []), ('capacity_acceptance.py', []), ('operation_comparison.py', []),
        ('product_scenarios.py', [])]
out = R/'results'/time.strftime('freeze_qualification_%Y%m%d_%H%M%S')
out.mkdir()
m = json.loads((R/'release.json').read_text('utf-8'))
receipt = dict(started=datetime.datetime.now().isoformat(), release_sha256=sha(R/'release.json'),
               images={k:sha(R/m[k]) for k in ('bit','elf','init')}, completed=False, checks=[])
def save(): (out/'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
def intact():
    assert sha(R/'release.json') == receipt['release_sha256']
    for item in m['artifacts']: assert sha(R/item['path']) == item['sha256'], item['path']
save()
try:
    for name, args in PLAN:
        intact()
        with serial.Serial('COM4',230400,timeout=.2,write_timeout=5) as uart:
            uart.reset_input_buffer(); c=JsonSerial(uart)
            for text in ('NETSTOP','LINKOBS 0'):
                reply=c.request(text,20); assert reply['ok'], reply
        start=time.time(); print('FREEZE_CHECK_START', name, flush=True)
        with (out/(name+'.log')).open('w',encoding='utf-8') as log:
            p=subprocess.run([sys.executable,'-X','utf8','-B',str(R/'tests'/name),*args],cwd=R,stdout=log,stderr=subprocess.STDOUT)
        evidence=[dict(path=p.relative_to(R).as_posix(),sha256=sha(p)) for p in (R/'results').rglob('*.json')
                  if p.stat().st_mtime>=start and p.parent!=out and ('acceptance' in p.name)]
        receipt['checks'].append(dict(test=name,test_sha256=sha(R/'tests'/name),exit_code=p.returncode,
                                     wall_seconds=time.time()-start,evidence=evidence))
        save(); intact(); print('FREEZE_CHECK_END',name,p.returncode,round(time.time()-start,2),flush=True)
        if p.returncode: raise RuntimeError(f'{name} failed: inspect {out/(name+".log")}')
    receipt.update(completed=True, finished=datetime.datetime.now().isoformat()); save()
    print('FREEZE_BOARD_SUITE_PASS',out,flush=True)
except BaseException:
    receipt['failure']=traceback.format_exc();save();raise
