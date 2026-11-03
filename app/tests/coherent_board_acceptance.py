"""Validate coherent DATA identity and real contiguous trace on the physical board."""
import sys,json,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps')]
import serial
from serial_json import JsonSerial
from observation_contract import coherent_observation
from product_config import DEFAULT,encode
from firmware_contract import VERSION,PROTOCOL

def run(port):
 out=ROOT/'results'/time.strftime('coherent_board_%Y%m%d_%H%M%S');out.mkdir()
 rows=[];observations=[]
 with serial.Serial(port,230400,timeout=.2,write_timeout=5) as uart:
  uart.reset_input_buffer();client=JsonSerial(uart)
  def cmd(s):
   r=client.request(s,20);rows.append(dict(command=s,response=r));assert r.get('ok')==1,(s,r);return r
  try:
   ping=cmd('PING');assert ping['version']==VERSION and ping['protocol']==PROTOCOL
   cmd('NETSTOP');cmd('SCENECFG '+encode(DEFAULT).hex());cmd('MEDIACLEAR 0 0');cmd('NETFEC 1');cmd('NETLOAD 0')
   for ideal in (1,0):
    cmd('NETSTART 12 20261009 '+str(ideal));cmd('LINKOBS 1')
    for link in (0,3,8,12):
     cmd('NETWATCH '+str(link));snapshot=cmd('NETSTEP 20')
     obs=coherent_observation(snapshot,out.name)
     assert obs and obs['link_id']==link and obs['age_ms']<2000,(link,obs)
     assert snapshot['version']==VERSION and obs['protocol']==PROTOCOL
     assert len(obs['waveform_samples']['received'])==128
     # Ideal rectangular DBPSK legitimately has only the two levels ±8192.
     unique=set(map(tuple,obs['waveform_samples']['received']))
     assert len(unique)>=2 if ideal else len(unique)>2
     if ideal:assert unique=={(8192,0),(-8192,0)}
     assert obs['captured'] and obs['crc_good'],obs
     # Distinct generation with same channel and PHY timestamp: never an ACK
     assert obs['generation']==obs['channel']['generation']
     assert len(obs['received'])==64 and obs['pre_bits']>0
     observations.append(dict(ideal=ideal,**obs))
    cmd('NETSTOP')
   memory=cmd('MEMORY');assert memory['stack_guard_ok'] and not memory['heap_failures']
  finally:
   (out/'uart.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
 report=dict(passed=True,version=f'{VERSION:08x}',protocol=PROTOCOL,port=port,observations=observations,memory=memory,
  images={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'ready').iterdir() if p.is_file()},
  scope='Eight physical same-DATA captures, both ARM and PL source endpoints, ideal and configured channels; no full-system acceptance claim')
 (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('COHERENT_BOARD_PASS',out,flush=True)
if __name__=='__main__':run(sys.argv[1])
