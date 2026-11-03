"""Stage-2 actual UART/FPGA acquisition evidence, including noise-only negatives."""
import argparse,binascii,json,random,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps')]
import serial
from serial_json import JsonSerial
from acceptance import frame
def main():
    p=argparse.ArgumentParser();p.add_argument('--port',default='COM4');args=p.parse_args()
    out=ROOT/'results'/time.strftime('acquisition_%Y%m%d_%H%M%S');out.mkdir()
    transcript=(out/'transcript.jsonl').open('w',encoding='utf-8');results=[]
    with serial.Serial(args.port,230400,timeout=.2,write_timeout=3) as s:
        s.reset_input_buffer();client=JsonSerial(s)
        def cmd(text):
            r=client.request(text,5);transcript.write(json.dumps({'command':text,'reply':r})+'\n');transcript.flush();return r
        def good(text):
            r=cmd(text);assert r.get('ok')==1,(text,r);return r
        assert good('PING')['version']==0x90001
        cases=[]
        for i in range(24):cases.append(dict(delay=(i*43)%1024,phase=(i*0x13579bdf)&0xffffffff,sigma=(i%4)*256,suppress=0))
        for i in range(8):cases.append(dict(delay=i*53,phase=i*0x12345678,sigma=i*1024,suppress=1))
        cases.append(dict(delay=1023,phase=0xc0000000,sigma=0,suppress=0))
        for i,c in enumerate(cases):
            good('RELEASE')
            for off in (112,116,120,124,128,132,136,140):good(f'WRITE {off} 0')
            for off,val in {12:0,48:5000000,64:32768,68:c['sigma'],80:c['delay'],84:c['phase'],88:20261011+i,92:0,96:c['suppress']}.items():good(f'WRITE {off} {val}')
            data=random.Random(i+10).randbytes(64);tx=frame(data,i+1)
            good(f'LOAD {i+1} {tx.hex()}');good('START')
            deadline=time.monotonic()+4
            while not good('STATUS')['status']&2:
                if time.monotonic()>deadline:raise TimeoutError('terminal result')
            r=cmd('RESULT');cap=good('READ 100')['value'];sample_count=good('READ 104')['value']
            if c['suppress']:assert r['ok']==0 and r['rx_hex']=='' and r['result_code']==5 and cap==0 and sample_count==8192,(c,r,cap,sample_count)
            else:assert r['ok']==1 and bytes.fromhex(r['rx_hex'])==tx and cap==1 and r['crc_calc']==binascii.crc_hqx(tx,0xffff),(c,r,cap)
            results.append(dict(parameters=c,result=r,captures=cap,samples=sample_count,tx_hex=tx.hex()))
        good('RELEASE')
        for off,val in {68:0,80:0,84:0,88:1,92:0,96:0}.items():good(f'WRITE {off} {val}')
    transcript.close()
    report={'pass':True,'version':'00090001','cases':results,'positive':25,'noise_only':8,'scope':'rectangular 4sps baseline; unknown frame start and fixed phase; no RRC/FEC/Gardner/estimated CFO yet'}
    (out/'acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('HARDWARE_DBPSK_ACQUISITION_PASS cases=33 evidence='+str(out))
if __name__=='__main__':main()
