"""Prepare honest pending metadata before the source manifest is sealed."""
from pathlib import Path
import json, shutil, datetime,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from current_evidence import publish
if __name__=='__main__':
    publish()
    raise SystemExit(0)
R=Path(__file__).resolve().parents[1]
p=R/'docs/product_evidence.json'
prior=R/'docs/parent_step26_product_evidence.json'
if not prior.exists(): shutil.copy2(p,prior)
old=json.loads(prior.read_text('utf-8'))
pending=dict(version='000d0003',protocol=17,accepted=False,ui_runs=[],
    current_scope='Fresh-source single-board build; current measurements and three full UI runs pending.',
    historical_basis=prior.relative_to(R).as_posix(),
    boundaries=old['boundaries'],deferred=old['deferred'],model_bandwidth=old.get('model_bandwidth'),
    note='Historical measurements are archived separately and do not confer acceptance on this rebuilt candidate.')
p.write_text(json.dumps(pending,ensure_ascii=False,indent=2),encoding='utf-8')
(R/'docs/progress.json').write_text(json.dumps(dict(schema=6,updated=datetime.datetime.now().isoformat(),
    state='FROZEN_SOURCE_CANDIDATE_PENDING_ACCEPTANCE',baseline='../step26_usability',http_port=8886,
    pl_version='000d0003',arm_build='20261021-edge1',fpga_rebuilt_from_source=True,arm_rebuilt_from_source=True,
    acceptance='results/freeze_acceptance.json',current_entry='D:/digitalcircuit/启动当前验收版.cmd',
    remaining=['Fresh-image physical/UI acceptance and three consecutive 900-second runs',
               'Independent ABC novice walkthrough and mentor comprehension check',
               'Official report, video, AI records and submission package']),ensure_ascii=False,indent=2),encoding='utf-8')
print('PENDING_FREEZE_METADATA_READY')
