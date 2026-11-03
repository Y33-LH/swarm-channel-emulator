"""Pinned official downloads; optional local inference only, no cloud key or telemetry."""
from pathlib import Path
import urllib.request,hashlib,json,time,zipfile
DEST=Path(r'D:\digitalcircuit\local_assistant');DEST.mkdir(exist_ok=True)
FILES=[
 ('llama-b11574-win-cpu-x64.zip','https://github.com/ggml-org/llama.cpp/releases/download/b11574/llama-b11574-bin-win-cpu-x64.zip',19509340,'3f185fa804d8f4af359d917e21cb19916e7d579459322820bb078a4b6705736f'),
 ('Qwen3-0.6B-Q8_0.gguf','https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/resolve/23749fefcc72300e3a2ad315e1317431b06b590a/Qwen3-0.6B-Q8_0.gguf',639446688,'9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031')]
rows=[]
for name,url,size,sha in FILES:
    p=DEST/name;part=p.with_suffix(p.suffix+'.part')
    if not p.exists():
        offset=part.stat().st_size if part.exists() else 0
        headers={'User-Agent':'Swarm-Local-Assistant'}
        if offset:headers['Range']=f'bytes={offset}-'
        with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=45) as r:
            if r.status!=206:offset=0
            with part.open('ab' if offset else 'wb') as f:
                last=time.monotonic()
                while True:
                    block=r.read(1024*1024)
                    if not block:break
                    f.write(block);offset+=len(block)
                    if time.monotonic()-last>10:print(name,offset,size,flush=True);last=time.monotonic()
        if part.stat().st_size!=size:raise RuntimeError('Incomplete download '+name)
        if hashlib.file_digest(part.open('rb'),'sha256').hexdigest()!=sha:raise RuntimeError('Checksum mismatch '+name)
        part.replace(p)
    assert p.stat().st_size==size and hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==sha
    rows.append(dict(file=name,url=url,sha256=sha,bytes=size));print('VERIFIED',name,flush=True)
with zipfile.ZipFile(DEST/FILES[0][0]) as z:
    target=DEST/'runtime';target.mkdir(exist_ok=True)
    for item in z.infolist():
        if not (target/item.filename).resolve().is_relative_to(target.resolve()):raise RuntimeError('Unsafe archive path')
    z.extractall(target)
for name,url in [('QWEN_LICENSE.txt','https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/raw/23749fefcc72300e3a2ad315e1317431b06b590a/LICENSE'),('LLAMA_LICENSE.txt','https://raw.githubusercontent.com/ggml-org/llama.cpp/b11574/LICENSE')]:
    with urllib.request.urlopen(url,timeout=30) as r:(DEST/name).write_bytes(r.read())
(DEST/'provenance.json').write_text(json.dumps(dict(downloaded=time.strftime('%Y-%m-%dT%H:%M:%S'),files=rows),indent=2))
print('LOCAL_ASSISTANT_DOWNLOAD_VERIFIED',DEST,flush=True)
