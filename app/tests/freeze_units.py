"""Run existing interface, framing and observation regressions on the frozen source."""
from pathlib import Path
import sys, hashlib, json, unittest
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'tests'))
names=['test_workflow','test_assistant_live_context','test_product_assistant_fallback','test_action_context',
       'test_product_metrics','test_network_wire','test_serial_json','test_link_experiment']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
mh=sha(R/'release.json')
suite=unittest.defaultTestLoader.loadTestsFromNames(names)
with (R/'results/freeze_units.log').open('w',encoding='utf-8') as log:
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
assert sha(R/'release.json')==mh
report={'pass':result.wasSuccessful(),'tests':result.testsRun,'release_sha256':mh,
        'test_sha256':{n:sha(R/'tests'/(n+'.py')) for n in names},
        'failures':[(str(t),detail) for t,detail in result.failures+result.errors]}
(R/'results/freeze_unit_receipt.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('FROZEN_UNIT_TESTS',result.testsRun,report['pass'])
if not result.wasSuccessful():raise SystemExit(1)
