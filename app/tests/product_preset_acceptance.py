"""Every selectable preset reaches ARM + physical PL; not all Cartesian combinations."""
from pathlib import Path
import sys,json,time,uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps')]
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX
from product_config import validate,encode,DEFAULT
from serial_json import JsonSerial
import serial

def run(port='COM4'):
    out=ROOT/'results'/time.strftime('presets_%Y%m%d_%H%M%S');out.mkdir()
    cases=[('baseline',dict(DEFAULT))]
    cases += [(f'environment_{e}',validate(dict(environment=e,formation=7,faults=0))) for e in range(1,8)]
    cases += [(f'weather_{w}',validate(dict(environment=4,weather=w,formation=7,faults=0))) for w in range(8)]
    cases += [(f'formation_{f}',validate(dict(environment=3,formation=f,faults=0))) for f in range(9)]
    rows=[]
    with serial.Serial(port,230400,timeout=.2,write_timeout=5) as ser,(out/'uart.jsonl').open('w') as log:
        ser.reset_input_buffer();client=JsonSerial(ser)
        def cmd(t):
            r=client.request(t,60);log.write(json.dumps(dict(command=t,response=r))+'\n');log.flush();assert r['ok'],(t,r);return r
        assert cmd('PING')['version']==VERSION
        cmd('NETSTOP');cmd('MEDIACLEAR 0 0');cmd('NETFEC 1');cmd('NETACKDROP 0');cmd('NETLOAD 0')
        for name,cfg in cases:
            cmd('SCENECFG '+encode(cfg).hex());cmd('NETSTART 10 20261013 0');r=cmd('NETSTEP 100')
            assert r['round']==100 and not r['running'] and r['slot_misses']==0
            assert 0<r['delivered']<=r['generated'] and r['generated']==160
            assert all(n[9]>0 for n in r['nodes']),name
            assert len(r['applied_links'])==32 and all(a[0] for a in r['applied_links'])
            assert all(x[1]<=x[0] and x[2]<=x[1] and x[8]<=x[7] for x in r['links'])
            rows.append(dict(name=name,config=cfg,delivery=r['delivered']/r['generated'],final=r))
            print('PRESET',name,rows[-1]['delivery'],flush=True)
        # Identical seed/config/input must reproduce all model outcomes, not host duration.
        cfg=validate(dict(environment=4,weather=4,formation=6,faults=0));cmd('SCENECFG '+encode(cfg).hex())
        def experiment(seed):cmd(f'NETSTART 10 {seed} 0');return cmd('NETSTEP 100')
        a=experiment(42);b=experiment(42);c=experiment(43)
        # Receiver generation is a monotonically increasing hardware transaction
        # identifier, not a model outcome. Keep original IDs in uart.jsonl; compare
        # all received samples, estimates, counters and model timestamps exactly.
        for s in (a,b):
            s.pop('wall_ms');s.pop('watch_iq_generation');s['watch_phy'][3]=0
        assert a==b,'Same model inputs did not reproduce'
        assert a['nodes']!=c['nodes'] and a['applied_links']!=c['applied_links'],'Different seeds did not change model'
        memory=cmd('MEMORY');assert memory['stack_guard_ok'] and not memory['heap_failures']
        cmd('SCENECFG '+encode(DEFAULT).hex())
    report=dict(**{'pass':True},source='physical_FPGA_and_ARM',cases=rows,seed_reproduction=True,memory=memory,
                reproduction_excludes=['wall_ms','watch_iq_generation','watch_phy[3] hardware generation ID'],
                scope='25 preset axis cases x 10 model seconds, plus reproducibility. Does not guarantee all combinations or arbitrary parameter values.')
    (out/'acceptance.json').write_text(json.dumps(report,indent=2));print('PRODUCT_PRESETS_PASS',out,flush=True)
    return report
if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else 'COM4')
