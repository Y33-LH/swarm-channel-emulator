import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from pcap_image import convert

class BitstreamTests(unittest.TestCase):
    def test_current_bitstream_and_bad_inputs(self):
        data=(ROOT/'ready/system_wrapper.bit').read_bytes()
        raw=convert(data)
        self.assertEqual(len(raw)%8,0)
        self.assertIn(bytes.fromhex('665599aa'),raw[:256])
        for bad in (b'',data[:-1],data+b'\0',b'\0'*32):
            with self.assertRaises(ValueError):convert(bad)

if __name__=='__main__':unittest.main()
