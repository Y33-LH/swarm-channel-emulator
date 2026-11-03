"""Predeclared paired physical-board study at equal total-frame energy/payload bit.

Includes preamble, framing and coding overhead; halves BOTH signal and noise
to preserve headroom. Reports failures, clipping and uncertainty. No retries.
"""
import sys,json,math,time,random,hashlib,binascii
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps'),str(ROOT/'tests')]
from firmware_contract import VERSION,PROTOCOL,BUILD
from serial_json import JsonSerial
from acceptance import frame
import serial

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def interval(k,n):
    z=1.959963984540054;p=k/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,mid-half),min(1,mid+half)]
def main(port):
    out=ROOT/'results'/time.strftime('fair_payload_energy_%Y%m%d_%H%M%S');out.mkdir()
    rng=random.Random(20261101);seeds=rng.sample(range(1,2**32),200)
    symbols={0:1326,1:5294};amplitude=4096;ebdb=16
    sigma={f:round(math.sqrt(amplitude**2*4*symbols[f]/(2*512*10**(ebdb/10)))) for f in (0,1)}
    images={p:sha(ROOT/'ready'/p) for p in ('system_wrapper.bit','swarm_app.elf','ps7_init.tcl')}
    plan=dict(seeds=seeds,payload_bits=512,signal_amplitude=amplitude,frame_symbols=symbols,samples_per_symbol=4,
        payload_ebn0_db=ebdb,sigma_iq=sigma,images=images,retries=0,paired_same_payload_seed=True,
        scope='One AWGN + fixed phase/delay operating point; total frame energy includes synchronization and CRC/coding. Not a whole-link or arbitrary fading claim.')
    (out/'plan.json').write_text(json.dumps(plan,indent=2));rows=[];start=time.monotonic()
    with serial.Serial(port,230400,timeout=.2,write_timeout=5) as s,(out/'uart.jsonl').open('w') as log:
        s.reset_input_buffer();client=JsonSerial(s)
        def cmd(t):
            r=client.request(t,20);log.write(json.dumps(dict(command=t,response=r))+'\n');log.flush();return r
        def good(t):
            r=cmd(t);assert r.get('ok')==1,(t,r);return r
        ping=good('PING');assert (ping['version'],ping['protocol'],ping['arm_build'])==(VERSION,PROTOCOL,BUILD)
        good('NETSTOP');good('RELEASE');good('WRITE 796 0')
        common={12:0,48:1000000,64:16384,72:0,80:37,84:round(.23*2**32),92:0,96:0,112:53,116:0,120:0,124:0,128:0,132:0,136:0,140:0,776:0}
        for a,v in common.items():good(f'WRITE {a} {v}')
        for a,v in common.items():assert good(f'READ {a}')['value']==v
        for k,seed in enumerate(seeds):
            tx=frame(hashlib.sha512(f'paired-headroom-{k}'.encode()).digest(),50000+k);pair={}
            for fec in ((0,1) if k%2==0 else (1,0)):
                good('RELEASE')
                for a,v in {68:sigma[fec],88:seed,192:fec}.items():
                    good(f'WRITE {a} {v}');assert good(f'READ {a}')['value']==v
                good(f'LOAD {50000+k} {tx.hex()}');good('START');deadline=time.monotonic()+5
                while not good('STATUS')['status']&2:assert time.monotonic()<deadline
                r=cmd('RESULT');p=good('PHYSTATS');clipped=good('READ 156')['value'];ok=r.get('ok')==1
                if ok:assert bytes.fromhex(r['rx_hex'])==tx and r['crc_calc']==r['crc_recv']==binascii.crc_hqx(tx,65535)
                else:assert not r['rx_hex']
                pair[fec]=dict(delivered=ok,clipped=clipped,phy=p,result_code=r.get('result_code'),cycles=r['cycles'])
            rows.append(dict(index=k,seed=seed,tx_sha256=hashlib.sha256(tx).hexdigest(),modes=pair))
            if (k+1)%20==0:print('PAIRED_ENERGY',k+1,[sum(x['modes'][f]['delivered'] for x in rows) for f in (0,1)],flush=True)
        good('RELEASE')
    summary={f:dict(delivered=sum(x['modes'][f]['delivered'] for x in rows),trials=len(rows),clipped=sum(x['modes'][f]['clipped'] for x in rows)) for f in (0,1)}
    for x in summary.values():x['confidence95_wilson']=interval(x['delivered'],x['trials'])
    wins=sum(x['modes'][1]['delivered'] and not x['modes'][0]['delivered'] for x in rows)
    losses=sum(x['modes'][0]['delivered'] and not x['modes'][1]['delivered'] for x in rows)
    discordant=wins+losses;p=min(1,2*sum(math.comb(discordant,j) for j in range(min(wins,losses)+1))/2**discordant) if discordant else 1
    no_clipping=not any(x['clipped'] for x in summary.values())
    report=dict(complete=True,images=images,arm_build=BUILD,plan=plan,summary=summary,paired_wins=wins,paired_losses=losses,
        exact_paired_two_sided_p=p,no_clipping=no_clipping,
        coding_benefit_at_tested_point=bool(no_clipping and wins>losses and p<.05),
        source='physical_FPGA_RX_UART',wall_s=time.monotonic()-start,rows=rows)
    assert images=={p:sha(ROOT/'ready'/p) for p in images}
    (out/'acceptance.json').write_text(json.dumps(report,indent=2));print('PAIRED_ENERGY_COMPLETE',out,summary,'p=',p,flush=True)
if __name__=='__main__':main(sys.argv[1])
