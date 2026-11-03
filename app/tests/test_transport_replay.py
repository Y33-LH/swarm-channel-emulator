"""Inject damaged USB responses, preserve execution count and raw identities."""
import json,sys,unittest,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from serial_json import JsonSerial,SerialResponseError
from test_serial_json import Clock,Port

class BoardPort(Port):
    def __init__(self,damage):
        super().__init__([],Clock());self.damage=damage;self.executed=0;self.cache={};self.protected_writes=[]
    def reset_input_buffer(self):self.chunks.clear()
    def write(self,wire):
        self.writes.append(wire)
        if wire==b'PING\n':
            self.chunks.append(b'{"ok":1,"type":"PING","transport":"crc32-replay-v1"}\n');return len(wire)
        head,rid,crc,body=wire.rstrip(b'\n').split(b' ',3)
        assert head==b'Q' and int(crc,16)==zlib.crc32(body)
        self.protected_writes.append(wire)
        if rid not in self.cache:
            self.executed+=1
            payload=json.dumps(dict(ok=1,type='COUNT',executions=self.executed,seq=0x80000001)).encode()
            self.cache[rid]=b'@'+rid+b':'+str(len(payload)).encode()+b':'+f'{zlib.crc32(payload):08x}'.encode()+b':'+payload+b'\r\n'
        response=self.cache[rid]
        if len(self.protected_writes)==1 or self.damage=='always':
            if self.damage=='missing':response=response[:20]+response[23:]
            elif self.damage=='timeout':response=response[:20]
            elif self.damage=='stale':response=response.replace(b'@'+rid+b':',b'@0:')
            else:response=response.replace(b'COUNT',b'COuNT')
        self.chunks.append(response)
        return len(wire)

class ReplayTests(unittest.TestCase):
    def test_damage_recovers_without_duplicate_execution(self):
        for damage in ('crc','missing','timeout','stale'):
            with self.subTest(damage=damage):
                p=BoardPort(damage);c=JsonSerial(p,clock=p.clock)
                c.request('PING');r=c.request('NETSTEP 200',.6)
                self.assertEqual(r['executions'],1);self.assertEqual(p.executed,1)
                self.assertEqual(r['seq'],0x80000001)
                self.assertEqual(p.protected_writes[0],p.protected_writes[1])
                self.assertEqual(len(c.recoveries),1)
                c.request('NETSTEP 200',.6)
                self.assertEqual(p.executed,2)
    def test_persistent_corruption_fails_closed(self):
        p=BoardPort('always');errors=[];c=JsonSerial(p,clock=p.clock,on_error=errors.append)
        c.request('PING')
        with self.assertRaises(SerialResponseError):c.request('NETSTEP 200',.6)
        self.assertEqual(p.executed,1);self.assertEqual(len(p.protected_writes),3)
        self.assertTrue(c.failed);self.assertEqual(len(errors),1)
        with self.assertRaises(RuntimeError):c.request('START')
    def test_illegal_request_not_transmitted(self):
        p=BoardPort('crc');c=JsonSerial(p,clock=p.clock);c.request('PING')
        with self.assertRaises(ValueError):c.request('NETSTEP 1\nNETSTEP 1')
        self.assertEqual(len(p.writes),1)

if __name__=='__main__':unittest.main(verbosity=2)
