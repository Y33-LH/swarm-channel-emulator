"""Bind final claims to current source, actual board receipts and three UI runs.

--prepare updates measured summaries before the UI/source freeze.
--accept is fail-closed; it never programs hardware or creates passing test data.
"""
from pathlib import Path
import argparse, datetime, hashlib, json, sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
if __name__=='__main__':
    # The historical implementation below is retained for receipt archaeology.
    # It cannot certify the redesigned protocol-21 system.
    if sys.argv[1:]==['--prepare']:
        from current_evidence import publish
        publish()
        raise SystemExit(0)
    raise SystemExit('Current development acceptance is not yet frozen. Use --prepare for measured current-image evidence; historical --accept is disabled until the current full audit closes.')
from qualify_delivery import PLAN
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def latest(pattern,predicate=lambda x:True):
    found=[(p,read(p)) for p in ROOT.glob(pattern) if predicate(read(p))]
    assert found,'No qualified evidence: '+pattern
    return max(found,key=lambda x:x[0].stat().st_mtime)
def rel(p):return p.relative_to(ROOT).as_posix()
def simulations():
    proofs=[]
    for pattern,marker in [('results/mixed_sim_*/simulation.log','MIXED_NODES_PHY_PASS'),
        ('results/sim_*/simulation.log','PAYLOAD_AXI_PASS'),('results/sim_*/independent_simulation.log','INDEPENDENT_RX_PASS'),
        ('results/phy_vectors/simulation.log','PHY_ALL_PASS')]:
        logs=[p for p in ROOT.glob(pattern) if marker in p.read_text(errors='replace')]
        assert logs,marker
        p=max(logs,key=lambda p:p.stat().st_mtime)
        assert max(f.stat().st_mtime for f in (ROOT/'rtl').iterdir() if f.is_file())<p.stat().st_mtime,'RTL edited after simulation'
        proofs.append(dict(path=rel(p),sha256=sha(p),marker=marker))
    return proofs
def qualify(images):
    checks={}
    for p in sorted(ROOT.glob('results/qualification_*/receipt.json')):
        r=read(p)
        if r['images']!=images:continue
        for c in r['checks']:
            if c['exit_code']==0 and sha(ROOT/'tests'/c['test'])==c['test_sha256']:
                checks[c['test']]=dict(c,receipt=rel(p))
    assert {x[0] for x in PLAN}<=checks.keys(), 'Missing current-image qualifications: '+str({x[0] for x in PLAN}-checks.keys())
    for c in checks.values():
        assert c['evidence'],c['test']
        for e in c['evidence']:assert sha(ROOT/e['path'])==e['sha256'],'Evidence changed: '+e['path']
    return checks
def main():
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--accept',action='store_true');a=ap.parse_args()
    m=read(ROOT/'release.json');assert m['version']=='000d0003' and m['protocol']==17
    images={k:sha(ROOT/m[k]) for k in ('bit','elf','init')};checks=qualify(images)
    build=read(ROOT/'docs/product_build.json');assert build['bit_sha256']==images['bit'] and build['rtl_verified']
    for name,h in build['build_scripts_sha256'].items():assert sha(ROOT/'hw'/name)==h
    clean_path,clean=latest('results/sdk_clean_*/acceptance.json',lambda x:x.get('pass') and x.get('elf_sha256')==images['elf'])
    for name,h in clean['sw_sha256'].items():assert sha(ROOT/'sw'/name)==h
    assert sha(ROOT/'build_sdk.tcl')==clean['build_script_sha256']
    for f in (Path(build['build'])/'core/ip_repo/swarm_minimal/src').iterdir():assert sha(f)==sha(ROOT/'rtl'/f.name)
    rp=ROOT/'results/resources.json';resources=read(rp);res=resources['resources'];assert resources['version']==m['version']
    assert min(res[k] for k in ('WNS_ns','WHS_ns','WPWS_ns'))>=0
    cp,channel=latest('results/channel_reference_*/acceptance.json',lambda x:x.get('pass_channel',False))
    for name,h in channel['rtl_sha256'].items():assert sha(ROOT/'rtl'/name)==h
    rx=read(ROOT/'results/receiver_summary.json');assert any(e['path']==rx['source'] for e in checks['receiver_study.py']['evidence'])
    cap=next(ROOT/e['path'] for e in checks['capacity_acceptance.py']['evidence'] if '/capacity_' in e['path'])
    capacity=read(cap);scenes=read(ROOT/'results/product_scenarios_acceptance.json')
    noise=read(next(ROOT/e['path'] for e in checks['noise_acceptance.py']['evidence'] if '/noise_acceptance_' in e['path']))
    sim=simulations();now=datetime.datetime.now().isoformat()
    ev=dict(updated=now,version=m['version'],protocol=17,accepted=False,image_hashes=images,
        receiver=dict(frames=rx['frames'],configurations=rx['configurations'],source=rx['source'],equal_energy_coding_gain_demonstrated=False),
        noise_qualification={k:noise[k] for k in ('version','trials','delivered','rate','scope','confidence95_wilson')},
        capacity=dict(payload_bps=capacity['measured_sustainable_payload_bps'],scope=capacity['scope'],source=rel(cap)),
        architecture=dict(boards=1,logical_uav=16,hardware_endpoints=[9,13],ARM_virtual_nodes=14,ground_stations=1,physical_cores=1,channel_classes=2,directional_contexts=32),
        channel_reference=rel(cp),clean_sdk=rel(clean_path),simulations=sim,qualification=checks,scenes=scenes['runs'],model_bandwidth=read(ROOT/'results/bandwidth_reference.json'),
        boundaries=['板内硬件端点不代表外接飞机或第二块板。','场景/天气为受控参数组，卫星地图不参与地形传播计算。',
        '最终送达率、及时送达率及实际计算耗时分别报告；不保证任意恶劣参数达到99%。','模型采样率不等于实际射频吞吐。','音视频为实际收发的短校准文件。'],
        deferred=['外部第二板','自由航点与自动选路','真实气象/地形标定','连续摄像头直播','正式报告和视频'])
    if a.prepare:
        write(ROOT/'docs/product_evidence.json',ev);print('CURRENT_MEASUREMENTS_PREPARED');return
    frozen=ROOT/'results/freeze_input_manifest.json';fm=read(frozen)
    for item in fm['artifacts']:
        if Path(item['path']).parts[0] not in ('docs','skill'):
            assert sha(ROOT/item['path'])==item['sha256'],'Untested change: '+item['path']
    assert {k:sha(ROOT/fm[k]) for k in images}==images
    up,ui=latest('results/product_ui_hardware_*/acceptance.json',lambda x:x.get('pass') and x.get('image_hashes')==images)
    assert len(ui['ui_runs'])==3 and len({x['id'] for x in ui['ui_runs']})==3
    assert all(ui[k] for k in ('concurrent_program_rejected','stop_reconnect','exports','history_read_only'))
    runs=[]
    for row in ui['ui_runs']:
        d=ROOT/'results'/row['id'];r=read(d/'acceptance.json');meta=read(d/'metadata.json')
        assert meta['release_sha256']==sha(frozen) and r['image_hashes']==images
        assert r['pass'] and r['duration_s']==900 and r['all_media_complete'] and all(r['performance_gates'].values())
        assert r['wall_total_seconds']<=120 and r['final']['delivered']/r['final']['generated']>.99 and r['final']['slot_misses']==0
        assert r['memory_after']['stack_guard_ok'] and r['memory_after']['heap_failures']==0
        for media in r['media'].values():assert media['complete'] and sha(d/media['file'])==media['sha256']
        runs.append(r)
    ai_path,ai=latest('results/assistant_ui_*/acceptance.json',lambda x:x.get('pass') and x.get('image_hashes')==images)
    assert ai['release_sha256']==sha(frozen),'Assistant UI was tested against different runtime source'
    assert ai['progress_round']>ai['before_round'] and ai['answer_seconds']<30 and ai['received_node9'][6]==450000 and not ai['errors']
    for filename,key in [('ui_error_recovery.json','pass'),('advice_replay_acceptance.json','pass'),('assistant_acceptance.json','pass_interface')]:assert read(ROOT/'results'/filename)[key]
    advice=read(ROOT/'results/advice_replay_acceptance.json');assert read(Path(advice['source']).parent/'acceptance.json')['image_hashes']==images
    res.update(runtime_measurement_pending=False,stack_reserved_bytes=8192,heap_reserved_bytes=8192,
        stack_peak_bound_bytes=max(r['memory_after']['stack_peak_bound'] for r in runs),heap_peak_bytes=max(r['memory_after']['heap_committed_peak'] for r in runs))
    resources.update(hardware_acceptance_pending=False,ui_runtime_source=rel(up));write(rp,resources)
    ev.update(accepted=True,ui_runs=ui['ui_runs'],ui_acceptance=rel(up),assistant_acceptance=rel(ai_path),
        timely_delivery=[r['final']['timely_delivered']/r['final']['generated'] for r in runs],
        maximum_model_delay_seconds=[r['final']['delay_max_ns']/1e9 for r in runs])
    write(ROOT/'docs/product_evidence.json',ev)
    progress=read(ROOT/'docs/progress.json');progress.update(state='SINGLE_BOARD_ENGINEERING_ACCEPTED',pending=[],updated=now,
        human_acceptance_pending=['novice_user_trial','judge_comprehension'],evidence='results/product_acceptance.json');write(ROOT/'docs/progress.json',progress)
    ledger=read(ROOT/'docs/development_status.json');ledger.update(state='single_board_engineering_accepted',updated=now)
    evidence_by_id={'mixed_nodes':checks['mixed_node_acceptance.py']['receipt'],'channel_reference':rel(cp),
        'receiver_extension':checks['modem_extension_acceptance.py']['receipt'],'channel_first_ui':rel(up),
        'runtime_advice_ai':rel(ai_path),'presentation':rel(up),'final_regression':'results/product_acceptance.json'}
    for item in ledger['milestones']:item.update(state='current_image_passed',evidence=evidence_by_id[item['id']])
    ledger['latest_full_run']=dict(version=m['version'],total_seconds=runs[-1]['wall_total_seconds'],delivery=runs[-1]['final']['delivered']/runs[-1]['final']['generated'],accepted=True,reason='Three distinct current-image browser/board runs passed; human usability remains separate.')
    write(ROOT/'docs/development_status.json',ledger)
    gate=dict(status='SINGLE_BOARD_ENGINEERING_ACCEPTED',accepted_at=now,version=m['version'],protocol=17,images=images,
        tested_manifest_sha256=sha(frozen),hardware_endpoints=[9,13],qualification=checks,ui_acceptance=rel(up),assistant_acceptance=rel(ai_path),ui_runs=ui['ui_runs'],
        physical_external_node_verified=False,human_usability_verified=False,formal_submission_completed=False)
    write(ROOT/'results/product_acceptance.json',gate)
    final=dict(m,accepted=True,development=False,accepted_at=now,acceptance_scope='single-board PL/ARM mixed-node engineering; no external aircraft, human usability or formal submission certification',
        acceptance_file='results/product_acceptance.json',acceptance_sha256=sha(ROOT/'results/product_acceptance.json'),tested_manifest_sha256=sha(frozen))
    final['artifacts']=[dict(x,sha256=sha(ROOT/x['path'])) for x in m['artifacts']];write(ROOT/'release.json',final)
    print('SINGLE_BOARD_ENGINEERING_ACCEPTED',json.dumps(gate,ensure_ascii=False))
if __name__=='__main__':main()
