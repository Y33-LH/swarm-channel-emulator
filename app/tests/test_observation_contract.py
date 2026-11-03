import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from observation_contract import coherent_observation

def snapshot():
 a=[1,1000,0,16384,8192,100,12,4,0,0,0xffffffff,0,0,42,300000]
 p=[1,1000,0,42,1,0xffffffff,0,0,262144,100,2,6]
 m=[0,1,1,0x80000001,0,0,0,6,0,10,4752,0,784,0,1,42]
 return dict(run_id=15,config_id=9,protocol=19,round=12,observation=dict(link=0,applied=a,phy=p,meta=m,
  iq=[[0xffff0001,0x0001ffff]],statistics=dict(evm_energy=8192**2,evm_symbols=100),wave_samples=[0xffff0001],wave_start_sample=2500))

class ObservationTest(unittest.TestCase):
 def test_one_identity_and_signed_words(self):
  o=coherent_observation(snapshot(),'run-A')
  self.assertEqual(o['received'],[[1,-1]]);self.assertEqual(o['equalized'],[[-1,1]])
  self.assertEqual(o['waveform_samples']['received'],[[1,-1]])
  self.assertEqual(o['evm_percent'],10);self.assertEqual(o['age_ms'],200)
  self.assertEqual(o['channel']['generation'],o['generation'])
  self.assertLess(o['channel']['cfo_hz'],0)
 def test_mixed_frames_and_ack_rejected(self):
  for key,index,value in [('applied',1,999),('phy',3,43),('phy',2,1),('applied',2,1),('applied',0,0)]:
   s=snapshot();s['observation'][key][index]=value
   with self.subTest(key=key,index=index):
    with self.assertRaises(ValueError):coherent_observation(s)
 def test_capture_failure_is_not_zero_ber(self):
  s=snapshot();s['observation']['phy'][4]=0;s['observation']['meta'][7]=2
  o=coherent_observation(s)
  self.assertFalse(o['captured']);self.assertFalse(o['crc_good']);self.assertIsNone(o['pre_ber']);self.assertIsNone(o['evm_percent'])
 def test_legacy_missing_is_not_fabricated(self):
  s=snapshot();s.pop('observation');self.assertIsNone(coherent_observation(s))
 def test_multitap_sample_rate_and_hash(self):
  s=snapshot();s.update(protocol=21,channel_id=17,sample_rate_hz=16000000)
  s['observation'].update(channel_id=17,sample_rate_hz=16000000,taps=[[8192,1023,0,0xffffffff,0xffffffff]]*8)
  o=coherent_observation(s)
  self.assertEqual(len(o['channel']['taps']),8)
  self.assertEqual(o['sample_rate_hz'],16000000)
  self.assertAlmostEqual(o['channel']['taps'][0]['cfo_hz'],-16000000/2**32)
  self.assertLess(o['channel']['taps'][0]['gain_slope_per_s'],0)
  s['observation']['channel_id']=18
  with self.assertRaises(ValueError):coherent_observation(s)
  s['observation']['channel_id']=17;s['observation']['taps'][0][1]=1024
  with self.assertRaises(ValueError):coherent_observation(s)

if __name__=='__main__':unittest.main()
