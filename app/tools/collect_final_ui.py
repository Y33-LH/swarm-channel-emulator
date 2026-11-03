"""Collect measured run evidence and separately identified browser observations.

Screenshots are manual browser QA, not an automatic pass of every control.
The run checks below consume saved UART/snapshot records from the real board.
"""
from pathlib import Path
import datetime, hashlib, json, math, shutil, subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/final_ui_20261101'
SCREEN = Path('D:/digitalcircuit/audit_20261101/ui')
RECORDS = ['network_20261101_071859_3c2904',
           'network_20261101_072516_72225b',
           'network_20261101_072550_b3e70f']
NODE = Path('C:/Users/yirui/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def collect():
    OUT.mkdir(parents=True, exist_ok=True)
    images = {k: sha(ROOT/'ready'/n) for k,n in
              [('bit','system_wrapper.bit'),('elf','swarm_app.elf'),('init','ps7_init.tcl')]}
    rows=[]
    for rid in RECORDS:
        folder=ROOT/'results'/rid
        a=read(folder/'acceptance.json')
        s=[json.loads(x) for x in (folder/'snapshots.jsonl').read_text().splitlines()]
        assert a['pass'] and a['image_hashes']==images
        assert a['continuous'] and a['requested_duration_s']==0
        assert not s[-1]['running'] and a['duration_s']>20
        assert all(x['watch_link']==4 for x in s)
        obs=[x['observation'] for x in s if x.get('observation')]
        assert obs and all(o['link']==4 for o in obs)
        assert all(o['phy'][3]==o['meta'][15] for o in obs)
        assert len({o['phy'][3] for o in obs})>10
        assert a['memory_after']['stack_guard_ok'] and not a['memory_after']['heap_failures']
        nodes={n[0]:n for n in s[0]['nodes']}
        movements=[math.dist(n[4:7],nodes[n[0]][4:7])/1000
                   for n in s[-1]['nodes'] if n[9] and nodes[n[0]][9]]
        assert len(movements)==16 and min(movements)>100
        final=s[-1]
        rows.append(dict(record=rid,acceptance_sha256=sha(folder/'acceptance.json'),
                         snapshot_sha256=sha(folder/'snapshots.jsonl'),
                         uart_sha256=sha(folder/'uart.jsonl'),
                         duration_model_s=a['duration_s'],wall_run_s=a['wall_run_seconds'],
                         generated=final['generated'],delivered=final['delivered'],
                         timely=final['timely_delivered'],
                         actual_carrier_mhz=a['config']['carrier_mhz'],
                         actual_speed_mmps=a['config']['speed_mmps'],
                         watch_link=4,unique_data_frames=len({o['phy'][3] for o in obs}),
                         minimum_received_net_displacement_m=min(movements),
                         complete_media=sum(x['complete'] for x in a['media_objects']),
                         incomplete_media=sum(not x['complete'] for x in a['media_objects'])))
    assert [(r['actual_carrier_mhz'],r['actual_speed_mmps']) for r in rows]==[(2400,12000),(2400,12000),(2500,14000)]
    logs=[]
    for name in ['ui_launch_context.cjs','received_tracks.cjs','ui_history_animation.cjs']:
        p=ROOT/'tests'/name
        r=subprocess.run([str(NODE),str(p)],capture_output=True,text=True,check=True)
        (OUT/(name+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
        logs.append(dict(test='tests/'+name,sha256=sha(p),returncode=r.returncode,output=r.stdout.strip()))
    shots=[]
    for name in ['instrument_live_final_1920x1080.png','instrument_live_final_1280x720.png',
                 'mission_live_final_1920x1080.png','mission_live_final_1280x720.png',
                 'history_final_1920x1080.png','history_final_1280x720.png',
                 'history_compare_final_1920x1080.png','history_rewind_final_1920x1080.png',
                 'invalid_parameter_final.png','draft_parameter_final.png','applied_parameter_final.png']:
        src=SCREEN/name; assert src.is_file(),name
        shutil.copy2(src,OUT/name)
        shots.append(dict(path=name,sha256=sha(OUT/name)))
    receipt=dict(pass_scoped=True,accepted=False,date=datetime.datetime.now().isoformat(),
        scope='Current firmware continuous runs, selected-link launch, restart, draft/apply separation, received movement; browser review of primary workflows at two viewport sizes. Not exhaustive verification of every user input.',
        image_hashes=images,records=rows,automated_regressions=logs,screenshots=shots,
        browser_observations=[
            'Reload during record 071859 restored link 4, wild/clear/grid configuration and same-frame real samples.',
            'Both 1920x1080 and 1280x720: document dimensions equal viewport, all eight chart canvases visible; secondary details use explicit dialogs.',
            'Map uses received-heartbeat trails and 3D net displacement from first received position; model trajectory remains separately labelled.',
            'SNR 1000 rejected before launch with visible 0–45 dB explanation; restoring 34 enabled launch.',
            'Draft fc=2500 and v=14 during 072516 visibly retained actual fc=2400 until explicit end-and-apply created 072550.',
            'History rewind hides future media and ground command receipts; replay shows source record, not the live workspace.',
            'Primary start/stop/restart, history view/compare/export/recompute, parameter dialogs and same-frame views inspected; screenshots are manual observations, not fabricated automatic assertions.'],
        ui_source_sha256={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in (ROOT/'ui').iterdir() if p.is_file()},
        remaining=['No physical USB cable removal was performed; session-interruption test covers host UART close/reopen.',
                   'No universal all-environment success or strict wall-clock real-time claim.',
                   '1280px charts are compact; magnification opens detailed charts.'])
    (OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print('FINAL_UI_SCOPED_PASS',[(r['record'],r['duration_model_s']) for r in rows])

if __name__=='__main__':collect()
