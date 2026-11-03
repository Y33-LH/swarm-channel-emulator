"""Independently check saved output from actual browser-driven board actions."""
from pathlib import Path
import sys,json,time,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'reference')]
import network_reproduction as nr
import workflow_context as wc
import action_observation as ao
from observation_contract import coherent_observation

def main(first,second):
    records=[nr.load(ROOT/'results'/rid,ROOT) for rid in (first,second)]
    a,b=records
    for r in records:
        report=r['report'];assert report['continuous'] and report['repeat_media'] and report['requested_duration_s']==0
        assert report['duration_s']>20 and report['final']['slot_misses']==0
        for s in r['snapshots']:
            if s.get('observation'):coherent_observation(s,r['id'])
    assert a['report']['config']['reference_snr_cdb']==3400
    assert b['report']['config']['reference_snr_cdb']==2400
    before=[s['observation']['applied'][5] for s in a['snapshots'] if s.get('observation')]
    assert before and set(before)=={116}
    events=wc.control_events(a['actions']);effects=ao.commands(a['snapshots'],events)
    e=next(x for x in effects if x['target']==5 and x['request']['opcode']==4)
    assert e['status']=='confirmed' and e['verdict']=='measured'
    assert e['before']['generated_fragments_per_s']==5 and e['after']['generated_fragments_per_s']==1
    assert e['confirmed_ms']>e['issued_ms']
    controls=wc.control_events(b['actions']);change=next(x for x in controls if x['action']['kind']=='change');restore=next(x for x in controls if x['action']['kind']=='restore')
    assert restore['effective_round']-change['effective_round']>200
    low=[s for s in b['snapshots'] if change['effective_round']+100<s['round']<restore['effective_round']]
    recovered=[s for s in b['snapshots'] if s['round']>=restore['effective_round']+100]
    assert low and recovered
    applied=[s['observation'] for s in low if s.get('observation',{}).get('link')==4]
    assert len(applied)>=10 and all(o['applied'][5]==8192 for o in applied)
    assert any(not o['meta'][7]&4 for o in applied)
    assert low[-1]['round']*100-low[-1]['nodes'][4][10]>10000
    assert recovered[-1]['round']*100-recovered[-1]['nodes'][4][10]<=2000
    assert recovered[-1]['observation']['applied'][5]==365
    last=recovered[-1];prev=next(s for s in reversed(recovered) if s['round']<=last['round']-100)
    tries=last['links'][4][19]-prev['links'][4][19];acked=last['links'][4][3]-prev['links'][4][3]
    assert tries>0 and tries==acked
    complete=[o for o in b['report']['media_objects'] if o['complete']]
    partial=[o for o in b['report']['media_objects'] if not o['complete']]
    assert any(o['kind']==4 for o in complete) and partial
    observations=[coherent_observation(s,b['id']) for s in b['snapshots'] if s.get('observation')]
    assert len({o['generation'] for o in observations})>30
    assert len({tuple(s['nodes'][0][4:7]) for s in b['snapshots']})>30
    result=dict(passed=True,source='saved_browser_driven_physical_board_records',records=[r['id'] for r in records],
        image_hashes=a['report']['image_hashes'],effect=e,intervention_model_seconds=(restore['effective_round']-change['effective_round'])/10,
        last_recovery_window=dict(attempts=tries,acknowledged=acked,position_age_ms=last['round']*100-last['nodes'][4][10]),
        distinct_frame_observations=len({o['generation'] for o in observations}),complete_media_objects=len(complete),incomplete_retained=len(partial),
        scope='UI-triggered continuous start, media-rate command, next-run SNR change, persistent edge disturbance and manual restore; not all configurations or visual usability.',
        inputs={r['id']:hashlib.sha256((ROOT/'results'/r['id']/'acceptance.json').read_bytes()).hexdigest() for r in records})
    out=ROOT/'results'/time.strftime('current_story_%Y%m%d_%H%M%S');out.mkdir();(out/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CURRENT_STORY_PASS',out)
if __name__=='__main__':main(*sys.argv[1:])
