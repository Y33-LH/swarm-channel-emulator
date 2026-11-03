import sys,json
from pathlib import Path
sys.path[:0]=[str(Path(__file__).parent/'python_deps'),str(Path(__file__).parent)]
import serial
from serial_json import JsonSerial
with serial.Serial('COM4',int(sys.argv[1]),timeout=.2) as s:
 s.reset_input_buffer();s.write(b'\n');s.read(256);s.reset_input_buffer()
 c=JsonSerial(s)
 for command in ('PING','MEMORY'):
  print(c.request(command,3),flush=True)
