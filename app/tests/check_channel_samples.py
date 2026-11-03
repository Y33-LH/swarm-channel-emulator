"""Independent integer channel oracle plus distribution/restart checks."""
from pathlib import Path
import sys,json,hashlib,math
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
out=Path(sys.argv[1]);cases={}
names='gain echo_gain sigma phase step seed delay echo_delay echo_phase echo_step ramp echo_ramp suppress'.split()
for line in (out/'channel_samples.txt').open():
    a=line.split();c=int(a[1])
    if a[0]=='C':cases[c]=dict(cfg=dict(zip(names,map(int,a[2:]))),source=[],received=[],taps=[])
    elif a[0]=='M':cases[c]['taps'].append(dict(zip(('gain','delay','phase','step','ramp'),map(int,a[3:]))))
    elif a[0]=='S':
        assert int(a[2])==len(cases[c]['source']);cases[c]['source'].append(int(a[3]))
    else:
        assert a[0]=='Y' and int(a[2])==len(cases[c]['received']);cases[c]['received'].append(tuple(map(int,a[3:])))
def memory(name,width):
    values=[int(s,16) for s in (ROOT/'rtl'/name).read_text().split()]
    return [v-(1<<width) if v&(1<<(width-1)) else v for v in values]
gauss=memory('gaussian_q12.mem',16);sine=memory('sine_q15.mem',17)
def nxt(x):
    x^=(x<<13)&0xffffffff;x^=x>>17;x^=(x<<5)&0xffffffff;return x&0xffffffff
results=[]
for cid,row in cases.items():
    c=row['cfg'];src=row['source'];actual=row['received'];rng=c['seed'];clipped=0
    taps=row['taps'] or [dict(gain=c['gain'],delay=c['delay'],phase=c['phase'],step=c['step'],ramp=c['ramp']),dict(gain=c['echo_gain'],delay=c['delay']+c['echo_delay'],phase=c['echo_phase'],step=c['echo_step'],ramp=c['echo_ramp'])]
    phases=[t['phase'] for t in taps];gains=[t['gain']<<16 for t in taps]
    assert len(src)==len(actual)==50000
    for n,(ii,qq) in enumerate(actual):
        r2=nxt(rng);ri=gauss[rng>>20]*c['sigma']>>12;rq=gauss[r2>>20]*c['sigma']>>12
        for j,t in enumerate(taps):
            x=(src[n-t['delay']] if n>=t['delay'] else 0)*(gains[j]>>16)>>15;p=(phases[j]>>24)&255
            ri+=x*sine[(p+64)&255]>>15;rq+=x*sine[p]>>15
            phases[j]=(phases[j]+t['step'])&0xffffffff;gains[j]=min(0x80000000,max(0,gains[j]+t['ramp']))
        clipped+=int(ri>32767 or ri< -32768 or rq>32767 or rq< -32768)
        expected=(max(-32768,min(32767,ri)),max(-32768,min(32767,rq)))
        assert (ii,qq)==expected,(cid,n,(ii,qq),expected)
        rng=nxt(r2)
    results.append(dict(case=cid,parameters=c,taps=taps,samples=len(actual),max_error_lsb=0,clipped_samples=clipped))
assert cases[2]['received']==cases[6]['received']==cases[7]['received'],'Restart/backpressure changed waveform'
assert cases[11]['received']==cases[12]['received'],'8-tap backpressure changed waveform'
assert results[5]['clipped_samples']>0
noise=np.concatenate([np.asarray(cases[i]['received'],float) for i in (4,8,9)])/1500
means=noise.mean(axis=0);variances=noise.var(axis=0);corr=float(np.corrcoef(noise.T)[0,1]);lag=float(np.corrcoef(noise[:-1,0],noise[1:,0])[0,1])
assert max(abs(means))<.015 and max(abs(variances-1))<.025 and abs(corr)<.015 and abs(lag)<.015
grid=np.linspace(-4,4,161);cdf_error=max(abs(float((noise[:,0]<=x).mean())-(1+math.erf(x/math.sqrt(2)))/2) for x in grid)
assert cdf_error<.012
report=dict(pass_channel=True,source='RTL sample stream versus independent integer oracle',cases=results,samples=sum(r['samples'] for r in results),max_error_lsb=0,reset_isolation=True,stall_invariance=True,noise=dict(complex_samples=len(noise),means_sigma=means.tolist(),variances_sigma2=variances.tolist(),iq_correlation=corr,lag1_correlation=lag,cdf_grid_max_error=cdf_error),
    scope='Quantized finite-table Gaussian AWGN; legacy two paths and selectable 1/3/8 independent delayed/rotated/ramped taps; 1023 sample delay; bounded saturation. RX readiness bypassed only in this channel unit harness.',
    rtl_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'rtl').glob('*') if p.is_file()})
(out/'acceptance.json').write_text(json.dumps(report,indent=2));print('CHANNEL_REFERENCE_PASS',out,report['samples'],report['noise'])
