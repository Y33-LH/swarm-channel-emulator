"""Explicit channel contract, separate from position/traffic configuration.

All quantities are integer wire units. mode=0 is the qualified legacy ABI;
mode=1 derives a tap profile from geometry/environment; mode=2 ignores those
presets and uses exactly the user's tap list. AWGN always uses user SNR.
"""
import hashlib,json,struct

BASE_FIELDS=('schema','mode','fading','sample_rate_khz','tap_count','rician_k_cdb',
 'scatter_millihz','loss_cdb','cfo_hz','phase_cdeg','delay_ns','delay_scale_percent',
 'echo_decay_cdb','reserved0','reserved1','reserved2')
FIELDS=BASE_FIELDS+tuple(f'tap{i}_{field}' for i in range(8) for field in ('power_cdb','delay_ns','phase_cdeg','cfo_hz'))
DEFAULT=dict(zip(BASE_FIELDS,(1,0,0,8000,2,1500,2000,1200,0,0,0,100,300,0,0,0)))
for i in range(8):
 DEFAULT.update({f'tap{i}_power_cdb':-300*i,f'tap{i}_delay_ns':i*125,f'tap{i}_phase_cdeg':0,f'tap{i}_cfo_hz':0})

def validate(value=None):
 value={} if value is None else value
 if not isinstance(value,dict) or set(value)-set(FIELDS):raise ValueError('信道配置有未知字段')
 c={**DEFAULT,**value}
 if any(type(v) is not int for v in c.values()):raise ValueError('信道配置必须使用规定的整数单位')
 # Wire field 13 (historically reserved0) now enables the procedural DEM.
 # Kept as an additive flag so archived schema-1 configurations stay replayable.
 bounds=((1,1),(0,2),(0,2),(8000,16000),(0,8),(0,3000),(0,5000),(0,6000),(-5000,5000),(0,35999),(0,60000),(25,400),(0,2400),(0,1),(0,0),(0,0))
 for k,(lo,hi) in zip(BASE_FIELDS,bounds):
  if not lo<=c[k]<=hi:raise ValueError(f'{k} 允许范围 {lo}～{hi}')
 if c['sample_rate_khz'] not in (8000,16000):raise ValueError('采样率仅支持 8 或 16 MSa/s；带宽分别为 4 或 8 MHz')
 if c['mode']==0 and c['sample_rate_khz']!=8000:raise ValueError('旧版二径回归模式固定 8 MSa/s')
 if c['mode']==2 and c['tap_count']==0:raise ValueError('自主模式必须明确选择 1–8 个抽头')
 for i in range(8):
  for name,lo,hi in [('power_cdb',-6000,0),('delay_ns',0,60000),('phase_cdeg',0,35999),('cfo_hz',-5000,5000)]:
   if not lo<=c[f'tap{i}_{name}']<=hi:raise ValueError(f'抽头 {i} 的 {name} 超范围')
  if i<c['tap_count'] and c['mode']==2:
   if (c['delay_ns']+c[f'tap{i}_delay_ns'])*c['sample_rate_khz']/1e6>1023:raise ValueError('总时延超过 FPGA 的 1023 采样缓存')
   if abs(c['cfo_hz']+c[f'tap{i}_cfo_hz'])>6000:raise ValueError('总频偏超过当前接收机 ±6 kHz 研究范围')
 return c

def encode(c=None):return struct.pack('<48i',*(validate(c)[k] for k in FIELDS))
def wire_id(c=None):
 h=2166136261
 for b in encode(c):h=((h^b)*16777619)&0xffffffff
 return h
def digest(c=None):return hashlib.sha256(encode(c)).hexdigest()
def configure(command,c=None):
 c=validate(c);r=command('CHANNELCFG '+encode(c).hex())
 if r.get('ok')!=1 or r.get('channel_id')!=wire_id(c):raise ValueError('ARM 未确认所要求的信道配置')
 r=command('CHANNELINFO')
 if r.get('values')!=[c[k] for k in FIELDS] or r.get('channel_id')!=wire_id(c):raise ValueError('信道配置完整读回不一致')
 return r
