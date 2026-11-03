"""Independent float waveform generator. Only sampled IQ enters the RTL RX."""
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'reference'))
from fec_probe import permutation,scramble,conv,turbo
def main():
 out=ROOT/'results/phy_vectors';out.mkdir(parents=True,exist_ok=True)
 pre=np.array(json.loads((ROOT/'reference/preamble.json').read_text())['preamble'])
 rng=np.random.default_rng(743);bits=rng.integers(0,2,784);ext=np.array([(j%8)*98+j//8 for j in range(784)])
 encoded=turbo(conv(scramble(bits)[ext]),permutation(1580,2026100901))
 symbols=np.r_[1-2*pre,np.cumprod(1-2*encoded.astype(int))]
 base=np.r_[np.zeros(151),np.repeat(symbols,4)*8192,np.zeros(3000)]
 rows=[]
 settings=[(0,0,0,0,1,0),(5000,0,0,0,.7,.8),(-6000,0,0,0,.6,-1.3),(500,0,.18,350,.75,1.1),(1000,200,0,200,.8,.7),(-1500,-200,.12,200,.8,-.9)]
 for c,(cfo,ppm,echo,sigma,gain,phase) in enumerate(settings):
  t=np.arange(26000)*(1+ppm*1e-6)
  tx=np.interp(t,np.arange(len(base)),base,left=0,right=0)
  delayed=np.interp(t-8,np.arange(len(base)),base,left=0,right=0)
  wave=(gain*tx+echo*np.exp(1j*.9)*delayed)*np.exp(1j*(phase+2*np.pi*cfo*np.arange(26000)/8e6))
  wave+=sigma*(rng.normal(size=26000)+1j*rng.normal(size=26000))
  ii=np.clip(np.rint(wave.real),-32768,32767).astype(int);qq=np.clip(np.rint(wave.imag),-32768,32767).astype(int)
  (out/f'iq_{c}.mem').write_text(''.join(f'{((int(q)&65535)<<16)|(int(i)&65535):08x}\n' for i,q in zip(ii,qq)))
  rows.append(dict(case=c,cfo_hz=cfo,sample_clock_ppm=ppm,echo_gain=echo,sigma=sigma,gain=gain,initial_phase=phase))
 (out/'bits.mem').write_text(''.join(f'{b:x}\n' for b in bits));(out/'coded.mem').write_text(''.join(f'{b:x}\n' for b in encoded));(out/'vectors.json').write_text(json.dumps(rows,indent=2));print(out)
if __name__=='__main__':main()
