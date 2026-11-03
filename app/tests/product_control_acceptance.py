"""Physical-board test: uplink external bytes and reverse multi-hop business commands."""
from pathlib import Path
import sys,struct,json,time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/python_deps')]
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX
import serial
from serial_json import JsonSerial
from product_config import validate,encode
from endpoint_gateway import EndpointGateway

def run(port='COM4'):
    out=ROOT/'results'/time.strftime('controls_%Y%m%d_%H%M%S');out.mkdir();log=(out/'uart.jsonl').open('w');checks=0
    with serial.Serial(port,230400,timeout=.2,write_timeout=5) as s:
        s.reset_input_buffer();c=JsonSerial(s)
        def cmd(text,ok=1):
            nonlocal checks
            r=c.request(text,30);log.write(json.dumps(dict(command=text,response=r))+'\n');log.flush();checks+=1;assert r['ok']==ok,(text,r);return r
        ping=cmd('PING');assert ping['version']==VERSION and ping['protocol'] ==PROTOCOL
        cmd('NETSTOP');cmd('SCENECFG '+encode(validate({'environment':1,'formation':7,'external_node':1,'faults':0})).hex());cmd('MEDIACLEAR 0 0');cmd('NETLOAD 0');cmd('NETFEC 1');started=cmd('NETSTART 90 77 1')
        xyz=struct.pack('<4i',4900000,4700000,420000,0)
        gateway=EndpointGateway(1,started['run_id']);registration=gateway.register(dict(v=1,type='HELLO',node=1,identity='single_board_protocol_test',capabilities=['heartbeat','bytes']))
        request=gateway.accept(dict(v=1,type='DATA',node=1,identity='single_board_protocol_test',run_id=started['run_id'],model_ms=0,sequence=1,kind=1,payload_hex=xyz.hex()),0)
        cmd(request['command']);first=cmd('NETSTEP 10');assert first['nodes'][0][4:7]==[4900000,4700000,420000] and first['nodes'][0][9]==1
        (out/'endpoint_registration.json').write_text(json.dumps(registration,indent=2))
        # Arbitrary bytes, not regenerated PN or a fixed canned answer.
        payload=bytes.fromhex('00112200ff804142434445deadbeef')
        injected=cmd('EXTINJECT 1 5 '+payload.hex());cmd('NETSTEP 10');received=bytes.fromhex(cmd('EXTRX')['frame_hex'])
        assert received[32:32+len(payload)]==payload and int.from_bytes(received[12:16],'little')==injected['sequence']
        assert received[4]==1 and received[5]==0 and received[6]==4 and received[7]==0
        before=cmd('NETSTATUS')
        def command(cid,node,opcode,value,ttl=10000):return cmd('GCOMMAND '+struct.pack('<5I',cid,node,opcode,value,ttl).hex())
        command(101,5,1,0);command(102,9,2,2000);command(103,5,3,1);command(104,5,4,2);command(105,16,5,450)
        command(106,8,2,151) # Rejection originates at destination, returns through PL.
        command(107,1,1,0,100) # Four reverse hops cannot meet a 100ms expiry.
        cmd('GCOMMAND '+struct.pack('<5I',101,5,1,0,10000).hex(),0)
        after=cmd('NETSTEP 200');status=cmd('CMDSTATUS');byid={row[0]:row for row in status['commands']}
        for cid in (101,102,103,104,105):assert byid[cid][4]==2,(cid,byid)
        assert byid[106][4]==3 and byid[107][4]==4,byid
        assert any(x[19]>y[19] for x,y in zip(after['links'][16:],before['links'][16:])), 'No downlink DATA traversed PL'
        assert after['nodes'][15][6]==450000,after['nodes'][15]
        command(108,5,3,0);cmd('NETSTEP 100');assert cmd('CMDSTATUS')['commands'][-1][4]==2
        command(109,2,2,5000);cmd('GACKDROP 109');cmd('NETSTEP 100')
        confirmed=cmd('CMDSTATUS');assert confirmed['commands'][-1][4]==2 and confirmed['commands'][-1][7]==5000
        trace=cmd('CMDTRACE');executions=dict(trace['executions']);assert executions[109]==1
        events=[x for x in trace['hops'] if x[1]==109 and x[2]==6 and x[4]==2]
        assert any(x[6]==1 and x[7]==1 and x[8]==0 for x in events),events
        assert any(x[7]==2 and x[8]==1 for x in events),events
        for kind,path in ((6,[(0,8),(8,7),(7,6),(6,5)]),(7,[(5,6),(6,7),(7,8),(8,0)])):
            observed={(x[3],x[4]) for x in trace['hops'] if x[1]==101 and x[2]==kind and x[6] and x[7] and x[8]}
            assert observed==set(path),(kind,observed)
        (out/'command_trace.json').write_text(json.dumps(trace,indent=2))
        invalid=struct.pack('<4i',11000000,0,400000,0).hex();cmd('EXTINJECT 1 1 '+invalid,0)
        cmd('NETSTOP');memory=cmd('MEMORY');assert memory['stack_guard_ok'] and not memory['heap_failures']
        # Run restart must clear command state, positions and external received bytes.
        cmd('NETSTART 1 78 1');assert cmd('CMDSTATUS')['commands']==[];cmd('EXTRX',0);cmd('NETSTEP 10');cmd('NETSTOP')
    report=dict(pass_controls=True,checks=checks,source='physical_board_FPGA_RX',scope='single-board emulated external endpoint; reverse commands and result packets each traverse physical PL; one lost ACK causes retransmission but exactly one destination execution; no second board tested',final_commands=confirmed,memory=memory)
    (out/'acceptance.json').write_text(json.dumps(report,indent=2));print('PRODUCT_CONTROLS_PASS',out,flush=True)
    return report

if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else 'COM4')
