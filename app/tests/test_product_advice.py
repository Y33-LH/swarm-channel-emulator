import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from product_advice import analyze,validate_action

class AdviceTest(unittest.TestCase):
    def snap(self):
        return dict(run_id=7,round=100,nodes=[[n,0,0,0,0,0,0,9900,1,1,9900] for n in range(1,17)],links=[[0]*21 for _ in range(32)],delay_max_ns=1,late_delivered=0,pending=0)
    def test_stale_received_data(self):
        s=self.snap();s['nodes'][1][10]=1000
        rows=analyze(s);self.assertEqual(rows[0]['action']['target'],2)
        self.assertEqual(rows[0]['evidence']['age_ms'],9000)
    def test_slow_heartbeat_does_not_extend_ground_freshness(self):
        s=self.snap();s['nodes'][1][10]=1000
        row,=analyze(s,commands=[[1,2,2,5000,2,9000,10000,5000,0,5]])
        self.assertEqual(row['evidence']['threshold_ms'],3000)
        self.assertEqual((row['action']['target'],row['action']['value']),(2,1000))
    def test_broken_path_does_not_suggest_repeated_query(self):
        s=self.snap();p=copy.deepcopy(s);p['round']=50;s['nodes'][1][10]=1000
        s['links'][2][19]=10
        row=next(x for x in analyze(s,p) if x['evidence'].get('node')==2)
        self.assertIsNone(row['action']);self.assertEqual(row['evidence']['unconfirmed_hops'],[2])
        self.assertIn('3→4',row['advice'])
    def test_no_fake_window_from_other_run(self):
        s=self.snap();s['links'][0][19]=100;s['links'][0][4]=80
        p=copy.deepcopy(s);p['run_id']=8;p['links'][0]=[0]*21;p['round']=50
        self.assertEqual(analyze(s,p),[])
    def test_read_only_and_allowlist(self):
        s=self.snap();old=copy.deepcopy(s);analyze(s);self.assertEqual(s,old)
        for bad in ({'target':0,'opcode':1,'value':0,'ttl_ms':1000},{'target':1,'opcode':99,'value':0,'ttl_ms':1000},{'target':1,'opcode':2,'value':150,'ttl_ms':1000}):
            with self.assertRaises(ValueError):validate_action(bad)

if __name__=='__main__':unittest.main()
