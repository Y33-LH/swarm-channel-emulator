import sys,unittest,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'reference')]
import channel_config as cc,product_config as pc
from channel_model import frame
from product_scene import position
class Contract(unittest.TestCase):
 def test_full_experiment_identity_includes_taps(self):
  a=pc.validate({'channel':{'mode':2,'tap_count':8}})
  b=pc.validate({**a,'channel':{**a['channel'],'tap7_delay_ns':1700}})
  self.assertEqual(pc.wire_id(a),pc.wire_id(b))
  self.assertNotEqual(pc.config_hash(a),pc.config_hash(b))
  self.assertNotEqual(cc.wire_id(a['channel']),cc.wire_id(b['channel']))
  self.assertEqual(len(pc.encode(a)),64);self.assertEqual(len(cc.encode(a['channel'])),192)
 def test_limits_reject_not_silently_clamp(self):
  for x in ({'mode':2,'tap_count':0},{'tap_count':9},{'sample_rate_khz':12000},{'mode':2,'sample_rate_khz':16000,'delay_ns':60000,'tap0_delay_ns':60000},{'reserved0':2}):
   with self.subTest(x=x),self.assertRaises(ValueError):cc.validate(x)
  with self.assertRaises(ValueError):pc.validate({'weather':4,'carrier_mhz':200,'channel':{'mode':1}})
 def test_manual_is_independent_of_scene(self):
  a=pc.validate({'environment':1,'weather':0});b=pc.validate({'environment':4,'weather':4,'altitude_m':700,'speed_mmps':1000})
  for model in (0,1,2):
   c=cc.validate({'mode':2,'tap_count':8,'fading':model,'sample_rate_khz':16000})
   self.assertEqual(frame(3,51.2,77,a,c),frame(3,51.2,77,b,c))
 def test_scene_auto_profile_and_rng(self):
  c=cc.validate({'mode':1,'tap_count':0,'fading':1})
  a=pc.validate({'environment':1});b=pc.validate({'environment':4,'altitude_m':150})
  self.assertEqual(len(frame(0,1,7,a,c)['taps']),2)
  self.assertEqual(len(frame(3,1,7,b,c)['taps']),8)
  self.assertEqual(frame(0,1,7,a,c),frame(0,1,7,a,c))
  self.assertNotEqual(frame(0,1,7,a,c)['taps'],frame(0,1,8,a,c)['taps'])
 def test_x_geometry_really_changes(self):
  a=pc.validate({'formation':0,'jitter_percent':0,'speed_mmps':0});b=pc.validate({**a,'speed_mmps':12000})
  self.assertEqual(position(1,0,1,a,21),position(1,100,1,a,21))
  self.assertGreater(math.dist(position(1,0,1,b,21),position(1,100,1,b,21)),900)
  p=position(1,0,1,a,21);q=position(1,0,1,{**a,'altitude_m':700},21)
  self.assertEqual(q[2]-p[2],300)
  self.assertEqual(position(1,50,1,a,20),position(1,50,1,b,20))
if __name__=='__main__':unittest.main()
