"""Validate exported evidence against source records without touching the board."""
import hashlib,json,urllib.request,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
ids=['network_20261011_112704_d0ae14','capacity_20261011_113300_99c7db']
out=[]
for rid in ids:
    with urllib.request.urlopen('http://127.0.0.1:8876/api/export?id='+rid+'&save=1',timeout=60) as response:
        meta=json.load(response)
    path=Path(meta['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest()==meta['sha256']
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        provenance=json.loads(z.read('provenance.json'))
        assert provenance['complete'] and provenance['id']==rid
        assert json.loads(z.read('acceptance.json'))['pass']
        for name,expected in provenance['sha256'].items():
            assert hashlib.sha256(z.read(name)).hexdigest()==expected,name
            assert z.read(name)==(root/'results'/rid/name).read_bytes(),name
        required=['metrics.csv','report.html','uart.jsonl']
        if rid.startswith('network'):
            required+=['received_audio.wav','received_video.webm','snapshots.jsonl']
        else:
            required+=['rate_'+str(rate)+'.json' for rate in [0,2,4,5,6,8,12]]
        assert all(name in z.namelist() for name in required)
        out.append(dict(id=rid,archive=str(path.relative_to(root)),sha256=meta['sha256'],files=len(z.namelist())))
(root/'results/export_check.json').write_text(json.dumps({'pass':True,'records':out},indent=2),encoding='utf-8')
print('EXPORT_EVIDENCE_PASS',json.dumps(out))
