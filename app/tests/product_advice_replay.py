"""Check actual fault/recovery evidence drives advice, without controlling hardware."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from product_advice import AdviceTracker
if len(sys.argv)>1:p=Path(sys.argv[1])
else:
    candidates=[]
    for a in (ROOT/'results').glob('network_*/acceptance.json'):
        r=json.loads(a.read_text());cfg=r.get('config',{})
        if r.get('duration_s')==900 and r.get('ideal')==0 and cfg.get('environment')==0 and not r['final'].get('command_results'):candidates.append(a.parent/'snapshots.jsonl')
    p=max(candidates,key=lambda x:x.stat().st_mtime)
snaps=[json.loads(x) for x in p.read_text().splitlines()]
t=AdviceTracker();previous=None;history=[]
for s in snaps:
    cards,events=t.update(s,previous,s['config'],s.get('command_results',[]))
    history.append(dict(model_ms=s['round']*100,cards=cards,events=events));previous=s
allcards=[c for row in history for c in row['cards']]
assert any(c['evidence'].get('node')==2 for c in allcards)
assert any(c['evidence'].get('node')==12 for c in allcards)
assert any('retry_fraction' in c['evidence'] for c in allcards)
assert any('pending' in c['evidence'] for c in allcards)
assert any(e['event']=='advice_resolved' for row in history for e in row['events'])
assert not any('node' in c['evidence'] for c in history[-1]['cards']),'Stale-position warning failed to clear after recovery'
out=ROOT/'results/advice_replay_acceptance.json'
out.write_text(json.dumps(dict(**{'pass':True},source=str(p),actions_executed=0,history=history),ensure_ascii=False,indent=2),encoding='utf-8')
print('PRODUCT_ADVICE_REPLAY_PASS',out)
