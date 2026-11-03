"""Build a portable demo and optional delta against a recipient's manifest."""
import argparse,hashlib,json,shutil,zipfile,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(out,previous=None):
    version=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    dest=out/('SwarmDemo_'+version);dest.mkdir(parents=True)
    names=set()
    release=json.loads((ROOT/'app/release.json').read_text(encoding='utf-8'))
    names.update('app/'+r['path'] for r in release['artifacts'])
    names.update(['app/release.json','launcher.py','portable_server.py','demo_update.py'])
    for folder in ['runtime','assistant','licenses','app/openocd']:
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.log','.pyc'))
    for name in sorted(names):
        p=dest/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,p)
    for d in ['logs','app/results','app/exports']: (dest/d).mkdir(parents=True,exist_ok=True)
    cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
    cfg.update(port='',xsct='',board_profile='unconfirmed')
    (dest/'config.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    for name,action in [('01_首次设置.cmd','setup'),('02_启动演示.cmd','start'),('03_检查文件.cmd','check'),('04_停止服务.cmd','stop')]:
        (dest/name).write_text('@echo off\nchcp 65001 >nul\n"%~dp0runtime\\python\\python.exe" -X utf8 -B "%~dp0launcher.py" --action '+action+'\npause\n',encoding='utf-8')
    (dest/'05_安装更新.cmd').write_text('@echo off\nchcp 65001 >nul\n"%~dp0runtime\\python\\python.exe" -X utf8 -B "%~dp0demo_update.py" %*\npause\n',encoding='utf-8')
    shutil.copy2(ROOT/'demo_instructions.txt',dest/'先读我.txt')
    shutil.copy2(ROOT/'demo_instructions.txt',dest/'当前运行与验收说明.txt')
    rows=[dict(path=p.relative_to(dest).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(dest.rglob('*')) if p.is_file() and p.name!='config.json']
    manifest=dict(demo_version=version,arm_build=release['arm_build'],protocol=release['protocol'],files=rows)
    (dest/'PACKAGE_SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=out/(dest.name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
        for p in dest.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(out))
    if previous:
        old=json.loads(Path(previous).read_text(encoding='utf-8'));oldhash={r['path']:r['sha256'] for r in old['files']}
        changed=[r for r in rows if oldhash.get(r['path'])!=r['sha256']]
        changed.append(dict(path='PACKAGE_SHA256.json',sha256=sha(dest/'PACKAGE_SHA256.json')))
        patch=dict(base_version=old['demo_version'],target_version=version,files=changed)
        with zipfile.ZipFile(out/('Update_'+old['demo_version']+'_to_'+version+'.zip'),'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
            z.writestr('UPDATE.json',json.dumps(patch))
            for r in changed:z.write(dest/r['path'],'files/'+r['path'])
    (out/(archive.name+'.sha256.txt')).write_text(sha(archive)+'  '+archive.name+'\n',encoding='utf-8')
    print(json.dumps(dict(folder=str(dest),zip=str(archive),zip_bytes=archive.stat().st_size,unpacked_bytes=sum(r['bytes'] for r in rows),files=len(rows)),ensure_ascii=False),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default=r'D:\digitalcircuit\演示交付');p.add_argument('--previous');a=p.parse_args();build(Path(a.out),a.previous)
