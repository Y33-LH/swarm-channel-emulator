import math,sys,unittest
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/p) for p in ('reference','tools')]
from product_config import validate
from product_scene import position,channel
from channel_model import frame
from truth_track import track
class SceneClock(unittest.TestCase):
 def setUp(self):
  self.c=validate(dict(environment=6,formation=7,spacing_m=900,speed_mmps=20000,reserved=16,jitter_percent=0,channel={'mode':1,'tap_count':7,'fading':2,'reserved0':1}))
  self.normal={**self.c,'reserved':0}
 def test_scene_and_channel_share_physical_time(self):
  for t in [0,1,20,35,90]:
   for n in [0,1,9,13,16]:self.assertEqual(position(n,t,7,self.c,22),position(n,t*16,7,self.normal,22))
   for link in [0,3,11,19]:
    self.assertEqual(channel(link,t,7,self.c,22),channel(link,t*16,7,self.normal,22))
    self.assertEqual(frame(link,t,7,self.c,self.c['channel']),frame(link,t*16,7,self.normal,self.c['channel']))
 def test_speed_is_physical_not_accelerated_doppler(self):
  p=position(1,1,7,self.c,22);q=position(1,1.001,7,self.c,22)
  self.assertAlmostEqual(math.dist(p,q)/.001/16,20,places=4)
 def test_continuous_truth_not_clamped_at_zero(self):
  tr=track([dict(round=100,scene_runtime={})],self.c,7,0,22,10)
  self.assertEqual(tr['samples'][0][0],list(position(1,10,7,self.c,22)))
 def test_truth_window_has_no_repeated_future_tail(self):
  tr=track([dict(round=100,scene_runtime={})],self.c,7,0,22,10.2)
  self.assertEqual(tr['end_s'],13)
  self.assertTrue(all(b>a for a,b in zip(tr['times'],tr['times'][1:])))
  self.assertTrue(all(a[0]!=b[0] for a,b in zip(tr['samples'],tr['samples'][1:])))
  for t,row in zip(tr['times'],tr['samples']):self.assertEqual(row[0],list(position(1,t,7,self.c,22)))
 def test_legacy_records_ignore_new_clock(self):
  self.assertEqual(position(1,10,7,self.c,21),position(1,10,7,self.normal,21))
 def test_config_bounds(self):
  with self.assertRaises(ValueError):validate({**self.c,'reserved':65})
if __name__=='__main__':unittest.main()
