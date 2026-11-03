from pathlib import Path
import sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests'),str(ROOT/'reference')]
import network_intervention as ni
from intervention_session import Session,save
from network_acceptance import run
def main():
    parent=ROOT/'results'/time.strftime('intervention_edges_%Y%m%d_%H%M%S');parent.mkdir()
    results=[]
    for link,mild in ((3,False),(8,False),(0,True)):
        p=ni.plan({'link':link});out=parent/f'edge{link}_mild{int(mild)}';out.mkdir()
        def progress(s,session):
            if s['round']%100==0:print('EDGE',link,'MILD',mild,'TIME',s['round']/10,'AGE',[n['age_ms'] for n in session.view['nodes']],flush=True)
            if session.phase=='waiting':
                if s['round']==100:a=dict(kind='change',gain_permille=700 if mild else 50,sigma=1800 if mild else 8192,window_s=20)
                elif s['round']==300:a=dict(kind='restore',window_s=20)
                else:a=dict(kind='finish')
                session.submit(a,session.id)
        session=Session(out.name,out,p,progress,lambda:False);report=session.run(run,'COM4')
        if not mild:
            assert report['intervention']['effect_observed'],report['intervention']
            assert report['intervention']['recovery_observed'],report['intervention']
        else:
            assert not report['intervention']['effect_observed'],'Mild test unexpectedly crosses application deadline'
            assert all(s['nodes'][0][9] and s['round']*100-s['nodes'][0][10]<=2000 for s in session.snapshots if 100<=s['round']<=300)
        results.append(dict(link=link,mild=mild,report=report['intervention'],memory=report['memory_after']))
    save(parent/'acceptance.json',dict(passed=True,runs=results));print('EDGE_COVERAGE_PASS',parent,flush=True)
if __name__=='__main__':main()
