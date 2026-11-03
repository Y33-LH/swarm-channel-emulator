"""Original procedural DEM + dominant-edge approximation, all SI units.

P.526-16 (2025), equations 26 and 31:
https://www.itu.int/dms_pubrec/itu-r/rec/p/R-REC-P.526-16-202511-I!!PDF-E.pdf
63 interior samples. Flat local Earth, no buildings/multi-edge diffraction.
Output is a model prediction, never a receiver channel estimate.
"""
import math

def environment(config,t):
 return config['environment'] or (1 if t<300 else 3 if t<600 else 4)

def enabled(config):
 c=config.get('channel',{})
 return c.get('mode',0)==1 and c.get('reserved0',0)==1

def height(x,y,env):
 return max(0,(5,5,16,22,10,110,65,85)[env]+(8,8,8,8,8,95,48,25)[env]*math.sin(x/680)*math.cos(y/830)+(2,2,4,7,3,28,12,8)[env]*math.sin((x+y)/340))

def knife_edge(nu):
 return 0. if nu<=-.78 else max(0.,6.9+20*math.log10(math.hypot(nu-.1,1)+nu-.1))

def elevation(x,y,env,t=0):
 if env:return height(x,y,env)
 def blend(start):
  u=min(1,max(0,(t-start)/20));return u*u*(3-2*u)
 w=blend(300);v=blend(600)
 return (1-w)*height(x,y,1)+(w-v)*height(x,y,3)+v*height(x,y,4)

def path(p,q,env,fc,t=0):
 horizontal=math.hypot(q[0]-p[0],q[1]-p[1]);d=math.dist(p,q)
 out=dict(loss_db=0.,nu=-1e9,clearance_m=1e9,x=0.,y=0.,height_m=0.,ground_z=elevation(5000,5000,env,t)+10)
 if horizontal<1 or d<1 or fc<=0:return out
 for i in range(1,64):
  u=i/64;x=p[0]+(q[0]-p[0])*u;y=p[1]+(q[1]-p[1])*u;z=elevation(x,y,env,t)
  clearance=p[2]+(q[2]-p[2])*u-z
  nu=-clearance*horizontal/d*math.sqrt(2/((299792458/fc)*d*u*(1-u)))
  if nu>out['nu']:out.update(nu=nu,clearance_m=clearance,x=x,y=y,height_m=z)
 out['loss_db']=knife_edge(out['nu']);return out
