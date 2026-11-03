from pathlib import Path
import json,hashlib,shutil,sys,zipfile
BASE=Path(__file__).resolve().parent
SOURCE=Path(r'D:\digitalcircuit\swarm_minimal\step29_live')
DEST=BASE.parent/'Swarm_20261023_step29'
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def initial():
    if DEST.exists():raise RuntimeError('Destination exists; do not overwrite an existing delivery')
    DEST.mkdir();app=DEST/'app';app.mkdir()
    manifest=json.loads((SOURCE/'release.json').read_text(encoding='utf-8-sig'))
    for item in manifest['artifacts']:
        p=SOURCE/item['path'];assert digest(p)==item['sha256'],item['path'];copy(p,app/item['path'])
    copy(SOURCE/'release.json',DEST/'provenance/original_release.json')
    # Preserve complete test records, logs and plots; omit large build intermediates,
    # browser profiles, duplicate firmware and machine-specific SDK workspaces.
    allowed={'.json','.jsonl','.log','.rpt','.csv','.wav','.webm','.png','.txt'}
    for p in (SOURCE/'results').rglob('*'):
        rel=p.relative_to(SOURCE/'results')
        if p.is_file() and p.suffix.lower() in allowed and not any(x in {'profile','browser_profile','__pycache__','.Xil'} for x in rel.parts):
            if rel.parts[0].startswith(('board_','sdk_')) and len(rel.parts)>2:continue
            copy(p,app/'results'/rel)
    for name in ('exports','results'):(app/name).mkdir(exist_ok=True)
    old=BASE.parent/'Swarm_20261019_d3'
    for folder in ('runtime','assistant','licenses'):
        shutil.copytree(old/folder,DEST/folder,ignore=shutil.ignore_patterns('__pycache__','*.log','server_pid.txt'))
    py=Path(r'D:\miniconda')
    # Host-only portability changes; FPGA/ARM binaries and algorithms are unchanged.
    patches={
      'tools/server.py':[("sdk = Path(r'D:\\Xilinx\\SDK\\2018.3\\bin\\xsct.bat')", "if os.environ.get('SWARM_BOARD_PROFILE') != 'wildfire7020': raise RuntimeError('请先在启动菜单确认板卡为匹配的野火7020；不能直接用于PYNQ。')\n    sdk = Path(os.environ.get('SWARM_XSCT',''))"),("[str(sdk),str(BASE/'program_run.tcl'),str(BASE/m['bit']),str(BASE/m['init']),str(BASE/m['elf'])]", "[str(sdk),os.path.relpath(BASE/'program_run.tcl',out),os.path.relpath(BASE/m['bit'],out),os.path.relpath(BASE/m['init'],out),os.path.relpath(BASE/m['elf'],out)]")],
      'tools/product_assistant.py':[("import json,re,urllib.request,urllib.error","import json,re,urllib.request,urllib.error,os"),("URL='http://127.0.0.1:8882'","URL=os.environ.get('SWARM_ASSISTANT_URL','http://127.0.0.1:18882')")]
    }
    changes=[]
    for rel,replacements in patches.items():
        p=app/rel;copy(p,DEST/'provenance/original_host'/rel);s=p.read_text(encoding='utf-8')
        for old,new in replacements:assert s.count(old)==1,rel;s=s.replace(old,new)
        p.write_text(s,encoding='utf-8');changes.append(rel)
    for name in ('start.ps1','launch.cmd','tools/start_assistant.ps1'):
        copy(app/name,DEST/'provenance/original_host'/name)
    (app/'launch.cmd').write_text('@echo off\r\ncall "%~dp0..\\START.cmd"\r\n',encoding='ascii')
    (app/'start.ps1').write_text('& (Join-Path $PSScriptRoot "..\\runtime\\python\\python.exe") -X utf8 -B (Join-Path $PSScriptRoot "..\\launcher.py") --action start\nexit $LASTEXITCODE\n',encoding='utf-8-sig')
    (app/'tools/start_assistant.ps1').write_text('& (Join-Path $PSScriptRoot "..\\..\\runtime\\python\\python.exe") -X utf8 -B (Join-Path $PSScriptRoot "..\\..\\launcher.py") --action ai\nexit $LASTEXITCODE\n',encoding='utf-8-sig')
    changes+=['start.ps1','launch.cmd','tools/start_assistant.ps1']
    for item in manifest['artifacts']:item['sha256']=digest(app/item['path'])
    manifest['portable']={'package':'Swarm_20261023_step29','changed_host_files':changes,'original_manifest_sha256':digest(SOURCE/'release.json'),'same_firmware':True,'acceptance_note':'Original engineering acceptance applies to original files/images. Portable-host validation is separately recorded in validation/.'}
    dump(app/'release.json',manifest)
    dump(DEST/'provenance/packaging.json',dict(source_release=str(SOURCE),original_manifest_sha256=digest(SOURCE/'release.json'),host_changes=changes,images_unchanged=True,runtime_source=str(py),runtime_isolation='python314._pth + local native DLL directories',historical_evidence='app/results records dated 20261018 or earlier are original-machine evidence, not destination-machine tests'))
    (DEST/'logs').mkdir();(DEST/'validation').mkdir()
    (DEST/'config.json').write_text(json.dumps(dict(port='',xsct='',board_profile='unconfirmed',http_port=18878,ai_port=18882,ai_enabled=True),indent=2))
    print('INITIAL_COPY_COMPLETE',flush=True)
def finish():
    for name in ('launcher.py','portable_server.py','先读我_换电脑运行.txt'):
        copy(BASE/name,DEST/name)
    (DEST/'START.cmd').write_text('@echo off\r\nchcp 65001 >nul\r\n"%~dp0runtime\\python\\python.exe" -X utf8 -B "%~dp0launcher.py" %*\r\nif errorlevel 1 pause\r\n',encoding='ascii')
    exclude={'PACKAGE_SHA256.json','config.json','services.json'}
    files=[]
    for p in DEST.rglob('*'):
        if p.is_file() and p.name not in exclude and '__pycache__' not in p.parts and p.relative_to(DEST).parts[0] not in {'logs','validation'}:
            files.append(dict(path=p.relative_to(DEST).as_posix(),bytes=p.stat().st_size,sha256=digest(p)))
    dump(DEST/'PACKAGE_SHA256.json',dict(package='Swarm_20261023_step29',files=files))
    print('PACKAGE_MANIFEST',len(files),sum(x['bytes'] for x in files),flush=True)
if __name__=='__main__':
    if sys.argv[1]=='initial':initial()
    elif sys.argv[1]=='finish':finish()
