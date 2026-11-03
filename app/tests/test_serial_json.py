"""Regression tests for split serial replies, without relying on a physical USB scheduler."""
import json, unittest, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from serial_json import JsonSerial, SerialResponseError


class Clock:
    def __init__(self): self.now=0.
    def __call__(self): return self.now


class Port:
    def __init__(self, chunks, clock):
        self.chunks=list(chunks);self.clock=clock;self.timeout=.2;self.writes=[]
    def write(self, b): self.writes.append(b);return len(b)
    def flush(self): pass
    @property
    def in_waiting(self): return len(self.chunks[0]) if self.chunks else 0
    def read(self,size=1):
        self.clock.now+=self.timeout
        if not self.chunks: return b''
        b=self.chunks.pop(0)
        if size is not None and len(b)>size:
            self.chunks.insert(0,b[size:]);b=b[:size]
        return b


class FramingTests(unittest.TestCase):
    def setUp(self):
        self.clock=Clock()
        self.result={'ok':1,'type':'RESULT','version':458753,'rx_len':64,'rx_hex':bytes(range(96)).hex()}
        self.wire=json.dumps(self.result).encode()+b'\r\n'
    def run_chunks(self,chunks,timeout=5):
        p=Port(chunks,self.clock);r=JsonSerial(p,clock=self.clock).request('RESULT',timeout)
        self.assertEqual(r,self.result);self.assertEqual(p.writes,[b'RESULT\n']);self.assertEqual(p.timeout,.2)
    def test_split_inside_rx_hex_after_old_timeout(self):
        cut=self.wire.index(b'rx_hex')+15
        with self.assertRaises(json.JSONDecodeError): json.loads(self.wire[:cut])
        self.run_chunks([self.wire[:cut],b'',b'',self.wire[cut:]])
        self.assertGreater(self.clock.now,.2)
    def test_every_single_split_point(self):
        for cut in range(1,len(self.wire)):
            with self.subTest(cut=cut): self.run_chunks([self.wire[:cut],b'',self.wire[cut:]])
    def test_split_cr_lf(self): self.run_chunks([self.wire[:-1],b'',self.wire[-1:]])
    def test_several_read_timeouts(self): self.run_chunks([b'']*10+[self.wire])
    def test_whole_response(self): self.run_chunks([self.wire])
    def test_startup_and_blanks(self): self.run_chunks([b'\r\n',b'{"type":"RE',b'ADY"}\n',self.wire])
    def test_every_byte_separate(self): self.run_chunks([bytes([b]) for b in self.wire],timeout=200)
    def test_no_lf_is_not_a_complete_response(self):
        errors=[];p=Port([self.wire.rstrip()],self.clock);x=JsonSerial(p,clock=self.clock,on_error=errors.append)
        with self.assertRaises(SerialResponseError) as got: x.request('RESULT',.7)
        self.assertEqual(got.exception.detail['reason'],'deadline_without_complete_response')
        self.assertEqual(bytes.fromhex(errors[0]['partial_hex']),self.wire.rstrip())
        self.assertLessEqual(self.clock.now,.700001)
        with self.assertRaises(RuntimeError): x.request('START')
        self.assertEqual(p.writes,[b'RESULT\n'])
    def test_truncated_then_timeout_records_all_bytes(self):
        p=Port([self.wire[:40],b'',self.wire[40:100]],self.clock)
        with self.assertRaises(SerialResponseError) as got: JsonSerial(p,clock=self.clock).request('RESULT',1)
        self.assertEqual(got.exception.detail['partial_hex'],self.wire[:100].hex())
        self.assertEqual(p.writes,[b'RESULT\n'])
    def test_malformed_complete_line_not_silently_skipped(self):
        p=Port([b'{"rx_hex":"bad\n',self.wire],self.clock)
        with self.assertRaises(SerialResponseError) as got: JsonSerial(p,clock=self.clock).request('RESULT')
        self.assertEqual(got.exception.detail['reason'],'invalid_complete_json')
        self.assertEqual(got.exception.detail['offending_line_hex'],b'{"rx_hex":"bad\n'.hex())
        self.assertEqual(len(p.chunks),1)
    def test_non_ascii_corruption_is_error(self):
        p=Port([b'{"ok":1,"x":"\xff"}\n'],self.clock)
        with self.assertRaises(SerialResponseError): JsonSerial(p,clock=self.clock).request('RESULT')
    def test_scalar_json_rejected(self):
        p=Port([b'42\n'],self.clock)
        with self.assertRaises(SerialResponseError): JsonSerial(p,clock=self.clock).request('RESULT')
    def test_line_size_limit(self):
        p=Port([b'x'*1000],self.clock)
        with self.assertRaises(SerialResponseError) as got: JsonSerial(p,clock=self.clock,max_line=64).request('RESULT')
        self.assertEqual(got.exception.detail['reason'],'line_too_long')
        self.assertEqual(got.exception.detail['partial_bytes'],64)
    def test_bad_request_not_written(self):
        p=Port([],self.clock)
        with self.assertRaises(ValueError): JsonSerial(p,clock=self.clock).request('RESULT\nSTART')
        self.assertEqual(p.writes,[])

if __name__=='__main__': unittest.main(verbosity=2)
