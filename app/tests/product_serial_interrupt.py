"""Interrupt a real UART session mid-response, then reopen and verify actual PL work.

This is a controlled host-session interruption, not a claimed physical USB unplug.
"""
import sys,json,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps')]
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX,BUILD
import serial
from serial_json import JsonSerial,SerialResponseError
from product_config import DEFAULT,encode

class InterruptedPort:
    def __init__(self,port):self.port=port;self.armed=False;self.received=0;self.writes=0
    @property
    def timeout(self):return self.port.timeout
    @timeout.setter
    def timeout(self,value):self.port.timeout=value
    @property
    def in_waiting(self):return self.port.in_waiting
    def flush(self):return self.port.flush()
    def write(self,data):self.writes+=1;return self.port.write(data)
    def read(self,n):
        data=self.port.read(min(n,50));self.received+=len(data)
        if self.armed and self.received>=50:self.port.close()
        return data

def run(port_name):
    out=ROOT/'results'/time.strftime('serial_interrupt_%Y%m%d_%H%M%S');out.mkdir()
    images={n:hashlib.sha256((ROOT/'ready'/n).read_bytes()).hexdigest() for n in ('system_wrapper.bit','swarm_app.elf','ps7_init.tcl')}
    with serial.Serial(port_name,230400,timeout=.2,write_timeout=5) as raw:
        raw.reset_input_buffer();port=InterruptedPort(raw);client=JsonSerial(port,on_error=lambda x:(out/'partial_error.json').write_text(json.dumps(x,indent=2)))
        ping=client.request('PING');assert (ping['version'],ping['protocol'],ping['arm_build'])==(VERSION,PROTOCOL,BUILD)
        assert client.request('NETSTOP')['ok']==1
        assert client.request('SCENECFG '+encode(DEFAULT).hex())['ok']==1
        assert client.request('NETACKDROP 0')['ok']==1
        assert client.request('NETLOAD 0')['ok']==1
        assert client.request('MEDIACLEAR 0 0')['ok']==1
        assert client.request('NETFEC 1')['ok']==1
        assert client.request('NETSTART 1 71 1')['ok']==1
        port.received=0;port.armed=True
        try:client.request('NETSTEP 10',20);raise AssertionError('Partial response was accepted')
        except SerialResponseError:pass
        writes=port.writes
        try:client.request('NETSTART 1 71 1');raise AssertionError('Poisoned session reused')
        except RuntimeError:pass
        assert port.writes==writes and client.failed
    time.sleep(1)
    with serial.Serial(port_name,230400,timeout=.2,write_timeout=5) as raw:
        raw.reset_input_buffer();c=JsonSerial(raw)
        ping=c.request('PING');assert (ping['version'],ping['protocol'],ping['arm_build'])==(VERSION,PROTOCOL,BUILD)
        assert c.request('NETSTOP')['ok']==1
        c.request('NETLOAD 0');c.request('NETSTART 2 72 1');r=c.request('NETSTEP 20',20)
        (out/'reopened_snapshot.json').write_text(json.dumps(r,indent=2))
        assert r['round']==20 and r['generated']==r['delivered']==32 and r['slot_misses']==0
        assert sum(x[0] for x in r['links'])>0
        memory=c.request('MEMORY');assert memory['stack_guard_ok'] and not memory['heap_failures']
    report=dict(**{'pass':True},images=images,version=VERSION_HEX,arm_build=BUILD,port=port_name,source='actual_board_UART',scope='host session closed during a real JSON response; physical cable remained attached',partial_bytes=port.received,no_retry_on_poisoned_session=True,reopened_and_received_32_real_packets=True,memory=memory)
    (out/'acceptance.json').write_text(json.dumps(report,indent=2));print('SERIAL_INTERRUPT_RECOVERY_PASS',out)
if __name__=='__main__':run(sys.argv[1])
