import unittest,sys,struct,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from endpoint_gateway import EndpointGateway
class EndpointTest(unittest.TestCase):
    def init(self):
        g=EndpointGateway(1,91);g.register(dict(v=1,type='HELLO',node=1,identity='test_node',capabilities=['heartbeat','bytes']))
        msg=dict(v=1,type='DATA',node=1,identity='test_node',run_id=91,model_ms=1000,sequence=1,kind=1,payload_hex=struct.pack('<4i',1,2,400000,10).hex())
        return g,msg
    def test_clock_identity_sequence(self):
        g,msg=self.init()
        for field,value in [('model_ms',999),('run_id',90),('node',2),('identity','other')]:
            bad=dict(msg);bad[field]=value
            with self.assertRaises(ValueError):g.accept(bad,1000)
        result=g.accept(msg,1000);self.assertEqual(result['source'],'software_protocol_test');self.assertEqual(result['status'],'validated_not_delivered')
        with self.assertRaises(ValueError):g.accept(msg,1000)
    def test_disconnect_does_not_fabricate_heartbeat(self):
        g,msg=self.init();g.disconnect()
        with self.assertRaises(ValueError):g.accept(msg,1000)
    def test_bounds(self):
        g,msg=self.init();msg['payload_hex']=struct.pack('<4i',11000000,2,400000,10).hex()
        with self.assertRaises(ValueError):g.accept(msg,1000)
if __name__=='__main__':unittest.main()
