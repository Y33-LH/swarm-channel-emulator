"""Measured offered-load sweep; all DATA/ACK go through the FPGA. No analytic result substituted."""
import json,sys,time,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps')]
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX
import serial
from serial_json import JsonSerial
from product_config import DEFAULT,encode
def run(port='COM4',out=None,progress=None,cancel=None):
 out=Path(out) if out else ROOT/'results'/time.strftime('capacity_%Y%m%d_%H%M%S');out.mkdir(parents=True,exist_ok=True)
 rows=[];started=time.monotonic()
 with serial.Serial(port,230400,timeout=.2,write_timeout=5) as s,(out/'uart.jsonl').open('w') as f:
  s.reset_input_buffer();c=JsonSerial(s,max_line=16384)
  def cmd(t):
   r=c.request(t,90);f.write(json.dumps(dict(command=t,response=r))+'\n');f.flush();assert r.get('ok')==1,(t,r);return r
  assert cmd('PING')['version']==VERSION
  cmd('NETSTOP');cmd('SCENECFG '+encode(DEFAULT).hex());cmd('MEDIACLEAR 0 0');cmd('NETFEC 1');cmd('NETACKDROP 0')
  for rate in (0,2,4,5,6,8,12):
   cmd(f'NETLOAD {rate}');cmd('NETSTART 60 20261009 1');snapshots=[];warm=None;last=None
   while True:
    if cancel and cancel():cmd('NETSTOP');cmd('NETLOAD 0');raise InterruptedError('容量扫描已停止，未发布完整通过结论')
    r=cmd('NETSTEP 100');snapshots.append(r)
    if r['round']==100:warm=r
    if r['round']==500:last=r;cmd('NETLOAD 0')
    if progress:progress(dict(rows=rows,rate_pps=rate,model_s=r['round']/10,total_rates=7,status='running'))
    if not r['running']:break
   assert warm and last and r['slot_misses']==0
   assert all(x[8]<=x[7] and x[14]<=x[13] for x in r['links'])
   offered=rate*4*64*8
   goodput=(last['load_bytes']-warm['load_bytes'])*8/40
   load_delivery=r['load_delivered']/r['load_generated'] if r['load_generated'] else 1
   growth=last['pending']-warm['pending']
   # Fixed, declared engineering acceptance gate; not Shannon capacity.
   sustainable=(not rate or goodput>=.98*offered) and load_delivery>=.99 and r['queue_drops']==0 and growth<=4 and r['delay_max_ns']<=1_000_000_000
   row=dict(rate_pps_per_source=rate,sources=[1,5,9,13],offered_payload_bps=offered,steady_goodput_bps=goodput,
    load_delivery=load_delivery,pending_growth=growth,queue_drops=r['queue_drops'],max_delay_ms=r['delay_max_ns']/1e6,
    sustainable=sustainable,final=r)
   rows.append(row);(out/f'rate_{rate}.json').write_text(json.dumps(dict(summary=row,snapshots=snapshots),indent=2))
   if progress:progress(dict(rows=rows,rate_pps=rate,model_s=60,total_rates=7,status='running'))
  cmd('NETLOAD 0')
 assert any(x['sustainable'] and x['rate_pps_per_source'] for x in rows)
 assert any(not x['sustainable'] for x in rows),'Sweep did not bracket saturation; extend loads'
 best=max((x for x in rows if x['sustainable']),key=lambda x:x['steady_goodput_bps'])
 report=dict(**{'pass':True},source='FPGA_DATA_ACK_AND_ARM_QUEUES',version=VERSION_HEX,rows=rows,
  measured_sustainable_payload_bps=best['steady_goodput_bps'],max_tested_sustainable_rate_pps=best['rate_pps_per_source'],
  scope='固定四条4跳路径、16节点1Hz心跳、理想物理链路、满FEC、TDMA下的附加业务可持续容量；非射频容量或所有场景通用上限',
  thresholds=dict(steady_goodput_fraction=.98,load_delivery=.99,max_delay_ms=1000,max_queue_growth=4,queue_drops=0),
  interval=dict(warmup_s=10,measurement_s=40,drain_s=10),wall_s=time.monotonic()-started)
 (out/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('HARDWARE_CAPACITY_PASS evidence='+str(out));return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',default='COM4');p.add_argument('--out');a=p.parse_args();run(a.port,a.out,lambda x:print('CAPACITY_PROGRESS rate='+str(x['rate_pps'])+' model_s='+str(x['model_s']),flush=True))
