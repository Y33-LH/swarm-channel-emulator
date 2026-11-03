"""Physical-board noise qualification; no retries, seed hunting or noise reduction."""
import argparse, binascii, hashlib, json, math, random, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps'),str(ROOT/'tests')]
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX
import serial
from serial_json import JsonSerial
from acceptance import frame

def run(port='COM4', count=200, version=VERSION, baseline=False, out=None):
    out=Path(out) if out else ROOT/'results'/time.strftime(('noise_baseline_' if baseline else 'noise_acceptance_')+'%Y%m%d_%H%M%S')
    out.mkdir(parents=True,exist_ok=False)
    rng=random.Random(20261014)
    seeds=[7]+rng.sample(range(100,2**32-1),count-1)
    rows=[]
    common={12:0,48:5000000,64:19661,68:2800,72:0,80:0,84:298261618,92:214748,96:0,112:0,116:0,120:0,124:2,128:1073741824,132:214748,136:0,140:0,192:1,776:0}
    start=time.monotonic()
    (out/'plan.json').write_text(json.dumps(dict(count=count,seeds=seeds,registers=common,version=f'{version:08x}',retries=0,baseline=baseline),indent=2))
    with serial.Serial(port,230400,timeout=.2,write_timeout=5) as s,(out/'uart.jsonl').open('w') as log:
        s.reset_input_buffer();c=JsonSerial(s)
        def cmd(t):
            r=c.request(t,15);log.write(json.dumps(dict(command=t,response=r))+'\n');log.flush();return r
        def good(t):
            r=cmd(t);assert r.get('ok')==1,(t,r);return r
        ping=good('PING');assert ping['version']==version and ping['protocol'] ==PROTOCOL,ping
        good('NETSTOP');good('RELEASE');good('WRITE 796 0')
        for a,v in common.items():good(f'WRITE {a} {v}')
        for a,v in common.items():assert good(f'READ {a}')['value']==v,(a,v)
        for k,seed in enumerate(seeds):
            good('RELEASE');good(f'WRITE 88 {seed}')
            assert good('READ 88')['value']==seed
            size=[1,16,32,63,64][k%5]
            payload=hashlib.sha512(f'noise qualification payload {k}'.encode()).digest()[:size]
            tx=frame(payload,40000+k)
            good(f'LOAD {40000+k} {tx.hex()}');good('START')
            deadline=time.monotonic()+10
            while not good('STATUS')['status']&2:assert time.monotonic()<deadline
            r=cmd('RESULT');p=good('PHYSTATS');captures=good('READ 100')['value']
            rx=bytes.fromhex(r.get('rx_hex',''));crc=binascii.crc_hqx(tx,0xffff)
            match=r.get('ok')==1
            if match:
                assert rx==tx and len(rx)==96 and r['crc_calc']==r['crc_recv']==crc,(k,r)
                assert p['post_errors']==0 and p['turbo_iterations']==2 and p['pre_bits']==4752,p
            else:assert not rx,'Rejected frame must not publish payload'
            row=dict(index=k,seed=seed,length=size,match=match,captures=captures,result=r,phy=p,tx_hex=tx.hex(),crc_expected=crc)
            rows.append(row)
            (out/'trials.json').write_text(json.dumps(rows,indent=2))
            if (k+1)%10==0 or k==0:print(f'NOISE_PHYSICAL frames={k+1} delivered={sum(x["match"] for x in rows)} captured={sum(x["captures"]>0 for x in rows)}',flush=True)
        good('RELEASE')
    delivered=sum(x['match'] for x in rows);rate=delivered/count
    failures={}
    for x in rows:
        if not x['match']:
            reason='capture' if not x['captures'] else f'result_{x["result"].get("result_code")}'
            failures[reason]=failures.get(reason,0)+1
    z=1.96;den=1+z*z/count;center=(rate+z*z/(2*count))/den
    half=z*math.sqrt(rate*(1-rate)/count+z*z/(4*count*count))/den
    report=dict(**{'pass':rate>=.9 and rows[0]['match']},source='physical_board_UART',baseline=baseline,
        version=f'{version:08x}',trials=count,delivered=delivered,captured=sum(x['captures']>0 for x in rows),
        rate=rate,reference_seed_7_pass=rows[0]['match'],failures=failures,retries=0,
        confidence95_wilson=[center-half,center+half],registers=common,nominal_complex_sample_snr_db=10*math.log10((8192*19661/32768)**2/(2*2800**2)),
        coded_bit_errors=sum(x['phy']['pre_errors'] for x in rows),coded_bits=sum(x['phy']['pre_bits'] for x in rows),
        independently_compared_bytes=96*delivered,elapsed_s=time.monotonic()-start,
        files={n:hashlib.sha256((ROOT/'ready'/n).read_bytes()).hexdigest() for n in ('system_wrapper.bit','swarm_app.elf','ps7_init.tcl')},
        scope='Single-attempt full-FEC frames at gain 0.6, sigma 2800 per I/Q, phase 25 deg, CFO 400 Hz. Not all SNRs or uncoded frames.')
    (out/'acceptance.json').write_text(json.dumps(report,indent=2))
    print(('NOISE_BASELINE_RECORDED ' if baseline else 'NOISE_HARDWARE_RESULT ')+json.dumps(report),flush=True)
    if not baseline:assert report['pass'],f'Noise gate not reached: {out}'
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',default='COM4');p.add_argument('--count',type=int,default=200)
    p.add_argument('--version',type=lambda x:int(x,16),default=VERSION);p.add_argument('--baseline',action='store_true');p.add_argument('--out')
    a=p.parse_args();assert 100<=a.count<=1000;run(a.port,a.count,a.version,a.baseline,a.out)
