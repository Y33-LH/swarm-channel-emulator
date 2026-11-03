"""Fault diagnosis from received telemetry only; no timer changes outcomes."""
import re
from product_advice import validate_action

def diagnose(s, previous=None):
    if not s:return dict(issues=[],summary='等待实收数据',healthy=False)
    now=s['round']*100;commands=s.get('command_results',[]);periods={};rates={}
    prior=(previous or {}) if previous and previous.get('run_id')==s.get('run_id') else {}
    open_slow={i['node']:i for i in prior.get('recovery',{}).get('issues',[]) if i.get('slow_period_ms')}
    prior_nodes={n[0]:n for n in prior.get('nodes',[])}
    for c in commands:
        if c[4]==2:
            if c[2]==2:periods[c[1]]=c
            if c[2]==4:rates[c[1]]=c[3]
    issues=[]
    resolved=dict(prior.get('recovery',{}).get('resolved_heartbeats',{}))
    for n in s['nodes']:
        age=now-n[10] if n[9] else None
        cmd=periods.get(n[0]);period=(cmd[7] if len(cmd)>7 else cmd[3]) if cmd else 1000
        expired=now>3000 and (age is None or age>3000)
        old=open_slow.get(n[0])
        if not expired and not old:continue
        if period>3000 or old:
            # A sporadic packet at the slow rate is not recovery. Require two
            # fresh source timestamps at the restored cadence after its receipt.
            prev=prior_nodes.get(n[0]);ack_ms=cmd[5] if cmd and len(cmd)>5 else None
            if (period<=3000 and not expired and ack_ms is not None and prev and prev[9]
                    and prev[10]>=ack_ms and n[9]>prev[9] and 0<n[10]-prev[10]<=3000
                    and abs(n[10]-prev[10]-(n[9]-prev[9])*period)<=100):
                resolved[str(n[0])]=dict(node=n[0],period_ms=period,ack_ms=ack_ms,first_ms=prev[10],second_ms=n[10])
                continue
            resolved.pop(str(n[0]),None)
            action=f'节点 {n[0]} 心跳间隔 1000 毫秒' if period>3000 else None
            age_text='尚未收到' if age is None else f'{age/1000:g} 秒未更新'
            title=(f'节点 {n[0]} 心跳超期 · {age_text}' if expired and period>3000 else
                   f'节点 {n[0]} 心跳周期仍为 {period/1000:g} 秒' if action else f'节点 {n[0]} 等待连续心跳确认')
            issues.append(dict(kind='heartbeat',node=n[0],title=title,age_ms=age,
                overdue_ms=None if age is None else max(0,age-3000),slow_period_ms=period if action else old['slow_period_ms'],
                advice=(f'节点回执为 {period/1000:g} 秒，位置时效要求 3 秒。发送「{action}」。' if action else
                        f'节点已回执 {period} 毫秒，等待地面收到连续两次新心跳。'),command=action))
            continue
        issues.append(dict(kind='heartbeat',node=n[0],age_ms=age,overdue_ms=None if age is None else age-3000,
            title=f'节点 {n[0]} 心跳'+('尚未收到' if age is None else f'已 {age/1000:.1f} 秒未更新，超期 {(age-3000)/1000:.1f} 秒'),
            advice='检查上行逐跳确认和转发积压。',command=None))
    if s.get('pending',0)>=24:
        high=[n for n,r in rates.items() if r>5]
        issues.append(dict(kind='congestion',title=f'待转发业务积压 {s["pending"]} 条',pending=s['pending'],
            advice='先降低媒体负载，保留心跳与告警。'+('已收到高负载指令回执：'+','.join(map(str,high))+'。' if high else '积压也可能由链路故障导致，需同时检查逐跳接收。')+'执行后看积压下降，而非删除历史丢包计数。',command=f'节点 {high[0]} 媒体速率 1' if high else '节点 5 媒体速率 1'))
    if previous and previous.get('run_id')==s.get('run_id'):
        for i,(a,b) in enumerate(zip(s.get('links',[]),previous.get('links',[]))):
            attempts=a[19]-b[19];failed=a[5]-b[5]
            if i<16 and attempts>=2 and failed>=2 and failed/attempts>=.4:
                issues.append(dict(kind='link',link=i,title=f'链路 {i} 最近 {attempts} 次DATA尝试有 {failed} 次接收失败',
                    advice=f'先核对链路 {i} 的实际增益与噪声。若是人工衰减干预，可输入“恢复链路 {i}”调整回原条件；这是信道参数操作，不是节点自行修复。当前已有最多64次、最长60模型秒的有界重传，继续增加重传不能保证恢复。',command=f'恢复链路 {i}'))
    healthy=now>3000 and not issues
    return dict(model_ms=now,issues=issues,healthy=healthy,resolved_heartbeats=resolved,pending=s.get('pending',0),summary='；'.join(x['title'] for x in issues[:4]) or ('当前观测正常' if healthy else '正在建立心跳基线'))

def parse(text):
    text=str(text).strip();m=re.fullmatch(r'(?:恢复|还原)链路\s*(\d+)',text)
    if m:
        link=int(m[1])
        if not 0<=link<16:raise ValueError('上行链路编号为0–15')
        return dict(kind='restore',link=link,label=f'撤销链路 {link} 的实验扰动')
    m=re.fullmatch(r'节点\s*(\d+)\s*(心跳间隔|媒体速率|高度)\s*(\d+)\s*(毫秒|ms|秒|米|m|片/秒)?',text)
    if not m:raise ValueError('请写明目标与数值，例如：节点 5 媒体速率 1；节点 2 心跳间隔 1000 毫秒；恢复链路 4。不执行含糊指令或未实现的重组网。')
    node,kind,value,unit=int(m[1]),m[2],int(m[3]),m[4]
    if kind=='心跳间隔':
        if unit not in ('毫秒','ms','秒'):raise ValueError('心跳间隔必须注明毫秒或秒')
        if unit=='秒':value*=1000
    elif kind=='高度' and unit not in ('米','m'):raise ValueError('高度必须注明米')
    elif kind=='媒体速率' and unit not in (None,'片/秒'):raise ValueError('媒体速率单位为片/秒')
    action=validate_action(dict(target=node,opcode={'心跳间隔':2,'媒体速率':4,'高度':5}[kind],value=value,ttl_ms=10000))
    return dict(kind='command',action=action,label=text)
