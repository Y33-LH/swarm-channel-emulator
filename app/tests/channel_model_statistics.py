"""Statistical qualification of the coefficient generator, not receiver claims."""
import sys,math,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'reference')]
import numpy as np
from channel_model import scatter,unit,rain_attenuation
from channel_config import validate,encode,wire_id

def run():
 rows=[];N=16384;time=np.arange(N)*.0137
 z=[]
 for tap in range(4):
  wave=np.zeros(N,dtype=complex)
  for m in range(32):
   key=7*256+tap*32+m;w=2*np.pi*3.7*np.cos(2*np.pi*(m+unit(20261101,key,'angle'))/32)
   wave+=np.exp(1j*(w*time+2*np.pi*unit(20261101,key,'scatter')))/np.sqrt(32)
  z.append(wave)
 z=np.asarray(z)
 # Ensemble/time CDF, not a favorable selected seed/frame.
 x=np.abs(z.ravel())**2;grid=np.linspace(0,6,121)
 cdf=max(abs(np.mean(x<=v)-(1-np.exp(-v))) for v in grid)
 cross=max(abs(np.mean(z[a]*np.conj(z[b]))) for a in range(4) for b in range(a))
 assert abs(np.mean(x)-1)<.08 and cdf<.04 and cross<.12,(np.mean(x),cdf,cross)
 # Rician normalized mean and variance at 10 dB; theoretical var |h|²=(1+2K)/(1+K)².
 K=10.;rice=z/math.sqrt(1+K)+math.sqrt(K/(1+K));p=np.abs(rice)**2
 assert abs(np.mean(p)-1)<.05 and abs(np.var(p)-(1+2*K)/(1+K)**2)<.035
 # The same scalar reference must agree with independent vectorized generation.
 for tap in range(4):
  for i in (0,71,1001,N-1):
   a,ph,_,_=scatter(7,tap,float(time[i]),20261101,3.7,1,0)
   assert abs(a*np.exp(1j*ph)-z[tap,i])<1e-10
 # Test bounded frame-linear coefficient approximation independently.
 # Measure absolute error relative to unit expected channel power, not deep-null
 # relative error; retain the maximum and upper quantiles without hiding nulls.
 errs=[]
 for seed in range(1,2001):
  for model,K in ((1,0),(2,10)):
   a,ph,s,f=scatter(0,0,.314,seed,5.,model,K)
   ae,pe,_,_=scatter(0,0,.314+.0028,seed,5.,model,K)
   approx=max(0,a+s*.0028)*np.exp(1j*(ph+2*np.pi*f*.0028))
   errs.append(abs(approx-ae*np.exp(1j*pe)))
 # Deep fades can make local polar linearization inaccurate; never hide this.
 report=dict(scope='Coefficient model only; FPGA fixed-point and receiver gates are separate',samples=int(x.size),rayleigh=dict(mean_power=float(np.mean(x)),cdf_max=float(cdf),cross_correlation_max=float(cross)),rician=dict(k_linear=10,mean_power=float(np.mean(p)),power_variance=float(np.var(p))),frame_linear_approximation=dict(fd_hz=5,duration_ms=2.8,samples=len(errs),max_abs_error=float(max(errs)),p99_abs_error=float(np.quantile(errs,.99)),fraction_above_005=float(np.mean(np.array(errs)>.05))))
 assert report['frame_linear_approximation']['p99_abs_error']<.03,report
 # Published P.838-3 table values at 1,2,6 GHz, vertical polarization.
 for f,k,a in ((1,.0000308,.8592),(2,.0000998,.9490),(6,.0004878,1.5728)):
  expected=k*50**a;actual=rain_attenuation(f,50);assert abs(actual/expected-1)<.004,(f,actual,expected)
 validate();assert len(encode())==192
 out=ROOT/'results/channel_model_statistics.json';out.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));return report
if __name__=='__main__':run()
