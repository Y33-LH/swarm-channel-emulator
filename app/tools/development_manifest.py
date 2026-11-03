"""Hash development artifacts without representing them as accepted test results."""
from pathlib import Path
import json,hashlib,datetime,shutil,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from firmware_contract import VERSION_HEX,PROTOCOL,BUILD
from pcap_image import derive
root=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ws=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/'sdk_workspace_product'
if not ws.is_relative_to(root):raise ValueError('SDK workspace must remain inside project')
elf=ws/'swarm_app/Debug/swarm_app.elf'
for p in (root/'sw').iterdir():
    if p.is_file():assert sha(p)==sha(ws/'swarm_app/src'/p.name),f'Firmware not rebuilt: {p.name}'
assert elf.is_file()
assert BUILD.encode() in elf.read_bytes(),"ELF build identity is stale; force rebuild before packaging"
build=json.loads((root/'docs/product_build.json').read_text())
assert sha(root/'ready/system_wrapper.bit')==build['bit_sha256'],'Ready FPGA image differs from audited build'
packaged=Path(build['build'])/'core/ip_repo/swarm_minimal/src'
compiled_rtl=[]
for p in packaged.iterdir():
    if p.is_file():
        assert sha(root/'rtl'/p.name)==sha(p),f'FPGA source not rebuilt: {p.name}'
        compiled_rtl.append(p.name)
assert {'axi_minimal.sv','phy_receiver.sv','hardware_node.sv','two_path_link.sv'}<=set(compiled_rtl)
hdf=Path(build['build'])/'board/swarm.hdf'
assert sha(hdf)==build['hdf_sha256'],'HDF differs from audited FPGA build'
for source,name in ((elf,'swarm_app.elf'),(ws/'swarm_hw/ps7_init.tcl','ps7_init.tcl'),(hdf,'system.hdf')):
    shutil.copy2(source,root/'ready'/name)
pcap=derive(root/'ready/system_wrapper.bit',root/'ready/system_wrapper_pcap.bin')
(root/'ready/pcap_source.json').write_text(json.dumps(pcap,indent=2))
files=[p for area in ('sw','rtl','hw','tests','tools','docs','ui','reference','media','configs','skill','ready') for p in (root/area).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
files.extend(p for p in root.iterdir() if p.is_file() and p.suffix in ('.ps1','.tcl','.cmd','.txt','.md'))
files.extend(p for p in (root/'openocd').iterdir() if p.is_file() and p.suffix in ('.tcl','.cfg'))
m=dict(schema=1,name=root.name,development=True,accepted=False,version=VERSION_HEX,protocol=PROTOCOL,arm_build=BUILD,pl_hz=62500000,
       bit='ready/system_wrapper.bit',init='ready/ps7_init.tcl',elf='ready/swarm_app.elf',pcap='ready/system_wrapper_pcap.bin',
       toolchain='Vivado + SDK 2018.3',part='xc7z020clg400-2',compiled_rtl=sorted(compiled_rtl),created=datetime.datetime.now().isoformat(),
       artifacts=[dict(path=p.relative_to(root).as_posix(),sha256=sha(p)) for p in sorted(set(files))])
(root/'release.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
print('DEVELOPMENT_MANIFEST',len(files))
