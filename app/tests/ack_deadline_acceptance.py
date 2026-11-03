"""Forced missing ACK must fit the TDMA slot and retransmit without duplicate delivery."""
import sys,time,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'tools'),str(root/'tools/python_deps')]
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX
import serial
from serial_json import JsonSerial
from product_config import DEFAULT,encode
out=root/'results'/time.strftime('ack_deadline_%Y%m%d_%H%M%S');out.mkdir()
with serial.Serial(sys.argv[1] if len(sys.argv)>1 else 'COM9',230400,timeout=.2) as s,(out/'uart.jsonl').open('w') as f:
 s.reset_input_buffer();c=JsonSerial(s)
 def cmd(t):
  r=c.request(t,20);f.write(json.dumps(dict(command=t,response=r))+'\n');f.flush();assert r.get('ok')==1,(t,r);return r
 assert cmd('PING')['version']==VERSION
 cmd('NETSTOP');cmd('SCENECFG '+encode(DEFAULT).hex());cmd('MEDIACLEAR 0 0');cmd('NETFEC 1');cmd('NETLOAD 0');cmd('NETACKDROP 1');cmd('NETSTART 2 20261009 1')
 r=cmd('NETSTEP 20');assert r['slot_misses']==0,r
 assert r['delivered']==r['generated']==32,r
 assert sum(x[4] for x in r['links'])>=1 and sum(x[6] for x in r['links'])>=1,r
 assert r['links'][16][0]>r['links'][16][1],r
 report=dict(**{'pass':True},final=r,scope='Full-FEC FPGA ACK suppression, deadline, retry and dedup; fixed 5ms TDMA slot')
 (out/'acceptance.json').write_text(json.dumps(report,indent=2));print('HARDWARE_ACK_DEADLINE_PASS evidence='+str(out))
