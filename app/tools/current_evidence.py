"""Publish measured, current-image evidence without declaring product acceptance.

This replaces summaries containing hard-coded historical versions. Each source
remains linked with a digest; absent evidence remains pending, never a pass.
"""
from pathlib import Path
import datetime,hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from firmware_contract import VERSION_HEX,PROTOCOL,BUILD
ROOT=Path(__file__).resolve().parents[1]
NAMES={'bit':'system_wrapper.bit','elf':'swarm_app.elf','init':'ps7_init.tcl'}
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def current_images():return {k:sha(ROOT/'ready'/v) for k,v in NAMES.items()}
def matches(d,images):
    other=d.get('image_hashes') or d.get('images') or {}
    return all(other.get(k,other.get(NAMES[k]))==v for k,v in images.items())
def find(pattern,predicate):
    candidates=[]
    for p in ROOT.glob(pattern):
        try:
            d=read(p)
            if isinstance(d,dict) and predicate(d):candidates.append((p,d))
        except (ValueError,OSError):continue
    return max(candidates,key=lambda x:x[0].stat().st_mtime) if candidates else (None,None)
def source(p):return dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p))
def publish():
    images=current_images();proof={};pending=[]
    def take(key,pattern,predicate):
        p,d=find(pattern,predicate)
        if p:proof[key]=source(p)
        else:pending.append(key)
        return p,d
    boardp,board=take('eight_board_gates','results/board_suite_*/report.json',lambda d:d.get('complete') and matches(d,images))
    jp,joint=take('joint_receiver','results/joint_receiver_*/study.json',lambda d:d.get('complete') and matches(d,images))
    sp,stability=take('three_complete_runs','results/current_network_stability_*/acceptance.json',lambda d:d.get('passed') and len(d.get('runs',[]))==3 and matches(d,images))
    ep,extended=take('extended_suite','results/extended_suite_*/receipt.json',lambda d:d.get('complete') and matches(d,images))
    cp,clean=take('clean_sdk','results/sdk_clean_*/acceptance.json',lambda d:d.get('pass') and d.get('elf_sha256')==images['elf'])
    fp,fair=take('paired_payload_energy','results/fair_payload_energy_*/acceptance.json',lambda d:d.get('complete') and d.get('no_clipping') and matches(d,images))
    up,story=take('browser_driven_story','results/current_story_*/acceptance.json',lambda d:d.get('passed') and matches(d,images))
    rp,recomputed=take('physical_recomputation','results/network_*/acceptance.json',lambda d:d.get('pass') and d.get('reproduction',{}).get('exact_match') and matches(d,images))
    ip,interrupted=take('serial_session_recovery','results/serial_interrupt_*/acceptance.json',lambda d:d.get('pass') and matches(d,images))
    qp,ui=take('final_ui_workflow','results/final_ui_*/receipt.json',lambda d:d.get('pass_scoped') and matches(d,images))
    np,endpoints=take('endpoint_count_feasibility','results/endpoint_count_study_*/study.json',lambda d:d.get('study_complete') and d.get('baseline_bit_sha256')==images['bit'])
    if ui:
        if any(sha(ROOT/n)!=h for n,h in ui['ui_source_sha256'].items()):
            proof['historical_ui_workflow']=proof.pop('final_ui_workflow')
            pending.append('final_ui_workflow_after_layout_revision')
            ui=None
    if clean:
        for n,h in clean['sw_sha256'].items():assert sha(ROOT/'sw'/n)==h,'Clean rebuild source changed: '+n
        assert sha(ROOT/'build_sdk.tcl')==clean['build_script_sha256']
    bp=ROOT/'docs/product_build.json';build=read(bp)
    assert build['bit_sha256']==images['bit'] and build['rtl_verified']
    for n,h in build['build_scripts_sha256'].items():assert sha(ROOT/'hw'/n)==h,'Build script changed: '+n
    for p in (Path(build['build'])/'core/ip_repo/swarm_minimal/src').iterdir():
        if p.is_file():assert sha(ROOT/'rtl'/p.name)==sha(p),'RTL no longer matches bitstream: '+p.name
    proof['fpga_build']=source(bp)
    if extended:
        for row in extended['checks']:
            assert row['returncode']==0 and sha(ROOT/'tests'/row['test'])==row['test_sha256']
            for e in row['evidence']:assert sha(ROOT/e['path'])==e['sha256']
    ev=dict(updated=datetime.datetime.now().isoformat(),version=VERSION_HEX,protocol=PROTOCOL,arm_build=BUILD,
        accepted=False,image_hashes=images,ui_runs=[],evidence=proof,pending=pending,
        performance_gate_deferred_by_user=True,
        architecture=dict(boards=1,logical_uav=16,hardware_endpoints=[9,13],ARM_virtual_nodes=14,ground_stations=1,
                          physical_cores=1,channel_classes=2,directional_contexts=32),
        boundaries=['单板数字基带实验；无真实无人机、GPS或RF。2个PL端点+14个ARM虚拟节点，非32路并行硬件。',
                    '场景含程序DEM单障碍近似、P.838雨衰及公开经验参数，非真实地形/气象标定。',
                    '8/16 MSa/s是模型采样率；不等于实际处理吞吐或射频采样设备。',
                    '参考采样SNR由用户设置；深衰落及强长多径可以导致接收失败。',
                    '送达率、按时率、逐跳ACK率及接收BER采用不同分母，不能混用。',
                    '连续音视频为真实多跳传送的重复校准素材，不是现场摄像头直播。',
                    '无MIMO/独立相位噪声谱/IQ失衡模型；不能把未实现项目标作已实现。'],
        deferred=['外部多板/无人机','真实气象地形标定','自由航点/自动选路','正式文稿与视频'],
        note='当前镜像的专项与UI主流程测量汇总；accepted=false，不等于竞赛最终提交验收或任意参数组合保证。')
    if ui:ev['ui_workflow']=dict(scope=ui['scope'],records=ui['records'],remaining=ui['remaining'])
    if endpoints:ev['endpoint_count_feasibility']={k:endpoints[k] for k in ('study_complete','candidate_implemented','candidate_programmed','baseline_endpoints','candidate_endpoints','candidate_failure','decision','qualification')}
    if story:
        for rid,h in story['inputs'].items():assert sha(ROOT/'results'/rid/'acceptance.json')==h
        ev['ui_runs']=story['records']
        ev['interactive_story']={k:story[k] for k in ('effect','intervention_model_seconds','last_recovery_window','distinct_frame_observations','complete_media_objects','incomplete_retained','scope')}
    if recomputed:ev['physical_recomputation']=recomputed['reproduction']
    if interrupted:ev['serial_session_recovery']={k:interrupted[k] for k in ('scope','partial_bytes','no_retry_on_poisoned_session','reopened_and_received_32_real_packets')}
    if fair:
        assert len(fair['rows'])==200 and fair['plan']['retries']==0
        ev['paired_energy_comparison']=dict(summary=fair['summary'],paired_wins=fair['paired_wins'],paired_losses=fair['paired_losses'],
            payload_ebn0_db=fair['plan']['payload_ebn0_db'],payload_bits=fair['plan']['payload_bits'],
            no_clipping=fair['no_clipping'],exact_paired_two_sided_p=fair['exact_paired_two_sided_p'],
            coding_benefit_at_tested_point=fair['coding_benefit_at_tested_point'],scope=fair['plan']['scope'],
            note='Equal total frame energy per payload bit, including synchronization overhead. Benefit at this one measured operating point; not a coding-gain curve or arbitrary-channel guarantee.')
    if stability:ev['core_runs']=[dict(wall_s=r['wall_s'],delivery=r['delivery'],timely=r['timely'],max_delay_ms=r['max_delay_ms']) for r in stability['runs']]
    if joint:
        cases=joint['cases'];ev['joint_receiver']=dict(configurations=len(cases),data_attempts=sum(r['data_attempts'] for r in cases),source=proof['joint_receiver']['path'],
           lowest_hop_success=min(r['hop_success'] for r in cases),scope='36 finite same-seed joint configurations; retain failures. Not a universal 99% guarantee.',
           rows=[dict(profile=r['profile'],fading=r['config']['channel']['fading'],sample_rate_hz=r['config']['channel']['sample_rate_khz']*1000,snr_db=r['config']['reference_snr_cdb']/100,
                      attempts=r['data_attempts'],acked=r['acked'],hop_success=r['hop_success']) for r in cases])
    # Capacity belongs to the successful board suite, not an arbitrary older file.
    if board:
        # Use the suite's recorded capacity log, not filesystem modification order.
        text=(boardp.parent/'capacity.log').read_text(encoding='utf-8',errors='replace')
        candidates=[p for p in (ROOT/'results').glob('capacity_*/acceptance.json') if str(p.parent) in text or p.parent.name in text]
        if candidates:
            p=max(candidates,key=lambda p:p.stat().st_mtime);d=read(p)
            assert d['pass'] and str(d['version']).lower().replace('0x','').zfill(8)==VERSION_HEX
            ev['capacity']=dict(payload_bps=d['measured_sustainable_payload_bps'],scope=d['scope'],source=p.relative_to(ROOT).as_posix());proof['capacity']=source(p)
    if extended:
        for row in extended['checks']:
            for e in row['evidence']:
                p=ROOT/e['path'];d=read(p)
                if row['test']=='noise_acceptance.py' and 'trials' in d:
                    ev['noise_qualification']={k:d[k] for k in ('version','trials','delivered','rate','scope','confidence95_wilson')}
                    proof['noise']=source(p)
                if row['test']=='receiver_study.py' and d.get('completed') and d.get('rows'):
                    rows=d['rows']
                    ev['receiver']=dict(frames=sum(r['measured']['attempts'] for r in rows),configurations=len(rows),source=e['path'],
                        qualification=d['qualification'],energy_definition=d['energy_definition'],
                        equal_energy_coding_gain_demonstrated=False,
                        rows=[dict(config=r['config'],measured=r['measured']) for r in rows],
                        note='Finite paired measurements; an observed advantage at selected points is not a general coding-gain claim.')
                    proof['receiver']=source(p)
    memories=[]
    if stability:memories=[r['memory'] for r in stability['runs']]
    if not memories:
        mp,md=find('results/current_network_stability_*/run_*/acceptance.json',lambda d:d.get('pass') and matches(d,images))
        if md:memories=[md['memory_after']];proof['runtime_memory']=source(mp)
    if memories:
        assert all(m['stack_guard_ok'] and not m['heap_failures'] for m in memories)
        rp=ROOT/'results/resources.json';resources=read(rp);assert resources['version']==VERSION_HEX
        resources['resources'].update(runtime_measurement_pending=False,stack_reserved_bytes=memories[0]['stack_reserved'],
            stack_peak_bound_bytes=max(m['stack_peak_bound'] for m in memories),heap_reserved_bytes=memories[0]['heap_reserved'],
            heap_peak_bytes=max(m['heap_committed_peak'] for m in memories))
        resources['runtime_scope']='Current-image finite board tests; conservative stack paint bound and sbrk high-water mark, not whole DDR usage.'
        resources['runtime_source']=proof.get('three_complete_runs',proof.get('runtime_memory'))
        rp.write_text(json.dumps(resources,ensure_ascii=False,indent=2),encoding='utf-8');ev['resources']=resources
    (ROOT/'docs/product_evidence.json').write_text(json.dumps(ev,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CURRENT_EVIDENCE_PREPARED',VERSION_HEX,BUILD,'pending='+','.join(pending))
    return ev
if __name__=='__main__':publish()
