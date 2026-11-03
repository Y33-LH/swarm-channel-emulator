import sys,unittest,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'reference')]
from truth_track import track
from product_scene import position
from product_config import validate

class RuntimeTrack(unittest.TestCase):
 def test_executed_transition_not_queued_or_future(self):
  cfg=validate({'formation':1,'jitter_percent':0})
  events={'schema':1,'altitude':[[9,400,480,2.5],[9,440,450,7.5]],'external':None}
  snaps=[dict(round=0),dict(round=100,scene_runtime=events)]
  self.assertEqual(track(snaps,cfg,7,20,21,2,2)['samples'][0][8][2],400)
  self.assertEqual(track(snaps,cfg,7,20,21,7.5,2)['samples'][0][8][2],440)
  self.assertEqual(position(9,17.5,7,cfg,21,events)[2],450)
  self.assertEqual(position(8,17.5,7,cfg,21,events)[2],400)
 def test_external_update_does_not_leak_back(self):
  cfg=validate({'formation':1,'external_node':1})
  snaps=[dict(round=10,scene_runtime=dict(schema=1,external=[1,2000,3000,450,1],altitude=[])),
         dict(round=30,scene_runtime=dict(schema=1,external=[1,2100,3100,480,3],altitude=[]))]
  self.assertEqual(track(snaps,cfg,7,10,21,2,2)['samples'][0][0],[2000,3000,450])
  self.assertEqual(track(snaps,cfg,7,10,21,3,2)['samples'][0][0],[2100,3100,480])
 def test_invalid_time(self):
  with self.assertRaises(ValueError):track([{'round':1}],validate({}),7,10,21,float('nan'))
if __name__=='__main__':unittest.main()
