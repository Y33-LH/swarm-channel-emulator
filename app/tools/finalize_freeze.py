"""Verify exact frozen artifacts and fresh receipts. Does not modify the manifest."""
from pathlib import Path
import json, hashlib, datetime
raise SystemExit('Historical freeze checker is disabled for protocol 21. Use tools/current_evidence.py for current measured results; complete the current audit before final acceptance.')
R=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text('utf-8'))
write=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
manifest=read(R/'release.json');mh=sha(R/'release.json')
for x in manifest['artifacts']:assert sha(R/x['path'])==x['sha256'],x['path']
images={k:sha(R/manifest[k]) for k in ('bit','elf','init')}
def latest(pattern):
    p=max(R.glob(pattern),key=lambda p:p.stat().st_mtime);return p,read(p)
proof=[]
def track(p):
    proof.append(dict(path=p.relative_to(R).as_posix(),sha256=sha(p)))
build=read(R/'docs/product_build.json');b=Path(build['build']);assert b.resolve().is_relative_to((R/'results').resolve())
assert build['bit_sha256']==images['bit'] and build['rtl_verified'] and build['ps_init_identical']
assert build['wns_ns']>=0 and build['whs_ns']>=0
for name,h in build['build_scripts_sha256'].items():assert sha(R/'hw'/name)==h
for p in (b/'core/ip_repo/swarm_minimal/src').iterdir():assert sha(p)==sha(R/'rtl'/p.name)
for p in (R/'sw').iterdir():
    if p.is_file():assert sha(p)==sha(R/'sdk_workspace_product/swarm_app/src'/p.name)
assert sha(R/'sdk_workspace_product/swarm_app/Debug/swarm_app.elf')==images['elf']
track(R/'docs/product_build.json');track(R/'results/clean_build_console.log')
sdklog=max((R/'results').glob('sdk_rebuild_*.log'),key=lambda p:p.stat().st_mtime)
assert 'SDK_BUILD_FINISHED' in sdklog.read_text(errors='replace');track(sdklog)
pp,program=latest('results/firmware_*/acceptance.json');assert program['pass_load']
assert read(pp.parent/'metadata.json')['release_sha256']==mh
assert 'PROGRAM_RUN_FINISHED' in (pp.parent/'program.log').read_text(errors='replace');track(pp);track(pp.parent/'program.log')
qp,q=latest('results/freeze_qualification_*/receipt.json')
assert q['completed'] and q['images']==images and len(q['checks'])==14
if q['release_sha256']!=mh:
    # A final visual review corrected PDP labels after the board suite. Keep
    # that suite's original identity; only reuse it if ALL hardware, protocol,
    # build inputs, measurements and test sources are byte-for-byte unchanged.
    prior=R/'results/frozen_manifests'/(q['release_sha256']+'.json')
    assert sha(prior)==q['release_sha256']
    before={x['path']:x['sha256'] for x in read(prior)['artifacts']}
    after={x['path']:x['sha256'] for x in manifest['artifacts']}
    assert before.keys()==after.keys()
    changes={p for p in before if before[p]!=after[p]}
    assert changes=={'ui/instrument.js','tools/finalize_freeze.py'},changes
    track(prior)
for item in q['checks']:
    assert item['exit_code']==0 and sha(R/'tests'/item['test'])==item['test_sha256']
    assert item['evidence'],item['test']
    for e in item['evidence']:assert sha(R/e['path'])==e['sha256'],e['path']
track(qp)
cp,c=latest('results/channel_reference_*/acceptance.json');assert c['pass_channel'] and c['max_error_lsb']==0
for name,h in c['rtl_sha256'].items():assert sha(R/'rtl'/name)==h
track(cp)
units=read(R/'results/freeze_unit_receipt.json');assert units['pass'] and units['release_sha256']==mh;track(R/'results/freeze_unit_receipt.json')
for name in ('causal','comparison','height'):
    p=R/'results/workflow_ui'/f'{name}.json';v=read(p);assert v['pass'] and v['release_sha256']==mh;track(p)
for name in ('layout','hardware'):
    p=R/'results/usability_ui'/f'{name}.json';v=read(p);assert v['pass'] and v['manifest_sha256']==mh;track(p)
p=R/'results/workflow_context_ui.json';v=read(p);assert v['pass'] and v['release_sha256']==mh;track(p)
tp,t=latest('results/freeze_stability_ui_*/acceptance.json');assert t['pass'] and len(t['runs'])==3 and t['images']==images and t['release_sha256']==mh
assert len({x['id'] for x in t['runs']})==3;track(tp)
runs=[]
for row in t['runs']:
    p=R/'results'/row['id'];r=read(p/'acceptance.json');assert r['pass'] and r['duration_s']==900 and r['ideal']==0
    assert r['config']['faults']==1 and r['config']['environment']==0
    assert r['image_hashes']==images and read(p/'metadata.json')['release_sha256']==mh
    assert all(r['performance_gates'].values()) and r['wall_total_seconds']<=120
    f=r['final'];assert f['delivered']/f['generated']>.99 and f['pending']==0 and f['slot_misses']==0
    assert r['all_media_complete'] and r['memory_after']['stack_guard_ok'] and r['memory_after']['heap_failures']==0
    assert [a[0] for a in f['alarm_events']]==[1,2,3,4]
    src=read(R/'media/source_manifest.json')
    for kind,received in (('audio','received_audio.wav'),('video','received_video.webm')):
        assert (p/received).read_bytes()==(R/'media'/src[kind]['file']).read_bytes()
    assert sha(p/'acceptance.json')==row['acceptance_sha256'] and sha(p/'snapshots.jsonl')==row['snapshots_sha256'] and sha(p/'uart.jsonl')==row['uart_sha256']
    track(p/'acceptance.json');runs.append(r)
p=R/'results/freeze_export.json';x=read(p);assert x['pass_export'] and x['release_sha256']==mh;track(p)
np,n=latest('results/noise_acceptance_*/acceptance.json');assert n['pass'] and n['rate']>=.9;track(np)
rp,receiver=latest('results/receiver_study_*/acceptance.json');assert receiver['completed'];track(rp)
capfile,capacity=latest('results/capacity_*/acceptance.json');assert capacity['pass'];track(capfile)
resources=read(R/'results/resources.json');res=resources['resources']
res.update(runtime_measurement_pending=False,stack_reserved_bytes=8192,heap_reserved_bytes=8192,
           stack_peak_bound_bytes=max(r['memory_after']['stack_peak_bound'] for r in runs),
           heap_peak_bytes=max(r['memory_after']['heap_committed_peak'] for r in runs))
resources.update(hardware_acceptance_pending=False,runtime_source=tp.relative_to(R).as_posix())
write(R/'results/resources.json',resources);track(R/'results/resources.json')
gate=dict(pass_freeze=True,engineering_accepted=True,full_submission_complete=False,created=datetime.datetime.now().isoformat(),
          tested_manifest_sha256=mh,images=images,build=build['build'],runs=t['runs'],evidence=proof,
          remaining_human_and_submission=['ABC novice walkthrough and mentor comprehension','Official project report, video, AI records and submission review'],
          limits=read(R/'docs/product_evidence.json')['boundaries'])
write(R/'results/freeze_acceptance.json',gate)
ev=read(R/'docs/product_evidence.json')
ev.update(accepted=True,tested_manifest_sha256=mh,image_hashes=images,current_scope='Fresh-source single-board engineering acceptance',
    ui_runs=[dict(id=x['id'],wall_s=x['wall_seconds'],delivery=x['delivered']/x['generated']) for x in t['runs']],
    noise_qualification={k:n[k] for k in ('version','delivered','trials','rate')},
    capacity=dict(payload_bps=capacity['measured_sustainable_payload_bps'],scope=capacity['scope']),
    receiver=dict(frames=sum(x['measured']['attempts'] for x in receiver['rows']),configurations=len(receiver['rows'])),
    acceptance='results/freeze_acceptance.json',acceptance_sha256=sha(R/'results/freeze_acceptance.json'),
    timely_delivery=[r['final']['timely_delivered']/r['final']['generated'] for r in runs],
    maximum_model_delay_seconds=[r['final']['delay_max_ns']/1e9 for r in runs],
    note='Three fresh 900-model-second UI runs use this exact rebuild. Human usability and formal submission remain separate.')
write(R/'results/product_evidence.json',ev)
print('CURRENT_SOURCE_FREEZE_ACCEPTED',mh,[(x['wall_seconds'],x['delivered'],x['generated']) for x in t['runs']])
