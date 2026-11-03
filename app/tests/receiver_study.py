"""Measured frame/capture/BER boundaries and energy-declared FEC comparisons.
No reconstructed TX bits enter RX results. Failed captures remain in denominator.
"""
import json,sys,time,math,hashlib,argparse,binascii
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps'),str(ROOT/'tests')]
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX,BUILD
import serial
from serial_json import JsonSerial
from acceptance import frame

def run(port='COM4',out=None):
 out=Path(out) if out else ROOT/'results'/time.strftime('receiver_study_%Y%m%d_%H%M%S')
 out.mkdir(parents=True,exist_ok=True);rows=[]
 configs=[dict(name='cfo_'+str(f),fec=1,cfo=f,gain=.6,sigma=300) for f in (-7000,-6000,-4000,0,4000,6000,7000)]
 configs += [dict(name='delay_'+str(d),fec=1,delay=d,echo=.12,echo_delay=32,sigma=500,cfo=500) for d in (0,128,256,512)]
 configs += [dict(name='low_gain_'+str(g),fec=1,gain=g,sigma=200,echo=g*.2,echo_delay=8,cfo=-220) for g in (.4,.2,.1,.05)]
 # Equal received Es/N0: same amplitude, sample count per symbol and noise.
 for snr in (18,12,9,6,3,0):
  sigma=round(8192/math.sqrt(2*10**(snr/10)))
  for fec in (0,1):configs.append(dict(name=f'es_comparison_{snr}_{fec}',comparison='equal_complex_sample_snr',sample_snr_db=snr,fec=fec,sigma=sigma))
 # Equal information Eb/N0, including 784 protected bits; 4 samples/symbol.
 # sigma^2 = A^2 * samples_per_symbol / (2 * code_rate * Eb/N0).
 # Preamble energy and total frame duration are also disclosed; no free gain.
 for eb in (8,12,16,20):
  for fec in (0,1):
   rate=784/4752 if fec else 1
   sigma=round(math.sqrt(8192**2*4/(2*rate*10**(eb/10))))
   configs.append(dict(name=f'eb_comparison_{eb}_{fec}',comparison='equal_information_ebn0',ebn0_db=eb,code_rate=rate,fec=fec,sigma=sigma))
 # Fair per-payload-bit energy includes transmitted synchronization and framing.
 for eb in (16,18,20,22,24):
  for fec in (0,1):
   symbols=542+(4752 if fec else 784)
   sigma=round(math.sqrt(8192**2*4*symbols/(2*512*10**(eb/10))))
   configs.append(dict(name=f'payload_energy_{eb}_{fec}',comparison='equal_total_frame_energy_per_payload_bit',payload_ebn0_db=eb,payload_bits=512,frame_symbols=symbols,fec=fec,sigma=sigma))
 with serial.Serial(port,230400,timeout=.2,write_timeout=5) as s,(out/'uart.jsonl').open('w') as log:
  s.reset_input_buffer();client=JsonSerial(s)
  def cmd(t):
   r=client.request(t,20);log.write(json.dumps(dict(command=t,response=r))+'\n');log.flush();return r
  def good(t):
   r=cmd(t);assert r.get('ok')==1,(t,r);return r
  ping=good('PING');assert ping['version']==VERSION and ping['protocol']==PROTOCOL and ping['arm_build']==BUILD;good('NETSTOP');good('RELEASE');good('WRITE 796 0')
  for cfg in configs:
   agg=dict(attempts=0,captured=0,crc_delivered=0,pre_errors=0,pre_bits=0,post_errors=0,post_bits=0,decoded_frame_bit_errors=0,decoded_frames=0,cycles=0,clipped_iq_samples=0)
   trials=30 if 'comparison' in cfg else 8
   examples=[]
   for k in range(trials):
    good('RELEASE');cfo=cfg.get('cfo',0)
    regs={12:0,48:1000000,64:round(cfg.get('gain',1)*32768),68:cfg.get('sigma',0),72:0,80:37,84:round(.23*2**32),88:20261012+k*733,
     92:round(cfo/8e6*2**32),96:0,112:cfg.get('delay',53),116:0,120:round(cfg.get('echo',0)*32768),124:cfg.get('echo_delay',0),128:round(.61*2**32),132:round(cfo/8e6*2**32),136:0,140:0,192:cfg['fec'],776:0}
    for a,v in regs.items():good(f'WRITE {a} {v&0xffffffff}')
    # Same input information and random seeds in each paired coded/raw trial.
    tx=frame(hashlib.sha512(f'energy-pair-{k}'.encode()).digest(),18000+k)
    good(f'LOAD {18000+k} {tx.hex()}');good('START')
    deadline=time.monotonic()+5
    while not good('STATUS')['status']&2:assert time.monotonic()<deadline
    result=cmd('RESULT');p=good('PHYSTATS');cap=good('READ 100')['value']
    agg['attempts']+=1;agg['captured']+=cap;agg['cycles']+=result['cycles'];agg['clipped_iq_samples']+=good('READ 156')['value']
    for field in ('pre_errors','pre_bits','post_errors','post_bits'):agg[field]+=p[field]
    if result['ok']:
     rx=bytes.fromhex(result['rx_hex']);assert rx==tx and result['crc_calc']==result['crc_recv']==binascii.crc_hqx(tx,0xffff)
     agg['crc_delivered']+=1
    else:assert not result['rx_hex']
    if p['post_bits']:agg['decoded_frames']+=1;agg['decoded_frame_bit_errors']+=p['post_errors']
    if k<2:examples.append(dict(result=result,phy=p))
   agg.update(capture_fraction=agg['captured']/trials,frame_delivery=agg['crc_delivered']/trials,
     pre_ber=agg['pre_errors']/agg['pre_bits'] if agg['pre_bits'] else None,
     decoded_post_ber=agg['post_errors']/agg['post_bits'] if agg['post_bits'] else None,
     frame_error_upper95_if_zero=1-.05**(1/trials) if agg['crc_delivered']==trials else None)
   row=dict(config=cfg,measured=agg,examples=examples);rows.append(row)
   (out/'progress.json').write_text(json.dumps(rows,indent=2));print('STUDY '+cfg['name']+' '+str(agg),flush=True)
  good('RELEASE');memory=good('MEMORY')
 report=dict(completed=True,source='physical_FPGA_RX_UART',version=VERSION_HEX,ping=ping,images={n:hashlib.sha256((ROOT/'ready'/n).read_bytes()).hexdigest() for n in ('system_wrapper.bit','swarm_app.elf')},rows=rows,memory=memory,
  qualification='Finite deterministic engineering sweep. Zero observed errors is not proof of zero BER; captured-only BER and all-attempt delivery denominators are separate.',
  energy_definition='A=8192; 4 complex samples per rectangular symbol; independent I/Q sigma. Es comparison keeps noise and symbol energy fixed; Eb comparison scales sigma by inverse sqrt(code rate). Information count includes frame CRC (784 bits), header 542 symbols excluded from Eb but transmitted and subject to the same noise.',
  code_rates=dict(raw=1,full=784/4752),frame_symbols=dict(raw=1326,full=5294),turbo_iterations=2)
 (out/'acceptance.json').write_text(json.dumps(report,indent=2));print('RECEIVER_STUDY_COMPLETE '+str(out));return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',default='COM4');p.add_argument('--out');a=p.parse_args();run(a.port,a.out)
