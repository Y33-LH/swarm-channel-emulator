"""ABC A-v1 + CR001: geometry-owned distance, bounded seeded slow variation.
Parameters are controlled demonstration presets, not a certified channel model.
No packet delivery decisions are made here.
"""
import json,math,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CONFIG=json.loads((ROOT/'a_config_20261009/a_config_v1.json').read_text(encoding='utf-8-sig'))
BASELINE=json.loads((ROOT/'baseline_profile.json').read_text(encoding='utf-8'))
TAU=2*math.pi;FS=8_000_000;C=299_792_458.0;FC=2_400_000_000
def seed_for(seed,node,kind):return zlib.crc32(f'A2|{seed}|{node}|{kind}'.encode()) or 1
def phase_for(seed,node,kind):return seed_for(seed,node,kind)/2**32*TAU
def smooth_weight(t,start,length=20):
    u=max(0.,min(1.,(t-start)/length));return u*u*(3-2*u)
def env_weights(t):
    a=smooth_weight(t,300);b=smooth_weight(t,600);return (1-a,a-b,b)
def blend(t,values):return sum(w*v for w,v in zip(env_weights(t),values))
def variation(t,seed,key,period=13):
    # Sum of two bounded sinusoids with seeded phase: continuous, not white jitter.
    return .6*math.sin(TAU*t/period+phase_for(seed,key,'slow1'))+.4*math.sin(TAU*t/(period*1.73)+phase_for(seed,key,'slow2'))
def position(node,t,seed=20261009):
    if node==0:return tuple(CONFIG['common']['ground_xyz_m'])
    spec=CONFIG['nodes'][node-1];p=spec['group']*math.pi/2;np=(node-1)*TAU/16
    amplitude=blend(t,(3.,9.,18.));base=spec['base_xyz_m']
    return (
        base[0]+400*(math.cos(TAU*t/180+p)-math.cos(p))+40*(math.sin(TAU*t/120+np)-math.sin(np))+amplitude*variation(t,seed,node*3,37),
        base[1]+400*(math.sin(TAU*t/180+p)-math.sin(p))+amplitude*variation(t,seed,node*3+1,41),
        base[2]+30*(math.sin(TAU*t/120+np)-math.sin(np))+.3*amplitude*variation(t,seed,node*3+2,43))
def velocity(node,t,seed=20261009):
    a=position(node,t-.001,seed);b=position(node,t+.001,seed);return tuple((y-x)/.002 for x,y in zip(a,b))
def channel(link_id,t,seed=20261009,rectangular=True,reference_snr_db=None,echo_offset_db=None):
    if reference_snr_db is None:reference_snr_db=BASELINE['reference_complex_sample_snr_db']
    if echo_offset_db is None:echo_offset_db=BASELINE['echo_power_offset_db']
    link=CONFIG['links'][link_id];tx,rx=link['tx'],link['rx'];cls=link['channel_class'];ag=cls=='air_ground'
    p=position(tx,t,seed);q=position(rx,t,seed);vp=velocity(tx,t,seed);vq=velocity(rx,t,seed)
    dvec=tuple(b-a for a,b in zip(p,q));d=math.sqrt(sum(v*v for v in dvec));radial=sum((b-a)*v/d for a,b,v in zip(vp,vq,dvec))
    profiles=[next(a for a in CONFIG['profiles'] if a['environment']==e and a['channel_class']==cls) for e in ('open_field','suburb','city')]
    def param(key):return blend(t,[x[key] for x in profiles])
    # Declared peak bound ordering for corresponding slow disturbances.
    spread=blend(t,(.2,.6,1.2))*(1.5 if ag else 1.)
    loss_jitter=spread*variation(t,seed,1000+link_id,17)
    noise_jitter=.5*spread*variation(t,seed,2000+link_id,19)
    fault=(660<=t<700 and (tx==12 or rx==12))
    fault_envelope=smooth_weight(t,660,1)*(1-smooth_weight(t,699,1)) if fault else 0.
    loss=10*param('path_loss_exponent')*math.log10(max(d,1000)/1000)+param('excess_loss_db')+loss_jitter+12*fault_envelope
    amplitude=10**(-loss/20);r=10**((param('echo_relative_power_db')+echo_offset_db)/20);q0=1/math.sqrt(1+r*r);q1=r*q0
    fade=[1-param('direct_fade_depth' if j==0 else 'echo_fade_depth')*(1-math.cos(TAU*t/(param('fade_period_s')*(1 if j==0 else .8))+phase_for(seed,link_id,f'fade{j}')))/2 for j in range(2)]
    oscillator=lambda n:0 if n==0 else CONFIG['nodes'][n-1]['oscillator_offset_hz']
    cfo=oscillator(tx)-oscillator(rx)-FC*radial/C
    # Geometric phase (not Doppler integration again) + oscillator phase.
    phase=(-TAU*FC*d/C+TAU*(oscillator(tx)-oscillator(rx))*t) % TAU
    echo_doppler=param('echo_extra_doppler_magnitude_hz')*(1 if seed_for(seed,link_id,'echo_sign')&1 else -1)
    echo_phase=(phase+phase_for(seed,link_id,'echo')+TAU*echo_doppler*t)%TAU
    tx_power=(8192.0**2) if rectangular else (8192.0**2/4)
    sigma=math.sqrt(tx_power/(2*10**(reference_snr_db/10)))*10**((param('noise_excess_db')+noise_jitter+6*fault_envelope)/20)
    return dict(link_id=link_id,tx=tx,rx=rx,channel_class=cls,distance_m=d,radial_velocity_mps=radial,
        gain0=amplitude*q0*fade[0],gain1=amplitude*q1*fade[1],sigma=sigma,delay_samples=d/C*FS,
        echo_delay_samples=param('echo_excess_delay_us')*8,cfo_hz=cfo,echo_cfo_hz=cfo+echo_doppler,
        phase_radians=phase,echo_phase_radians=echo_phase,loss_db=loss,loss_spread_db=spread,
        noise_spread_db=spread*.5,node_available=not(330<=t<370 and (tx==2 or rx==2)),
        noise_seed=seed_for(seed,link_id,'fast'),environment_weights=env_weights(t))
def validate():
    maximum_speed=0.;maximum_acceleration=0.;minimum_separation=1e20;max_cfo=0.;max_delay=0.;samples=[]
    for step in range(9001):
        t=step/10
        positions=[position(n,t) for n in range(1,17)]
        for n,p in enumerate(positions,1):
            assert all(0<=x<=limit for x,limit in zip(p,(10000,10000,1000)))
            v=velocity(n,t);speed=math.sqrt(sum(x*x for x in v));maximum_speed=max(maximum_speed,speed);assert speed<20
            a=velocity(n,t-.01);b=velocity(n,t+.01);acc=math.sqrt(sum(((y-x)/.02)**2 for x,y in zip(a,b)));maximum_acceleration=max(maximum_acceleration,acc);assert acc<3
        if step%10==0:
            minimum_separation=min(minimum_separation,min(math.dist(a,b) for i,a in enumerate(positions) for b in positions[i+1:]))
            for link in range(32):
                c=channel(link,t);max_cfo=max(max_cfo,abs(c['cfo_hz']),abs(c['echo_cfo_hz']));max_delay=max(max_delay,c['delay_samples']+c['echo_delay_samples'])
                assert c['delay_samples']<512 and c['echo_delay_samples']<=32 and abs(c['cfo_hz'])<1000
            if step%1000==0:samples.append({'time':t,'nodes':positions,'links':[channel(i,t) for i in range(32)]})
    for t in (0.,333.,620.,899.):
        assert position(1,t)==position(1,t)
        assert position(1,t,7)!=position(1,t,8)
        for aa,ag in ((0,3),(4,7),(8,11),(12,15)):
            assert channel(ag,t)['loss_spread_db']>channel(aa,t)['loss_spread_db']
    assert channel(0,620)['loss_spread_db']>channel(0,320)['loss_spread_db']>channel(0,0)['loss_spread_db']
    report=dict(pass_validation=True,duration_s=900,dt_s=.1,max_speed_mps=maximum_speed,max_acceleration_mps2=maximum_acceleration,min_separation_m=minimum_separation,max_cfo_hz=max_cfo,max_delay_samples=max_delay,seed=20261009,model='controlled_two_tap_seeded_bounded_not_standard_statistical',samples=samples)
    (ROOT/'data').mkdir(exist_ok=True)
    (ROOT/'data/scenario_reference_validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='samples'}))
if __name__=='__main__':validate()
