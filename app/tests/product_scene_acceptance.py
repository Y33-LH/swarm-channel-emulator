"""Independent geometry checks and real ARM configuration/readback checks."""
import sys,math,json,time,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps'),str(ROOT/'reference')]
from firmware_contract import PROTOCOL
from product_config import DEFAULT,validate,encode,wire_id,formation_points
from product_scene import position,channel

def offline():
    checks=0;minimum=1e9;maximum_delay=0;maximum_cfo=0
    for env in range(1,8):
        for weather in range(8):
            for form in range(9):
                c=validate(dict(environment=env,weather=weather,formation=form))
                for t in (0,101,330,370,670,710,899):
                    points=[position(n,t,7,c,protocol=PROTOCOL) for n in range(1,17)]
                    assert all(0<x<10000 and 0<y<10000 and 0<z<1000 for x,y,z in points)
                    sep=min(math.dist(a,b) for i,a in enumerate(points) for b in points[i+1:]);minimum=min(minimum,sep);assert sep>=100
                    for link in (0,3,11,19):
                        r=channel(link,t,7,c,protocol=PROTOCOL);assert all(math.isfinite(v) for v in r.values() if isinstance(v,float))
                        assert 0<=r['delay_samples']<=512 and 0<=r['echo_delay_samples']<=32
                        assert abs(r['cfo_hz'])<6000
                        maximum_cfo=max(maximum_cfo,abs(r['cfo_hz']));maximum_delay=max(maximum_delay,r['delay_samples'])
                    checks+=1
    for bad in ({'formation':1,'spacing_m':1100},{'schema':2},{'weather':8},{'reference_snr_cdb':float('nan')},{'unknown':1}):
        try:validate(bad)
        except ValueError:checks+=1
        else:raise AssertionError(bad)
    for a,b in ((1,3),(3,4)):
        ca=channel(0,123,7,validate({'environment':a}));cb=channel(0,123,7,validate({'environment':b}));assert ca['loss_spread_db']<cb['loss_spread_db']
    for env in range(1,8):
        c=validate({'environment':env});assert channel(3,123,7,c)['loss_spread_db']>channel(0,123,7,c)['loss_spread_db']
    result=dict(pass_geometry=True,source='independent_python_reference',checks=checks,min_separation_m=minimum,max_delay_samples=maximum_delay,max_cfo_hz=maximum_cfo,scope='504 preset combinations at 7 model times; not exhaustive arbitrary geometry validation')
    (ROOT/'results/product_geometry.json').write_text(json.dumps(result,indent=2));print(result,flush=True)

def board(port):
    import serial
    from serial_json import JsonSerial
    rows=[]
    with serial.Serial(port,230400,timeout=.2,write_timeout=5) as s:
        s.reset_input_buffer();client=JsonSerial(s)
        def cmd(text,ok=1):
            r=client.request(text,20);rows.append(dict(command=text,response=r));assert r['ok']==ok,(text,r);return r
        ping=cmd('PING');assert ping['protocol'] ==PROTOCOL and ping['pl_hz']==62500000
        cmd('NETSTOP')
        for c in [DEFAULT]+[validate(dict(environment=e,weather=w,formation=f)) for e,w,f in ((1,0,1),(2,1,2),(3,2,3),(4,4,4),(5,5,5),(6,6,6),(7,7,7),(4,0,8))]:
            r=cmd('SCENECFG '+encode(c).hex());assert r['config_id']==wire_id(c)
            info=cmd('SCENEINFO');assert info['values']==list(c.values())
            for t in (0,334,670,710,899):
                for link in (0,3,11,19,27):
                    p=channel(link,t,20261009,c,protocol=ping['protocol']);r=cmd(f'SCENE {link} {t*1000}')
                    for field,expected,tolerance in [('distance_mm',round(p['distance_m']*1000),1),('cfo_millihz',round(p['cfo_hz']*1000),2),('gain0_q15',round(min(1,p['gain0'])*32768),1),('gain1_q15',round(min(1,p['gain1'])*32768),1),('sigma',round(p['sigma']),1),('delay_samples',round(p['delay_samples']),1),('seed',p['noise_seed'],0)]:
                        assert abs(r[field]-expected)<=tolerance,(c,t,link,field,r[field],expected)
        previous=cmd('SCENEINFO')
        for text in ('z'*128,'00',struct.pack('<16i',2,*list(DEFAULT.values())[1:]).hex()):cmd('SCENECFG '+text,0)
        assert cmd('SCENEINFO')==previous
        cmd('SCENECFG '+encode(DEFAULT).hex());cmd('MEDIACLEAR 0 0');cmd('NETSTART 1 7 1')
        cmd('SCENECFG '+encode(DEFAULT).hex(),0)
        r=cmd('NETSTEP 10');assert r['generated']==r['delivered']==16 and r['slot_misses']==0
        cmd('NETSTOP');memory=cmd('MEMORY');assert memory['stack_guard_ok'] and not memory['heap_failures']
    report=dict(pass_board=True,port=port,checks=len(rows),scope='real ARM parameter calculations and ideal FPGA short network; full new-scene performance pending',memory=memory)
    (ROOT/'results/product_scene_uart.json').write_text(json.dumps(rows,indent=2));(ROOT/'results/product_scene_acceptance.json').write_text(json.dumps(report,indent=2));print(report,flush=True)

if __name__=='__main__':
    offline()
    if '--board' in sys.argv:board(sys.argv[sys.argv.index('--board')+1])
