"""Physical ARM coefficient checks + byte-verified FPGA multi-tap DATA captures.

The raw-PHY waveform is independently regenerated from the transmitted bytes,
then passed through an integer tap/AWGN oracle. Expected bytes never repair RX.
"""
import sys,json,time,math,binascii,hashlib,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps'),str(ROOT/'reference')]
import serial
from serial_json import JsonSerial
import channel_config as cc,product_config as pc
from channel_model import frame
from generate_preamble import pn
from observation_contract import coherent_observation
from firmware_contract import VERSION,PROTOCOL

def signed(n,bits=32):return n-(1<<bits) if n&(1<<(bits-1)) else n
def table(name,bits):return [signed(int(x,16),bits) for x in (ROOT/'rtl'/name).read_text().split()]
def nxt(x):
 x^=(x<<13)&0xffffffff;x^=x>>17;x^=(x<<5)&0xffffffff;return x&0xffffffff
def raw_source(body,delay):
 bits=lambda b:[(v>>i)&1 for v in b for i in range(7,-1,-1)]
 pre=pn(7,[0,3])*2+pn(8,[0,4,5,6])+bits(bytes.fromhex('d391c5a7'))+[0]
 signs=[1-2*b for b in pre];last=1
 for b in bits(body+binascii.crc_hqx(body,0xffff).to_bytes(2,'big')):last*=1-2*b;signs.append(last)
 return [0]*(128+delay)+[v*8192 for v in signs for _ in range(4)]
def check_wave(s):
 o=s['observation'];body=bytes.fromhex(o['tx_hex']);src=raw_source(body,o['link']*7%61)
 start=o['wave_start_sample'];actual=o['wave_samples'];gauss=table('gaussian_q12.mem',16);sine=table('sine_q15.mem',17)
 ts=o['taps'];assert ts and len(actual)==128
 phases=[t[2] for t in ts];gains=[t[0]<<16 for t in ts];rng=o['applied'][13];sigma=o['applied'][5]
 errors=[]
 for n in range(start+len(actual)):
  r2=nxt(rng);re=gauss[rng>>20]*sigma>>12;im=gauss[r2>>20]*sigma>>12
  for i,(g,d,p,step,ramp) in enumerate(ts):
   x=(src[n-d] if 0<=n-d<len(src) else 0)*(gains[i]>>16)>>15;k=phases[i]>>24
   re+=x*sine[(k+64)&255]>>15;im+=x*sine[k]>>15
   phases[i]=(phases[i]+step)&0xffffffff;gains[i]=min(0x80000000,max(0,gains[i]+signed(ramp)))
  if n>=start:
   expected=(max(-32768,min(32767,re)),max(-32768,min(32767,im)));w=actual[n-start];got=(signed(w&65535,16),signed(w>>16,16))
   if expected!=got:errors.append((n,expected,got))
  rng=nxt(r2)
 assert not errors,errors[:5]
 return dict(samples=len(actual),max_error_lsb=0,independent_source='known raw DBPSK frame bytes + preamble + integer tap/AWGN oracle')

def run(port):
 out=ROOT/'results'/time.strftime('multitap_board_%Y%m%d_%H%M%S');out.mkdir();rows=[];coefficient_cases=[];captures=[]
 with serial.Serial(port,230400,timeout=.2,write_timeout=5) as uart,(out/'uart.jsonl').open('w',encoding='utf-8') as log:
  uart.reset_input_buffer();client=JsonSerial(uart,max_line=32768)
  def cmd(text,ok=True):
   r=client.request(text,60);log.write(json.dumps(dict(command=text,response=r))+'\n');log.flush()
   if ok:assert r.get('ok')==1,(text,r)
   return r
  p=cmd('PING');assert p['version']==VERSION and p['protocol']==PROTOCOL;cmd('NETSTOP')
  scenes=[pc.validate({'environment':e,'weather':w,'altitude_m':h,'faults':0}) for e,w,h in ((1,0,400),(4,4,150),(5,0,700))]
  for mode in (1,2):
   for model in (0,1,2):
    for rate in (8000,16000):
     for sc in scenes:
      cmd('SCENECFG '+pc.encode(sc).hex());c=cc.validate({'mode':mode,'fading':model,'sample_rate_khz':rate,'tap_count':0 if mode==1 else 8})
      cc.configure(cmd,c)
      for link,t,seed in ((0,0,7),(3,321.125,20261101),(12,701.5,12345)):
       actual=cmd(f'CHFRAME {link} {round(t*1000)} {seed}');expected=frame(link,t,seed,sc,c)
       assert actual['sample_rate_hz']==expected['sample_rate_hz'] and actual['limited']==expected['limited']
       assert len(actual['taps'])==len(expected['taps'])
       for a,b in zip(actual['taps'],expected['taps']):
        for x,y in zip(a,b):assert abs(x-y)<max(3e-5,abs(y)*1e-7),(mode,model,rate,link,a,b)
       for k in ('loss_db','rain_db_km'):assert abs(actual[k]-expected[k])<1e-6,(k,actual,expected)
       coefficient_cases.append(dict(mode=mode,model=model,rate=rate,scene=sc,link=link,time=t,seed=seed))
  print('ARM_MULTITAP_REFERENCE_PASS',len(coefficient_cases),flush=True)
  # Rejected configuration must leave the previous block intact.
  old=cmd('CHANNELINFO');bad=list(old['values']);bad[4]=9
  r=cmd('CHANNELCFG '+struct.pack('<48i',*bad).hex(),False);assert not r['ok'] and cmd('CHANNELINFO')==old
  # Mild multi-path cases are positive checks, not a maximum RX range claim.
  for count,rate,model in ((1,8000,0),(3,8000,0),(8,8000,0),(8,16000,0),(3,8000,2),(3,16000,2)):
   sc=pc.validate({'environment':1,'faults':0,'jitter_percent':0});c=cc.validate({'mode':2,'fading':model,'tap_count':count,'sample_rate_khz':rate,'rician_k_cdb':2000,'loss_cdb':600,'scatter_millihz':1000,
      **{f'tap{i}_power_cdb':0 if i==0 else -3000-100*i for i in range(8)}})
   cmd('SCENECFG '+pc.encode(sc).hex());cc.configure(cmd,c);cmd('NETFEC 0');cmd('NETLOAD 0');cmd('MEDIACLEAR 0 0');cmd('LINKOBS 1');cmd('NETWATCH 0')
   cmd('NETSTART 3 20261101 0')
   rejected=cmd('CHANNELCFG '+cc.encode(c).hex(),False);assert not rejected['ok'] and rejected['error_code']==6
   s=cmd('NETSTEP 10');s['config']={**sc,'channel':c};o=coherent_observation(s,out.name)
   assert o and o['channel_id']==cc.wire_id(c) and len(o['channel']['taps'])==count and o['crc_good'],o
   raw=s['observation'];assert raw['tx_hex']==raw['rx_hex']
   oracle=check_wave(s)
   captures.append(dict(config=c,observation=o,wave_oracle=oracle));cmd('NETSTOP')
   print('FPGA_MULTITAP_CAPTURE_PASS',count,rate,model,flush=True)
  mem=cmd('MEMORY');assert mem['stack_guard_ok'] and not mem['heap_failures'],mem
  cmd('SCENECFG '+pc.encode(pc.DEFAULT).hex());cmd('NETFEC 1')
 report=dict(passed=True,version=f'{VERSION:08x}',protocol=PROTOCOL,port=port,coefficient_cases=coefficient_cases,captures=captures,memory=mem,
  images={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'ready').iterdir() if p.is_file()},
  scope='ARM/independent model comparison, configuration readback/rollback, actual FPGA raw DATA exact waveform and payload; full-FEC, arbitrary strong multipath and statistical hardware qualification remain separate')
 (out/'acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('MULTITAP_BOARD_PASS',out,flush=True)
if __name__=='__main__':run(sys.argv[1])
