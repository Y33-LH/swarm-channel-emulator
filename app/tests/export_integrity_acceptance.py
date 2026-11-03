"""Verify exported evidence and playable media against an existing board record.

Read-only with respect to hardware; the HTTP export endpoint writes a local copy.
An incomplete object must not be served as a playable received file.
"""
from pathlib import Path
import sys,json,time,hashlib,urllib.request,urllib.error,io,zipfile
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()

def main(record,port):
    root=(ROOT/'results'/record).resolve()
    assert root.is_relative_to((ROOT/'results').resolve()) and root.is_dir()
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def get(path):
        with opener.open(f'http://127.0.0.1:{port}'+path,timeout=90) as response:return response.read()
    archive=get('/api/export?id='+record)
    verified=[];objects=[];rejected=[]
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        report=z.read('report.html').decode('utf-8')
        assert '不代表整机最终验收' in report and '两种位域的误码数不能直接相减' in report
        assert '边界：' in report and 'repeated_objects' in report
        provenance=json.loads(z.read('provenance.json'))
        assert set(z.namelist())==set(provenance['sha256'])|{'provenance.json'}
        for name,digest in provenance['sha256'].items():
            assert sha(z.read(name))==digest,name
            if name not in ('metrics.csv','report.html'):assert z.read(name)==(root/name).read_bytes(),name
            verified.append(name)
        for p in sorted((root/'media_objects').glob('*/object.json')):
            obj=json.loads(p.read_text());kind=obj['kind'];seq=obj['object_id']
            assert str(seq) in report,'Export summary omitted a repeated media object'
            route=f'/media-object/{record}/{kind}/{seq}'
            assert p.relative_to(root).as_posix() in verified
            if obj['complete']:
                name='received_audio.wav' if kind==3 else 'received_video.webm'
                data=get(route);assert sha(data)==obj['sha256']
                assert data==(p.parent/name).read_bytes()
                objects.append(dict(kind=kind,object_id=seq,bytes=len(data),sha256=sha(data)))
            else:
                try:get(route)
                except urllib.error.HTTPError as e:
                    assert e.code==400;rejected.append(dict(kind=kind,object_id=seq,http_status=e.code))
                else:raise AssertionError('Incomplete object was served: '+route)
    assert objects and rejected,'Fixture must include both complete and incomplete objects'
    out=ROOT/'results'/time.strftime('export_integrity_%Y%m%d_%H%M%S');out.mkdir()
    result=dict(passed=True,record=record,export_sha256=sha(archive),export_files=len(verified),
                complete_media=objects,incomplete_media_rejected=rejected,
                server_source_sha256=sha((ROOT/'tools/server.py').read_bytes()),
                scope='All exported bytes verified, complete media routes verified, incomplete media rejected; no new hardware run.')
    (out/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('EXPORT_INTEGRITY_PASS',out,len(verified),len(objects),len(rejected))
if __name__=='__main__':main(sys.argv[1],int(sys.argv[2]) if len(sys.argv)>2 else 18878)
