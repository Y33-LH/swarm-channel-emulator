"""Compare all actual board snapshots; only wall-clock elapsed time may differ."""
import argparse,json,hashlib
from pathlib import Path
def normalized(path):
    data=[json.loads(line) for line in (path/'snapshots.jsonl').read_text().splitlines()]
    for row in data:row.pop('wall_ms',None)
    return data
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('first',type=Path);p.add_argument('second',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    reports=[json.loads((d/'acceptance.json').read_text()) for d in (a.first,a.second)]
    assert all(r['pass'] and r['duration_s']==900 and r['ideal']==0 for r in reports)
    left,right=normalized(a.first),normalized(a.second)
    assert len(left)==len(right)==90
    for i,(x,y) in enumerate(zip(left,right)):
        if x!=y:raise AssertionError({'snapshot':i,'differing_fields':[k for k in set(x)|set(y) if x.get(k)!=y.get(k)]})
    for name in ('received_audio.wav','received_video.webm'):assert (a.first/name).read_bytes()==(a.second/name).read_bytes()
    digest=hashlib.sha256(json.dumps(left,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    result={'pass':True,'first':str(a.first),'second':str(a.second),'snapshots_compared':90,'ignored_fields':['wall_ms'],'sha256_normalized_snapshots':digest,'all_received_media_equal':True,'duration_s':900,'seed':reports[0]['seed']}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2));print('HARDWARE_REPLAY_PASS '+str(a.out))
