"""Real-board gate for iterative FEC, estimated DSP and actual sample RAM."""
import argparse,binascii,hashlib,json,math,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps'),str(ROOT/'tests'),str(ROOT/'reference')]
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX
import serial
from serial_json import JsonSerial
from acceptance import frame
def run(port='COM4',out=None):
 out=Path(out) if out else ROOT/'results'/time.strftime('full_phy_%Y%m%d_%H%M%S');out.mkdir(parents=True,exist_ok=True)
 rows=[];total_corrections=0
 configs=[dict(name='raw_ideal',fec=0),dict(name='fec_ideal',fec=1),dict(name='cfo_positive',fec=1,cfo=5000,phase=110,gain=.7),
  dict(name='cfo_negative',fec=1,cfo=-5000,phase=-130,gain=.6),dict(name='multipath',fec=1,cfo=500,echo=.15,delay=8,phase=30,sigma=400),
  dict(name='fec_noise',fec=1,sigma=3000),dict(name='raw_noise_comparison',fec=0,sigma=3000),dict(name='bad_crc',fec=1,bad_crc=1),dict(name='no_frame',fec=1,suppress=1)]
 with serial.Serial(port,230400,timeout=.2,write_timeout=5) as s,(out/'uart.jsonl').open('w') as f:
  s.reset_input_buffer();c=JsonSerial(s,max_line=16384)
  def cmd(t):
   r=c.request(t,20);f.write(json.dumps(dict(command=t,response=r))+'\n');f.flush();return r
  def good(t):
   r=cmd(t);assert r.get('ok')==1,(t,r);return r
  assert good('PING')['version']==VERSION;good('NETSTOP')
  for k,cfg in enumerate(configs):
   good('RELEASE');cfo=cfg.get('cfo',0)
   regs={796:0,12:cfg.get('bad_crc',0),48:5000000,64:round(cfg.get('gain',1)*32768),68:cfg.get('sigma',0),72:0,80:37,84:round(cfg.get('phase',0)/360*2**32),88:1001,
    92:round(cfo/8e6*2**32),96:cfg.get('suppress',0),112:53,116:0,120:round(cfg.get('echo',0)*32768),124:cfg.get('delay',0),128:round(110/360*2**32),132:round(cfo/8e6*2**32),136:0,140:0,192:cfg['fec'],776:0}
   for a,v in regs.items():good(f'WRITE {a} {v&0xffffffff}')
   payload=hashlib.sha512(f'full-phy-known-payload-{k}'.encode()).digest();tx=frame(payload,1700+k)
   good(f'LOAD {1700+k} {tx.hex()}');good('START');deadline=time.monotonic()+10
   while not good('STATUS')['status']&2:
    assert time.monotonic()<deadline
   result=cmd('RESULT');stats=good('PHYSTATS');rx=bytes.fromhex(result.get('rx_hex',''))
   expected_reject=cfg.get('bad_crc') or cfg.get('suppress')
   if expected_reject:assert result['ok']==0 and not rx
   elif cfg['name']=='raw_noise_comparison':assert (rx==tx if result['ok'] else not rx)
   else:assert result['ok']==1 and rx==tx,(cfg,result,stats)
   if result['ok']:assert result['crc_calc']==result['crc_recv']==binascii.crc_hqx(tx,0xffff)
   if stats['pre_bits'] and cfg['fec']:assert stats['turbo_iterations']==2 and stats['pre_bits']==4752
   if result['ok'] and cfg['fec']:total_corrections+=stats['pre_errors'];assert stats['post_errors']==0
   iq={}
   for bank in (0,1):
    samples=[]
    for start in range(0,stats['iq_count'],64):
     q=good(f'IQ {start} {min(64,stats["iq_count"]-start)} {bank}');assert q['source']=='FPGA_SAMPLE_RAM' and q['generation']==result['generation'];samples+=q['iq']
    iq['equalized' if bank else 'received']=samples
   estimate=stats['cfo_phase_step']*8e6/2**32
   evm=100*math.sqrt(stats['evm_error_sum']/(stats['evm_symbols']*8192**2)) if stats['evm_symbols'] else None
   if cfg['name'] in ('raw_ideal','fec_ideal'):assert evm==0 and stats['pre_errors']==0 and len(iq['equalized'])==512
   if cfg['name'].startswith('cfo_'):assert abs(estimate-cfo)<50 and evm<10,(estimate,evm)
   if cfg['name']=='multipath':assert evm<25,(stats,evm)
   row=dict(config=cfg,result=result,phy=stats,estimated_cfo_hz=estimate,payload_evm_percent=evm,iq=iq,tx_hex=tx.hex())
   rows.append(row);(out/f'case_{k}.json').write_text(json.dumps(row,indent=2));print('FULL_PHY_CASE '+cfg['name']+' '+str({x:stats[x] for x in ('pre_errors','post_errors','turbo_iterations')}),flush=True)
  good('RELEASE')
 assert total_corrections>0,'Noise did not exercise actual FEC correction'
 report=dict(**{'pass':True},version=VERSION_HEX,cases=rows,coded_hard_decision_errors_in_verified_successful_frames=total_corrections,source='physical_board_UART',scope='Independent payload/CRC checks, iterative FPGA FEC, sample-only CFO/gain/timing/DFE and received IQ RAM; encoded-bit errors and decoded-bit errors have different denominators, not a bit correction counter')
 (out/'acceptance.json').write_text(json.dumps(report,indent=2));print('HARDWARE_FULL_PHY_PASS evidence='+str(out));return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',default='COM4');p.add_argument('--out');a=p.parse_args();run(a.port,a.out)
