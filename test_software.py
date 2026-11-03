import sys,unittest
from pathlib import Path
r=Path(__file__).resolve().parent/'app'
sys.path[:0]=[str(r/p) for p in ('tests','tools','reference','tools/python_deps')]
s=unittest.defaultTestLoader.loadTestsFromNames(['test_workflow', 'test_assistant_live_context', 'test_product_assistant_fallback', 'test_action_context', 'test_product_metrics', 'test_network_wire', 'test_serial_json', 'test_link_experiment', 'test_mission_environment'])
sys.exit(not unittest.TextTestRunner(verbosity=2).run(s).wasSuccessful())
