"""Reference waveform occupied bandwidth; never mislabel as an RF measurement."""
from pathlib import Path
import numpy as np,json
ROOT=Path(__file__).resolve().parents[1]
rng=np.random.default_rng(20261013);bits=rng.integers(0,2,131072);symbols=np.cumprod(1-2*bits);wave=np.repeat(symbols,4).astype(float)
nfft=4096;segments=wave[:len(wave)//nfft*nfft].reshape(-1,nfft);window=np.hanning(nfft)
psd=np.mean(abs(np.fft.fft(segments*window,axis=1))**2,axis=0);psd=np.fft.fftshift(psd);f=np.fft.fftshift(np.fft.fftfreq(nfft,1/8e6))
order=np.argsort(abs(f));cumulative=np.cumsum(psd[order])/psd.sum()
bw={str(percent):float(2*abs(f[order[np.searchsorted(cumulative,percent/100)]])) for percent in (90,95,99)}
delay=np.arange(0,4.0001,.5);ripple=[]
for us in delay:
 h=1+.4*np.exp(-2j*np.pi*f*us*1e-6);power=20*np.log10(abs(h));inside=abs(f)<=2e6
 ripple.append(dict(echo_delay_us=float(us),relative_to_symbol_time=float(us/.5),ripple_mainlobe_db=float(power[inside].max()-power[inside].min())))
report=dict(source='independent_reference_not_RF_or_ADC_measurement',sample_rate_hz=8000000,symbol_rate_hz=2000000,pulse='rectangular_4_samples',mainlobe_null_to_null_hz=4000000,occupied_bandwidth_hz=bw,window='Hann 4096-point Welch segments',n_symbols=len(symbols),sample_stream_hardware_realtime_claim=False,two_path_frequency_selectivity=ripple)
(ROOT/'results/bandwidth_reference.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)
