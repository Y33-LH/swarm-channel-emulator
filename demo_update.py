"""Apply a version-bound local update; preserve configuration and experiment data."""
import hashlib,json,shutil,subprocess,sys,tempfile,zipfile,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def safe(name):
    p=Path(name)
    if p.is_absolute() or '..' in p.parts or ':' in name or '\\' in name:raise ValueError('更新包路径不安全')
    target=(ROOT/p).resolve()
    if not target.is_relative_to(ROOT):raise ValueError('更新路径越界')
    if name=='config.json' or name=='services.json' or name.startswith(('app/results/','logs/','backups/')):raise ValueError('更新不能覆盖本机配置或记录')
    return target
def apply(archive):
    current=json.loads((ROOT/'PACKAGE_SHA256.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(archive) as z:
        patch=json.loads(z.read('UPDATE.json'))
        if patch['base_version']!=current.get('demo_version'):raise ValueError('版本不匹配，请发送本机PACKAGE_SHA256.json，让作者生成对应更新包。')
        with tempfile.TemporaryDirectory(prefix='swarm_update_',dir=ROOT) as temp:
            stage=Path(temp)
            for row in patch['files']:
                name=row['path'];safe(name);data=z.read('files/'+name)
                if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('更新文件损坏：'+name)
                p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            # Confirm all untouched files still match the target version before changing anything.
            manifest=json.loads((stage/'PACKAGE_SHA256.json').read_text(encoding='utf-8'))
            for row in manifest['files']:
                dest=safe(row['path']);p=stage/row['path'];p=p if p.exists() else dest
                if not p.is_file() or digest(p)!=row['sha256']:raise ValueError('当前包缺失或有改动：'+row['path'])
            subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'launcher.py'),'--action','stop'],check=True)
            backup=ROOT/'backups'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S');backup.mkdir(parents=True)
            applied=[]
            try:
                for row in patch['files']:
                    name=row['path'];dest=safe(name);old=backup/name
                    existed=dest.exists()
                    if existed:old.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,old)
                    applied.append((name,existed));dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(stage/name,dest)
            except Exception:
                for name,existed in reversed(applied):
                    dest=safe(name)
                    if existed:shutil.copy2(backup/name,dest)
                    elif dest.exists():dest.unlink()
                raise
            (backup/'rollback.json').write_text(json.dumps(applied),encoding='utf-8')
            print('更新成功。配置和实验记录已保留，旧文件备份在：'+str(backup))
            print('重新启动系统；若固件版本变化，请点击“上电后加载固件”。')
if __name__=='__main__':
    try:apply(Path(sys.argv[1] if len(sys.argv)>1 else input('将更新ZIP拖入此窗口，按回车：').strip().strip('"')))
    except Exception as e:print('未完成更新：'+str(e));sys.exit(1)
