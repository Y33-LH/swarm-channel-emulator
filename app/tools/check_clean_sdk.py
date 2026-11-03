"""Verify fresh BSP/app build produces identical loadable bytes and memory layout."""
from pathlib import Path
import sys,subprocess,hashlib,json,struct
ROOT=Path(__file__).resolve().parents[1]
fresh=Path(sys.argv[1]).resolve()
assert fresh.is_relative_to((ROOT/'results').resolve())
original=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else Path(json.loads((ROOT/'docs/product_build.json').read_text())['sdk_workspace'])
assert original.is_relative_to(ROOT)
tool=Path(r'D:\Xilinx\SDK\2018.3\gnu\aarch32\nt\gcc-arm-none-eabi\bin\arm-none-eabi-objcopy.exe')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def segments(p):
    data=p.read_bytes();assert data[:7]==b'\x7fELF\x01\x01\x01'
    phoff=struct.unpack_from('<I',data,28)[0];size,count=struct.unpack_from('<HH',data,42)
    return [struct.unpack_from('<8I',data,phoff+i*size) for i in range(count)]
for p in (ROOT/'sw').iterdir():
    if p.is_file():assert sha(p)==sha(fresh/'swarm_app/src'/p.name)
files=[]
for label,ws in [('original',original),('clean',fresh)]:
    elf=ws/'swarm_app/Debug/swarm_app.elf';dest=fresh/(label+'.bin')
    subprocess.run([str(tool),'-O','binary',str(elf),str(dest)],check=True)
    files.append((elf,dest))
assert sha(files[0][1])==sha(files[1][1]),'Different loadable program bytes'
assert segments(files[0][0])==segments(files[1][0]),'Different ELF program/memory layout'
report=dict(**{'pass':True},scope='Fresh SDK hardware/BSP/application workspace rebuild; same computer/toolchain, not independent other-PC validation',
    workspace=str(fresh),elf_sha256=sha(files[0][0]),clean_elf_sha256=sha(files[1][0]),loadable_sha256=sha(files[0][1]),
    sw_sha256={p.name:sha(p) for p in (ROOT/'sw').iterdir() if p.is_file()},build_script_sha256=sha(ROOT/'build_sdk.tcl'))
(fresh/'acceptance.json').write_text(json.dumps(report,indent=2));print('CLEAN_SDK_REBUILD_PASS',fresh)
