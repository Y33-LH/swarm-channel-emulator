"""Independent double-precision reference for ARM scene configuration v1."""
import sys, math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from product_config import validate,formation_points,DEFAULT
import terrain_model
from reference_scenario import position as legacy_position,channel as legacy_channel,seed_for,phase_for,variation,blend,smooth_weight
TAU=math.tau
ENV=[None,(2,0,-18,.125,.05,8,0,1,.2,3),(2.1,1,-15,.1875,.075,7,.5,1.5,.4,6),(2.2,2,-12,.25,.1,6,1,2,.6,9),(2.4,4,-9,.5,.2,4,2,5,1.2,18),(2.3,3,-10,1,.18,5,1.5,4,1,12),(2.2,2,-13,.5,.12,6,1,3,.7,9),(2.05,.5,-16,.25,.08,7,.4,2,.35,5)]
WEATHER_LOSS=(0,.01,.02,.05,.15,.01,.03,.08)
WEATHER_MOTION=(0,.1,.2,.4,.8,.2,.4,.7)
OSC=(0,-113,24,161,-203,-66,71,208,-156,-19,118,-246,-109,28,165,-199,-62)

def param(c,k,t):return ENV[c['environment']][k] if c['environment'] else blend(t,[ENV[i][k] for i in (1,3,4)])
def position_physical(node,t,seed=20261009,config=None,protocol=17,runtime=None):
    c=DEFAULT if config is None else config
    if node==0:return (5000.,5000.,terrain_model.elevation(5000,5000,c['environment'],t)+10 if terrain_model.enabled(c) else 0.)
    if c['formation']==0 and protocol<=20:return legacy_position(node,t,seed)
    x,y=formation_points(c['formation'])[node-1];x*=c['spacing_m'];y*=c['spacing_m'];a=c['heading_deg']*TAU/360
    # protocol 18 起：蜂群整体绕场景中心公转，轨道半径 = 可用区域90% − 编队半径
    # （须与 sw/scene_product.c 完全一致）；protocol 17 及当前在役固件：轨道固定 250 m。
    if protocol>=23:
        extent=max(max(abs(px*math.cos(a)-py*math.sin(a)),abs(px*math.sin(a)+py*math.cos(a))) for px,py in formation_points(c['formation']))*c['spacing_m']
        av=min(c['center_x_m'],10000-c['center_x_m'],c['center_y_m'],10000-c['center_y_m'])
        orbit=max(0,av-extent-200) if c['speed_mmps'] else 0
    elif protocol>=18:
        fr=max(math.hypot(px,py) for px,py in formation_points(c['formation']))*c['spacing_m']+400
        av=min(c['center_x_m'],10000-c['center_x_m'],c['center_y_m'],10000-c['center_y_m'])
        orbit=max(0,.9*av-fr) if c['speed_mmps'] else 0
    else:
        orbit=250 if c['speed_mmps'] else 0
    theta=c['speed_mmps']/1000/orbit*t if c['speed_mmps'] and orbit>1 else 0
    j=min(.08*c['spacing_m'],param(c,9,t)*c['jitter_percent']/100*(1+WEATHER_MOTION[c['weather']]))
    result=(c['center_x_m']+x*math.cos(a)-y*math.sin(a)+orbit*math.sin(theta)+j*variation(t,seed,node*3,37),
            c['center_y_m']+x*math.sin(a)+y*math.cos(a)+orbit*math.cos(theta)+j*variation(t,seed,node*3+1,41),
            c['altitude_m']+.3*j*variation(t,seed,node*3+2,43))
    if runtime and runtime.get('schema')==1:
        ext=runtime.get('external')
        if ext and ext[0]==node and t>=ext[4]:return tuple(ext[1:4])
        for n,old,new,at in runtime.get('altitude',[]):
            if n==node and t>=at:
                u=min(1,max(0,(t-at)/10));result=(*result[:2],old+(new-old)*u*u*(3-2*u))
    return result

def node_off(n,t,c):return bool(c['faults'] and n==2 and 330<=t<370)
def channel_physical(link,t,seed=20261009,config=None,protocol=20,runtime=None):
    c=DEFAULT if config is None else config
    if protocol<=19 and all(c[k]==DEFAULT[k] for k in ('environment','weather','formation','reference_snr_cdb','faults','jitter_percent')):return legacy_channel(link,t,seed)
    tx=link%16+1;rx=tx+1 if tx%4 else 0;ag=rx==0
    if link>=16:tx,rx=rx,tx
    p,q=(position_physical(n,t,seed,c,protocol=protocol,runtime=runtime) for n in (tx,rx));dv=[b-a for a,b in zip(p,q)];distance=math.dist(p,q)
    velocity=lambda n:[(b-a)/.002 for a,b in zip(position_physical(n,t-.001,seed,c,protocol=protocol,runtime=runtime),position_physical(n,t+.001,seed,c,protocol=protocol,runtime=runtime))]
    radial=sum((b-a)*d for a,b,d in zip(velocity(tx),velocity(rx),dv))/max(1,distance)
    eta=param(c,0,t)+(.2 if ag else 0);extra=param(c,1,t)+(2 if ag else 0);echo=param(c,2,t)+(3 if ag else 0)
    depth=param(c,4,t)*(1.5 if ag else 1);period=param(c,5,t)*(.75 if ag else 1);noise=param(c,6,t)+(2 if ag else 0)
    spread=param(c,8,t)*(1.5 if ag else 1)*c['jitter_percent']/100
    fault=smooth_weight(t,660,1)*(1-smooth_weight(t,699,1)) if c['faults'] and 660<=t<700 and 12 in (tx,rx) else 0
    loss=10*eta*math.log10(1+distance/1000 if protocol>=20 else max(distance,1000)/1000)+extra+spread*variation(t,seed,1000+link,17)+12*fault+WEATHER_LOSS[c['weather']]*distance/1000*(1.5 if ag else 1)
    gain=10**(-loss/20);ratio=10**((echo-6)/20);q0=1/math.sqrt(1+ratio**2)
    g0=gain*q0*(1-depth*(1-math.cos(TAU*t/period+phase_for(seed,link,'fade0')))/2)
    g1=gain*ratio*q0*(1-depth*(1-math.cos(TAU*t/(period*.8)+phase_for(seed,link,'fade1')))/2)
    sigma=math.sqrt(8192**2/(2*10**(c['reference_snr_cdb']/1000)))
    if protocol<=19:sigma*=10**((noise+.5*spread*variation(t,seed,2000+link,19)+6*fault)/20)
    freq=c['carrier_mhz']*1e6;cfo=OSC[tx]-OSC[rx]-freq*radial/299792458
    ed=param(c,7,t)*(1.6 if ag else 1)*(1 if seed_for(seed,link,'echo_sign')&1 else -1)
    phase=(-TAU*freq*distance/299792458+TAU*(OSC[tx]-OSC[rx])*t)%TAU
    return dict(link_id=link,tx=tx,rx=rx,channel_class='air_ground' if ag else 'air_air',distance_m=distance,radial_velocity_mps=radial,
                gain0=g0,gain1=g1,sigma=sigma,delay_samples=distance/299792458*8e6,echo_delay_samples=param(c,3,t)*8*(2 if ag else 1),
                cfo_hz=cfo,echo_cfo_hz=cfo+ed,phase_radians=phase,echo_phase_radians=(phase+phase_for(seed,link,'echo')+TAU*ed*t)%TAU,
                loss_db=loss,loss_spread_db=spread,noise_spread_db=spread*.5,node_available=not(node_off(tx,t,c) or node_off(rx,t,c)),noise_seed=seed_for(seed,link,'fast'))

def scene_time(t,config,protocol=22):
    return t*max(1,(config or DEFAULT).get('reserved',0)) if protocol>=22 else t

def position(node,t,seed=20261009,config=None,protocol=17,runtime=None):
    return position_physical(node,scene_time(t,config,protocol),seed,config,protocol,runtime)

def channel(link,t,seed=20261009,config=None,protocol=20,runtime=None):
    return channel_physical(link,scene_time(t,config,protocol),seed,config,protocol,runtime)
