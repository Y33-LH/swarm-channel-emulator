"""Create an isolated three-endpoint implementation candidate, never promote it.

Same core, queues, telemetry, sample clock and device as the current design.
The third generic endpoint (logical node 1) is MMIO-addressable and connected to
the shared TX/RX path so synthesis cannot discard it. This is a resource/timing
experiment, not a firmware-compatible or hardware-accepted release.
"""
from pathlib import Path
import shutil,json,hashlib,time
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'results'/time.strftime('endpoint3_feasibility_%Y%m%d_%H%M%S')
out.mkdir()
for area in ('rtl','hw'):shutil.copytree(ROOT/area,out/area)
p=out/'rtl/axi_minimal.sv';s=p.read_text()
s=s.replace('[11:0] s_axi_awaddr','[12:0] s_axi_awaddr').replace('[11:0] s_axi_araddr','[12:0] s_axi_araddr').replace('[11:0] awaddr','[12:0] awaddr')
start=s.index(' hardware_node #(.NODE_ID(13))');end=s.index(' wire [7:0] tx_input_byte',start)
clone=s[start:end].replace('NODE_ID(13)','NODE_ID(1)').replace('node13(', 'node1(').replace('hn13','hn1').replace("awaddr>=12'h800&&awaddr<12'hc00","awaddr>=13'h1000&&awaddr<13'h1400")
s=s[:end]+" wire [7:0] hn1_byte,hn1_ack;\n wire hn1_ready,hn1_ack_ready;\n wire [31:0] hn1_read,hn1_len,hn1_seq;\n"+clone+s[end:]
s=s.replace('tx_source==4?hn13_ack:tx_mem','tx_source==4?hn13_ack:tx_source==5?hn1_byte:tx_source==6?hn1_ack:tx_mem')
s=s.replace("tx_source==4?hn13_ack_ready:1'b0","tx_source==4?hn13_ack_ready:tx_source==5?hn1_ready:tx_source==6?hn1_ack_ready:1'b0")
s=s.replace("tx_source==2?hn13_len:32'd12","tx_source==2?hn13_len:tx_source==5?hn1_len:32'd12")
s=s.replace('(tx_source>=3)','(tx_source==3||tx_source==4||tx_source==6)')
s=s.replace("awaddr>=12'h400&&awaddr<12'hc00)begin end","(awaddr>=12'h400&&awaddr<12'hc00)||(awaddr>=13'h1000&&awaddr<13'h1400))begin end")
s=s.replace('if(merged>4)last_error<=ERR_RANGE;else tx_source','if(merged>6)last_error<=ERR_RANGE;else tx_source')
needle="else if(s_axi_araddr>=12'h800&&s_axi_araddr<12'hc00)s_axi_rdata<=hn13_read;"
assert needle in s;s=s.replace(needle,needle+"\n    else if(s_axi_araddr>=13'h1000&&s_axi_araddr<13'h1400)s_axi_rdata<=hn1_read;")
assert s.count('hardware_node #')==3 and 'tx_source==5?hn1_byte' in s
p.write_text(s)
p=out/'hw/check_core.tcl';p.write_text(p.read_text().replace('set_property range 4096 $block','set_property range 8192 $block'))
p=out/'hw/build_board.tcl';p.write_text(p.read_text().replace('-range 4K','-range 8K'))
plan=dict(created=time.strftime('%Y-%m-%dT%H:%M:%S'),part='xc7z020clg400-2',clock_hz=62500000,
    endpoints=[9,13,1],address_range_bytes=8192,third_endpoint_offset=4096,
    promotion_allowed=False,scope='Candidate implementation feasibility only, no firmware or hardware acceptance',
    baseline_bit_sha256=hashlib.sha256((ROOT/'ready/system_wrapper.bit').read_bytes()).hexdigest(),
    source_sha256={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for d in ('hw','rtl') for p in (out/d).iterdir() if p.is_file()})
(out/'plan.json').write_text(json.dumps(plan,indent=2))
print(out)
