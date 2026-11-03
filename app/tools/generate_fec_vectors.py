"""Independent numpy reference produces ROMs and noisy soft-input RTL vectors."""
import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'reference'))
from fec_probe import permutation,scramble,conv,turbo,unturbo,viterbi
def mem(path,values,width):
    path.write_text(''.join(f'{int(v)&((1<<width)-1):0{(width+3)//4}x}\n' for v in values))
def main():
    out=ROOT/'results/fec_vectors';out.mkdir(parents=True,exist_ok=True)
    rows=[];rng=np.random.default_rng(417)
    for kind,length,seed in [('data',784,2026100901),('ack',112,2026100902)]:
        n=2*(length+6);pi=permutation(n,seed);inv=np.argsort(pi)
        mem(ROOT/f'rtl/turbo_{kind}.mem',pi,11);mem(ROOT/f'rtl/turbo_{kind}_inv.mem',inv,11)
        ext=np.array([(j%8)*(length//8)+j//8 for j in range(length)])
        for pattern in range(4):
            bits=[np.zeros(length,dtype=int),np.ones(length,dtype=int),np.arange(length)%2,rng.integers(0,2,length)][pattern]
            encoded=turbo(conv(scramble(bits)[ext]),pi)
            for noisy in range(2):
                llr=np.clip(np.rint(32*(1-2*encoded.astype(float)+(rng.normal(0,.7,len(encoded)) if noisy else 0))),-127,127).astype(int)
                soft=unturbo(llr,pi,2);v=viterbi(soft);restored=np.empty(length,dtype=int);restored[ext]=v;decoded=scramble(restored)
                assert np.array_equal(decoded,bits)
                case=len(rows);mem(out/f'in_{case}.mem',bits,1);mem(out/f'coded_{case}.mem',encoded,1);mem(out/f'llr_{case}.mem',llr,8)
                rows.append(dict(case=case,ack=kind=='ack',pattern=pattern,input_bits=length,coded_bits=len(encoded),hard_errors=int(np.sum((llr<0)!=encoded)),reference_errors=0))
    (out/'vectors.json').write_text(json.dumps(rows,indent=2));print(out)
if __name__=='__main__':main()
