"""Derive instruments only from one captured FPGA DATA frame.

The snapshot's cumulative counters can cover many frames; never merge them
into this record. Register readback is distinct from receiver estimation.
"""
import math

def coherent_observation(snapshot,record_id=None):
    o=snapshot.get('observation')
    if not o:return None
    a,p,m=o.get('applied'),o.get('phy'),o.get('meta')
    if not (isinstance(a,list) and len(a)==15 and isinstance(p,list) and len(p)==12 and isinstance(m,list) and len(m)==16):
        raise ValueError('Incomplete coherent observation')
    link=o.get('link');iq=o.get('iq',[])
    if not isinstance(link,int) or not 0<=link<32:raise ValueError('Invalid observation link')
    if not a[0] or not p[0] or a[1]!=p[1] or a[2]!=0 or p[2]!=0 or p[3]!=m[15]:
        raise ValueError('Observation frame/channel identity mismatch')
    if not 0<=a[1]<=snapshot['round']*100:raise ValueError('Observation is outside snapshot time')
    if len(iq)>64 or any(not isinstance(pair,list) or len(pair)!=2 or any(not isinstance(w,int) or not 0<=w<2**32 for w in pair) for pair in iq):raise ValueError('Invalid observation IQ shape')
    wave=o.get('wave_samples',[])
    if not isinstance(wave,list) or len(wave)>128 or any(not isinstance(w,int) or not 0<=w<2**32 for w in wave):raise ValueError('Invalid continuous waveform')
    if wave and (not isinstance(o.get('wave_start_sample'),int) or not 0<=o['wave_start_sample']<=32768-len(wave)):raise ValueError('Invalid waveform offset')
    signed=lambda v:v-(1<<32) if v>=(1<<31) else v
    fs=o.get('sample_rate_hz',8000000)
    if fs not in (8000000,16000000):raise ValueError('Unsupported observation sample rate')
    if snapshot.get('protocol',0)>=21 and (o.get('channel_id')!=snapshot.get('channel_id') or fs!=snapshot.get('sample_rate_hz')):
        raise ValueError('Observation channel configuration identity mismatch')
    raw_taps=o.get('taps',[])
    if not isinstance(raw_taps,list) or len(raw_taps)>8 or any(not isinstance(t,list) or len(t)!=5 or any(type(v)is not int or not 0<=v<2**32 for v in t) for t in raw_taps):
        raise ValueError('Invalid tap readback')
    if raw_taps:
        if any(t[0]>32768 or t[1]>1023 for t in raw_taps):raise ValueError('Tap readback outside FPGA range')
        taps=[dict(gain=t[0]/32768,delay_samples=t[1],phase_radians=t[2]*math.tau/2**32,cfo_hz=signed(t[3])*fs/2**32,gain_slope_per_s=signed(t[4])*fs/2**31) for t in raw_taps]
    else:
        taps=[dict(gain=a[3]/32768,delay_samples=a[6],phase_radians=a[8]*math.tau/2**32,cfo_hz=signed(a[10])*fs/2**32,gain_slope_per_s=0),dict(gain=a[4]/32768,delay_samples=a[6]+a[7],phase_radians=a[9]*math.tau/2**32,cfo_hz=signed(a[11])*fs/2**32,gain_slope_per_s=0)]
    def unpack(w):
        lo=w&65535;hi=(w>>16)&65535
        return [lo-65536 if lo>=32768 else lo,hi-65536 if hi>=32768 else hi]
    tx=link%16+1;rx=tx+1 if tx%4 else 0
    if link>=16:tx,rx=rx,tx
    ident=dict(record_id=record_id,run_id=snapshot['run_id'],config_id=snapshot['config_id'],
        protocol=snapshot.get('protocol'),channel_id=o.get('channel_id'),sample_rate_hz=fs,link_id=link,tx=tx,rx=rx,model_ms=a[1],generation=m[15],waveform='DATA')
    statistics=o.get('statistics') or {}
    model_meta=o.get('model_metadata')
    if model_meta is not None and (not isinstance(model_meta,list) or len(model_meta)!=6 or any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in model_meta)):
        raise ValueError('Invalid ARM model metadata')
    n=statistics.get('evm_symbols',0)
    terrain=o.get('terrain')
    scale=o.get('digital_scale',1.)
    if not isinstance(scale,(int,float)) or not math.isfinite(scale) or not 0<scale<=1:raise ValueError('Invalid digital scale')
    if terrain is not None and (not isinstance(terrain,list) or len(terrain)!=7 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in terrain)):
        raise ValueError('Invalid same-frame terrain provenance')
    return dict(**ident,received=[unpack(pair[0]) for pair in iq],equalized=[unpack(pair[1]) for pair in iq],
        captured=bool(p[4]),crc_good=bool(m[7]&4),frame_status=m[7],result_code=m[8],condition_id=m[0],
        channel=dict(applied=True,reference='SAME_FRAME_FPGA_REGISTER_READBACK',**ident,
            taps=taps,coefficient_limited=o.get('coefficient_limited',0),terrain=terrain,digital_scale=scale,
            model_metadata=model_meta,model_metadata_source='ARM_MODEL_NOT_RX_ESTIMATE' if model_meta else None,
            gain0=a[3]/32768,gain1=a[4]/32768,sigma=a[5],delay_samples=a[6],echo_delay_samples=a[7],
            phase_radians=a[8]*math.tau/(1<<32),echo_phase_radians=a[9]*math.tau/(1<<32),
            cfo_hz=signed(a[10])*fs/(1<<32),echo_cfo_hz=signed(a[11])*fs/(1<<32),distance_m=a[14]/1000),
        cfo_hz=signed(p[5])*fs/(1<<32) if p[9] else None,timing_updates=p[9],
        pre_errors=m[9],pre_bits=m[10],post_errors=m[11],post_bits=m[12],
        pre_ber=m[9]/m[10] if p[4] and m[10] else None,post_ber=m[11]/m[12] if p[4] and m[12] else None,
        evm_percent=100*math.sqrt(statistics['evm_energy']/(n*8192**2)) if n and p[4] else None,
        decode_cycles=statistics.get('decode_cycles'),iterations=statistics.get('iterations'),clipping=statistics.get('clipping'),
        waveform_samples=dict(received=[unpack(w) for w in o.get('wave_samples',[])],start_sample=o.get('wave_start_sample'),sample_rate_hz=fs,samples_per_symbol=4),
        source='COHERENT_FPGA_DATA_FRAME',age_ms=snapshot['round']*100-a[1])
