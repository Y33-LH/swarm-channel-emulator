import sys,json,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root/'tools'),str(root/'tools/python_deps')]
import serial
from serial_json import JsonSerial
with serial.Serial('COM4',230400,timeout=.2,write_timeout=3) as s:
 s.reset_input_buffer();c=JsonSerial(s)
 def cmd(t):return c.request(t,5)
 for phase in (0,0x40000000,0x80000000,0xc0000000):
  cmd('RELEASE');cmd('WRITE 84 '+str(phase));cmd('SEND 42 41424344');time.sleep(.05)
  print(json.dumps({'phase':phase,'result':cmd('RESULT'),'regs':{hex(i):cmd('READ '+str(i))['value'] for i in list(range(80,144,4))+list(range(144,188,4))}}),flush=True)
