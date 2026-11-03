"""Independent host verification of ARM -> FPGA DBPSK -> ARM receive bytes."""
import argparse, binascii, json, random, struct, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/python_deps'))
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX
import serial
sys.path.insert(0,str(ROOT/'tools'))
from serial_json import JsonSerial

def frame(data,seq):
    return struct.pack('<BBBBBBBBIIHHQHBB',1,1,0,5,1,0,1,2,0x13,seq,0,1,seq*100000000,len(data),0,0)+data+bytes(64-len(data))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--port',default='COM4');ap.add_argument('--out',type=Path);args=ap.parse_args()
    out=args.out or ROOT/'results'/time.strftime('hardware_%Y%m%d_%H%M%S');out.mkdir(parents=True,exist_ok=True)
    log=(out/'transcript.jsonl').open('w',encoding='utf-8');vec=(out/'vectors.jsonl').open('w',encoding='utf-8');checks=0;frames=0;bytes_checked=0
    ser=serial.Serial(args.port,230400,timeout=.2,write_timeout=3);ser.reset_input_buffer()
    transport=JsonSerial(ser,on_error=lambda detail:(out/'serial_failure.json').write_text(json.dumps(detail,indent=2),encoding='utf-8'))
    def ck(ok,msg):
        nonlocal checks
        checks+=1
        if not ok:raise AssertionError(msg)
    def cmd(s,timeout=5):
        obj=transport.request(s,timeout)
        log.write(json.dumps({'time':time.time(),'command':s,'response':obj})+'\n');log.flush()
        return obj
    def good(s,timeout=5):
        r=cmd(s,timeout);ck(r.get('ok')==1,f'{s}: {r}');return r
    def write(a,v):return good(f'WRITE {a} {v}')
    def read(a):return good(f'READ {a}')['value']
    def clean():
        good('RELEASE');write(12,0);write(48,5000000);write(64,32768);write(68,0);write(192,0);write(772,0);write(776,0)
        for off in (80,84,88,92,96,112,116,120,124,128,132,136,140):write(off,1 if off==88 else 0)
    def wait():
        end=time.monotonic()+4
        while time.monotonic()<end:
            if good('STATUS')['status']&2:return cmd('RESULT')
        raise TimeoutError('FPGA completion')
    def verify(tx,tag):
        nonlocal frames,bytes_checked
        r=wait();rx=bytes.fromhex(r.get('rx_hex',''));c=binascii.crc_hqx(tx,0xffff);length=int.from_bytes(tx[28:30],'little')
        ck(r.get('ok')==1,f'result {r}');ck(r['tag']==tag,'tag');ck(r['rx_len']==length,'valid length');ck(r['rx_frame_bytes']==96,'body length')
        ck(rx==tx,'all 96 received bytes incl header/padding');ck(r['tx_bits']==784 and r['rx_bits']==784,'wire bit count');ck(r['crc_calc']==c and r['crc_recv']==c,'independent CRC16');ck(r['result_code']==0,'result code')
        vec.write(json.dumps({'tag':tag,'tx_hex':tx.hex(),'result':r,'independent_crc16':c})+'\n');vec.flush();frames+=1;bytes_checked+=96
        return r
    try:
        ping=good('PING');ck(ping['version']==VERSION and ping['protocol'] ==PROTOCOL,'matching firmware')
        good('NETSTOP');clean();s=good('STATUS');ck(s['gain_q15']==32768 and s['sigma']==0,'ideal channel')
        rng=random.Random(20261010);seq=100
        for pattern in range(4):
            for n in (1,2,3,4,7,15,16,31,32,33,63,64):
                clean();seq+=1
                data=bytes((0 if pattern==0 else 255 if pattern==1 else (0xaa if i%2==0 else 0x55) if pattern==2 else rng.randrange(256)) for i in range(n))
                tx=frame(data,seq);good(f'LOAD {seq} {tx.hex()}');good('START');r=verify(tx,seq)
        # A received result cannot be overwritten before explicit release.
        ck(cmd('START')['code']==2,'pending start rejected');ck(cmd('WRITE 256 0')['code']==2,'pending overwrite rejected')
        r2=cmd('RESULT');ck(bytes.fromhex(r2['rx_hex'])==tx,'RX preserved after rejected writes')
        clean();ck(read(512)==0 and read(52)==9,'stale RX hidden')
        for n in (0,65):
            write(4,n);ck(cmd('START')['code']==3,'invalid lengths rejected')
        write(4,1);ck(cmd('START')['code']==4,'unwritten TX rejected')
        seq+=1;tx=frame(bytes(range(64)),seq);good(f'LOAD {seq} {tx.hex()}');write(4,63);ck(cmd('START')['code']==5,'header length mismatch')
        clean();good(f'LOAD {seq} {tx.hex()}');write(72,1);good('START')
        ck(good('STATUS')['status']&1,'RX hold causes busy')
        ck(cmd('START')['code']==1,'busy start rejected');ck(cmd('WRITE 256 0')['code']==1,'busy write rejected');ck(cmd('RELEASE')['code']==1,'busy release rejected')
        write(72,0);verify(tx,seq)
        # Correct payload with one bad transmitted CRC bit cannot be exposed.
        clean();good(f'LOAD {seq} {tx.hex()}');write(12,1);good('START');r=wait()
        ck(r['result_code']==1 and r['ok']==0 and r['rx_len']==0 and r['rx_hex']=='','CRC rejection');ck(read(512)==0,'bad CRC RX hidden')
        clean();good(f'LOAD {seq} {tx.hex()}');write(72,1);good('START');good('ABORT');r=cmd('RESULT')
        ck(r['result_code']==3 and r['rx_hex']=='' and not r['status']&1,'abort complete');ck(read(512)==0,'aborted RX hidden')
        clean();good(f'LOAD {seq} {tx.hex()}');good('START');verify(tx,seq)
        clean();good(f'LOAD {seq} {tx.hex()}');write(72,1);write(48,1000);good('START');r=wait()
        ck(r['result_code']==4 and r['rx_len']==0 and r['rx_hex']=='','timeout terminal')
        clean();good(f'LOAD {seq} {tx.hex()}');good('START');verify(tx,seq)
        partial=good('ABORTTEST');ck(256<=partial['rx_bits_before_abort']<784 and partial['result_code']==3 and partial['rx_len']==0,'mid-frame abort')
        clean();good(f'LOAD {seq} {tx.hex()}');good('START');verify(tx,seq)
        # More than a thousand ARM-originated transactions; every byte checked by ARM.
        clean();stress=good('SELFTEST 1024',timeout=30);ck(stress['passed']==1024 and stress['bytes_compared']==98304 and stress['generation_delta']==1024,'1024 stress cycles')
        # Public SEND convenience path, checked against an independent header encoder.
        clean();payload=b'ARM -> FPGA DBPSK -> ARM';tag=424242;good(f'SEND {tag} {payload.hex()}');r=wait()
        expected=struct.pack('<BBBBBBBBIIHHQHBB',1,1,0,1,1,0,1,0,0x13,tag,0,1,0,len(payload),0,0)+payload+bytes(64-len(payload))
        ck(bytes.fromhex(r['rx_hex'])==expected and r['ok']==1,'SEND payload exact')
        vec.write(json.dumps({'tag':tag,'tx_hex':expected.hex(),'result':r})+'\n');frames+=1;bytes_checked+=96
        clean();ck(cmd('SEND 1 0')['error']=='HEX_LENGTH','odd hex rejected');ck(cmd('SEND 1 '+('00'*65))['error']=='HEX_LENGTH','oversize rejected')
        ck(cmd('WRITE 512 123')['code']==7,'RX read only');ck(cmd('WRITE 768 123')['code']==8,'unmapped write safe');ck(cmd('WRITE 0 3')['code']==6,'bad command safe');ck(cmd('WRITE 48 0')['code']==10,'timeout range safe')
        good('RELEASE');good('PING')
        result={'pass':True,'transport':'UART','port':args.port,'version':VERSION,'checks':checks,'host_verified_frames':frames,'host_compared_bytes':bytes_checked,'arm_stress_frames':1024,'arm_stress_compared_bytes':98304,'ideal_gain_q15':32768,'noise_sigma':0,'time':time.strftime('%Y-%m-%d %H:%M:%S')}
        (out/'acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('HARDWARE_PAYLOAD_PASS '+json.dumps(result),flush=True)
        print('evidence='+str(out),flush=True)
    except BaseException as e:
        (out/'failure.json').write_text(json.dumps({'error':str(e),'checks':checks,'frames':frames},indent=2),encoding='utf-8');raise
    finally:ser.close();log.close();vec.close()
if __name__=='__main__':main()
