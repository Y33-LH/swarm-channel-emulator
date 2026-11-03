"""Action-aware grounded answers; generated text never directly controls the board."""
import re
from assistant_facts import node_mentions
from product_advice import validate_action

def extend(question,snapshot,context,rows):
    context=context or {};rows=list(rows);nodes=node_mentions(question)
    def add(id,title,text,evidence,action=None):
        rows.append(dict(id=id,title=title,advice=text,evidence=evidence,action=action,severity='notice'))
    if snapshot and snapshot.get('recovery'):
        for i,issue in enumerate(snapshot['recovery']['issues'][:4]):
            if nodes and issue.get('node') and issue['node'] not in nodes:continue
            text=issue['advice']
            if issue.get('command') and issue['command'] not in text:text+=' 建议文字指令：'+issue['command']+'。'
            if issue.get('slow_period_ms') and issue.get('command'):text+='收到执行回执和连续两次新心跳后确认恢复。'
            add('recovery_'+str(i),issue['title'],text,dict(issue,model_ms=snapshot['round']*100))
        if re.search('恢复|修好|正常|修复',question):
            for v in snapshot['recovery'].get('resolved_heartbeats',{}).values():
                if nodes and v['node'] not in nodes:continue
                if any(i.get('node')==v['node'] for i in snapshot['recovery']['issues']):continue
                add('heartbeat_resolved_'+str(v['node']),f"节点 {v['node']} 心跳已恢复",
                    f"节点回执为 {v['period_ms']} 毫秒，地面已收到源时间为 {v['first_ms']/1000:g} 秒和 {v['second_ms']/1000:g} 秒的新心跳。",v)
        if re.search('高度|编码|接收配置',question):
            add('recovery_bounds','措施的适用边界','高度指令允许100–800米且不能低于地形安全下限；没有对照测量，不能声称某一高度保证恢复，也不能一律建议下降。当前网络纠错链固定，不能用文字切换未实现的编码配置。',dict(source='validated_command_limits'))
    if snapshot and re.search('天气|地形|环境|现场',question):
        cfg=snapshot.get('config',{});env=cfg.get('environment',0)
        if not env:env=[1,3,4][min(2,snapshot['round']//3000)]
        weather=cfg.get('weather',0)
        en={1:'旷野',2:'乡村',3:'郊区',4:'城市',5:'山地',6:'丘陵',7:'高原'}.get(env,'未识别场景')
        wn=['晴天','雾','小雨','中雨','大雨','小雪','中雪','大雪'][weather]
        terrain_on=cfg.get('channel',{}).get('mode')==1 and bool(cfg.get('channel',{}).get('reserved0'))
        add('scene_brief','当前任务的环境简报',
            f'模型 {snapshot["round"]/10:g} 秒，场景设为{en}、{wn}。这些来自本轮配置，不是无人机实测气象或地形。'
            +'地面收到的心跳包含节点位置，可判断消息时效。'
            +('程序地形已参与单个主导障碍的绕射损耗计算；这是抽象地形模型，不是实测地形、多重绕射、建筑射线追踪或飞行避障。' if terrain_on else '程序地形遮挡当前关闭，地形只用于空间展示；没有实施飞行避障。')
            +('复杂场景应重点检查回波、接收失败和位置年龄。' if env in (4,5) else '仍应以当前接收结果判断通信，不能仅凭场景名称认定可靠。')
            +'若媒体积压，可以讨论降低生成速率，但必须确认执行回执并比较后续窗口；这不会消除噪声或修复衰减。',
            dict(model_ms=snapshot['round']*100,environment=env,weather=weather,source='scenario_configuration_not_sensor',terrain_affects_physics=terrain_on))
    if snapshot and re.search('信道|幅度|噪声|sigma|频偏|多径|星座|BER|EVM',question,re.I):
        o=snapshot.get('observation');link=context.get('link',snapshot.get('watch_link',0))
        if o and o['link']==link:
            a=o['applied'];m=o['meta'];fs=o.get('sample_rate_hz',snapshot.get('sample_rate_hz',8e6));cfo=(a[10]-2**32 if a[10]>=2**31 else a[10])*fs/2**32
            taps=o.get('taps',[])
            profile=(f'{len(taps)} 个实际复抽头；幅度 '+', '.join(f'{t[0]/32768:.4f}' for t in taps)+'；时延 '+', '.join(str(t[1]) for t in taps)+' 采样。') if taps else f'旧二径幅度 {a[3]/32768:.6f} / {a[4]/32768:.6f}。'
            add('applied_frame','所选DATA帧的实际应用参数',f'链路 {link}，模型 {a[1]/1000:g} 秒，FPGA帧 {m[15]}：'+profile+f'每路I/Q噪声σ {a[5]}码值，模型采样率 {fs/1e6:g} MSa/s，主径频偏 {cfo:.2f} Hz。以上是FPGA实际应用参数读回，不是接收端估计。'+('该帧正文校验成功。' if m[7]&4 else '该帧未交付有效正文，不拿旧成功帧替代。'),dict(link=link,model_ms=a[1],generation=m[15],registers=a,taps=taps,sample_rate_hz=fs))
        else:
            add('no_matched_parameters','没有当前所选链路的同帧参数','当前模式或时刻没有完整同帧应用参数；不能把另一条链路或更新后的ACK参数当作本帧读回。可在首页链路任务采集新DATA帧后再分析。',dict(link=link))
    if context.get('geometry_locked'):
        rows=[r for r in rows if r['id'] not in ('command_none','command_proposal','command_not_supported') or not re.search('高度|升高|下降|降低.*米',question)]
        if re.search('高度|升高|下降|降低.*米',question):
            add('height_locked','本任务固定几何条件','当前链路对照任务不接受高度变更。请结束或保存本次实验，再切到“整机 · 编队与业务”，选择非X形编队后发送模拟高度指令；等待执行回执及后续实收Z坐标。不能把升高当成必然改善信道。',dict(task='causal',locked=True))
    if len(nodes)==1 and nodes[0] in range(1,17):
        node=nodes[0];proposal=None;reason=None
        rate=re.search(r'(?:速率|频率)[^\d]{0,12}(\d+)\s*(?:分片|片|包|次)?\s*(?:/|每)?\s*秒',question)
        heartbeat=re.search(r'心跳(?:周期|间隔)[^\d]{0,10}(\d+)\s*(毫秒|ms|秒)',question)
        if rate:
            if node not in (1,5):reason='媒体源只有节点1语音与节点5视频，其他节点不能设置媒体生成速率。'
            else:proposal=dict(target=node,opcode=4,value=int(rate[1]),ttl_ms=10000)
        elif heartbeat:proposal=dict(target=node,opcode=2,value=int(heartbeat[1])*(1000 if heartbeat[2]=='秒' else 1),ttl_ms=10000)
        if proposal:
            try:validate_action(proposal)
            except ValueError as e:reason=str(e);proposal=None
        if proposal:
            rows=[r for r in rows if r['id'] not in ('command_none','command_proposal')]
            add('command_proposal',f'节点 {node} 的待确认措施',
                (f'媒体生成速率设为 {proposal["value"]} 分片/秒；只改变后续新分片，已经排队的数据继续传输。降低速率会推迟文件收齐，不能修复断链。' if proposal['opcode']==4 else f'心跳周期设为 {proposal["value"]} 毫秒；更低频率节省业务负载，但位置更新会变慢。')+'收到执行回执后再观察至少5模型秒，分别检查媒体新分片、积压与位置年龄，不预判改善。',dict(model_ms=snapshot['round']*100),proposal)
        elif reason:add('proposal_invalid','参数不适用',reason,{})
    if re.search('建议|怎么办|积压|限速|媒体|视频|语音|措施|改善|恢复',question):
        if re.search('噪声|信道|限速',question):
            add('load_not_noise','负载措施的作用范围','降低或暂停媒体只减少后续新分片，不能消除信道噪声、改善物理层信噪比或修复断链。是否减少积压、是否让心跳更及时，须看执行回执之后的独立时间窗。',dict(scope='queue_load_not_channel_repair'))
        for i,r in enumerate(context.get('recommendations',[])[:2]):
            action=(r.get('action') or {}).get('command')
            if action and nodes and action['target'] not in nodes:continue
            if any(x['id']=='command_proposal' for x in rows):action=None
            add('workflow_advice_'+str(i),r['title'],r['advice']+' '+r.get('effect',''),r['evidence'],action)
        for effect in [c for c in context.get('effects',[]) if not nodes or c['target'] in nodes][-2:]:
            add('measured_effect_'+str(effect['id']),f'节点 {effect["target"]} 措施 #{effect["id"]} 的实际效果',effect['explanation'],effect)
    if context.get('mode')=='history':
        for r in rows:r['action']=None
        add('history_scope','只读历史时刻',f'回答只依据 {context["model_ms"]/1000:g} 模型秒及以前的记录；不能在历史中发送指令，后续结果未用于当前判断。',dict(record_id=context['record_id'],model_ms=context['model_ms']))
    return sorted(rows,key=lambda r:0 if r["id"].startswith("recovery_") else 1)
