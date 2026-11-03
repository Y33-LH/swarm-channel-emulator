"""Question-specific, timestamped facts. Never infer an unobserved node state."""
import re
from product_config import ENV_NAMES,WEATHER_NAMES,FORMATION_NAMES

def node_mentions(text):
    # Common spoken aliases are resolved before optional model inference.
    chinese={'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'十一':11,'十二':12,'十三':13,'十四':14,'十五':15,'十六':16}
    for word,num in sorted(chinese.items(),key=lambda x:-len(x[0])):
        text=re.sub(r'(?:节点|无人机|小|第)'+word+r'(?:号|架)?(?![一二三四五六七八九十])','节点'+str(num)+' ',text)
        text=re.sub(word+r'号(?:节点|无人机)?','节点'+str(num)+' ',text)
    text=re.sub(r'(\d{1,2})号(?:节点|无人机)?',r'节点\1 ',text)
    return list(dict.fromkeys(int(x) for x in re.findall(r'(?:节点|无人机|node|UAV[- ]?)\s*0*(\d{1,2})(?!\d)',text,re.I)))

def facts(question,snapshot,config,commands=()):
    cfg=config or {};s=snapshot;out=[]
    def add(id,title,text,evidence,action=None):
        out.append(dict(id=id,title=title,advice=text,evidence=evidence,action=action,severity='notice'))
    nodes=node_mentions(question)
    scopes=[]
    if nodes or re.search('位置|心跳|离线|节点|故障',question):scopes.append('node_health')
    if re.search('送达|丢包|吞吐|重传|时延|延迟|拥塞|可靠|成功',question):scopes.append('delivery')
    if re.search('信道|噪声|幅度|频偏|频移|多径|星座|sigma|EVM|SNR|BER|均衡|调制|解调|纠错|Turbo|DBPSK',question,re.I):scopes.append('channel')
    if re.search('场景|天气|城市|雨|雪|编队|间距|高度|晴天',question):scopes.append('configuration')
    if re.search('命令|指令|调整|改变|暂停|恢复|执行',question):scopes.append('command')
    if not scopes:scopes=['delivery','configuration']
    if not s:
        add('no_run','尚无当前实验接收记录','先检查连接并运行一次实验。配置预览只描述输入，不能判断节点是否在线或通信是否成功。',{})
    else:
        now=s['round']*100
        if 'node_health' in scopes:
            ids=nodes or [n[0] for n in s['nodes'] if not n[9] or now-n[10]>3000][:3]
            if not ids:ids=[1]
            for id in ids:
                n=next((x for x in s['nodes'] if x[0]==id),None)
                if n is None:
                    add(f'node_{id}','节点编号不存在','无人机编号为 1–16，0 是地面站。',dict(node=id));continue
                period=1000
                for c in commands:
                    if c[1]==id and c[2]==2 and c[4]==2:period=c[3]
                age=now-n[10] if n[9] else None;fresh=age is not None and age<=3000
                xyz=[v/1000 for v in n[4:7]] if n[9] else None
                route=list(range(id,((id-1)//4+1)*4+1))+[0]
                text=(f'地面累计收到 {n[9]} 次位置更新；最近源时间 {n[10]/1000:g} 秒，当前位置数据年龄 {age/1000:g} 秒。记录坐标 {xyz} 米。' if n[9] else '地面尚未收到该节点的位置，不能拿场景设定位置代替接收位置。')
                text+=f'固定上行路径为 {" → ".join(map(str,route))}。'
                action=None
                if not fresh and period>3000:
                    text+=f'已确认的心跳间隔为 {period} 毫秒。建议将其调至 1000 毫秒，收到新位置后再确认恢复。'
                    action=dict(target=id,opcode=2,value=1000,ttl_ms=10000)
                elif not fresh:
                    text+='检查路径上哪一跳缺少确认，以及中继是否积压。'
                add(f'node_{id}',f'节点 {id:02d}：'+('位置新鲜' if fresh else '位置不可作当前值'),text,dict(node=id,source_ms=n[10] if n[9] else None,age_ms=age,xyz_m=xyz,route=route),action)
        if 'delivery' in scopes:
            g=s.get('generated',0);d=s.get('delivered',0);timely=s.get('timely_delivered',0)
            text=f'累计生成 {g} 条、最终送达 {d} 条'+(f'（{d/g*100:.2f}%）' if g else '')+f'，其中按时送达 {timely} 条、迟到 {s.get("late_delivered",0)} 条。待转发 {s.get("pending",0)} 条；队列溢出 {s.get("queue_drops",0)} 条、过期 {s.get("expired",0)} 条、重试耗尽 {s.get("attempt_limit",0)} 条。'
            text+=('运行尚未结束，当前比率不是最终验收结果。' if s.get('running') else '以上为本次已结束实验的累计值。')
            if s.get('pending',0)>32:text+='优先保留心跳和告警；可在第二页暂停节点1或5的媒体新分片，再比较待转发量是否下降。已在队列中的数据不会因此消失。'
            else:text+='当前没有明显总队列积压；若仍有迟到，应检查故障区间和逐跳重传，而不是只提高重试次数。'
            add('delivery_current','送达与及时性',text,{k:s.get(k) for k in ('generated','delivered','timely_delivered','late_delivered','pending','queue_drops','expired','attempt_limit')})
        if 'channel' in scopes:
            id=s.get('watch_link',0);p=s.get('watch_phy',[])
            if len(p)>=12 and p[0]:
                raw=p[5];step=raw-(1<<32) if raw>=1<<31 else raw
                text=f'当前选中链路 {id} 的最近接收快照在模型 {p[1]/1000:g} 秒，帧类型为 {"ACK" if p[2] else "DATA"}。帧头'+('已捕获' if p[4] else '未捕获')+'，CRC '+('通过' if p[11]&8 else '未通过')+'。'
                sample_rate=s.get('observation',{}).get('sample_rate_hz',s.get('sample_rate_hz',cfg.get('channel',{}).get('sample_rate_khz',8000)*1000))
                if p[4]:text+=f'估计频偏 {step*sample_rate/(1<<32):.1f} Hz（本帧模型采样率 {sample_rate/1e6:g} MSa/s）。'
                text+='首页 PDP/CFR 由本帧实际应用的复抽头读回计算；接收端估计和原始/均衡 I/Q 单独显示，不能把设定值当作估计精度。'
                add('receiver_current','当前链路接收情况',text,dict(link=id,model_ms=p[1],captured=p[4],crc=bool(p[11]&8)))
            else:add('receiver_absent','没有所选链路接收快照','运行网络并在首页选择有数据的链路；若要单独比较纠错，请先结束整机实验，再用相同文本、信道和固定种子发送单帧。',{})
        if 'command' in scopes:
            selected=[c for c in commands if not nodes or c[1] in nodes]
            status={1:'等待地面回执',2:'收到执行成功回执',3:'收到参数拒绝回执',4:'收到指令过期回执',5:'等待超时，不能认定执行成功'}
            if selected:
                for c in selected[-3:]:add(f'command_{c[0]}',f'指令 #{c[0]} → 节点 {c[1]}',status.get(c[4],'未知状态')+f'；地面接收时间 {c[5]/1000:g} 模型秒。'+('高度调整要继续核对后续实收心跳 Z 坐标。' if c[2]==5 else '心跳周期与媒体设置以回执值及后续接收变化共同确认。'),dict(command=c))
            else:add('command_none','当前没有对应指令回执','可在第二页选择节点并确认发送：查询、心跳周期、媒体暂停/速率或模拟高度。文字问答不会自动发指令；点击发送也不等于已经执行。',{})
    if 'configuration' in scopes:
        names=(ENV_NAMES[cfg.get('environment',0)],WEATHER_NAMES[cfg.get('weather',0)],FORMATION_NAMES[cfg.get('formation',0)])
        add('configuration_current','本轮条件',f'{" / ".join(names)}；参考 SNR {cfg.get("reference_snr_cdb",3400)/100:g} dB，起伏尺度 {cfg.get("jitter_percent",100)}%。这是受控参数预设，未用真实气象或地形逐点标定。比较天气影响时保持种子、编队、负载与接收算法相同，只改天气；提高参考 SNR 可用于下一轮受控对照，不能代表已经改善真实飞行环境。',dict(config=cfg))
    if re.search('坠毁|保证|真实|2000|安全',question):add('scope','实验能力边界','系统没有接入真实无人机、GPS或气象传感器，不能判断实际坠毁或保证飞行安全。模拟高度允许100–800米、单次变化不超过100米；执行结果仍须由地面实收回执确认。',{})
    if len(nodes)==1 and 1<=nodes[0]<=16 and s:
        node=nodes[0];action=None;reason=None;absolute=re.search(r'(?:高度|升|降|设置|设|调整)(?:为|到|至)?\s*(\d+)\s*米',question)
        relative=re.search(r'(提高|升高|上升|降低|下降)\s*(\d+)\s*米',question)
        if absolute or relative:
            base=cfg.get('altitude_m',400)
            for command in commands:
                if command[1]==node and command[2]==5 and command[4]==2:base=command[3]
            for hn in s.get('hardware_nodes',[]):
                if hn[0]==node and hn[17]:base=hn[16]
            value=base+(1 if relative[1] in ('提高','升高','上升') else -1)*int(relative[2]) if relative else int(absolute[1])
            if not 100<=value<=800 or abs(value-base)>100:reason=f'目标 {value} 米超出允许范围，或与当前目标 {base} 米相差超过100米；没有生成发送指令。'
            else:action=dict(target=node,opcode=5,value=value,ttl_ms=10000)
        elif re.search('暂停.*(?:音|视频|媒体)',question):
            if node in (1,5):action=dict(target=node,opcode=3,value=1,ttl_ms=10000)
            else:reason='当前音频源是节点1，视频源是节点5；所选节点没有待暂停的媒体源。'
        elif re.search('恢复.*(?:音|视频|媒体)',question):
            if node in (1,5):action=dict(target=node,opcode=3,value=0,ttl_ms=10000)
        if action:add('command_proposal',f'可确认的节点 {node} 操作',('把模拟目标高度设为 '+str(action['value'])+' 米。' if action['opcode']==5 else ('暂停' if action['value'] else '恢复')+'媒体新分片。')+'这只是待确认建议；需要在运行中的同一轮实验点击确认，并观察实际回执和后续接收变化。',dict(proposal=action,model_ms=s['round']*100),action)
        elif reason:add('command_not_supported','未生成操作建议',reason,{})
    return out,scopes
