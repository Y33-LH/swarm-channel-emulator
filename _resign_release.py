"""重新计算 release.json 中被修改文件的 SHA256。

用途：工程用 release.json 做发布完整性校验（check_release），改动任何 UI/文档/源码后
必须重签，否则实验拒绝启动。本脚本只更新文件哈希，不触碰 BIT/ELF/HDF，也不把开发版
标为已验收；每次实验仍会把 release.json 自身的哈希写入记录 metadata，改动可追溯。
"""
import json, hashlib, sys
from pathlib import Path

ROOT = Path(r'D:/Swarm_20261023_step29/app')
rel = ROOT / 'release.json'
m = json.loads(rel.read_text(encoding='utf-8-sig'))

AREA_SUFFIX = {'.js', '.css', '.html', '.json', '.py', '.sv', '.v', '.c', '.h', '.tcl',
               '.ps1', '.md', '.txt', '.mem', '.csv', '.cmd'}

changed, missing, added = [], [], []
index = {a['path']: a for a in m['artifacts']}

# 1) 重算清单内已有文件
for a in m['artifacts']:
    p = ROOT / a['path']
    if not p.is_file():
        missing.append(a['path'])
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    if h != a['sha256']:
        changed.append(a['path'])
        a['sha256'] = h

# 2) 把新增的源文件纳入清单（保持与 development_manifest.py 相同的范围）
for area in ('ui', 'tools', 'docs', 'configs', 'sw', 'rtl'):
    for p in sorted((ROOT / area).rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.suffix == '.pyc':
            continue
        if p.suffix not in AREA_SUFFIX:
            continue
        key = p.relative_to(ROOT).as_posix()
        if key not in index:
            index[key] = dict(path=key, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            added.append(key)

m['artifacts'] = [index[k] for k in sorted(index)]
rel.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding='utf-8')

print('重签完成')
print('  更新哈希:', len(changed))
for c in changed:
    print('    -', c)
print('  新纳入  :', len(added))
for a in added:
    print('    +', a)
if missing:
    print('  !! 缺失文件:', missing)
print('  release.json 自身 SHA256:', hashlib.sha256(rel.read_bytes()).hexdigest()[:16])
sys.exit(1 if missing else 0)
