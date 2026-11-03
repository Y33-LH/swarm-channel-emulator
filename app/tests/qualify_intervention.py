"""Real board regression: manual API-equivalent actions, restore, exact recomputation."""
from pathlib import Path
import sys,json,time,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests'),str(ROOT/'tools/python_deps')]
from network_acceptance import run
import network_intervention as ni
from intervention_session import Session,record,save

def main():
    parent=ROOT/'results'/time.strftime('intervention_qualification_%Y%m%d_%H%M%S');parent.mkdir()
    p=ni.plan({})
    def progress(s,session):
        if s['round']%100==0:
            v=session.view
            print('MEASURED',s['round']/10,[(n['id'],n['age_ms'],n['new_updates']) for n in v['nodes']],s['media'],flush=True)
        if session.phase=='waiting':
            if s['round']==100:a=dict(kind='change',gain_permille=50,sigma=8192,window_s=20)
            elif s['round']==300:a=dict(kind='restore',window_s=20)
            else:a=dict(kind='finish')
            session.submit(a,session.id)
    out=parent/'original';out.mkdir()
    session=Session('original',out,p,progress,lambda:False)
    report=session.run(run,'COM4')
    gate=report['intervention']
    assert gate['effect_observed'] and gate['recovery_observed'],gate
    snaps=session.snapshots
    d0=next(s for s in snaps if s['round']==120);d1=next(s for s in snaps if s['round']==300)
    assert d1['media'][0]==d0['media'][0], 'Voice should not advance across the degraded 1->2 edge'
    assert d1['media'][2]>d0['media'][2], 'Control video on another route must continue'
    assert any(s['media'][0]>d1['media'][0] for s in snaps if s['round']>300),'Voice must resume from RX'
    assert report['media']['received_audio.wav']['complete'],'Voice not fully recovered'
    assert all(s['slot_misses']==0 for s in snaps)
    out2=parent/'recomputed';out2.mkdir()
    replay=Session('recomputed',out2,p,lambda s,t:None,lambda:False,record(out))
    repeated=replay.run(run,'COM4')
    assert repeated['reproduction']['exact_match'],repeated['reproduction']
    result=dict(passed=True,scope='Real FPGA directed-edge change, heartbeat/voice disruption, received recovery, exact recomputation',
                original=str(out),recomputed=str(out2),gates=gate,
                reproduction=repeated['reproduction'],voice_during=[d0['media'][0],d1['media'][0]],
                control_video_during=[d0['media'][2],d1['media'][2]],voice_final=report['media']['received_audio.wav'],
                memory=report['memory_after'],image_hashes=report['image_hashes'])
    save(parent/'acceptance.json',result);print('INTERVENTION_HARDWARE_PASS',parent,flush=True)
if __name__=='__main__':main()
