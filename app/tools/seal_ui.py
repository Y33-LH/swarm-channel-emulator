"""Seal UI-only release; FPGA/ARM binaries must remain identical to the accepted parent."""
from pathlib import Path
import json,hashlib,datetime
root=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
parent=json.loads((root/'docs/parent_release.json').read_text())
old={x['path']:x['sha256'] for x in parent['artifacts']}
for path in old:
    if path.split('/')[0] in ('ready','rtl','sw','hw'):
        assert sha(root/path)==old[path], 'Unexpected FPGA/ARM change: '+path
files=[p for area in ('sw','rtl','hw','tests','tools','docs','ui','reference','media','configs','skill','ready') for p in (root/area).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
files.extend(p for p in root.iterdir() if p.is_file() and p.suffix in ('.ps1','.tcl','.cmd','.txt','.md'))
m=dict(schema=1,name='step21_workbench',development=True,accepted=False,version=parent['version'],protocol=17,pl_hz=62500000,
       bit=parent['bit'],init=parent['init'],elf=parent['elf'],toolchain=parent['toolchain'],part=parent['part'],
       parent_manifest_sha256=sha(root/'docs/parent_release.json'),acceptance_scope='UI revision; unchanged accepted FPGA/ARM images. New UI qualification is recorded separately.',
       created=datetime.datetime.now().isoformat(),artifacts=[dict(path=p.relative_to(root).as_posix(),sha256=sha(p)) for p in sorted(set(files))])
(root/'release.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
print('UI_MANIFEST',len(files))
