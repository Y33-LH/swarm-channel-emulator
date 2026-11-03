"""Freeze the single-board engineering release only with distinct UI/board evidence."""
from pathlib import Path
import json,hashlib,datetime
ROOT=Path(__file__).resolve().parents[1]
raise SystemExit('Historical finalizer disabled for step20. Use tools/finalize_delivery.py --prepare, freeze the manifest, run final UI acceptance, then --accept.')
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
candidates=[]
for p in (ROOT/'results').glob('product_ui_hardware_*/acceptance.json'):
    d=read(p)
    if d.get('pass'):candidates.append((p,d))
assert candidates,'No passed UI hardware acceptance'
source,ui=max(candidates,key=lambda x:x[0].stat().st_mtime)
assert len(ui['ui_runs'])==3 and len({x['id'] for x in ui['ui_runs']})==3
frozen_input=ROOT/'results/freeze_input_manifest.json'
if not frozen_input.exists():frozen_input.write_bytes((ROOT/'release.json').read_bytes())
tested=read(frozen_input);tested_hash=sha(frozen_input)
for item in tested['artifacts']:
    # Documentation and the resources/evidence summary are updated after testing;
    # executing software, RTL, UI and programmed artifacts must remain identical.
    if Path(item['path']).parts[0] in ('sw','rtl','hw','tools','ui','ready') and Path(item['path']).suffix not in ('.md','.rst'):
        assert sha(ROOT/item['path'])==item['sha256'],f"Untested code change: {item['path']}"
images={k:sha(ROOT/tested[k]) for k in ('bit','elf','init')}
assert images==ui['image_hashes']
runs=[]
for x in ui['ui_runs']:
    p=ROOT/'results'/x['id'];r=read(p/'acceptance.json');meta=read(p/'metadata.json')
    assert meta['release_sha256']==tested_hash, 'Run used a different manifest'
    assert r['image_hashes']==images and r['version']=='000d0003' and r['protocol']==17
    assert r['pass'] and r['all_media_complete'] and all(r['performance_gates'].values())
    assert r['duration_s']==900 and r['telemetry_rounds']==200 and r['final']['slot_misses']==0
    assert r['memory_after']['stack_guard_ok'] and r['memory_after']['heap_failures']==0
    for m in r['media'].values():assert m['complete'] and sha(p/m['file'])==m['sha256']
    runs.append(r)
for path,key in [('results/product_scenarios_acceptance.json','pass'),('results/ui_error_recovery.json','pass'),
                 ('results/assistant_acceptance.json','pass_interface'),('results/concurrent_operation_guard.json','pass')]:
    assert read(ROOT/path)[key],path
now=datetime.datetime.now().isoformat()
resources=read(ROOT/'results/resources.json');res=resources['resources']
res['stack_peak_bound_bytes']=max(res['stack_peak_bound_bytes'],*(r['memory_after']['stack_peak_bound'] for r in runs))
res['heap_peak_bytes']=max(res['heap_peak_bytes'],*(r['memory_after']['heap_committed_peak'] for r in runs))
resources['ui_runtime_source']=str(source.relative_to(ROOT));write(ROOT/'results/resources.json',resources)
ev=read(ROOT/'docs/product_evidence.json');ev.update(updated=now,ui_runs=ui['ui_runs'],ui_acceptance=str(source.relative_to(ROOT)),
    ui_controls='pause, expiry, reissue, success response, stop/reconnect, media identity, exports and read-only replay passed',
    human_usability='Automated UI workflows and visual review completed. Independent five-minute novice trial and judge comprehension remain human acceptance activities.')
write(ROOT/'docs/product_evidence.json',ev)
progress=read(ROOT/'docs/progress.json');progress.update(updated=now,release='SINGLE_BOARD_ENGINEERING_ACCEPTED',
    deferred_by_user=['physical_second_board','formal_report','final_video'],
    human_acceptance_pending=['five_minute_novice_trial','three_minute_project_comprehension'])
statuses=['baseline_and_contract_verified','environment_weather_presets_board_verified','formations_and_geometry_board_verified',
          'metrics_events_replay_comparison_verified','receiver_ranges_and_fair_comparison_published',
          'single_board_gateway_verified_physical_endpoint_deferred','reverse_commands_and_dedup_board_verified',
          'evidence_advice_and_recovery_verified','local_evidence_selection_and_fallback_verified',
          'three_current_core_and_three_distinct_UI_runs_verified','UI_engineering_verified_human_usability_pending']
for item,status in zip(progress['steps'],statuses):item['status']=status
write(ROOT/'docs/progress.json',progress)
gate=dict(schema=1,status='SINGLE_BOARD_ENGINEERING_ACCEPTED',accepted_at=now,version='000d0003',protocol=17,
          images=images,tested_manifest_sha256=tested_hash,ui_acceptance=str(source.relative_to(ROOT)),
          ui_runs=ui['ui_runs'],timely_delivery=[r['final']['timely_delivered']/r['final']['generated'] for r in runs],
          maximum_model_delay_seconds=[r['final']['delay_max_ns']/1e9 for r in runs],
          physical_external_node_verified=False,human_usability_verified=False,formal_submission_completed=False)
write(ROOT/'results/product_acceptance.json',gate)
files=[p for area in ('sw','rtl','hw','tests','tools','docs','ui','reference','media','configs','skill','ready')
       for p in (ROOT/area).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
files.extend(p for p in ROOT.iterdir() if p.is_file() and p.suffix in ('.ps1','.tcl','.cmd','.txt','.md'))
final=dict(tested,development=False,accepted=True,acceptance_scope='single_board_engineering; physical endpoint and human usability not certified',
           accepted_at=now,acceptance_file='results/product_acceptance.json',acceptance_sha256=sha(ROOT/'results/product_acceptance.json'),
           tested_manifest_sha256=tested_hash,artifacts=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in sorted(set(files))])
write(ROOT/'release.json',final)
print('SINGLE_BOARD_ENGINEERING_ACCEPTED',json.dumps(gate,ensure_ascii=False))
