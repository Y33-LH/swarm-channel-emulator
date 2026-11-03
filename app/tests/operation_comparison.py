"""Controlled application action: pause video versus status query, same workload.

Ideal channel removes traffic-dependent noise-consumption confounding. This
isolates scheduling/business effects, not a claim of better propagation or BER.
Both commands traverse the real downlink and return through the FPGA PHY.
"""
from pathlib import Path
import sys,json,time,struct,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps')]
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX
import serial
from serial_json import JsonSerial
from product_config import validate,encode
out=ROOT/'results'/time.strftime('operation_comparison_%Y%m%d_%H%M%S');out.mkdir()
video=bytes((i*37+19)%256 for i in range(32768))
rows=[];config=validate(dict(environment=1,formation=7,faults=0))
with serial.Serial((sys.argv[1] if len(sys.argv)>1 else 'COM9'),230400,timeout=.2,write_timeout=5) as s,(out/'uart.jsonl').open('w') as f:
    client=JsonSerial(s,max_line=32768)
    def cmd(t):
        r=client.request(t,90);f.write(json.dumps(dict(command=t,response=r))+'\n');f.flush();assert r.get('ok')==1,(t,r);return r
    assert cmd('PING')['version']==VERSION
    for pause in (False,True):
        cmd('NETSTOP');cmd('SCENECFG '+encode(config).hex());cmd('NETACKDROP 0');cmd('NETFEC 1');cmd('NETLOAD 8')
        cmd(f'MEDIACLEAR 0 {len(video)}')
        for i in range(0,len(video),64):cmd(f'MEDIASET 4 {i} '+video[i:i+64].hex())
        cmd('NETSTART 60 20261017 1');snapshots=[]
        while True:
            r=cmd('NETSTEP 100');snapshots.append(r)
            if r['round']==200:cmd('GCOMMAND '+struct.pack('<5I',1,5,3 if pause else 1,1 if pause else 0,10000).hex())
            if r['round']==500:cmd('NETLOAD 0')
            if not r['running']:break
        result=cmd('CMDSTATUS')['commands'];assert result[0][4]==2 and result[0][8]==int(pause),result
        assert r['slot_misses']==0
        received=0
        for off in range(0,len(video),64):
            q=client.request(f'MEDIAGET 4 {off} 64',20)
            f.write(json.dumps(dict(command=f'MEDIAGET 4 {off} 64',response=q))+'\n');f.flush()
            if q.get('ok')==1:assert bytes.fromhex(q['hex'])==video[off:off+64];received+=64
            else:assert q.get('error')=='MISSING_RECEIVED_FRAGMENT'
        assert received==r['media'][2]
        rows.append(dict(pause_video=pause,command=result[0],snapshots=snapshots,final=r,received_video_bytes=received))
        print('OPERATION_CASE',pause,r['hb'],received,r['pending'],flush=True)
    cmd('NETSTOP');cmd('NETLOAD 0')
assert rows[0]['final']['business_counts'][0][1]==rows[1]['final']['business_counts'][0][1]
assert rows[1]['received_video_bytes']<rows[0]['received_video_bytes'],'No observable business action effect'
report=dict(**{'pass':True},version=VERSION_HEX,config=config,seed=20261017,ideal=True,load_pps_per_source=8,
    intervention='At 20 model seconds send a real status query (control) or pause-video command to node 5 (treatment). Same payload, heartbeat schedule, TDMA, route and duration.',
    scope='Controlled scheduling/business experiment. Ideal PHY intentionally excludes traffic-dependent random-noise consumption. It does not measure coding gain or promise better heartbeat timing.',
    source_video_sha256=hashlib.sha256(video).hexdigest(),rows=rows)
(out/'acceptance.json').write_text(json.dumps(report,indent=2));print('OPERATION_COMPARISON_PASS',out)
