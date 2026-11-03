"""B-v1 software-only FEC feasibility probe. NOT the running FPGA profile.
Exact agreed trellises; Max-Log-MAP soft output feeds terminated soft Viterbi.
The test injects AWGN into coded-bit LLRs, not a DBPSK waveform/channel claim.
"""
import json,math,hashlib,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]

def permutation(n,seed):
    p=list(range(n));state=seed
    for i in range(n-1,0,-1):
        state=(1664525*state+1013904223)&0xffffffff;j=state%(i+1);p[i],p[j]=p[j],p[i]
    return np.array(p)
def scramble(bits):
    s=511;out=[]
    for b in bits:out.append(int(b)^(s&1));s=(s>>1)|(((s^(s>>5))&1)<<8)
    return np.array(out,dtype=np.int8)
def conv(bits):
    state=0;out=[]
    for b in list(bits)+[0]*6:
        q=(int(b)<<6)|state;out.extend(((q&0o171).bit_count()%2,(q&0o133).bit_count()%2));state=q>>1
    assert state==0;return np.array(out,dtype=np.int8)
def viterbi(llr):
    nxt=np.arange(64);u=nxt>>5;prev=((nxt&31)<<1)[:,None]+np.arange(2)
    q=(u[:,None]<<6)|prev
    # Parentheses keep parity in {0,1} before sign mapping.
    signs=np.array([[[1-2*((int(v)&g).bit_count()%2) for g in (0o171,0o133)] for v in row] for row in q])
    m=np.full(64,-1e20);m[0]=0;trace=[]
    for pair in np.asarray(llr).reshape(-1,2):
        candidate=m[prev]+.5*np.sum(signs*pair,axis=2);pick=candidate.argmax(axis=1);m=candidate[nxt,pick];m-=m.max();trace.append(prev[nxt,pick])
    state=0;decoded=[]
    for row in reversed(trace):decoded.append(state>>5);state=int(row[state])
    assert state==0;return np.array(decoded[::-1][:-6],dtype=np.int8)
def rsc(bits):
    state=0;parity=[]
    for u in bits:
        v=int(u)^((state>>1)&1)^(state&1);parity.append(v^((state>>2)&1)^(state&1));state=(v<<2)|(state>>1)
    tail=[]
    for _ in range(3):
        u=((state>>1)&1)^(state&1);p=((state>>2)&1)^(state&1);tail.extend((u,p));state>>=1
    assert state==0;return np.array(parity,dtype=np.int8),np.array(tail,dtype=np.int8)
def turbo(bits,pi):
    p1,t1=rsc(bits);p2,t2=rsc(bits[pi]);return np.concatenate((np.stack((bits,p1,p2),axis=1).ravel(),t1,t2))

STATES=np.arange(8);INPUT=np.arange(2)
NEXT=np.empty((8,2),dtype=int);PARITY=np.empty((8,2),dtype=int)
for state in range(8):
    for u in range(2):
        v=u^((state>>1)&1)^(state&1);NEXT[state,u]=(v<<2)|(state>>1);PARITY[state,u]=v^((state>>2)&1)^(state&1)
def siso(systematic,parity,apriori):
    n=len(systematic);gamma=.5*((1-2*INPUT)[None,None,:]*(systematic+apriori)[:,None,None]+(1-2*PARITY)[None,:,:]*parity[:,None,None])
    alpha=np.full((n+1,8),-1e20);alpha[0,0]=0
    for k in range(n):
        np.maximum.at(alpha[k+1],NEXT.ravel(),(alpha[k,:,None]+gamma[k]).ravel());alpha[k+1]-=alpha[k+1].max()
    beta=np.full(8,-1e20);beta[0]=0;app=np.empty(n)
    for k in range(n-1,-1,-1):
        branch=gamma[k]+beta[NEXT];metrics=alpha[k,:,None]+branch;app[k]=metrics[:,0].max()-metrics[:,1].max();beta=branch.max(axis=1);beta-=beta.max()
    return app,app-systematic-apriori
def unturbo(llr,pi,iterations=2):
    n=len(pi);body=np.asarray(llr[:n*3]).reshape(n,3);tail1=np.asarray(llr[n*3:n*3+6]).reshape(3,2);tail2=np.asarray(llr[n*3+6:]).reshape(3,2)
    sys1=np.r_[body[:,0],tail1[:,0]];par1=np.r_[body[:,1],tail1[:,1]];sys2=np.r_[body[pi,0],tail2[:,0]];par2=np.r_[body[:,2],tail2[:,1]];prior=np.zeros(n)
    for _ in range(iterations):
        _,ext1=siso(sys1,par1,np.r_[prior,np.zeros(3)])
        app2,ext2=siso(sys2,par2,np.r_[.75*ext1[:n][pi],np.zeros(3)])
        prior=np.empty(n);prior[pi]=.75*ext2[:n]
    result=np.empty(n);result[pi]=app2[:n];return result
def main():
    rng=np.random.default_rng(20261011);rows=[];start=time.monotonic()
    for length,seed in ((784,2026100901),(112,2026100902)):
        ext=np.array([(j%8)*(length//8)+j//8 for j in range(length)]);pi=permutation(2*(length+6),seed)
        for pattern in range(4):
            bits=np.zeros(length,dtype=np.int8) if pattern==0 else np.ones(length,dtype=np.int8) if pattern==1 else np.arange(length,dtype=np.int8)%2 if pattern==2 else rng.integers(0,2,length,dtype=np.int8)
            c=conv(scramble(bits)[ext]);encoded=turbo(c,pi)
            for sigma in (0,.65):
                y=1-2*encoded.astype(float)+(rng.normal(0,sigma,len(encoded)) if sigma else 0);llr=2*y/(sigma*sigma if sigma else .1)
                soft=unturbo(llr,pi,2);v=viterbi(soft);restored=np.empty(length,dtype=np.int8);restored[ext]=v;decoded=scramble(restored)
                errors=int(np.sum(decoded!=bits));assert errors==0,(length,pattern,sigma,errors)
                rows.append({'input_bits':length,'encoded_bits':len(encoded),'pattern':pattern,'llr_awgn_sigma':sigma,'coded_hard_errors':int(np.sum((llr<0)!=encoded)),'decoded_errors':errors,'iterations':2})
    report={'pass':True,'scope':'software-only FEC feasibility, no FPGA FEC claim','cases':rows,'elapsed_s':time.monotonic()-start,'data_coded_bits':4752,'ack_coded_bits':720,'waveform_samples_data_with_preamble':21176,'current_fpga_window_samples':8192,'must_expand_window':True,'airtime_data_plus_ack_us':(5294+1262)/2,'must_parallelize_trellis_states':True,'additional_validation':['Independent implementation comparison','Fixed-point saturation/normalization','BER/FER vs Eb/N0 with DBPSK soft demapper','FPGA resource/timing and end-to-end slot deadline']}
    out=ROOT/'results/fec_probe.json';out.write_text(json.dumps(report,indent=2));print('FEC_SOFTWARE_PROBE_PASS cases='+str(len(rows))+' evidence='+str(out))
if __name__=='__main__':main()
