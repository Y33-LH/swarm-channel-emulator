"""A user-driven experiment on the real 16-node network, with deterministic replay."""
import binascii, copy, hashlib, json, struct
import action_observation as ao
from product_config import DEFAULT, validate, config_hash
from product_scene import channel

SCHEMA=2
def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def plan(data):
    if not isinstance(data,dict):raise ValueError('实验设置必须是对象')
    link=data.get('link',0);seed=data.get('seed',20261021);seconds=data.get('seconds',90)
    for key,value,lo,hi in (('链路',link,0,15),('种子',seed,1,2**32-1),('时长',seconds,90,900)):
        if type(value)!=int or not lo<=value<=hi:raise ValueError(f'{key}范围 {lo}–{hi}')
    config=validate(data.get('config') or {**DEFAULT,'environment':1,'faults':0})
    if config['faults'] or config['external_node']:raise ValueError('因果实验请关闭预设故障和外部注入，避免混杂因素')
    p=dict(schema=SCHEMA,link=link,seed=seed,seconds=seconds,config=config,batch_rounds=10,
           config_sha256=config_hash(config),ideal=0,baseline_window_s=10,
           scope='Actual PL on every hop; one directed uplink changes; reverse ACK and other edges keep their scenario settings')
    if data.get('continuous') is True:p['continuous']=True
    p['sha256']=digest(p);return p

def action(data):
    kind=data.get('kind')
    if kind not in ('change','restore','advance','finish','command','pause','resume'):raise ValueError('未知实验动作')
    window=data.get('window_s',10)
    if type(window)!=int or not 1<=window<=60:raise ValueError('观察窗口为 1–60 模型秒')
    a=dict(kind=kind,window_s=window)
    if kind=='change':
        gain=data.get('gain_permille',50);sigma=data.get('sigma',8192)
        if type(gain)!=int or not 0<=gain<=1000 or type(sigma)!=int or not 0<=sigma<=8192:
            raise ValueError('幅度保留 0–1000‰；每路噪声 σ 为 0–8192 码值')
        a.update(gain_permille=gain,sigma=sigma)
    elif kind=='restore':a.update(gain_permille=1000,sigma=0)
    elif kind=='command':a['command']=ao.validate_command(data.get('command'))
    return a

def verify_observation(s,p,events):
    """Independent frame identity, CRC, received bytes and coefficient readback checks."""
    assert s.get('observation_schema')==1
    assert not s['edge_trace_overflow'],'Selected-hop trace truncated'
    o=s.get('observation')
    if not o:return
    a,m,phy=o['applied'],o['meta'],o['phy']
    assert o['link']==p['link'] and a[2]==0 and phy[2]==0
    assert a[1]==phy[1] and m[15]==phy[3]==s['watch_iq_generation']
    assert s['watch_phy']==phy and s['watch_iq']==o['iq']
    tx=bytes.fromhex(o['tx_hex']);rx=bytes.fromhex(o['rx_hex'])
    assert len(tx)==96 and tx[1]==m[1] and tx[4]==m[2]
    assert int.from_bytes(tx[12:16],'little')==m[3] and int.from_bytes(tx[16:18],'little')==m[4]
    if m[7]&4:
        assert len(rx)==96 and rx==tx,'RX mismatch: never fill from TX'
        assert binascii.crc_hqx(rx,65535)==(m[13]&65535)==(m[13]>>16)
    else:assert not rx
    if not phy[4]:assert not o['iq']
    policies=[e for e in events if e.get('condition_id')==m[0]]
    assert not m[0] or len(policies)==1
    c=channel(p['link'],a[1]/1000,p['seed'],p['config'],protocol=s.get('protocol',20),runtime=s.get('scene_runtime'))
    if p['config'].get('channel',{}).get('mode',0):
        from channel_model import frame,digital_scale
        f=frame(p['link'],a[1]/1000,p['seed'],p['config'],p['config']['channel'],s.get('scene_runtime'))
        scale=digital_scale(f,c['sigma']) if 'digital_scale' in o else 1.
        if 'digital_scale' in o:assert abs(scale-o['digital_scale'])<1e-8
        gains=[round(min(1,t[0]*scale)*32768) for t in f['taps'][:2]]
        if len(gains)==1:gains.append(0)
    else:scale=1.;gains=[round(min(1,c[k])*32768) for k in ('gain0','gain1')]
    sigma=round(c['sigma']*scale)
    if policies and policies[0]['action']['kind']=='change':
        policy=policies[0]['action']
        gains=[(g*policy['gain_permille']+500)//1000 for g in gains]
        sigma=policy['sigma']
    assert abs(a[3]-gains[0])<=1 and abs(a[4]-gains[1])<=1 and abs(a[5]-sigma)<=1,(a,c,policies)

def view(s,previous,p,events):
    if not s:return None
    i=p['link'];source=i+1;group=i//4
    affected=list(range(group*4+1,source+1))
    control=5 if group==0 else 1
    a=s['links'][i];b=previous['links'][i] if previous else [0]*21
    attempts=a[19]-b[19];good=a[2]-b[2];failed=a[5]-b[5]
    o=s.get('observation');obs=o and dict(
        model_ms=o['applied'][1],condition_id=o['meta'][0],sequence=o['meta'][3],
        origin=o['meta'][2],kind=o['meta'][1],fragment=o['meta'][4],
        captured=bool(o['phy'][4]),received=bool(o['meta'][7]&4),
        gain=o['applied'][3]/32768,sigma=o['applied'][5],generation=o['meta'][15],
        pre_errors=o['meta'][9],pre_bits=o['meta'][10],post_errors=o['meta'][11],post_bits=o['meta'][12])
    nodes=[]
    for node in (*affected,control):
        n=s['nodes'][node-1];old=previous['nodes'][node-1] if previous else [0]*11
        age=s['round']*100-n[10] if n[9] else None
        restores=[e for e in events if e['action']['kind']=='restore' and e['effective_round']<=s['round']]
        fresh_after_restore=bool(restores and n[9] and n[10]>=restores[-1]['effective_round']*100)
        nodes.append(dict(id=node,control=node==control,received_updates=n[9],new_updates=n[9]-old[9],
                          generation_ms=n[10] if n[9] else None,received_ms=n[7] if n[9] else None,
                          age_ms=age,sequence=n[8] if n[9] else None,xyz_mm=n[4:7] if n[9] else None,
                          fresh=age is not None and age<=2000,recovered=fresh_after_restore and age<=2000))
    return dict(model_s=s['round']/10,affected=affected,control=control,nodes=nodes,observation=obs,
                window_s=(s['round']-(previous or {}).get('round',0))/10,
                attempts=attempts,crc_good=good,failed=failed,retries=a[4]-b[4],
                pending=s['pending'],audio_bytes=s['media'][0],audio_total=s['media'][1],
                new_audio_bytes=s.get('media_totals',s['media'])[0]-(previous or {}).get('media_totals',(previous or {}).get('media',[0,0,0,0]))[0],
                video_bytes=s['media'][2],video_total=s['media'][3],
                new_video_bytes=s.get('media_totals',s['media'])[2]-(previous or {}).get('media_totals',(previous or {}).get('media',[0,0,0,0]))[2])

def measurement(s):
    """Exclude wall time and absolute hardware generation only, not failures or samples."""
    d=copy.deepcopy(s)
    for k in ('wall_ms','hardware_nodes'):d.pop(k,None)
    if d.get('tdma'):
        # ARM service is a wall-clock measurement, not model time. Retain it in
        # the original record, exclude only these two fields from exact replay.
        d['tdma'].pop('max_arm_transaction_us',None);d['tdma'].pop('arm_service_overruns',None)
    if d.get('watch_phy'):d['watch_phy'][3]=0
    d['watch_iq_generation']=0
    if d.get('observation'):
        d['observation']['phy'][3]=0;d['observation']['meta'][15]=0
    for cell in d.get('wall_iq',[]):cell[2]=0  # Absolute PL frame counter. Keep every IQ byte and timestamp.
    for row in d.get('edge_trace',[]):row[2]=0
    return d

def compare(original,current):
    left=original['snapshots'];right=current['snapshots']
    mismatches=[]
    for i,(a,b) in enumerate(zip(left,right)):
        if digest(measurement(a))!=digest(measurement(b)):mismatches.append(dict(index=i,round=a['round']))
    media_left=(original.get('report') or {}).get('media',{})
    media_right=(current.get('report') or {}).get('media',{})
    media_equal={k:v.get('sha256') for k,v in media_left.items()}=={k:v.get('sha256') for k,v in media_right.items()}
    return dict(exact_match=len(left)==len(right) and not mismatches and media_equal,
                compared_snapshots=min(len(left),len(right)),original_snapshots=len(left),
                current_snapshots=len(right),mismatches=mismatches,media_hashes_equal=media_equal,
                exclusions=['wall_ms','absolute FPGA generation','hardware endpoint diagnostics','ARM wall-clock service peak and overruns'])

def validate_reproduction(record):
    p=record['plan']
    timeline=digest([dict(round=e['effective_round'],action=e['action']) for e in record['events']])
    if record['report'].get('action_timeline_sha256')!=timeline:
        raise ValueError('操作时间轴摘要缺失或不一致；此记录可查看，但不能作为当前版重算基准')
    canonical=plan({k:p[k] for k in ('link','seed','seconds','config','continuous') if k in p})
    if canonical!=p:raise ValueError('记录的实验计划校验失败')
    last=-1
    for e in record['events']:
        a=action(e['action'])
        if a!=e['action'] or type(e['effective_round'])!=int or not last<=e['effective_round']<=(record['report']['stop_round'] if p.get('continuous') and record['report'].get('continuous') else p['seconds']*10-1) or e['effective_round']%p['batch_rounds']:
            raise ValueError('记录的操作时间轴校验失败')
        last=e['effective_round']
    expected=record['report'].get('measurement_sha256')
    if not expected or expected!=digest([measurement(s) for s in record['snapshots']]):
        raise ValueError('记录的观测摘要校验失败；不能作为原条件重算基准')

def evaluate(snaps,p,events):
    changes=[e for e in events if e['action']['kind']=='change']
    restores=[e for e in events if e['action']['kind']=='restore']
    result=dict(changes=len(changes),restores=len(restores),effect_observed=False,recovery_observed=False)
    if not changes or not restores:return result
    change=changes[0];restore=next((e for e in restores if e['effective_round']>change['effective_round']),None)
    if not restore:return result
    node=p['link']//4*4+1;control=5 if node==1 else 1
    degraded=[s for s in snaps if change['effective_round']+30<=s['round']<=restore['effective_round']]
    recovered=[s for s in snaps if s['round']>restore['effective_round']]
    result['effect_observed']=any(s['nodes'][node-1][9] and s['round']*100-s['nodes'][node-1][10]>2000
                                  and s['round']*100-s['nodes'][control-1][10]<=2000
                                  and any(r[1]==change['condition_id'] and not r[8] for r in s['edge_trace']) for s in degraded)
    result['recovery_observed']=any(s['nodes'][node-1][10]>=restore['effective_round']*100
                                    and s['round']*100-s['nodes'][node-1][10]<=2000
                                    and any(r[1]==restore['condition_id'] and r[8] for r in s['edge_trace']) for s in recovered)
    result.update(affected_node=node,control_node=control,changed_at_s=change['effective_round']/10,
                  restored_at_s=restore['effective_round']/10,
                  interpretation='These gates describe observed heartbeat disruption/recovery, not a forced test outcome; milder conditions may cause no business failure.')
    return result
