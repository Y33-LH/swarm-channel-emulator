"""Physical-board acceptance of independently generated PL node business."""
from pathlib import Path
import sys,json,time,struct
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps')]
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX
import serial
from serial_json import JsonSerial
from product_config import validate,encode

def run(port='COM4'):
    out=ROOT/'results'/time.strftime('mixed_nodes_%Y%m%d_%H%M%S');out.mkdir()
    with (out/'uart.jsonl').open('w') as log,serial.Serial(port,230400,timeout=.2,write_timeout=5) as uart:
        uart.reset_input_buffer();client=JsonSerial(uart);checks=0
        def cmd(text,ok=1):
            nonlocal checks
            r=client.request(text,40);log.write(json.dumps(dict(command=text,response=r))+'\n');log.flush()
            assert r.get('ok')==ok,(text,r);checks+=1;return r
        def nodes():return {r[0]:r for r in cmd('HNSTATUS')['hardware_nodes']}
        def control(cid,node,op,value,ttl=10000):cmd('GCOMMAND '+struct.pack('<5I',cid,node,op,value,ttl).hex())
        p=cmd('PING');assert p['version']==VERSION and p['protocol'] ==PROTOCOL,p
        cmd('NETSTOP');cmd('HNENABLE 9x 1',0);cmd('HNENABLE 9 nope',0);cmd('HNRESET 9x',0);cmd('HNENABLE 9 1');cmd('HNENABLE 13 1')
        cmd('SCENECFG '+encode(validate({'environment':1,'formation':7,'faults':0})).hex())
        cmd('MEDIACLEAR 0 0');cmd('NETLOAD 0');cmd('NETFEC 1');cmd('NETACKDROP 0')
        cmd('NETSTART 90 77 1');first=cmd('NETFAST 20');full=cmd('NETSTATUS');assert first['links']==full['links'] and first['watch_iq']==full['watch_iq'];hn=nodes()
        assert first['generated']==32 and first['delivered']==32,first
        assert all(n[9]==2 for n in first['nodes']),first['nodes']
        assert all(n[2]==2 and n[6]==2 and n[5]==0 for n in hn.values()),hn
        assert first['nodes'][8][6]>0 and first['nodes'][12][6]>0
        # PL receives command bytes through PHY, responds through PHY and applies
        # a new heartbeat period. Drop a real final-hop ACK to force duplicate RX.
        control(101,9,2,2000);cmd('GACKDROP 101');control(102,13,1,0)
        control(103,13,2,151);control(104,9,5,450)
        after=cmd('NETSTEP 200');hn=nodes();results=cmd('CMDSTATUS')
        rows={r[0]:r for r in results['commands']}
        assert rows[101][4]==2 and rows[101][7]==2000,rows
        assert rows[102][4]==2 and rows[103][4]==3 and rows[104][4]==2,rows
        trace=cmd('CMDTRACE');assert dict(trace['executions'])[101]==1,trace
        assert hn[9][11]>=1 and hn[9][13]==2000 and hn[9][16]==450,hn
        assert after['nodes'][8][6]==450000,after['nodes'][8]
        assert hn[9][2]<hn[13][2],hn
        # Node 9 isolation cannot prevent node 13 and fourteen ARM nodes working.
        cmd('HNENABLE 9 0');before=nodes();cmd('NETSTEP 30');disabled=nodes()
        assert disabled[9][2]==before[9][2] and disabled[13][2]>before[13][2],disabled
        cmd('HNRESET 9',0);cmd('HNENABLE 9 1');cmd('NETSTEP 20');reenabled=nodes()
        assert reenabled[9][2]>disabled[9][2],reenabled
        cmd('NETSTOP');before=nodes();cmd('HNRESET 9');isolated=nodes()
        assert isolated[9][18]==before[9][18]+1 and isolated[13]==before[13],isolated
        cmd('NETSTART 2 78 1');again=cmd('NETSTEP 20');reset=nodes()
        plain=cmd('NETSTATUS')
        for field in ('links','watch_iq','applied_links'):
            assert again[field]==plain[field],('Compact full telemetry differs from plain register/counter snapshot',field)
        assert again['generated']==again['delivered']==32 and all(n[13]==1000 for n in reset.values()),again
        mem=cmd('MEMORY');assert mem['stack_guard_ok'] and not mem['heap_failures'],mem
    report=dict(pass_mixed_nodes=True,checks=checks,version=VERSION_HEX,hardware_nodes=[9,13],virtual_nodes=14,
        scope='Real UART board run; PL-generated heartbeat/response and decoded command/ACK; isolated disable/reset; all packets through shared FPGA PHY.',
        first=first,commands=results,hardware_after_commands=hn,reset=reset,memory=mem)
    (out/'acceptance.json').write_text(json.dumps(report,indent=2));print('MIXED_HARDWARE_PASS',out,flush=True)
if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else 'COM4')
