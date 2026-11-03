"""Compare complete physical runs without hiding changes in protocol or actions."""
from product_metrics import comparison
from product_config import config_hash
import network_intervention as ni

def actions(record):
    return [dict(round=e['effective_round'],action={k:v for k,v in e['action'].items() if k!='window_s'})
            for e in record.get('events',[]) if e['action']['kind'] not in ('advance','finish')]

def compare(left,right):
    result=comparison(left,right)
    a=left.get('report') or {};b=right.get('report') or {};reasons=[]
    for label,r in [('A',left),('B',right)]:
        report=r.get('report') or {};snaps=r.get('snapshots',[])
        if not r.get('complete') or not snaps or snaps[-1]['round']!=report.get('duration_s',0)*10:
            reasons.append(label+'不是完整结束的实板记录')
        if not report.get('image_hashes') or not r.get('meta',{}).get('release_sha256'):
            reasons.append(label+'缺少固件或软件版本指纹')
        try:
            if config_hash(report.get('config',{}))!=report.get('config_sha256'):raise ValueError('配置摘要不一致')
            if r.get('plan'):ni.validate_reproduction(r)
        except (AssertionError,ValueError,KeyError) as e:reasons.append(label+'记录完整性未通过：'+str(e))
    conditions=result['changed_conditions']
    for key,va,vb in [('experiment_kind',left.get('meta',{}).get('kind'),right.get('meta',{}).get('kind')),
                      ('release_sha256',left.get('meta',{}).get('release_sha256'),right.get('meta',{}).get('release_sha256')),
                      ('observed_link',left.get('plan',{}).get('link'),right.get('plan',{}).get('link')),
                      ('action_timeline',actions(left),actions(right))]:
        if va!=vb:conditions[key]=dict(left=va,right=vb)
    # Matching commands are still interventions, not a pure scene-parameter study.
    if actions(left) or actions(right) or result['has_business_commands']:
        reasons.append('含用户信道干预或节点措施；只展示结果差异，不作纯场景参数归因')
    if not result['control_history_available']:
        reasons.append('缺少经过摘要验证的完整控制历史，不能排除未记录的操作影响')
    elif result['has_external_interventions']:
        reasons.append('UART 记录含运行中干预或外部报文，不作纯配置参数归因')
    if conditions:reasons.append('固定条件或版本不同：'+', '.join(conditions))
    changed=result['changed_config']
    if len(changed)>1:reasons.append('同时改变多个配置字段')
    qualified=not reasons
    mode='descriptive' if not qualified else 'repeat' if not changed else 'single_setting'
    if mode=='repeat':label='相同配置的重复实验；不是参数改变效果'
    elif mode=='single_setting':label='单设置对照；结果只适用于本组条件和种子'
    else:label='描述性对比；不能把差异归因于单一参数'
    composite=bool(set(changed)&{'environment','weather','formation'})
    result.update(mode=mode,label=label,controlled_single_setting_comparison=mode=='single_setting',
                  reasons=reasons,composite_preset=composite,
                  preset_note='场景、天气或编队是组合预设，会连带改变多个物理参数；不是只改变一个物理量。' if composite else '',
                  source='COMPLETE_BOARD_RECORDS',
                  qualification='同种子使输入可复现，但重传会改变采样时刻；单次对照不证明统计显著性或所有场景优势。',
                  left_conditions=dict(id=left['id'],config=a.get('config'),seed=a.get('seed'),seconds=a.get('duration_s'),link=left.get('plan',{}).get('link')),
                  right_conditions=dict(id=right['id'],config=b.get('config'),seed=b.get('seed'),seconds=b.get('duration_s'),link=right.get('plan',{}).get('link')))
    for side,r in [('left',left),('right',right)]:
        s=(r.get('report') or {}).get('final') or {};links=s.get('links') or []
        n=sum(x[11] for x in links);bits=sum(x[13] for x in links);errs=sum(x[14] for x in links)
        result[side].update(pending=s.get('pending'),heartbeat_received=sum(x[9] for x in s.get('nodes',[])),
            media_received_bytes=sum((s.get('media') or [0,0,0,0])[::2]),
            pre_ber=errs/bits if bits else None,evm_percent=sum(x[11]*x[12] for x in links)/n/10000 if n else None)
        o=(r.get('snapshots') or [{}])[-1].get('observation')
        if o:
            a=o['applied'];result[side+'_channel_sample']=dict(model_ms=a[1],gain0=a[3]/32768,gain1=a[4]/32768,sigma=a[5],delay_samples=a[6],echo_delay_samples=a[7],
                sample_rate_hz=o.get('sample_rate_hz',8000000),
                cfo_hz=(a[10]-2**32 if a[10]>=2**31 else a[10])*o.get('sample_rate_hz',8000000)/2**32,
                source='FPGA_APPLIED_DATA_READBACK_NOT_RX_ESTIMATE')
    result['delta']={k:result['right'][k]-v if isinstance(v,(int,float)) and isinstance(result['right'].get(k),(int,float)) else None for k,v in result['left'].items()}
    return result
