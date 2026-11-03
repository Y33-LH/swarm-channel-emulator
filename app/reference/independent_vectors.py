"""Floating-point waveform from B contract. RX testbench has no TX module.
The only reference passed to the receiver is sampled I/Q and its test window.
Expected bytes are used solely by the external assertion monitor.
"""
import binascii, cmath, json, math, random, struct
from pathlib import Path
from generate_preamble import pn
ROOT=Path(__file__).resolve().parents[1]
def bits(b):return [(v>>i)&1 for v in b for i in range(7,-1,-1)]
def waveform(body, offset, phase, sigma, seed, kind='data'):
    short=pn(7,[0,3]);train=pn(8,[0,4,5,6])
    pre=short*2+train+bits(bytes.fromhex('d391c5a7'))+[0]
    if kind=='bad_sfd':pre[509:541]=[0]*32
    if kind=='bad_pn':pre[:254]=[0]*254
    seq=[1-2*b for b in pre];last=1
    for b in bits(body+binascii.crc_hqx(body,0xffff).to_bytes(2,'big')):
        last*=1-2*b;seq.append(last)
    signal=[0]*offset+[v for v in seq for _ in range(4)]
    r=random.Random(seed);rotation=cmath.exp(1j*phase)
    out=[]
    for n in range(8192):
        v=0 if kind=='noise' or n>=len(signal) else 8192*signal[n]*rotation
        sample=complex(v)+complex(r.gauss(0,sigma),r.gauss(0,sigma))
        out.append(complex(max(-32768,min(32767,round(sample.real))),max(-32768,min(32767,round(sample.imag)))))
    return out
def scan(samples):
    # Batch correlation over every sample-phase candidate, independent of RTL FSM.
    p=pn(7,[0,3]);target=[a^b for a,b in zip(p,p[1:])]
    pre=p*2+pn(8,[0,4,5,6])+bits(bytes.fromhex('d391c5a7'))+[0]
    for phase in range(4):
        v=samples[phase::4]
        ds=[int((v[i]*v[i-1].conjugate()).real<0) for i in range(1,len(v))]
        for first in range(len(v)-1326):
            if sum(a!=b for a,b in zip(ds[first:first+126],target))>4:continue
            if not all(abs(v[i])>0 for i in (first+125,first+126)):continue
            diffs=ds[first+126:first+541]
            exp=[pre[i]^pre[i-1] for i in range(127,542)]
            if sum(a!=b for a,b in zip(diffs,exp))>16:continue
            if sum(a!=b for a,b in zip(diffs[382:414],exp[382:414]))>2:continue
            if diffs[-1]!=exp[-1]:continue
            data=ds[first+541:first+1325]
            return bytes(sum(data[i+j]<<(7-j) for j in range(8)) for i in range(0,784,8))
    return None
def main():
    out=ROOT/'reference';cases=[];expected=[]
    words=(out/'receiver_vectors.mem').open('w',encoding='ascii')
    for c in range(24):
        kind='data' if c<16 else 'noise' if c<20 else 'bad_sfd' if c<22 else 'bad_pn'
        r=random.Random(20261011+c);data=bytes(r.randrange(256) for _ in range(64))
        body=struct.pack('<BBBBBBBBIIHHQHBB',1,1,0,5,1,0,1,2,14,c,0,1,123,64,0,0)+data
        wire=body+binascii.crc_hqx(body,0xffff).to_bytes(2,'big');expected.extend(wire)
        offset=128+c*31;phase=c*.317;sigma=(c%4)*150 if kind=='data' else 1024
        samples=waveform(body,offset,phase,sigma,20261011+c,kind)
        rx=scan(samples)
        assert (rx==wire) if kind=='data' else rx is None,(c,kind,rx)
        for v in samples:words.write(f'{((int(v.imag)&65535)<<16)|(int(v.real)&65535):08x}\n')
        cases.append({'case':c,'kind':kind,'offset_samples':offset,'phase_radians':phase,'sigma':sigma,'captured':rx is not None,'matched':rx==wire})
    words.close();(out/'receiver_expected.mem').write_text(''.join(f'{v:02x}\n' for v in expected),encoding='ascii')
    (out/'reference_results.json').write_text(json.dumps({'pass':True,'cases':cases},indent=2),encoding='utf-8')
    print('INDEPENDENT_REFERENCE_PASS cases=24')
if __name__=='__main__':main()
