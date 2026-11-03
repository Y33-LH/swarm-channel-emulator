"""Physical PL channel and protocol diagnostics, independent UART byte comparison."""
import binascii,json,random,struct,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps')]
import serial
from serial_json import JsonSerial
from acceptance import frame

def main():
    out=ROOT/'results'/time.strftime('paths_%Y%m%d_%H%M%S');out.mkdir();evidence=[]
    transcript=(out/'uart.jsonl').open('w')
    with serial.Serial('COM4',230400,timeout=.2,write_timeout=3) as s:
        s.reset_input_buffer();client=JsonSerial(s,max_line=16384)
        def cmd(text):
            r=client.request(text,15);transcript.write(json.dumps({'command':text,'response':r})+'\n');transcript.flush();return r
        def good(text):
            r=cmd(text);assert r['ok']==1,(text,r);return r
        def read(off):return good(f'READ {off}')['value']
        assert good('PING')['version']==0x90001
        def transaction(params,seed=9,ack=False):
            good('RELEASE')
            settings={12:0,48:1000000,64:32768,68:0,80:0,84:0,88:seed,92:0,96:0,112:0,116:int(ack),120:0,124:0,128:0,132:0,136:0,140:0};settings.update(params)
            for off,v in settings.items():good(f'WRITE {off} {v&0xffffffff}')
            if ack:
                tx=struct.pack('<IIHBB',7,99,3,4,0)+bytes(84)
                good('WRITE 4 12');good('WRITE 8 99')
                for i in range(0,96,4):good(f'WRITE {256+i} {int.from_bytes(tx[i:i+4],"little")}')
            else:
                tx=frame(random.Random(723).randbytes(64),99);good(f'LOAD 99 {tx.hex()}')
            good('START')
            until=time.monotonic()+5
            while not good('STATUS')['status']&2:
                if time.monotonic()>until:raise TimeoutError('PL terminal state')
            r=cmd('RESULT');metrics={str(a):read(a) for a in (100,104,144,156,160,164,168,172,176,180,184)}
            if r['ok']:
                assert bytes.fromhex(r['rx_hex'])==tx
                assert r['rx_frame_bytes']==(12 if ack else 96)
                assert r['rx_bits']==(112 if ack else 784)
                assert r['crc_calc']==binascii.crc_hqx(tx[:12] if ack else tx,0xffff)
            else:assert r['rx_hex']=='' and r['rx_len']==0
            row={'settings':settings,'result':r,'metrics':metrics};evidence.append(row);return row
        # Independently rotated two paths, delayed arrival, both CFO signs, fractional gain ramps.
        for i in range(12):
            cfo=(-1 if i%2 else 1)*(100+75*i)
            row=transaction({64:22000,80:i*83,112:512 if i==11 else i*13,84:i*0x1597531,92:round(cfo*2**32/8e6),120:1800,124:(i%4)+1,128:(i*0x7654321)^0x56789abc,132:round((cfo+8)*2**32/8e6),136:-4096,140:1024})
            assert row['result']['ok']==1 and row['metrics']['160']==0,row
        noise=[]
        for sigma in (0,2048,3072):
            for seed in range(1,17):noise.append(transaction({68:sigma},seed))
        # Identical waveform/configuration/seed must reproduce bits and counters exactly.
        a=transaction({68:3072,112:23,120:1000,124:3},77)
        b=transaction({68:3072,112:23,120:1000,124:3},77)
        for key in ('ok','rx_hex','rx_bits','result_code','crc_calc','crc_recv'):assert a['result'][key]==b['result'][key]
        assert a['metrics']==b['metrics']
        assert sum(r['metrics']['160'] for r in noise if r['settings'][68]==0)==0
        assert sum(r['metrics']['160'] for r in noise if r['settings'][68]==3072)>0,'No measured errors at high noise'
        a=transaction({},ack=True);assert a['result']['ok']==1 and a['metrics']['164']==96
        b=transaction({});assert b['result']['ok']==1 and b['metrics']['164']==768
        # A real lost reverse ACK must force retransmission and suppress duplicate delivery.
        good('NETSTOP');good('MEDIACLEAR 0 0');good('NETACKDROP 1');good('NETSTART 3 20261009 1');r=good('NETSTEP 30')
        assert r['running']==0 and r['generated']==48 and r['delivered']==48,r
        assert sum(l[4] for l in r['links'])>=1 and sum(l[6] for l in r['links'])>=1,r
        assert r['links'][16][0]>r['links'][16][2],r
        assert r['slot_misses']==0
        # Abort an active scenario, start afresh, do not reuse counters/receive buffers.
        good('NETSTART 120 20261009 1');good('NETSTEP 1');good('NETSTOP');good('NETSTART 3 20261009 1');fresh=good('NETSTEP 30')
        assert fresh['generated']==48 and fresh['delivered']==48 and fresh['queue_drops']==0
        assert sum(l[4] for l in fresh['links'])==0 and fresh['slot_misses']==0
        good('NETSTOP');good('NETACKDROP 0');good('RELEASE')
    transcript.close();(out/'acceptance.json').write_text(json.dumps({'pass':True,'cases':evidence,'forced_ack_loss':r,'restart':fresh},indent=2))
    print('HARDWARE_PATH_ACK_RETRY_PASS evidence='+str(out),flush=True)
if __name__=='__main__':main()
