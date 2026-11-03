"""Double-precision reference for channel contract 1 (firmware protocol 21).

Coefficients below describe a controlled model. Terrain/atmospheric presets
are not measurements. P.838 rain is distinguished from empirical fog/snow loss.
"""
import math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from channel_config import validate
from product_scene import channel as scene_channel
from reference_scenario import seed_for
import terrain_model

def unit(seed,key,kind):return (seed_for(seed,key,kind)+.5)/2**32

def digital_scale(f,sigma):
 bounds=[max(0,t[0])+abs(t[4])*.005 for t in f['taps']]
 peak=max(bounds);total=sum(bounds)
 return min(1.,.98/peak if peak else 1.,30000/(8192*total+4*sigma) if total or sigma else 1.)

def rain_attenuation(ghz,rate):
 if rate<=0:return 0.
 if not 1<=ghz<=1000:raise ValueError('ITU-R P.838 is valid only at 1–1000 GHz')
 x=math.log10(ghz)
 k=-.16398*x+.63297+sum(a*math.exp(-((x-b)/c)**2) for a,b,c in zip(
  (-3.80595,-3.44965,-.39902,.50167),(.56934,-.22911,.73042,1.07319),(.81061,.51059,.11899,.27195)))
 alpha=-.053739*x+.83433+sum(a*math.exp(-((x-b)/c)**2) for a,b,c in zip(
  (-.07771,.56727,-.20238,-48.2991,48.5833),(2.33840,.95545,1.14520,.791669,.791459),(-.76284,.54039,.26809,.116226,.116479)))
 return 10**k*rate**alpha

def scatter(link,tap,t,seed,fd,model,K):
 if model==0:return 1.,0.,0.,0.
 z=0j;dz=0j
 for m in range(32):
  key=link*256+tap*32+m;w=math.tau*fd*math.cos(math.tau*(m+unit(seed,key,'angle'))/32)
  a=w*t+math.tau*unit(seed,key,'scatter');e=complex(math.cos(a),math.sin(a))
  z+=e;dz+=1j*w*e
 z/=math.sqrt(32);dz/=math.sqrt(32)
 if model==2:z=z/math.sqrt(1+K)+math.sqrt(K/(1+K));dz/=math.sqrt(1+K)
 power=abs(z)**2;q=z.conjugate()*dz
 return abs(z),math.atan2(z.imag,z.real),q.real/abs(z) if power>1e-12 else 0,q.imag/(math.tau*power) if power>1e-12 else 0

def frame(link,t,seed,scene,configuration=None,runtime=None,protocol=23):
 c=validate(configuration);scene={**scene,'channel':c};base=scene_channel(link,t,seed,scene,protocol=protocol,runtime=runtime);t=t*max(1,scene.get("reserved",0));fs=c['sample_rate_khz']*1000
 if c['mode']==0:
  return dict(sample_rate_hz=fs,loss_db=base['loss_db'],rain_db_km=0,limited=0,taps=[
   [base['gain0'],base['delay_samples'],base['phase_radians'],base['cfo_hz'],0,0],
   [base['gain1'],base['delay_samples']+base['echo_delay_samples'],base['echo_phase_radians'],base['echo_cfo_hz'],0,0]])
 n=c['tap_count'];rain=0;env=scene['environment'] or (1 if t<300 else 3 if t<600 else 4);ag=base['channel_class']=='air_ground';limited=0;terrain=None
 if not n:n=min(8,(2,2,3,4,6,7,5,3)[env]+int(ag)+int(scene['altitude_m']<200)-int(scene['altitude_m']>=650))
 if c['mode']==1:
  weather=scene['weather'];rate={2:2,3:10,4:50}.get(weather,0)
  rain=rain_attenuation(scene['carrier_mhz']/1000,rate)
  old=(0,.01,.02,.05,.15,.01,.03,.08)[weather]*base['distance_m']/1000*(1.5 if ag else 1)
  loss=base['loss_db']-old+rain*base['distance_m']/1000
  if weather==1 or weather>=5:loss+=(.003 if weather==1 else .02*(weather-4))*base['distance_m']/1000
  if terrain_model.enabled(scene):
   from product_scene import position_physical as position
   terrain=terrain_model.path(position(base['tx'],t,seed,scene,protocol,runtime),position(base['rx'],t,seed,scene,protocol,runtime),scene['environment'],scene['carrier_mhz']*1e6,t)
   loss+=terrain['loss_db']
  echo=(0,-18,-15,-12,-9,-10,-13,-16)[env]
  weights=[1.]+[10**((echo+(3 if ag else 0)-6-(i-1)*c['echo_decay_cdb']/100)/10) for i in range(1,n)]
  initial=base['phase_radians'];delay=base['distance_m']/299792458*fs;ed=base['echo_cfo_hz']-base['cfo_hz']
 else:
  loss=c['loss_cdb']/100;weights=[10**(c[f'tap{i}_power_cdb']/1000) for i in range(n)]
  initial=c['phase_cdeg']*math.tau/36000;delay=c['delay_ns']*fs/1e9;ed=0
 taps=[];gain=10**(-loss/20)
 for i in range(n):
  scale=gain*math.sqrt(weights[i]/sum(weights));a,p,s,f=scatter(link,i,t,seed,c['scatter_millihz']/1000,c['fading'],10**(c['rician_k_cdb']/1000))
  if c['mode']==2:
   ph=initial+p+c[f'tap{i}_phase_cdeg']*math.tau/36000;freq=c['cfo_hz']+c[f'tap{i}_cfo_hz']+f;d=delay+c[f'tap{i}_delay_ns']*fs/1e9
  else:
   ph=initial+p+(math.tau*unit(seed,link*8+i,'tap_phase')+math.tau*i*ed*t if i else 0)
   freq=base['cfo_hz']+i*ed+f;d=delay+i*(0,125,187.5,250,500,1000,500,250)[env]*(2 if ag else 1)*c['delay_scale_percent']/100*fs/1e9
  taps.append([scale*a,d,ph,freq,scale*s,1+(i-1)//2 if i else 0])
  limited+=int(d>1023 or abs(freq)>100000)
 return dict(sample_rate_hz=fs,loss_db=loss,rain_db_km=rain,limited=limited,taps=taps,terrain=terrain)
