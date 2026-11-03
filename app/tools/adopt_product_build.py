from pathlib import Path
import json,hashlib,re,shutil,zipfile,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from firmware_contract import VERSION_HEX
root=Path(__file__).resolve().parents[1]
build=Path(sys.argv[1]).resolve();board=build/'board'
workspace=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else root/'sdk_workspace_product'
if not workspace.is_relative_to(root):raise ValueError('SDK workspace outside product workspace')
if not build.is_relative_to((root/'results').resolve()):raise ValueError('Build outside product workspace')
u=(board/'board_utilization.rpt').read_text();t=(board/'board_timing.rpt').read_text();d=(board/'board_drc.rpt').read_text()
lines=t.splitlines();i=next(i for i,s in enumerate(lines) if 'WNS(ns)' in s and 'WHS(ns)' in s);a=lines[i+2].split();assert float(a[0])>=0 and float(a[4])>=0 and float(a[8])>=0,a
assert not re.search(r'\|\s*[^|]+\|\s*(?:Critical Warning|Error)\s*\|',d), 'Inspect DRC severity before adoption'
assert 'REQP-1839' not in d and 'REQP-1840' not in d, 'BRAM async control risk remains'
assert re.search(r'There are 0 pins that are not constrained for maximum delay\.',t),'Unconstrained timing endpoints'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
packaged_files=list((build/'core/ip_repo/swarm_minimal/src').iterdir())
assert 'hardware_node.sv' in {p.name for p in packaged_files} and {'axi_minimal.sv','phy_receiver.sv','dbpsk_capture.sv','fec_decoder.sv','two_path_link.sv'}<={p.name for p in packaged_files}
for packaged in packaged_files:
    assert sha(root/'rtl'/packaged.name)==sha(packaged),packaged.name
bit=board/'board.runs/impl_1/system_wrapper.bit';hdf=board/'swarm.hdf'
with zipfile.ZipFile(hdf) as z:
    name=next(x for x in z.namelist() if x.endswith('ps7_init.tcl'))
    init=z.read(name)
    existing=(workspace/'swarm_hw/ps7_init.tcl').read_bytes()
    assert init.replace(b'\r\n',b'\n')==existing.replace(b'\r\n',b'\n'), 'PS initialization changed: regenerate BSP'
shutil.copy2(bit,root/'ready/system_wrapper.bit');shutil.copy2(hdf,root/'ready/system.hdf')
def resource(label):
    row=next(x for x in u.splitlines() if re.match(r'\|\s*'+re.escape(label)+r'\s*\|',x));cells=[x.strip() for x in row.split('|')][1:-1]
    return dict(used=float(cells[1]),available=float(cells[-2]))
r={k:resource(v) for k,v in [('LUT','Slice LUTs'),('FF','Slice Registers'),('DSP48','DSPs'),('BRAM36','Block RAM Tile'),('Slice','Slice')]}
r.update(WNS_ns=float(a[0]),WHS_ns=float(a[4]),WPWS_ns=float(a[8]),pl_hz=62500000)
size=(workspace/'swarm_app/Debug/swarm_app.elf.size').read_text().splitlines()[1].split()
r.update(ARM_ELF_text_bytes=int(size[0]),ARM_ELF_data_bytes=int(size[1]),ARM_ELF_bss_bytes=int(size[2]),runtime_measurement_pending=True)
warnings=int(re.search(r'Violations found:\s*(\d+)',d).group(1))
(root/'results/resources.json').write_text(json.dumps(dict(version=VERSION_HEX,resources=r,source_build=str(board),build_accepted=True,hardware_acceptance_pending=True,
    drc=dict(errors=0,critical=0,warnings=warnings,qualification='DSP pipeline recommendations and any clock-buffer recommendations retained in raw report; no BRAM asynchronous-control DRC.'),
    memory_scope='ARM ELF static sections and measured stack/heap; not whole DDR or PC memory utilization'),indent=2))
(root/'docs/product_build.json').write_text(json.dumps(dict(build=str(build),sdk_workspace=str(workspace),bit_sha256=sha(bit),hdf_sha256=sha(hdf),wns_ns=float(a[0]),whs_ns=float(a[4]),rtl_verified=True,ps_init_identical=True,
    final_checkpoint=str(board/'board_physopt.dcp') if (board/'board_physopt.dcp').exists() else str(board/'board.runs/impl_1/system_wrapper_routed.dcp'),
    build_scripts_sha256={p.name:sha(p) for p in (root/'hw').glob('*.tcl')}),indent=2))
print('PRODUCT_BUILD_ADOPTED',json.dumps(r))
