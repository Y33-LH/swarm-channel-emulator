"""Evidence-based simulator advice. Never sends a command or asserts real flight safety."""
import hashlib,json

def analyze(snapshot,previous=None,config=None,commands=()):
    if not snapshot:return []
    t=snapshot['round']*100;periods={n:1000 for n in range(1,17)}
    for c in commands:
        if c[2]==2 and c[4]==2:periods[c[1]]=c[3]
    rows=[]
    links=snapshot.get('links') or [];old=(previous or {}).get('links') or []
    same=previous and previous.get('run_id')==snapshot['run_id'] and previous.get('round',0)<snapshot['round'] and len(old)==len(links)
    def action_label(a):
        op=a['opcode'];v=a['value'];n=a['target']
        return {1:f'查询节点 {n:02d} 状态（先确认）',2:f'节点 {n:02d} 心跳间隔调至 {v} ms',
                3:(f'暂停节点 {n:02d} 普通媒体' if v else f'恢复节点 {n:02d} 普通媒体'),
                4:f'节点 {n:02d} 媒体降到 {v} 片/秒',5:f'节点 {n:02d} 模拟高度调到 {v} m'}.get(op,f'操作 {op}')
    def add(key,severity,title,evidence,advice,action=None,actions=None):
        # A single "query status" proposal never changes anything. Every card now
        # offers the concrete operations that can actually alter the observed
        # state, each labelled with what it does and what it is expected to fix.
        cand=actions if actions is not None else ([action] if action else [])
        labelled=[dict(a,label=action_label(a)) for a in cand if a and (a['opcode'] not in (3,4) or a['target'] in (1,5))]
        rows.append(dict(id=hashlib.sha256((str(snapshot['run_id'])+key).encode()).hexdigest()[:12],severity=severity,title=title,evidence=evidence,
                         advice=advice,action=labelled[0] if labelled else None,actions=labelled,
                         run_id=snapshot['run_id'],model_ms=t,scope='数字基带仿真实验；不直接控制真实无人机'))
    for n in snapshot['nodes']:
        age=t-n[10] if n[9] else None;threshold=3000 # Fixed position freshness SLA, independent of configured heartbeat period
        if (age is None and t>threshold) or (age is not None and age>threshold):
            group=(n[0]-1)//4+1;relay=group*4
            route=list(range(n[0]-1,relay));blocked=[]
            if same:
                blocked=[i for i in route if i<len(links) and links[i][19]>old[i][19] and links[i][3]==old[i][3]]
            detail=('本窗口未获 DATA 确认的跳段：'+', '.join(f'{i+1}→{0 if (i+1)%4==0 else i+2}' for i in blocked)+'。先查看这些跳段的捕获和重传；链路未恢复前重复查询也会受阻。' if blocked else f'检查第 {group} 组到中继 {relay} 的路径；恢复后可发一次状态查询，并以新心跳和回执确认。')
            add(f'stale_{n[0]}','critical' if age is None or age>10000 else 'warning',f'节点 {n[0]:02d} 的地面位置已过期',
                dict(node=n[0],last_source_model_ms=n[10] if n[9] else None,age_ms=age,threshold_ms=threshold,received_updates=n[9],relay=relay,unconfirmed_hops=blocked),
                detail+'当前为固定路由，系统不会自动绕行；恢复前不要把旧位置当作当前位置。',
                actions=[] if blocked else [dict(target=n[0],opcode=2,value=1000,ttl_ms=10000)])
    if same:
        for i,(x,y) in enumerate(zip(links,old)):
            tries=x[19]-y[19] if len(x)>19 else x[0]-y[0]
            retry=x[4]-y[4]
            if tries>=8 and retry/tries>.2:
                leaf=(i%16//4)*4+1
                add(f'retry_{i}','warning',f'链路 {i:02d} 最近重传较多',dict(link=i,window_start_ms=previous['round']*100,window_end_ms=t,data_attempts=tries,retries=retry,retry_fraction=retry/tries),
                    '优先保障心跳和告警；可暂停该组的普通媒体业务，再观察同一时间窗口内的重传和按时送达变化。降低业务负载不能修复物理信道本身。',
                    actions=[dict(target=leaf,opcode=3,value=1,ttl_ms=10000),dict(target=leaf,opcode=4,value=1,ttl_ms=10000)] if leaf in (1,5) else [dict(target=leaf,opcode=4,value=1,ttl_ms=10000)])
    late=snapshot.get('late_delivered',0)
    if late:
        add('late','warning','部分数据虽已送达，但超过业务时限',dict(late_delivered=late,timely_delivered=snapshot.get('timely_delivered'),max_model_ms=snapshot['delay_max_ns']/1e6,p95_upper_ms=snapshot.get('p95_upper_ms')),
            f'已有 {late} 条业务迟到，最终送达不代表及时可用。先在回放中定位故障或积压窗口，再保持相同场景与种子做对照；如存在媒体拥塞，可降低普通媒体负载。旧位置仅用于历史分析，不需要对所有节点重复查询。')
    cfg=config or {}
    if cfg.get('weather') in (4,6,7):
        add('weather','notice','当前选择了恶劣天气实验预设',dict(weather_id=cfg['weather'],model='controlled_parameter_overlay'),
            '先用晴天作为对照，保持编队、随机种子和负载不变，只改变天气预设。这里的参数不能替代真实气象信息或实际飞行许可判断。')
    if snapshot.get('queue_drops') or snapshot.get('retry_drops'):
        add('drop','critical','存在未送达数据',dict(queue_drops=snapshot.get('queue_drops'),expired=snapshot.get('expired'),attempt_limit=snapshot.get('attempt_limit'),pending=snapshot.get('pending')),
            '分别检查队列拥塞、超时和持续链路故障。保留原始结果，再降低普通业务负载做对照；不能从分母中删除这些失败数据。')
    if snapshot.get('pending',0)>=64:
        add('backlog','warning','等待转发的数据正在积压',dict(pending=snapshot['pending'],queue_peak=snapshot.get('queue_peak'),model_ms=t),
            '先查看哪个中继的心跳已过期。若该路径仍有普通业务，可暂停媒体以减少新负载；故障恢复后再观察积压是否下降。心跳和告警继续保留。',
            actions=[dict(target=1,opcode=3,value=1,ttl_ms=10000),dict(target=5,opcode=3,value=1,ttl_ms=10000),
                     dict(target=1,opcode=4,value=1,ttl_ms=10000),dict(target=5,opcode=4,value=1,ttl_ms=10000)])
    if snapshot.get('recovery'):
        rows=[r for r in rows if 'last_source_model_ms' not in r['evidence']]
        for i,issue in enumerate(snapshot['recovery']['issues']):
            add('recovery_'+str(i),'warning',issue['title'],issue,issue['advice'])
    return sorted(rows,key=lambda x:({'critical':0,'warning':1,'notice':2}[x['severity']],x['id']))

class AdviceTracker:
    """Stable cards; weak-link warning requires two windows, clears after two.

    Missing/stale position warnings are immediate. Card identity, first/last model
    time and resolved events are recorded; no synthetic success is generated.
    """
    def __init__(self):self.run=None;self.cards={};self.counts={};self.round=-1
    def update(self,snapshot,previous=None,config=None,commands=()):
        if self.run!=snapshot['run_id'] or snapshot['round']<=self.round:
            self.run=snapshot['run_id'];self.cards={};self.counts={}
        self.round=snapshot['round'];now=self.round*100;events=[]
        proposals={r['id']:r for r in analyze(snapshot,previous,config,commands)}
        for key,row in proposals.items():
            self.counts[key]=self.counts.get(key,0)+1
            if 'retry_fraction' in row['evidence'] and self.counts[key]<2:continue
            first=self.cards.get(key,{}).get('first_model_ms',now)
            if key not in self.cards:events.append(dict(event='advice_opened',id=key,title=row['title'],model_ms=now,severity=row['severity']))
            self.cards[key]=dict(row,first_model_ms=first,last_model_ms=now,clear_windows=0)
        for key in list(self.cards):
            if key not in proposals:
                self.counts[key]=0;self.cards[key]['clear_windows']+=1
                self.cards[key]['action']=None
                self.cards[key]['actions']=[]
                self.cards[key]['awaiting_clear_confirmation']=True
                if self.cards[key]['clear_windows']>=2:
                    events.append(dict(event='advice_resolved',id=key,title=self.cards[key]['title'],model_ms=now))
                    del self.cards[key]
        return list(self.cards.values()),events

def validate_action(action):
    if not isinstance(action,dict) or set(action)!={'target','opcode','value','ttl_ms'}:raise ValueError('指令字段不完整')
    if any(type(x)!=int for x in action.values()):raise ValueError('指令必须使用整数参数')
    n,op,val,ttl=(action[k] for k in ('target','opcode','value','ttl_ms'))
    if not 1<=n<=16 or not 100<=ttl<=60000:raise ValueError('节点或时限超界')
    valid=(op==1 and val==0) or (op==2 and 100<=val<=10000 and val%100==0) or (op==3 and val in (0,1)) or (op==4 and 1<=val<=30) or (op==5 and 100<=val<=800)
    if not valid:raise ValueError('指令超出允许范围')
    if op in (3,4) and n not in (1,5):raise ValueError('只有节点01语音源和节点05视频源具有媒体业务；此操作不适用于其他节点')
    return dict(action)
