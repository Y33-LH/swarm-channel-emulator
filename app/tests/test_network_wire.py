import base64,copy,json,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from network_wire import expand_network

def pack(values):
    out=bytearray()
    for value in values:
        while value>127:out.append((value&127)|128);value>>=7
        out.append(value)
    return base64.b64encode(out).decode()

class WireTests(unittest.TestCase):
    def test_real_record_roundtrip(self):
        # Independent wire encoder over previously measured values.
        s=json.loads((ROOT/'tests/fixtures/compact_telemetry.json').read_text())
        x=copy.deepcopy(s);x.update(links=[],links_codec='uvarint-32x21-v1',links_data=pack(v for row in s['links'] for v in row),watch_iq=[],watch_iq_codec='le32-pairs-v1',watch_iq_data=base64.b64encode(b''.join(struct.pack('<II',*r) for r in s['watch_iq'])).decode())
        self.assertEqual(expand_network(x),s)
    def test_applied_register_readbacks_exact(self):
        values=[[((i+1)*0x1234567+j)&0xffffffff for j in range(15)] for i in range(32)]
        raw=b''.join(struct.pack('<15I',*r) for r in values)
        x=dict(type='NETWORK',applied_links=[],applied_codec='le32-32x15-v1',applied_data=base64.b64encode(raw).decode())
        self.assertEqual(expand_network(x)['applied_links'],values)
        for wrong in (raw[:-1],raw+b'\0'):
            with self.assertRaises(ValueError):expand_network(dict(type='NETWORK',applied_links=[],applied_codec='le32-32x15-v1',applied_data=base64.b64encode(wrong).decode()))
    def test_counter_limits_and_zero(self):
        values=[0 if i%3==0 else 0xffffffffffffffff if i%21==10 else 0xffffffff for i in range(672)]
        x=dict(type='NETWORK',links=[],links_codec='uvarint-32x21-v1',links_data=pack(values))
        self.assertEqual(sum(expand_network(x)['links'],[]),values)
    def test_bad_wire_rejected(self):
        for data in ('!',base64.b64encode(b'\x80').decode(),base64.b64encode(b'\x80\x00').decode(),pack([0]*671),pack([0]*673),pack([1<<64]*672)):
            with self.assertRaises(ValueError):expand_network(dict(type='NETWORK',links=[],links_codec='uvarint-32x21-v1',links_data=data))
        with self.assertRaises(ValueError):expand_network(dict(type='NETWORK',watch_iq=[],watch_iq_codec='le32-pairs-v1',watch_iq_data='AA=='))
if __name__=='__main__':unittest.main()
