import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from recovery_workflow import parse,diagnose
class RecoveryTests(unittest.TestCase):
 def test_closed_command_vocabulary(self):
  self.assertEqual(parse('节点 5 媒体速率 30')['action']['value'],30)
  self.assertEqual(parse('节点 2 心跳间隔 1 秒')['action']['value'],1000)
  for t in ['把它修好','节点 3 媒体速率 30','节点 2 心跳间隔 50 毫秒','恢复链路 99','节点 2 高度 900 米','节点 5 媒体速率 3 米']:
   with self.assertRaises(ValueError):parse(t)
 def test_slow_heartbeat_does_not_relax_sla(self):
  s={'round':60,'nodes':[[2,0,0,0,0,0,0,0,0,1,1000]],'command_results':[[1,2,2,10000,2]],'pending':0}
  r=diagnose(s);self.assertEqual(r['issues'][0]['overdue_ms'],2000)
  s['nodes'][0][10]=5900;self.assertTrue(diagnose(s)['healthy'])
 def test_no_startup_alarm(self):
  self.assertFalse(diagnose({'round':20,'nodes':[[1]*11]})['issues'])
 def test_single_slow_node_requires_receipt_and_two_new_heartbeats(self):
  previous=None
  slow=[1,9,2,10000,2,2000,12000,10000];fast=[2,9,2,1000,2,13000,23000,1000]
  def sample(now,count,stamp,commands):
   nonlocal previous
   s=dict(round=now//100,run_id=7,nodes=[[9,0,0,0,0,0,0,0,0,count,stamp]],command_results=commands)
   s['recovery']=diagnose(s,previous);previous=s;return s['recovery']
  self.assertFalse(sample(3000,2,1000,[slow])['issues'])
  self.assertEqual([i['node'] for i in sample(5000,2,1000,[slow])['issues']],[9])
  self.assertTrue(sample(12000,3,12000,[slow])['issues'][0]['command'])
  self.assertTrue(sample(13000,3,12000,[slow,[2,10,2,1000,2,13000,23000,1000]])['issues'])
  self.assertIsNone(sample(14000,4,14000,[slow,fast])['issues'][0]['command'])
  result=sample(15000,5,15000,[slow,fast])
  self.assertTrue(result['healthy']);self.assertEqual(result['resolved_heartbeats']['9']['second_ms'],15000)
if __name__=='__main__':unittest.main()
