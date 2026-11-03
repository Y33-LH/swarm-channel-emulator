from pathlib import Path
r=Path(__file__).resolve().parents[1];p=r/'tools/server.py';s=p.read_text()
s=s.replace('import link_experiment as le','import link_experiment as le\nimport network_intervention as ni\nimport intervention_session as nis\nintervention_current=None')
s=s.replace("if rid.startswith('link_'):","if rid.startswith(('link_','causal_')):")
s=s.replace("('network','capacity','link')","('network','capacity','link','causal')")
s=s.replace("version='LINK-EXPERIMENT-1'","version='NETWORK-INTERVENTION-1'")
s=s.replace("r.get('protocol') != 17:","r.get('protocol') != 17 or r.get('intervention_schema') != 1:")
fn='''
def intervention_task(p,replay=None):
    global intervention_current
    check_release();rid,out=new_record('causal')
    with mu:state.update(snapshot=None,snapshots=[],report=None,record_id=rid,network_record_id=rid,advice=[],commands=[],config=p['config'])
    def progress(s,session):
        with mu:
            state.update(status='paused' if session.phase=='waiting' else 'running',snapshot=s)
            state['snapshots'].append(s)
    session=nis.Session(rid,out,p,progress,halt.is_set,replay)
    with mu:intervention_current=session
    try:
        r=session.run(network_run,state['port'])
        with mu:state.update(report=r,connected=True)
        event('链路干预实验已保存；恢复状态依据地面实际接收的新心跳。')
    finally:
        save(out/'interventions.json',session.events)

'''
s=s.replace('class Handler(BaseHTTPRequestHandler):',fn+'class Handler(BaseHTTPRequestHandler):')
get='''
            if path=='/api/causal/state':
                with mu:session=intervention_current
                return self.json(dict(experiment=session.public() if session else None,busy=owner.locked(),connected=state['connected'],task=state['task']))
            if path=='/api/causal/records':
                rows=[]
                for p in sorted(RESULTS.glob('causal_*'),reverse=True):
                    if not (p/'intervention_plan.json').exists():continue
                    rec=nis.record(p);rows.append(dict(id=rec['id'],plan=rec['plan'],complete=rec['complete'],report=rec['report'],failure=rec['failure']))
                return self.json(rows)
            if path=='/api/causal/record':return self.json(nis.record(record_dir(q['id'][0])))
            if path=='/api/causal/export':
                p=record_dir(q['id'][0]);nis.record(p)
                dest=ROOT/'exports';dest.mkdir(exist_ok=True);target=dest/(p.name+'.zip')
                hashes={}
                with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
                    for item in sorted(p.iterdir()):
                        if item.is_file():
                            data=item.read_bytes();z.writestr(item.name,data);hashes[item.name]=hashlib.sha256(data).hexdigest()
                    z.writestr('contents_sha256.json',json.dumps(hashes,indent=2))
                return self.json(dict(ok=True,path=str(target),bytes=target.stat().st_size))
'''
s=s.replace("            if path=='/api/link/state':",get+"\n            if path=='/api/link/state':",1)
post='''
            if path=='/api/causal/start':
                p=ni.plan(d);begin('causal',intervention_task,p)
                return self.json(dict(ok=True,plan=p),202)
            if path=='/api/causal/action':
                if not intervention_current or not owner.locked() or state['task']!='causal':raise ValueError('没有活动的链路干预实验')
                return self.json(intervention_current.submit(d,d.get('id')),202)
            if path=='/api/causal/reproduce':
                rec=nis.record(record_dir(str(d.get('id',''))))
                if not rec['complete']:raise ValueError('请选择完整记录')
                hashes={k:hashlib.sha256((BASE/check_release()[k]).read_bytes()).hexdigest() for k in ('bit','elf','init')}
                if hashes!=rec['report']['image_hashes']:raise ValueError('固件与原记录不同，不能宣称原条件重算')
                begin('causal',intervention_task,rec['plan'],rec)
                return self.json(dict(ok=True,status='recomputing_all_rounds'),202)
'''
s=s.replace("            if path=='/api/link/preview':",post+"\n            if path=='/api/link/preview':",1)
p.write_text(s)
print('Network workflow API integrated')
