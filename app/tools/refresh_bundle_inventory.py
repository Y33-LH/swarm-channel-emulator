"""File integrity only; call after matching sources and firmware are sealed."""
from pathlib import Path
import datetime,hashlib,json,shutil
APP=Path(__file__).resolve().parents[1];ROOT=APP.parent
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def refresh():
    p=ROOT/'PACKAGE_SHA256.json';old=json.loads(p.read_text(encoding='utf-8-sig'))
    backup=ROOT/'logs/migration_originals'/('PACKAGE_'+sha(p)+'.json')
    backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(p,backup)
    release=json.loads((APP/'release.json').read_text(encoding='utf-8'))
    assert release['development'] and not release['accepted']
    names={x['path'] for x in old['files']}
    for row in release['artifacts']:
        f=APP/row['path'];assert f.resolve().is_relative_to(APP)
        assert sha(f)==row['sha256'],'Source changed after sealing: '+row['path']
        names.add('app/'+row['path'])
    names.update(['app/release.json','当前运行与验收说明.txt','HANDOFF/11_当前开发状态_20261101.txt','AI_START_HERE.txt','launcher.py','refresh_dev.py'])
    rows=[]
    for name in sorted(names):
        f=ROOT/name
        assert f.resolve().is_relative_to(ROOT) and f.is_file(),name
        assert not name.startswith(('app/results/','logs/')),'Mutable results cannot be runtime dependencies'
        rows.append(dict(path=name,sha256=sha(f),bytes=f.stat().st_size))
    m=dict(schema=1,kind='local_development_integrity',date=datetime.datetime.now().isoformat(),
        note='File integrity only, not acceptance. Original inventories retained in logs/migration_originals.',
        release_sha256=sha(APP/'release.json'),files=rows)
    p.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
    print('LOCAL_INTEGRITY_UPDATED',len(rows),'NOT PRODUCT ACCEPTANCE')
    return m
if __name__=='__main__':refresh()
