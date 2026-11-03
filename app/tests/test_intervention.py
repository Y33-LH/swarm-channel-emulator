import unittest,sys,json,copy,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'reference')]
import network_intervention as ni
from intervention_session import record

class ContractTests(unittest.TestCase):
    def setUp(self):
        override=os.environ.get('SWARM_ACTION_FIXTURE')
        paths=[Path(override)] if override else sorted(ROOT.glob('results/action_qualification_*/original'),reverse=True)
        fixture=next((p for p in paths if (p/'acceptance.json').exists()),None)
        if fixture is None:raise RuntimeError('Run tests/action_hardware.py before this evidence-mutation suite')
        self.record=record(fixture)
        self.success=next(s for s in self.record['snapshots'] if s.get('observation',{}).get('rx_hex') and s['observation']['iq'])
        self.failure=next(s for s in self.record['snapshots'] if s.get('observation') and not s['observation']['rx_hex'] and not s['observation']['phy'][4])
    def test_rejects_invalid_edge_gain_seed(self):
        for data in ({'link':16},{'seed':0},{'link':False},{'seconds':89},{'config':{'faults':1}},{'config':{'external_node':2}}):
            with self.assertRaises(ValueError):ni.plan(data)
        for data in ({'kind':'change','gain_permille':1001},{'kind':'change','sigma':8193},{'kind':'x'},{'kind':'restore','window_s':0}):
            with self.assertRaises(ValueError):ni.action(data)
    def test_saved_failure_is_valid_not_missing(self):
        s=self.failure
        ni.verify_observation(s,self.record['plan'],self.record['events'])
        self.assertFalse(s['observation']['rx_hex']);self.assertEqual(s['observation']['iq'],[])
    def test_frame_generation_mismatch_rejected(self):
        s=copy.deepcopy(self.success);s['observation']['phy'][3]+=1
        with self.assertRaises(AssertionError):ni.verify_observation(s,self.record['plan'],self.record['events'])
    def test_wrong_readback_rejected(self):
        s=copy.deepcopy(self.failure);s['observation']['applied'][5]=0
        with self.assertRaises(AssertionError):ni.verify_observation(s,self.record['plan'],self.record['events'])
    def test_corrupt_rx_rejected(self):
        s=copy.deepcopy(self.success);s['observation']['rx_hex']='ff'+s['observation']['rx_hex'][2:]
        with self.assertRaises(AssertionError):ni.verify_observation(s,self.record['plan'],self.record['events'])
    def test_old_queued_heartbeat_not_claimed_recovered(self):
        event=next(e for e in self.record['events'] if e['action']['kind']=='restore');t=event['effective_round']*100
        s=copy.deepcopy(next(s for s in self.record['snapshots'] if s['round']>event['effective_round']))
        node=self.record['plan']['link']//4*4;s['nodes'][node][10]=t-1;s['nodes'][node][7]=s['round']*100
        v=ni.view(s,None,self.record['plan'],self.record['events'])
        self.assertFalse(v['nodes'][0]['recovered'])
    def test_exact_comparison_detects_failure_and_iq_changes(self):
        other=copy.deepcopy(self.record);other['snapshots'][0]['observation']['iq'][0][0]^=1
        self.assertFalse(ni.compare(self.record,other)['exact_match'])
        other=copy.deepcopy(self.record);other['snapshots'][0]['links'][0][5]+=1
        self.assertFalse(ni.compare(self.record,other)['exact_match'])
    def test_comparison_ignores_wall_clock_only_expected_fields(self):
        other=copy.deepcopy(self.record)
        for s in other['snapshots']:s['wall_ms']+=500000
        self.assertTrue(ni.compare(self.record,other)['exact_match'])
    def test_no_predefined_business_failure(self):
        baseline=[copy.deepcopy(s) for s in self.record['snapshots'][:10]]
        e=[dict(condition_id=1,action={'kind':'change'},effective_round=0),
           dict(condition_id=2,action={'kind':'restore'},effective_round=50)]
        self.assertFalse(ni.evaluate(baseline,self.record['plan'],e)['effect_observed'])
    def test_replay_rejects_modified_plan_and_observations(self):
        ni.validate_reproduction(self.record)
        altered=copy.deepcopy(self.record);altered['plan']['seed']+=1
        with self.assertRaises(ValueError):ni.validate_reproduction(altered)
        altered=copy.deepcopy(self.record);altered['snapshots'][0]['nodes'][0][9]+=1
        with self.assertRaises(ValueError):ni.validate_reproduction(altered)
if __name__=='__main__':unittest.main()
