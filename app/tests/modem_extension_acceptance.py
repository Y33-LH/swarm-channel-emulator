"""Same-frame/same-channel/same-seed comparison of two real PL metric modules."""
from pathlib import Path
import sys,json,time,hashlib,binascii
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps'),str(ROOT/'tests')]
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX
import serial
from serial_json import JsonSerial
from acceptance import frame

def run(port_name='COM9'):
    out=ROOT/'results'/time.strftime('modem_extension_%Y%m%d_%H%M%S');out.mkdir();rows=[]
    with serial.Serial(port_name,230400,timeout=.2,write_timeout=5) as port,(out/'uart.jsonl').open('w') as log:
        port.reset_input_buffer();client=JsonSerial(port)
        def cmd(t,ok=True):
            r=client.request(t,15);log.write(json.dumps(dict(command=t,response=r))+'\n');log.flush()
            if ok:assert r['ok'],(t,r)
            return r
        assert cmd('PING')['version']==VERSION;cmd('NETSTOP');cmd('RELEASE');cmd('WRITE 796 0')
        for index in range(25):
            tx=frame(hashlib.sha512(f'extension-pair-{index}'.encode()).digest(),11000+index)
            for mode in (0,1):
                cmd('RELEASE')
                regs={12:0,48:5000000,64:19661,68:0 if index<5 else 2800,72:0,80:37,84:298261618,88:20261018+index*773,92:214748,96:0,112:53,116:0,120:0,124:8,128:1073741824,132:214748,136:0,140:0,192:1,776:mode}
                for a,v in regs.items():cmd(f'WRITE {a} {v}')
                assert cmd('READ 776')['value']==mode
                cmd(f'LOAD {11000+index} {tx.hex()}');cmd('START');deadline=time.monotonic()+8
                while not cmd('STATUS')['status']&2:assert time.monotonic()<deadline
                result=cmd('RESULT',False);phy=cmd('PHYSTATS');rx=bytes.fromhex(result.get('rx_hex',''))
                if result['ok']:assert rx==tx and result['crc_calc']==result['crc_recv']==binascii.crc_hqx(tx,65535)
                else:assert not rx
                if index<5:assert result['ok'],(index,mode,result)
                rows.append(dict(pair=index,mode=mode,config=regs,tx_sha256=hashlib.sha256(tx).hexdigest(),delivered=bool(result['ok']),result=result,phy=phy))
        cmd('RELEASE');assert not cmd('WRITE 776 2',False)['ok'];assert cmd('READ 776')['value']==1
        cmd('RELEASE');cmd('WRITE 776 0')
    summary=[dict(mode=m,clean_success=sum(x['delivered'] for x in rows if x['mode']==m and x['pair']<5),noise_success=sum(x['delivered'] for x in rows if x['mode']==m and x['pair']>=5),noise_trials=20) for m in (0,1)]
    report=dict(pass_extension=True,version=VERSION_HEX,source='physical_board_UART',rows=rows,summary=summary,scope='Compatible DBPSK decision-metric replacement, not arbitrary runtime modulation upload; same information and channel per pair; all successes independently byte/CRC checked; no universal superiority claim')
    (out/'acceptance.json').write_text(json.dumps(report,indent=2));print('MODEM_EXTENSION_PASS',out,summary,flush=True)
if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else 'COM9')
