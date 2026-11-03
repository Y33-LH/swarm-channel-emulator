import unittest,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'tools'),str(R/'reference')]
from network_reproduction import timeline,Control

class Tests(unittest.TestCase):
 def test_only_original_external_controls_and_boundaries(self):
  rows=[dict(command=c,response=r) for c,r in [('NETSTOP',{}),('NETSTART 0 9 0',{}),('NETWATCH 4',{'ok':1}),('NETSTEP 10',{'round':10}),('MEDIAADVANCE 3 99',{}),('GCOMMAND 01',{'ok':1}),('NETSTEP 10',{'round':20}),('NETSTOP',{}),('GCOMMAND 02',{})]]
  actual=timeline(rows)
  self.assertEqual([(x['round'],x['command']) for x in actual],[(0,'NETWATCH 4'),(10,'GCOMMAND 01')])
 def test_does_not_apply_future_commands_early(self):
  calls=[];c=Control([dict(round=20,command='NETWATCH 4',response={'ok':1})])
  cmd=lambda x,**kw:(calls.append(x) or {'ok':1})
  c(cmd,{'round':10});self.assertEqual(calls,[])
  c(cmd,{'round':20});self.assertEqual(calls,['NETWATCH 4'])
  c(cmd,{'round':20});self.assertEqual(len(calls),1)
 def test_missed_boundary_and_changed_response_fail(self):
  c=Control([dict(round=20,command='NETWATCH 4',response={'ok':1})])
  with self.assertRaises(AssertionError):c(lambda *a,**k:None,{'round':30})
  with self.assertRaises(AssertionError):c(lambda *a,**k:{'ok':0},{'round':20})
if __name__=='__main__':unittest.main()
