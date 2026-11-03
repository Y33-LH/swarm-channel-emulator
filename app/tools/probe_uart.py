import sys,time,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'python_deps'))
import serial
for port in ('COM4','COM5'):
 for baud in (230400,115200,230400,1000000):
  try:
   with serial.Serial(port,baud,timeout=.5) as s:
    s.reset_input_buffer();s.write(b'\nPING\n');s.flush();data=s.read(512)
    print(port,baud,repr(data),flush=True)
  except Exception as e:print(port,str(e),flush=True)
