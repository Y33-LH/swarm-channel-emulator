"""Resolve UI observation identities using saved or server-owned observations only."""
import copy,struct

def control_events(controls):
    """Use verified UART command boundaries, not UI button timestamps."""
    events=[]
    for row in controls or []:
        if row.get('response',{}).get('ok')!=1:continue
        parts=row['command'].split()
        if len(parts)!=2 or parts[0] not in ('GCOMMAND','LINKCOND'):continue
        values=struct.unpack('<5I',bytes.fromhex(parts[1]))
        e=dict(effective_round=row['round'],receipt=row['response'])
        if parts[0]=='GCOMMAND':
            cid,node,opcode,value,ttl=values
            e.update(command_id=cid,action=dict(kind='command',command=dict(target=node,opcode=opcode,value=value,ttl_ms=ttl)))
        else:e['action']=dict(kind='change' if values[2] else 'restore',link=values[1])
        events.append(e)
    return events

def select(request,state,session,read_record,causal_record):
    c=request.get('context') or {}
    if not isinstance(c,dict):raise ValueError('观测上下文格式错误')
    rid=c.get('record_id') or state.get('network_record_id')
    mode=c.get('mode','current');is_causal=bool(rid and rid.startswith('causal_'))
    if mode not in ('current','history'):raise ValueError('未知观测模式')
    if mode=='history':
        r=causal_record(rid) if is_causal else read_record(rid)
        snaps=r['snapshots'];events=r.get('events',[]) if is_causal else control_events(r.get('control_history'));plan=r.get('plan');cfg=(r.get('report') or {}).get('config')
    elif is_causal:
        if state.get('task') not in (None,'causal'):
            raise ValueError('已切换到其他板卡任务；请使用当前观测，或明确选择这条历史记录后提问')
        if not session or rid!=session.id:raise ValueError('实验已切换，请根据当前页面重新提问')
        with session.mu:snaps=copy.deepcopy(session.snapshots);events=copy.deepcopy(session.events);plan=copy.deepcopy(session.plan)
        cfg=plan['config']
    else:
        if rid!=state.get('network_record_id'):raise ValueError('实验已切换，请重新提问')
        snaps=copy.deepcopy(state.get('snapshots',[]));events=copy.deepcopy(state.get('workflow_events',[]));plan=None;cfg=state['config']
        if not snaps and state.get('snapshot'):snaps=[copy.deepcopy(state['snapshot'])]
    if not snaps:raise ValueError('当前尚无实板观测，请先运行实验')
    model_ms=c.get('model_ms')
    if model_ms is not None:
        matches=[i for i,s in enumerate(snaps) if s['round']*100==model_ms]
        if not matches:raise ValueError('所选时刻不存在，请刷新页面后重新提问')
        index=matches[-1]
    else:index=len(snaps)-1
    snaps=snaps[:index+1];s=copy.deepcopy(snaps[-1]);cfg=s.get('config') or cfg
    link=plan['link'] if plan else c.get('link',s.get('watch_link',0))
    if type(link)!=int or not 0<=link<32:raise ValueError('链路编号超界')
    if s.get('watch_link')!=link:
        s['watch_link']=link;s['watch_phy']=[];s['watch_iq']=[]
    details=dict(kind='causal' if is_causal else 'network',mode=mode,record_id=rid,run_id=s['run_id'],
                 model_ms=s['round']*100,link=link,index=index,geometry_locked=is_causal)
    if plan:
        import action_observation as ao
        details['recommendations']=ao.recommendations(snaps,plan,events)
        details['effects']=ao.commands(snaps,events)
    elif events and all('media' in x and 'nodes' in x and 'pending' in x for x in snaps):
        import action_observation as ao
        # Keep both successful and unsuccessful measures. Historical snapshots
        # are already cut at the selected time; later outcomes cannot leak in.
        details['effects']=ao.commands(snaps,events)
    if not is_causal:
        from recovery_workflow import diagnose
        s['recovery']=diagnose(s,snaps[-2] if len(snaps)>1 else None)
    return dict(snapshot=s,config=copy.deepcopy(cfg),identity=details)
