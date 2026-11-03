"""Received command acknowledgements and measured effects, never optimistic UI state."""
import copy
from product_advice import validate_action

NAMES={1:'查询状态',2:'调整心跳周期',3:'暂停/恢复媒体',4:'调整媒体速率',5:'调整模拟高度'}

def validate_command(a):
    a=validate_action(a)
    if a['opcode']==5:raise ValueError('此任务锁定几何条件；高度调整请使用整机任务，不能混入固定信道对照')
    if a['opcode'] in (3,4) and a['target'] not in (1,5):
        raise ValueError('当前语音源为节点1、视频源为节点5；其他节点没有该媒体业务')
    return a

def sample(s,node):
    n=s['nodes'][node-1];kind={1:3,5:4}.get(node)
    b=next((b for b in s.get('business_counts',[]) if b[0]==kind),None)
    mi={1:0,5:2}.get(node)
    return dict(model_ms=s['round']*100,pending=s['pending'],heartbeat_count=n[9],
        age_ms=s['round']*100-n[10] if n[9] else None,
        source_ms=n[10] if n[9] else None,height_mm=n[6] if n[9] else None,
        generated_fragments=b[1] if b else None,
        received_bytes=s.get('media_totals',s['media'])[mi] if mi is not None else None,
        current_received_bytes=s['media'][mi] if mi is not None else None,
        repeating=bool(s.get('repeat_media')),
        total_bytes=s['media'][mi+1] if mi is not None else None)

def window(snaps,node,end_ms,width=5000):
    valid=[s for s in snaps if s['round']*100<=end_ms]
    if not valid:return None
    end=valid[-1];starts=[s for s in valid if s['round']*100<=end['round']*100-width]
    if not starts:return None
    a,b=sample(starts[-1],node),sample(end,node);dt=(b['model_ms']-a['model_ms'])/1000
    return dict(start_ms=a['model_ms'],end_ms=b['model_ms'],seconds=dt,
        generated_fragments_per_s=(b['generated_fragments']-a['generated_fragments'])/dt if b['generated_fragments'] is not None else None,
        received_bytes_per_s=(b['received_bytes']-a['received_bytes'])/dt if b['received_bytes'] is not None else None,
        heartbeat_updates=b['heartbeat_count']-a['heartbeat_count'],
        latest_position_age_ms=b['age_ms'],pending_start=a['pending'],pending_end=b['pending'],
        pending_change=b['pending']-a['pending'],media_remaining_bytes=b['total_bytes']-b['current_received_bytes'] if b['total_bytes'] is not None else None,
        source_exhausted=bool(not b['repeating'] and b['total_bytes'] and a['generated_fragments']*64>=b['total_bytes']),height_mm=b['height_mm'])

def commands(snaps,events):
    if not snaps:return []
    last=snaps[-1];now=last['round']*100;results={c[0]:c for snap in snaps for c in snap.get('command_results',[])}
    trace=last.get('command_trace',{});rows=[]
    for e in events:
        if e['action']['kind']!='command' or e['effective_round']>last['round']:continue
        a=e['action']['command'];cid=e['command_id'];c=results.get(cid);issued=e['effective_round']*100
        hops=[h for h in trace.get('hops',[]) if h[1]==cid and h[2]==6 and h[4]==a['target'] and h[6] and h[7]]
        receipt=c[5] if c and c[4] in (2,3,4) else None
        status='confirmed' if c and c[4]==2 else 'rejected' if c and c[4]==3 else 'expired' if c and c[4]==4 else 'unconfirmed' if now>issued+a['ttl_ms'] else 'in_transit'
        before=window(snaps,a['target'],issued)
        relay=((a['target']-1)//4+1)*4
        # Freeze the first complete 5s post-ACK window, before a later command
        # or channel change can contaminate attribution to this action.
        future=[x['effective_round']*100 for x in events if x['effective_round']*100>issued and x['action']['kind'] in ('command','change','restore')]
        cutoff=min(future,default=now)
        post=[s for s in snaps if receipt is not None and receipt<=s['round']*100<=cutoff]
        first=post[0]['round']*100 if post else None
        after=window(post,a['target'],min(now,first+5000)) if first is not None else None
        text='等待真实多跳下行与上行执行回执；电脑入队不代表节点执行。'
        verdict='awaiting_confirmation'
        if status=='confirmed':
            verdict='awaiting_observation';text='地面已收到执行成功回执；继续观察至少5模型秒，再比较业务变化。'
            if future and cutoff<now and not after:
                verdict='confounded_window';text='已确认执行，但下一次操作发生过早，没有独立的5秒后窗口；不能把后续变化归因于这条措施。'
            if after and before:
                verdict='measured';text='已取得执行前后各5秒窗口。窗口前后对比不等于排除所有时变因素的因果证明。'
                if a['opcode']==4 and before['source_exhausted']:
                    verdict='no_remaining_media';text='执行已确认，但源端媒体已经全部生成，调整速率不会改变已排队分片；需新实验检验速率效果。'
                elif a['opcode']==4:
                    x,y=before['generated_fragments_per_s'],after['generated_fragments_per_s']
                    text=f'源端生成速率 {x:g} → {y:g} 分片/秒；地面接收 {before["received_bytes_per_s"]:g} → {after["received_bytes_per_s"]:g} 字节/秒。心跳时效与积压分别实测，不因执行成功自动判为改善。'
                elif a['opcode']==2:
                    text=f'回执确认心跳周期 {c[7]} ms；地面窗口新增心跳 {before["heartbeat_updates"]} → {after["heartbeat_updates"]} 条，最新位置年龄 {after["latest_position_age_ms"]} ms。'
                elif a['opcode']==1:text='状态查询只返回节点状态，本身不修复链路、不改变业务策略。'
        elif status in ('expired','rejected'):text='节点返回过期或拒绝结果；本次措施没有成功执行。';verdict=status
        elif status=='unconfirmed':text='指令有效期已过，地面尚未收到执行回执；不能断言未执行，也不能宣称成功。';verdict=status
        rows.append(dict(id=cid,target=a['target'],operation=NAMES[a['opcode']],request=copy.deepcopy(a),
            issued_ms=issued,queued=bool(e.get('receipt')),node_received_ms=min((h[0] for h in hops),default=None),
            node_receipt_source='ARM diagnostic of actual FPGA decoded command; timestamp is corresponding TX slot start, not exact RX arrival; not ground confirmation',
            confirmed_ms=receipt,status=status,readback=dict(heartbeat_ms=c[7],media_paused=c[8],media_rate=c[9]) if receipt else None,
            downlink_route=[0,*range(relay,a['target']-1,-1)],receipt_route=[*range(a['target'],relay+1),0],
            executions=dict(trace.get('executions',[])).get(cid),before=before,after=after,verdict=verdict,explanation=text))
    return rows

def recommendations(snaps,p,events):
    if not snaps:return []
    s=snaps[-1];i=p['link'];node=i//4*4+1;now=s['round']*100;n=s['nodes'][node-1]
    age=now-n[10] if n[9] else None;recent=[r for x in snaps[-5:] for r in x.get('edge_trace',[])]
    failures=sum(not r[8] for r in recent);trials=len(recent);pending=s['pending']
    media=sample(s,node);available=media['total_bytes'] and (media['repeating'] or media['generated_fragments']*64<media['total_bytes'])
    current=commands(snaps,events)
    active=next((e for e in reversed(events) if e['action']['kind'] in ('change','restore') and e['effective_round']<=s['round']),None)
    common=dict(run_id=s['run_id'],observed_round=s['round'],link=i,node=node,
                evidence=dict(position_age_ms=age,failed_frames=failures,attempts=trials,network_pending=pending),
                review_after_s=5)
    if active and active['action']['kind']=='change' and (age is None or age>2000):
        return [dict(common,title='所选链路受扰，位置更新已受影响',
            advice='先恢复本次施加的信道扰动，检查恢复后生成的新心跳。降低媒体负载不能修复失效的物理链路，执行回执也可能在返回途中受阻。',
            effect='恢复后观察新心跳、同帧接收及媒体继续交付。',action=dict(kind='restore',window_s=10),category='channel')]
    latest=next((c for c in reversed(current) if c['target']==node and c['status']=='confirmed'),None)
    if available and latest and latest['readback'] and (latest['readback']['media_paused'] or latest['readback']['media_rate']<5):
        paused=latest['readback']['media_paused']
        return [dict(common,title='媒体限制已生效，可以恢复业务并观察',
            advice='当前限制已有真实回执。恢复后检查新分片生成与地面接收，不把重新排队当作已经收到。',
            effect='恢复媒体吞吐会增加普通业务负载；心跳时效仍单独观察。',
            action=dict(kind='command',window_s=10,command=dict(target=node,opcode=3 if paused else 4,value=0 if paused else 5,ttl_ms=10000)),category='business')]
    if available and (pending>=8 or failures):
        return [dict(common,title=f'节点 {node} 的普通媒体仍在生成，可做负载调整实验',
            advice='将普通媒体降至每秒1片，给心跳保留优先级；先确认执行回执，再比较同长度窗口的生成速率、位置年龄与积压。',
            effect='降低新媒体负载；文件会更晚收齐，不保证信道误码或心跳时效一定改善。',
            action=dict(kind='command',window_s=10,command=dict(target=node,opcode=4,value=1,ttl_ms=10000)),category='business')]
    if available:
        return [dict(common,title='当前业务正常，可验证一次可逆的媒体速率调整',
            advice=f'选择节点 {node} 将媒体改为每秒1片。观察生成与接收速率下降，再恢复每秒5片；当前没有拥塞，不能把减速称作性能改善。',
            effect='展示执行回执与真实负载变化；不会改变物理信道条件。',
            action=dict(kind='command',window_s=10,command=dict(target=node,opcode=4,value=1,ttl_ms=10000)),category='business')]
    return [dict(common,title='没有待生成的媒体，按当前业务选择措施',
        advice='若要验证状态更新频率，可调整心跳周期并观察实收心跳数；若要检验媒体限速，请开始新实验。查询状态仅用于诊断。',
        effect='参数回执与实际更新次数分别呈现。',action=None,category='information')]
