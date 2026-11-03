"""Paired physical-board FEC study with explicit total frame energy budgets.

Both modes send identical 96-byte information frames. The first comparison uses
equal transmit amplitude (coded frame spends more energy). The second scales
the coded amplitude by sqrt(1326/5294), including the 542-symbol preamble.
This uses a composite TX-amplitude/channel-gain register for a one-tap fixture;
there is no claim that the transmitter has gained a new runtime power control.
No expected payload is used to repair received data.
"""
import sys,json,time,math,hashlib,binascii
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps'),str(ROOT/'tests')]
import serial
from serial_json import JsonSerial
from acceptance import frame
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX

def wilson(k,n):
    z=1.95996398454;p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d
    r=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-r),min(1,c+r)]

def run(port,trials=30):
    out=ROOT/'results'/time.strftime('fec_energy_%Y%m%d_%H%M%S');out.mkdir();rows=[]
    with serial.Serial(port,230400,timeout=.2,write_timeout=5) as uart,(out/'uart.jsonl').open('w') as log:
        uart.reset_input_buffer();client=JsonSerial(uart)
        def cmd(t,ok=True):
            r=client.request(t,20);log.write(json.dumps(dict(command=t,response=r))+'\n');log.flush()
            if ok:assert r.get('ok')==1,(t,r)
            return r
        ping=cmd('PING');assert ping['version']==VERSION and ping['protocol']==PROTOCOL
        cmd('NETSTOP');cmd('RELEASE')
        for a,v in {796:0,12:0,48:5000000,72:0,80:0,84:0,92:0,96:0,112:0,116:0,120:0,124:0,128:0,132:0,136:0,140:0,772:0,776:0}.items():cmd(f'WRITE {a} {v}')
        for sigma in (0,1800,2800,3800):
            for trial in range(trials if sigma else 3):
                tx=frame(hashlib.sha512(f'energy-comparison-{trial}'.encode()).digest(),3000+trial)
                seed=20261101+trial*773
                for mode,fec,gain in (('raw',0,.6),('coded_equal_amplitude',1,.6),('coded_equal_frame_energy',1,.6*math.sqrt(1326/5294))):
                    cmd('RELEASE');q=round(gain*32768)
                    for a,v in ((64,q),(68,sigma),(88,seed),(192,fec)):cmd(f'WRITE {a} {v}')
                    cmd(f'LOAD {3000+trial} {tx.hex()}');cmd('START');deadline=time.monotonic()+8
                    while not cmd('STATUS')['status']&2:assert time.monotonic()<deadline
                    result=cmd('RESULT',False);stats=cmd('PHYSTATS');rx=bytes.fromhex(result.get('rx_hex',''))
                    if result.get('ok'):assert rx==tx and result['crc_calc']==result['crc_recv']==binascii.crc_hqx(tx,65535)
                    else:assert not rx
                    if sigma==0:assert result.get('ok'),(mode,result,stats)
                    rows.append(dict(mode=mode,sigma=sigma,trial=trial,seed=seed,gain_q15=q,information_sha256=hashlib.sha256(tx).hexdigest(),
                        normalized_frame_energy=(q/32768)**2*(5294 if fec else 1326),delivered=bool(result.get('ok')),result=result,phy=stats))
            print('FEC_ENERGY_SNR_GROUP',sigma,flush=True)
        cmd('RELEASE');memory=cmd('MEMORY');assert memory['stack_guard_ok'] and not memory['heap_failures']
    groups=[]
    for sigma in (0,1800,2800,3800):
        for mode in ('raw','coded_equal_amplitude','coded_equal_frame_energy'):
            r=[x for x in rows if x['sigma']==sigma and x['mode']==mode];k=sum(x['delivered'] for x in r)
            groups.append(dict(mode=mode,sigma=sigma,trials=len(r),delivered=k,delivery_fraction=k/len(r),delivery_wilson95=wilson(k,len(r)),frame_energy=r[0]['normalized_frame_energy']))
    report=dict(completed=True,version=VERSION_HEX,protocol=PROTOCOL,groups=groups,rows=rows,memory=memory,
        scope='One-tap zero-CFO AWGN fixture; includes all preamble energy; coded duration is longer. Descriptive sample evidence, no universal coding-gain or superiority assertion.',
        symbol_counts=dict(preamble=542,raw_payload=784,coded_payload=4752),images={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'ready').iterdir() if p.is_file()})
    (out/'report.json').write_text(json.dumps(report,indent=2));print('FEC_ENERGY_STUDY_COMPLETED',out,flush=True)

if __name__=='__main__':run(sys.argv[1])
