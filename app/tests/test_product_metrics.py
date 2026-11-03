import unittest,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from product_metrics import link_windows,comparison
from product_advice import AdviceTracker
class ProductMetricsTest(unittest.TestCase):
    def test_evm_means_are_weighted_not_subtracted(self):
        a=[0]*21;b=[0]*21;a[0]=20;a[1]=10;a[2]=8;a[3]=6;a[19]=10;a[11]=10;a[12]=100000
        b[0]=50;b[1]=30;b[2]=24;b[3]=20;b[19]=30;b[11]=30;b[12]=200000
        w=link_windows(dict(run_id=1,round=20,links=[b]),dict(run_id=1,round=10,links=[a]))[0]
        self.assertEqual(w['evm_percent'],25);self.assertEqual(w['hop_success'],.7)
    def test_null_for_no_samples(self):
        w=link_windows(dict(run_id=1,round=10,links=[[0]*21]))[0]
        self.assertIsNone(w['post_ber']);self.assertIsNone(w['capture_rate'])
    def test_confounders_visible(self):
        a=dict(id='a',control_history=[],report=dict(config={'weather':0},config_sha256='x',image_hashes={'bit':'a','elf':'b','init':'c'},seed=1,duration_s=90,version='c',final={}))
        b=copy.deepcopy(a);b['id']='b';b['report']['config']['weather']=4
        self.assertTrue(comparison(a,b)['controlled_single_setting_comparison'])
        b['report']['seed']=2
        self.assertFalse(comparison(a,b)['controlled_single_setting_comparison'])
    def test_interventions_missing_history_and_nested_changes_are_not_controlled(self):
        a=dict(id='a',control_history=[],report=dict(config={'channel':{'mode':1,'fading':2}},config_sha256='x',image_hashes={'bit':'a'},final={}))
        b=copy.deepcopy(a);b['id']='b'
        self.assertTrue(comparison(a,b)['controlled_single_setting_comparison'])
        b['control_history']=[{'command':'LINKCOND change'}]
        self.assertFalse(comparison(a,b)['controlled_single_setting_comparison'])
        b['control_history']=None
        self.assertFalse(comparison(a,b)['controlled_single_setting_comparison'])
        b['control_history']=[];b['report']['config']['channel']={'mode':2,'fading':1}
        r=comparison(a,b)
        self.assertEqual(len(r['changed_config']),2)
        self.assertFalse(r['controlled_single_setting_comparison'])
    def test_advice_dedup_and_clear(self):
        s=dict(run_id=1,round=100,nodes=[[2,0,0,0,0,0,0,0,0,0,0]],links=[],delay_max_ns=0)
        tracker=AdviceTracker();cards,events=tracker.update(s);self.assertEqual(len(cards),1);self.assertEqual(len(events),1)
        s['round']=110;cards,events=tracker.update(s);self.assertEqual(len(events),0)
        s['nodes'][0][9]=1;s['nodes'][0][10]=12000;s['round']=120
        cards,events=tracker.update(s);self.assertIsNone(cards[0]['action'])
        s['round']=130;cards,events=tracker.update(s);self.assertEqual(cards,[]);self.assertEqual(events[0]['event'],'advice_resolved')
if __name__=='__main__':unittest.main()
