import unittest,sys,copy,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'tools'),str(R/'reference')]
import action_observation as ao
import network_intervention as ni
from intervention_session import Session

def snap(t,status=None):
 nodes=[[n,0,0,0,0,0,400000,t*1000,n,t,t*1000] for n in range(1,17)]
 return dict(round=t*10,run_id=1,nodes=nodes,pending=0,media=[min(6678,t*100),6678,min(15292,t*320),15292],business_counts=[[3,t,0,0],[4,t*5,0,0]],command_results=[] if status is None else [[1,5,4,1,status,12000,20000,1000,0,1]],command_trace={},edge_trace=[])
event=dict(index=1,action=dict(kind='command',window_s=10,command=dict(target=5,opcode=4,value=1,ttl_ms=10000)),effective_round=100,command_id=1,receipt={'ok':1})
class Tests(unittest.TestCase):
 def test_no_optimistic_confirmation(self):
  c=ao.commands([snap(t,1) for t in range(1,22)],[event])[0]
  self.assertEqual(c['status'],'unconfirmed');self.assertIsNone(c['confirmed_ms']);self.assertIsNone(c['after'])
 def test_rejected_not_effect(self):
  c=ao.commands([snap(t,3) for t in range(1,22)],[event])[0]
  self.assertEqual(c['verdict'],'rejected')
 def test_post_window_frozen_before_later_action(self):
  ss=[snap(t,2 if t>=12 else 1) for t in range(1,35)]
  c=ao.commands(ss,[event,dict(action={'kind':'restore'},effective_round=200)])[0]
  self.assertEqual(c['after']['start_ms'],12000);self.assertEqual(c['after']['end_ms'],17000)
 def test_command_results_not_excluded_from_reproduction(self):
  a=snap(20,2);b=copy.deepcopy(a);b['command_results'][0][4]=3
  self.assertNotEqual(ni.measurement(a),ni.measurement(b))
 def test_unsupported_media_node_rejected(self):
  for node in (2,9,13):
   with self.assertRaises(ValueError):ao.validate_command(dict(target=node,opcode=4,value=1,ttl_ms=10000))
 def test_stale_action_rejected(self):
  with tempfile.TemporaryDirectory(dir=R/'results') as d:
   x=Session('test',Path(d),ni.plan({}),lambda *a:None,lambda:False);x.snapshots=[snap(10)];x.phase='waiting'
   with self.assertRaises(ValueError):x.submit(dict(event['action'],observed_round=90),'test')
   with self.assertRaises(ValueError):x.submit(dict(event['action'],observed_round=100),'other')
 def test_pending_after_ack_requires_complete_window(self):
  c=ao.commands([snap(t,2 if t>=12 else 1) for t in range(1,16)],[event])[0]
  self.assertIsNone(c['after']);self.assertEqual(c['verdict'],'awaiting_observation')
 def test_restore_recommendation_is_not_generic_query(self):
  ss=[snap(t) for t in range(1,21)];ss[-1]['nodes'][0][10]=0
  rows=ao.recommendations(ss,ni.plan({}),[dict(action={'kind':'change'},effective_round=100)])
  self.assertEqual(rows[0]['action']['kind'],'restore')
 def test_tampered_timeline_rejected_before_hardware(self):
  es=[copy.deepcopy(event)];ss=[snap(10)];p=ni.plan({})
  r=dict(plan=p,events=es,snapshots=ss,report=dict(measurement_sha256=ni.digest([ni.measurement(s) for s in ss]),action_timeline_sha256=ni.digest([dict(round=e['effective_round'],action=e['action']) for e in es])))
  ni.validate_reproduction(r)
  r['events'][0]['action']['command']['value']=2
  with self.assertRaises(ValueError):ni.validate_reproduction(r)
 def test_later_change_does_not_invent_effect(self):
  ss=[snap(t,2 if t>=12 else 1) for t in range(1,25)]
  c=ao.commands(ss,[event,dict(action={'kind':'restore'},effective_round=140)])[0]
  self.assertIsNone(c['after']);self.assertEqual(c['verdict'],'confounded_window')
if __name__=='__main__':unittest.main()
