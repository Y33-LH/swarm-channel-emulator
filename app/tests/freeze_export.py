"""Read-only export verification of the three fresh UI experiments."""
from pathlib import Path
import json, hashlib, urllib.request, zipfile
R=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
gate=max((R/'results').glob('freeze_stability_ui_*/acceptance.json'),key=lambda p:p.stat().st_mtime)
g=json.loads(gate.read_text());assert g['pass'] and g['release_sha256']==sha(R/'release.json')
rows=[]
for run in g['runs']:
    rid=run['id']
    with urllib.request.urlopen('http://127.0.0.1:8886/api/export?id='+rid+'&save=1',timeout=60) as r: meta=json.load(r)
    p=Path(meta['path']);assert p.resolve().is_relative_to((R/'exports').resolve()) and sha(p)==meta['sha256']
    with zipfile.ZipFile(p) as z:
        assert z.testzip() is None
        provenance=json.loads(z.read('provenance.json'));assert provenance['complete'] and provenance['id']==rid
        for name,h in provenance['sha256'].items():
            b=z.read(name);assert hashlib.sha256(b).hexdigest()==h
            assert b==(R/'results'/rid/name).read_bytes(),name
        assert all(n in z.namelist() for n in ('acceptance.json','snapshots.jsonl','uart.jsonl','received_audio.wav','received_video.webm','metrics.csv','report.html'))
    rows.append(dict(id=rid,path=p.relative_to(R).as_posix(),sha256=sha(p)))
(R/'results/freeze_export.json').write_text(json.dumps(dict(pass_export=True,release_sha256=g['release_sha256'],records=rows),indent=2))
print('CURRENT_THREE_EXPORT_PASS',len(rows))
