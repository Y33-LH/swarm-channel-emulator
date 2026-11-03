import base64,sys,unittest
from pathlib import Path
APP=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(APP/'tools'),str(APP/'reference')]
from observation_scan import attach_bank,retain
class ScanTests(unittest.TestCase):
 def test_independent_wall_and_focus(self):
  identity=dict(run_id=1,round=10,watch_link=19)
  iq=base64.b64encode(bytes(range(128))).decode()
  cells=[[i,900+i,200+i,iq] for i in range(16)]
  bank=dict(identity,cells=cells,tap_history=[[500,30000,2000]])
  s=dict(identity);attach_bank(s,bank)
  self.assertEqual(len(s['wall_iq']),16);self.assertEqual(s['watch_link'],19)
  for change in (dict(run_id=2),dict(round=9),dict(watch_link=0),dict(cells=[cells[0],cells[0]]),
                 dict(cells=[[1,1100,4,iq]]),dict(cells=[[0,500,2,'AA==']])):
   with self.assertRaises(ValueError):attach_bank(s,dict(bank,**change))
  attach_bank(s,dict(bank,cells=[[2,400,5,'']],tap_history=[]))
  self.assertEqual(s['wall_iq'],[[2,400,5,'']])
 def test_replay_compares_wall_samples_and_time(self):
  from network_intervention import measurement
  s={'wall_iq':[[3,120,15,'AQIDBAUGBwg=']]}
  with_counter={'wall_iq':[[3,120,91,'AQIDBAUGBwg=']]}
  self.assertEqual(measurement(s),measurement(with_counter))
  self.assertEqual(s['wall_iq'][0][2],15)
  for changed in ([3,121,15,'AQIDBAUGBwg='],[3,120,15,'AAAAAAAAAAA=']):
   self.assertNotEqual(measurement(s),measurement({'wall_iq':[changed]}))
 def test_context_time_and_missing_samples(self):
  s=dict(run_id=1,config_id=2,channel_id=3,round=10)
  a=dict(run_id=1,config_id=2,channel_id=3,model_ms=900,link_id=0,received=[[1,2]])
  cache=retain({},a,s);self.assertEqual(cache['0'],a)
  self.assertEqual(retain(cache,None,s),cache)
  self.assertEqual(retain(cache,None,dict(s,round=8)),{})
  self.assertEqual(retain(cache,None,dict(s,channel_id=4)),{})
  self.assertEqual(retain(cache,None,dict(s,run_id=2)),{})
if __name__=='__main__':unittest.main()
