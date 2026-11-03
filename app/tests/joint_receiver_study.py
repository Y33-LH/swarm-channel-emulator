"""Finite 8-tap full-FEC receiver study; failures are results, never erased.

Not a guarantee for all combinations in the user-configurable range. All 16
nodes execute the physical PHY; no expected data is used to repair a receiver.
"""
import sys,json,time,hashlib,binascii,itertools
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps'),str(ROOT/'reference')]
import serial
from serial_json import JsonSerial
from firmware_contract import BUILD,VERSION,PROTOCOL
import channel_config as cc,product_config as pc

def run(port):
 out=ROOT/'results'/time.strftime('joint_receiver_%Y%m%d_%H%M%S');out.mkdir();rows=[]
 report=dict(complete=False,arm_build=BUILD,version=f'{VERSION:08x}',protocol=PROTOCOL,
  images={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'ready').iterdir() if p.is_file()},cases=rows,
  scope='36 finite eight-tap combinations; 10 model seconds each, full coding and actual shared FPGA; successful captured bytes checked, loss included. Fixed routes and identical seed across cases. Does not establish a universal joint receiver envelope.')
 def save():(out/'study.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
 save()
 with serial.Serial(port,230400,timeout=.2,write_timeout=5) as uart,(out/'uart.jsonl').open('w',encoding='utf-8') as log:
  uart.reset_input_buffer();client=JsonSerial(uart,max_line=32768)
  def cmd(text):
   r=client.request(text,60);log.write(json.dumps(dict(command=text,response=r))+'\n');log.flush();assert r.get('ok')==1,(text,r);return r
  p=cmd('PING');assert p['arm_build']==BUILD and p['version']==VERSION
  cmd('NETSTOP');cmd('NETFEC 1');cmd('NETLOAD 0');cmd('NETACKDROP 0');cmd('MEDIACLEAR 0 0');cmd('LINKOBS 1');cmd('NETWATCH 0')
  for index,(fs,model,snr,profile) in enumerate(itertools.product((8000,16000),(0,1,2),(16,28,40),('short_mild','long_strong'))):
   seed=20261101;cfo=-4000 if profile=='short_mild' else 4000
   sc=pc.validate(dict(environment=1,faults=0,jitter_percent=0,reference_snr_cdb=snr*100))
   cfg=cc.validate(dict(mode=2,fading=model,tap_count=8,sample_rate_khz=fs,loss_cdb=0,
     cfo_hz=cfo,phase_cdeg=13700,rician_k_cdb=1500,scatter_millihz=2000,
     **{f'tap{i}_{field}':value for i in range(8) for field,value in (
       ('power_cdb',0 if i==0 else (-1800-300*i if profile=='short_mild' else -300-300*i)),
       ('delay_ns',i*(125 if profile=='short_mild' else 750)),
       ('phase_cdeg',(i*3700)%36000),('cfo_hz',(-1 if i%2 else 1)*100))}))
   cmd('SCENECFG '+pc.encode(sc).hex());cc.configure(cmd,cfg);cmd(f'NETSTART 10 {seed} 0')
   observations=[]
   for second in range(10):
    s=cmd('NETSTEP 10');o=s.get('observation')
    if o:
     good=bool(o['meta'][7]&4);rx=bytes.fromhex(o['rx_hex']);tx=bytes.fromhex(o['tx_hex'])
     if good:
      assert rx==tx and len(rx)==96
      assert binascii.crc_hqx(rx,65535)==(o['meta'][13]&65535)==(o['meta'][13]>>16)
     else:assert not rx
     observations.append(dict(model_ms=o['applied'][1],captured=bool(o['phy'][4]),crc_good=good,
       limited=o.get('coefficient_limited'),digital_scale=o.get('digital_scale'),taps=o.get('taps')))
   links=s['links'];attempts=sum(x[19] for x in links);acked=sum(x[3] for x in links)
   rows.append(dict(index=index,seed=seed,config={**sc,'channel':cfg},profile=profile,model_s=10,
     data_attempts=attempts,acked=acked,hop_success=acked/attempts if attempts else None,
     delivered=s['delivered'],generated=s['generated'],pending=s['pending'],queue_drops=s['queue_drops'],retry_drops=s['retry_drops'],
     pre_errors=sum(x[14] for x in links),pre_bits=sum(x[13] for x in links),
     post_errors=sum(x[8] for x in links),post_bits=sum(x[7] for x in links),
     observations=observations,tdma=s.get('tdma')))
   assert s['slot_misses']==0
   save();print('JOINT_RX',index+1,fs,model,snr,profile,'ACK',rows[-1]['hop_success'],flush=True)
  mem=cmd('MEMORY');assert mem['stack_guard_ok'] and not mem['heap_failures']
  report.update(complete=True,memory=mem);save()
 print('JOINT_RECEIVER_STUDY_COMPLETE',out,flush=True)
 return out
if __name__=='__main__':run(sys.argv[1])
