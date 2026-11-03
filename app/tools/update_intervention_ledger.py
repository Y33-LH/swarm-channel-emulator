from pathlib import Path
import json,hashlib,datetime
root=Path(__file__).resolve().parents[1]
load=lambda p:json.loads(p.read_text('utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
qualified=load(root/'results/intervention_qualification_20261021_002643/acceptance.json')
edges=load(root/'results/intervention_edges_20261021_004211/acceptance.json')
assert qualified['passed'] and edges['passed']
for name in ('development_status.json','progress.json','product_evidence.json'):
    source=root/'docs'/name;dest=root/'docs'/('parent_step22_'+name)
    if not dest.exists():dest.write_bytes(source.read_bytes())
remaining=[
    'Apply the experiment/observation identity to remaining network actions and cross-page workflows',
    'Improve action-specific recommendations and distinguish advisory text from executed control',
    'Qualify full final-product stability and performance for the final artifact hash',
    'Complete novice-user review, formal report, video and submission material'
]
status=dict(schema=3,updated=datetime.datetime.now().isoformat(),state='SCOPED_NETWORK_INTERVENTION_QUALIFICATION',
    baseline='../step22_link_experiment',candidate_pl_version='000d0003',arm_build='20261021-edge1',
    firmware_changed=True,fpga_changed=False,
    scope='One real directed edge: user change -> applied readback -> same-frame reception -> received business impact -> restoration -> deterministic recomputation',
    evidence=['results/intervention_qualification_20261021_002643/acceptance.json',
              'results/intervention_edges_20261021_004211/acceptance.json',
              'results/intervention_abort/acceptance.json',
              'results/intervention_ui/acceptance.json'],
    final_acceptance='Use results/intervention_release_acceptance.json with matching release SHA256; no older whole-product acceptance is inherited',
    remaining=remaining,parent='docs/parent_step22_development_status.json')
write(root/'docs/development_status.json',status)
write(root/'docs/progress.json',dict(schema=3,updated=status['updated'],scope=status['scope'],
    state=status['state'],pl_version='000d0003',firmware_protocol=17,intervention_schema=1,
    current_ledger='docs/development_status.json',pending=remaining,
    node_architecture='2 PL hardware endpoints + 14 ARM virtual nodes + ground'))
e=load(root/'docs/parent_step22_product_evidence.json')
e.update(updated=status['updated'],accepted=False,image_hashes=qualified['image_hashes'],current_scope=status['scope'],
         historical_basis='docs/parent_step22_product_evidence.json',ui_runs=[],
         note='Prior whole-product three-run evidence belongs to the older ARM image. Current directed-edge validation is reported separately.')
e['intervention']=dict(evidence=status['evidence'],heartbeat_and_voice_disruption=True,restoration=True,
    exact_recomputed_snapshots=qualified['reproduction']['compared_snapshots'],coverage=['ARM source uplink','air-ground relay','FPGA endpoint uplink','mild interference without fabricated outage'])
for k in ('receiver','capacity','noise_qualification'):
    if k in e:e[k]['evidence_origin']='Historical unchanged-PL baseline; not rerun as part of this new ARM qualification'
write(root/'docs/product_evidence.json',e)
resources=load(root/'results/resources.json')
resources['resources'].update(ARM_ELF_text_bytes=137208,ARM_ELF_data_bytes=2684,ARM_ELF_bss_bytes=941680,
    stack_peak_bound_bytes=max(x['memory']['stack_peak_bound'] for x in edges['runs']),
    heap_peak_bytes=max(x['memory']['heap_committed_peak'] for x in edges['runs']))
resources.update(arm_build=status['arm_build'],image_hashes=qualified['image_hashes'],
    ui_runtime_source=status['evidence'][1],
    qualification_scope='FPGA build resources unchanged (identical bit hash); new ARM static sections and measured stack/heap from directed-edge experiments')
write(root/'results/resources.json',resources)
print('Scoped ledger updated; full-product pending work retained')
