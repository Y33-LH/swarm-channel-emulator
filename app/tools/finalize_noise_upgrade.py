"""Accept this focused upgrade using current physical and UI evidence, not old runs."""
from pathlib import Path
import argparse, datetime, hashlib, json, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
raise SystemExit('Focused noise-only acceptance cannot certify step20. Use tools/finalize_delivery.py.')
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def latest(pattern):
    paths=list((ROOT/'results').glob(pattern));assert paths,pattern
    return max(paths,key=lambda p:p.stat().st_mtime)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ui-proof',required=True);a=parser.parse_args()
    noise_p=latest('noise_acceptance_*/acceptance.json');noise=read(noise_p)
    stability_p=latest('release_stability_*/acceptance.json');stability=read(stability_p)
    ui_p=Path(a.ui_proof).resolve();assert ui_p.is_relative_to((ROOT/'results').resolve());ui=read(ui_p)
    images={k:sha(ROOT/'ready'/name) for k,name in [('bit','system_wrapper.bit'),('elf','swarm_app.elf'),('init','ps7_init.tcl')]}
    assert noise['pass'] and noise['trials']>=100 and noise['rate']>=.9 and noise['reference_seed_7_pass'] and noise['retries']==0
    assert noise['files']=={n:sha(ROOT/'ready'/n) for n in noise['files']}
    assert stability['pass'] and len(stability['runs'])==3 and stability['images']==images and stability['version']=='000d0003'
    assert all(all(x['gates'].values()) for x in stability['runs'])
    assert ui['pass'] and ui['version']=='000d0003' and ui['images']==images
    for rid in ui['batches']:
        b=read(ROOT/'results'/rid/'acceptance.json')
        assert b['finished'] and b['total']==10 and b['delivered']>=9 and len(set(b['seeds']))==10 and b['retries']==0
        for row in b['rows']:
            frame=read(ROOT/'results'/row['id']/'acceptance.json');assert frame['config']['sigma']==2800 and frame['config']['gain']==.6 and frame['config']['fec']==1
    control_p=latest('controls_*/acceptance.json');assert read(control_p)['pass_controls']
    now=datetime.datetime.now().isoformat()
    resources=read(ROOT/'results/resources.json');r=resources['resources']
    size=(ROOT/'sdk_workspace_product/swarm_app/Debug/swarm_app.elf.size').read_text().splitlines()[1].split()
    r.update(ARM_ELF_text_bytes=int(size[0]),ARM_ELF_data_bytes=int(size[1]),ARM_ELF_bss_bytes=int(size[2]),runtime_measurement_pending=False,
        stack_reserved_bytes=8192,stack_peak_bound_bytes=max(x['memory']['stack_peak_bound'] for x in stability['runs']),
        heap_reserved_bytes=8192,heap_peak_bytes=max(x['memory']['heap_committed_peak'] for x in stability['runs']))
    resources.update(hardware_acceptance_pending=False,runtime_source=str(stability_p.relative_to(ROOT)))
    write(ROOT/'results/resources.json',resources)
    ev=read(ROOT/'docs/product_evidence.json')
    if ev['version']!='000d0003':
        ev['historical_ui_version']=ev['version'];ev['receiver']['version']=ev['version'];ev['capacity']['version']=ev['version']
    ev.update(updated=now,version='000d0003',core_runs=[dict(wall_s=x['wall'],delivery=x['delivery']) for x in stability['runs']],
        core_source=str(stability_p.relative_to(ROOT)),image_hashes=images,
        noise_qualification=dict(version='000d0003',trials=noise['trials'],delivered=noise['delivered'],rate=noise['rate'],source=str(noise_p.relative_to(ROOT)),ui_source=str(ui_p.relative_to(ROOT))),
        noise_revision_scope='New capture matched filter; bounded exact dedup; current three full core runs plus targeted noise UI tests. Earlier full UI and preset range sweeps retain their original evidence versions.')
    write(ROOT/'docs/product_evidence.json',ev)
    progress=read(ROOT/'docs/progress.json');progress.update(pl_version='000d0003',updated=now,release='NOISE_UPGRADE_AND_TARGETED_REGRESSION_ACCEPTED',noise_gate=ev['noise_qualification'])
    progress['steps'][9]['status']='three_current_core_runs_and_noise_UI_acceptance_passed_historical_full_UI_tests_retained'
    write(ROOT/'docs/progress.json',progress)
    gate=dict(status='NOISE_UPGRADE_ACCEPTED',version='000d0003',accepted_at=now,images=images,
        noise=str(noise_p.relative_to(ROOT)),stability=str(stability_p.relative_to(ROOT)),ui=str(ui_p.relative_to(ROOT)),controls=str(control_p.relative_to(ROOT)),
        scope='Original noise-challenge conditions, full FEC, independent seeds, no retry; targeted regressions and 3 current network runs. Not a new certification of every channel setting.')
    gate_p=ROOT/'results/noise_upgrade_acceptance.json';write(gate_p,gate)
    subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'tools/development_manifest.py')],check=True)
    manifest=read(ROOT/'release.json');manifest.update(accepted=True,development=False,acceptance_scope=gate['scope'],
        accepted_at=now,acceptance_file=str(gate_p.relative_to(ROOT)),acceptance_sha256=sha(gate_p))
    write(ROOT/'release.json',manifest)
    print('NOISE_UPGRADE_ACCEPTED '+json.dumps(gate,ensure_ascii=False))
if __name__=='__main__':main()
