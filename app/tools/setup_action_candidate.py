from pathlib import Path
import shutil
r=Path(__file__).resolve().parents[1]
shutil.copyfile(r.parent/'step23_network_intervention/release.json',r/'docs/parent_step23_release.json')
for name in ('progress.json','development_status.json'):
 shutil.copyfile(r/'docs'/name,r/'docs'/('parent_step23_'+name))
p=r/'start.ps1';p.write_text(p.read_text(encoding='utf-8-sig').replace('8881','8883'),encoding='utf-8-sig')
p=r/'tools/seal_link_release.py';p.write_text(p.read_text().replace('parent_step22_release','parent_step23_release').replace('Directed-edge intervention and network business observation; ARM updated, FPGA unchanged. Acceptance requires new hardware evidence.','Commands, observed effects and shared experiment context; FPGA and ARM unchanged. New scoped acceptance required.'))
p=r/'tools/server.py';s=p.read_text(encoding='utf-8')
s=s.replace('import intervention_session as nis','import intervention_session as nis\nimport action_observation as ao')
s=s.replace("state.update(status='paused' if session.phase=='waiting' else 'running',snapshot=s)","state.update(status='paused' if session.phase=='waiting' else 'running',snapshot=s, commands=s.get('command_results',[]), link_windows=link_windows(s,state['snapshots'][-1] if state['snapshots'] else None), advice=[])" )
anchor="            if path=='/api/causal/state':"
block='''            if path=='/api/causal/context':
                rid=q.get('id',[None])[0];index=int(q.get('index',['-1'])[0])
                if rid:
                    rec=nis.record(record_dir(rid));snaps=rec['snapshots'];p=rec['plan'];events=rec['events'];report=rec['report'];mode='history'
                else:
                    with mu:session=intervention_current
                    if not session:return self.json(dict(context=None))
                    with session.mu:
                        rid=session.id;snaps=list(session.snapshots);p=session.plan;events=list(session.events);report=session.report
                    mode='current'
                if not snaps:return self.json(dict(context=None))
                index=index if index>=0 else len(snaps)-1
                if not 0<=index<len(snaps):raise ValueError('观测索引超出范围')
                snaps=snaps[:index+1];snap=snaps[-1];previous=snaps[-2] if len(snaps)>1 else None
                # All three pages receive exactly one snapshot identity. The watched DATA
                # frame replaces ACK-overwritten parameter rows for that link only.
                import copy
                shown=copy.deepcopy(snap)
                if shown.get('observation'):shown['applied_links'][p['link']]=shown['observation']['applied']
                frame=shown.get('observation')
                context=dict(record_id=rid,run_id=snap['run_id'],index=index,model_ms=snap['round']*100,
                    link=p['link'],mode=mode,config_sha256=p['config_sha256'],
                    frame_generation=frame['meta'][15] if frame else None,
                    frame_ms=frame['applied'][1] if frame else None,
                    identity=f"{rid}:{index}:{p['link']}")
                visible_report=report if index==len(rec['snapshots'])-1 else None if mode=='history' else report
                if mode=='current':visible_report=report
                return self.json(dict(context=context,snapshot=shown,metrics=metrics(snap),scene=scene(shown),
                    link_windows=link_windows(snap,previous),advice=[],report=visible_report,
                    commands=ao.commands(snaps,events),recommendations=ao.recommendations(snaps,p,events)))
'''
# Avoid referencing historical rec in the current branch.
block=block.replace("visible_report=report if index==len(rec['snapshots'])-1 else None if mode=='history' else report", "visible_report=report if mode=='current' or index==len(rec['snapshots'])-1 else None")
s=s.replace(anchor,block+anchor)
s=s.replace("if path=='/api/causal/start':\n                p=", "if path=='/api/causal/start':\n                p=")
s=s.replace("version='NETWORK-INTERVENTION-1'", "version='ACTION-CONTEXT-2'")
p.write_text(s,encoding='utf-8')
print('Prepared candidate on port 8883; baseline preserved')
