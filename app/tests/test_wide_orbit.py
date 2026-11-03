import math,sys,unittest
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/p) for p in ('reference','tools')]
from product_config import validate
from product_scene import position
class WideOrbit(unittest.TestCase):
 def setUp(self):self.c=validate(dict(formation=7,spacing_m=1050,speed_mmps=20000,reserved=16,jitter_percent=0))
 def test_radius_spacing_and_speed(self):
  pts=[position(n,0,7,self.c,23) for n in range(1,17)]
  center=[sum(p[k] for p in pts)/16 for k in range(2)]
  self.assertAlmostEqual(math.dist(center,[5000,5000]),3225)
  self.assertAlmostEqual(math.dist(pts[0],pts[1]),1050)
  self.assertAlmostEqual(math.dist(position(1,10,7,self.c,23),position(1,10.001,7,self.c,23))/.001/16,20,places=4)
 def test_whole_orbit_inside_existing_domain(self):
  for heading in (0,30,45,90,135,225):
   c={**self.c,'heading_deg':heading,'jitter_percent':200,'weather':7}
   for t in range(0,170,2):
    for n in range(1,17):
     x,y,_=position(n,t,7,c,23)
     self.assertTrue(0<=x<=10000 and 0<=y<=10000,(heading,t,n,x,y))
 def test_old_protocol_geometry_preserved(self):
  c={**self.c,'spacing_m':900};pts=[position(n,0,7,c,22) for n in range(1,17)]
  self.assertAlmostEqual(sum(p[1] for p in pts)/16-5000,4100-900*math.sqrt(4.5))
if __name__=='__main__':unittest.main()
