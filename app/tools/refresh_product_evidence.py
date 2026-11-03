"""Summarize measured evidence; never turn a missing test into a completed gate."""
from pathlib import Path
import json,datetime
ROOT=Path(__file__).resolve().parents[1]
def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8-sig'))
def write(path,data):(ROOT/path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
if read('release.json')['version']!='000c0001':
    raise SystemExit('Historical updater disabled. Use finalize_delivery.py --prepare for current measured evidence.')
stability=read('results/release_stability_20261013_030046/acceptance.json')
resources=read('results/resources.json')
size=(ROOT/'sdk_workspace_product/swarm_app/Debug/swarm_app.elf.size').read_text().splitlines()[1].split()
r=resources['resources']
r.update(ARM_ELF_text_bytes=int(size[0]),ARM_ELF_data_bytes=int(size[1]),ARM_ELF_bss_bytes=int(size[2]),
         runtime_measurement_pending=False,stack_reserved_bytes=8192,
         stack_peak_bound_bytes=max(x['memory']['stack_peak_bound'] for x in stability['runs']),
         heap_reserved_bytes=8192,heap_peak_bytes=max(x['memory']['heap_committed_peak'] for x in stability['runs']))
resources.update(hardware_acceptance_pending=False,runtime_source='results/release_stability_20261013_030046/acceptance.json',
                 drc=dict(errors=0,critical=0,warnings=257,qualification='Existing pipeline/reset/inferred-memory warnings retained; see implementation report'),
                 memory_scope='ELF static sections and conservative measured stack bound; not the whole PC or board DDR usage')
write('results/resources.json',resources)
rx=read('results/receiver_summary.json');capacity=read('results/capacity_20261013_025839/acceptance.json')
scenarios=read('results/product_scenarios_acceptance.json')
evidence=dict(updated=datetime.datetime.now().isoformat(),version='000c0001',protocol=16,
    core_runs=[dict(wall_s=x['wall'],delivery=x['delivery']) for x in stability['runs']],
    core_source='results/release_stability_20261013_030046/acceptance.json',image_hashes=stability['images'],
    receiver=dict(frames=rx['frames'],configurations=rx['configurations'],equal_energy_coding_gain_demonstrated=False,
                  source=rx['source'],qualification='独立极限不代表可以同时组合；相同采样SNR下的收益不等于相同帧能量下的编码增益。'),
    capacity=dict(payload_bps=capacity['measured_sustainable_payload_bps'],scope=capacity['scope'],source='results/capacity_20261013_025839/acceptance.json'),
    scenes=scenarios['runs'],model_bandwidth=read('results/bandwidth_reference.json'),
    architecture=dict(boards=1,logical_uav=16,ground_stations=1,physical_cores=1,channel_classes=2,directional_contexts=32),
    deferred=['第二块板实体端点实测','自动发现/动态路由','自由航点编辑','真实气象与地形标定','连续摄像头直播','正式文稿和视频'],
    boundaries=['全部数字基带，无射频和真实飞行。','7种独立环境、8种天气、9种编队为受控参数预设。',
                '外部端点网关仅完成单板协议测试，不能计作实体无人机接入。','音视频为实际收发并校验的短文件。',
                '99%以上最终送达与120秒目标只适用于指定已验收场景，不保证任意恶劣设置。',
                '模型8Msample/s、2Msymbol/s不是实际射频吞吐；容量是固定负载扫描结果。'])
write('docs/product_evidence.json',evidence)
progress=read('docs/progress.json');progress.update(pl_version='000c0001',updated=evidence['updated'])
labels=['baseline_verified','preset_board_tests_pass','geometry_and_formation_board_tests_pass','metrics_and_comparison_pass',
        'receiver_and_build_tests_pass_equal_energy_gain_not_demonstrated','single_board_gateway_pass_physical_endpoint_deferred',
        'reverse_commands_retries_dedup_pass','measured_advice_replay_pass','constrained_local_model_pass',
        'three_consecutive_core_runs_pass_UI_acceptance_pending','in_progress']
for row,label in zip(progress['steps'],labels):row['status']=label
write('docs/progress.json',progress)
print('PRODUCT_EVIDENCE_UPDATED')
