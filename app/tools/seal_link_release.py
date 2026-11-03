"""Record an exact candidate manifest. This script does not confer acceptance."""
from pathlib import Path
import json,hashlib,datetime
root=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
parent=json.loads((root/'docs/parent_step23_release.json').read_text('utf-8'))
m={k:parent[k] for k in ('version','protocol','pl_hz','bit','elf','init','toolchain','part')}
m.update(schema=1,name=root.name,development=True,accepted=False,
         created=datetime.datetime.now().isoformat(),
         parent_manifest_sha256=sha(root/'docs/parent_step23_release.json'),
         acceptance_scope='Commands, observed effects and shared experiment context; FPGA and ARM unchanged. New scoped acceptance required.',
         artifacts=[])
for p in sorted(root.rglob('*')):
    if not p.is_file() or p.name=='release.json' or p.suffix=='.pyc':continue
    rel=p.relative_to(root)
    if rel.parts[0] in ('results','exports','configs','sdk_workspace_product') or '__pycache__' in rel.parts:continue
    m['artifacts'].append(dict(path=rel.as_posix(),sha256=sha(p)))
(root/'release.json').write_text(json.dumps(m,indent=2,ensure_ascii=False),encoding='utf-8')
print('CANDIDATE',sha(root/'release.json'),'files',len(m['artifacts']))
