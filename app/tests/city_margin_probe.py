"""Measure the uncoded receiver margin using real city IQ channel settings."""
import sys,json,time,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'tools/python_deps'),str(ROOT/'reference')]
import serial
from serial_json import JsonSerial
from acceptance import frame
from reference_scenario import channel
out=ROOT/'results'/time.strftime('city_margin_%Y%m%d_%H%M%S');out.mkdir()
rows=[]
with serial.Serial('COM4',230400,timeout=.2,write_timeout=3) as s:
    client=JsonSerial(s,max_line=16384);s.reset_input_buffer()
    def cmd(text):return client.request(text,10)
    def good(text):
        r=cmd(text);assert r.get('ok')==1,(text,r);return r
    good('NETSTOP')
    for snr in (30,34):
        for t in (625,710,750,850):
            for link in (3,7,11,15):
                c=channel(link,t,reference_snr_db=24,echo_offset_db=0);tx=frame(bytes(range(64)),71)
                # Explicit fallback profile: weaker, still nonzero delayed echo.
                echo_factor=10**(-6/20);old_r=10**(-6/20)
                norm=math.sqrt(1+old_r*old_r)/math.sqrt(1+(old_r*echo_factor)**2)
                c['gain0']*=norm;c['gain1']*=norm*echo_factor
                good('RELEASE')
                word=lambda p:round(p/(2*math.pi)*2**32)&0xffffffff
                settings={12:0,48:1000000,64:round(min(1,c['gain0'])*32768),68:round(c['sigma']*10**((24-snr)/20)),80:link*7%61,84:word(c['phase_radians']),88:c['noise_seed'],92:round(c['cfo_hz']*2**32/8e6)&0xffffffff,96:0,112:round(c['delay_samples']),116:0,120:round(min(1,c['gain1'])*32768),124:round(c['echo_delay_samples']),128:word(c['echo_phase_radians']),132:round(c['echo_cfo_hz']*2**32/8e6)&0xffffffff,136:0,140:0}
                for a,v in settings.items():good(f'WRITE {a} {v}')
                good(f'LOAD 71 {tx.hex()}');good('START')
                while not good('STATUS')['status']&2:pass
                r=cmd('RESULT');errs=good('READ 160')['value']
                if r['ok']:assert bytes.fromhex(r['rx_hex'])==tx
                rows.append({'snr_reference_db':snr,'echo_offset_db':-6,'t':t,'link':link,'ok':r['ok'],'code':r['result_code'],'bit_errors':errs,'sigma':settings[68]})
        print(json.dumps({'snr_reference_db':snr,'received':sum(r['ok'] for r in rows if r['snr_reference_db']==snr),'trials':16}),flush=True)
    good('RELEASE')
(out/'results.json').write_text(json.dumps(rows,indent=2));print('CITY_MARGIN_MEASURED '+str(out))
