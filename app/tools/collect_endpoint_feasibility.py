"""Archive an implementation outcome; a failed candidate is never a passed build."""
from pathlib import Path
import hashlib,json,re,shutil,sys,datetime
ROOT=Path(__file__).resolve().parents[1]
source=Path(sys.argv[1]).resolve()
planroot=ROOT/'results/endpoint3_feasibility_20261101_064453'
plan=json.loads((planroot/'plan.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert source.is_relative_to(Path('D:/digitalcircuit'))
for name,h in plan['source_sha256'].items():assert sha(source/name)==h,name
assert sha(ROOT/'ready/system_wrapper.bit')==plan['baseline_bit_sha256']
text=(source/'candidate.log').read_text(errors='replace')
match=re.search(r'total of (\d+) slices.*?of which (\d+) slices are available.*?require (\d+) slices',text)
assert 'ERROR: [Place 30-487]' in text and match and 'BUILD_FAILED' in text
total,available,required=map(int,match.groups())
build=source/'results/board_20261101_065246/board'
assert not (build/'board.runs/impl_1/system_wrapper.bit').exists()
out=ROOT/'results/endpoint_count_study_20261101';out.mkdir(exist_ok=True)
files={}
for src,name in [(source/'candidate.log','candidate.log'),(planroot/'plan.json','candidate_plan.json'),
 (build/'board.runs/system_swarm_0_synth_1/system_swarm_0_utilization_synth.rpt','candidate_synthesis.rpt'),
 (ROOT/'results/current_hierarchy_utilization.rpt','baseline_hierarchy.rpt'),
 (ROOT/'results/resources.json','baseline_resources.json')]:
 shutil.copy2(src,out/name);files[name]=sha(out/name)
resources=json.loads((ROOT/'results/resources.json').read_text())['resources']
r=dict(study_complete=True,candidate_implemented=False,candidate_programmed=False,
 date=datetime.datetime.now().isoformat(),baseline_endpoints=[9,13],candidate_endpoints=[9,13,1],
 baseline_bit_sha256=plan['baseline_bit_sha256'],baseline_resources=resources,
 same_core='8 complex taps, full FEC, 62.5 MHz; only endpoint/MMIO/TX mux extension',
 candidate_failure=dict(phase='detail placement',code='Place 30-487',device_slices=total,
   remaining_slices=available,unplaced_required_slices=required,packing_deficit=required-available),
 decision='Retain current 2 hardware endpoints + 14 ARM virtual nodes; all per-hop PHY work still uses FPGA.',
 qualification='This particular three-endpoint implementation does not fit. It does not prove a mathematical maximum; queue/BRAM architecture changes or other implementation strategies may change the result.',
 command='Vivado 2018.3 -mode batch -source hw/build_verified_entry.tcl',source_directory=str(source),
 candidate_source_sha256=plan['source_sha256'],evidence_sha256=files)
(out/'study.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print('ENDPOINT_COUNT_STUDY_COMPLETE',out,'candidate FAILED placement; baseline retained')
