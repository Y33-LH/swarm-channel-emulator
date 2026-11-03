import math,sys,unittest
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/p) for p in ('reference','tools')]
from product_config import validate,DEFAULT
from product_scene import channel,position,OSC

class ChannelContract20(unittest.TestCase):
 def test_noise_is_user_setting_across_environments_weather_edges_faults(self):
  expected=8192/math.sqrt(2*10**3.4)
  for env in range(8):
   for weather in range(8):
    cfg=validate(dict(environment=env,weather=weather,formation=7))
    for t in (0,345,675):
     for link in (0,3,11,19,27):
      self.assertAlmostEqual(channel(link,t,5,cfg,20)['sigma'],expected,places=10)
 def test_carrier_no_longer_bypassed_in_default_preset(self):
  a=channel(3,100,5,DEFAULT,20);b=channel(3,100,5,{**DEFAULT,'carrier_mhz':4800},20)
  oscillator=OSC[a['tx']]-OSC[a['rx']]
  self.assertGreater(abs(a['cfo_hz']-oscillator),.01)
  self.assertAlmostEqual(b['cfo_hz']-oscillator,2*(a['cfo_hz']-oscillator),places=8)
 def test_distance_changes_below_one_kilometre(self):
  base=dict(environment=1,formation=7,faults=0,jitter_percent=0,speed_mmps=0)
  a=channel(0,0,5,validate({**base,'spacing_m':200}),20)
  b=channel(0,0,5,validate({**base,'spacing_m':300}),20)
  self.assertAlmostEqual(a['distance_m'],200);self.assertAlmostEqual(b['distance_m'],300)
  self.assertGreater(a['gain0'],b['gain0']);self.assertEqual(a['sigma'],b['sigma'])
 def test_old_record_keeps_original_equations(self):
  a=channel(3,345,5,DEFAULT,17);b=channel(3,345,5,DEFAULT,19)
  self.assertEqual(a,b)
  self.assertNotEqual(a['sigma'],channel(3,345,5,DEFAULT,20)['sigma'])
if __name__=='__main__':unittest.main()
