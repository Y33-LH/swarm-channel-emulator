"""Comparable experiment summaries and explicit telemetry-window provenance."""
import math

def ratio(a,b):return a/b if b else None

def link_windows(snapshot,previous=None):
    current=snapshot.get('links',[]);old=(previous or {}).get('links',[])
    usable=bool(previous and previous.get('run_id')==snapshot.get('run_id') and previous['round']<snapshot['round'] and len(old)==len(current))
    start=previous['round'] if usable else 0
    interval=(snapshot['round']-start)/10
    rows=[]
    for i,v in enumerate(current):
        p=old[i] if usable else [0]*len(v)
        d=[a-b for a,b in zip(v,p)]
        # EVM field 12 is already a per-frame mean; it is not a counter.
        evm_samples=d[11]
        evm_mean=(v[12]*v[11]-p[12]*p[11])/evm_samples if evm_samples else None
        data=d[19] if len(d)>19 else 0
        rows.append(dict(link_id=i,start_model_ms=start*100,end_model_ms=snapshot['round']*100,
            data_attempts=data,ack_attempts=d[20] if len(d)>20 else None,
            attempts=d[0],captured=d[1],crc_good=d[2],acked=d[3],retries=d[4],duplicates=d[6],
            capture_rate=ratio(d[1],d[0]),crc_rate=ratio(d[2],d[1]),hop_success=ratio(d[3],data),
            post_bits=d[7],post_errors=d[8],post_ber=ratio(d[8],d[7]),pre_ber=ratio(d[14],d[13]),
            evm_percent=evm_mean/10000 if evm_mean is not None else None,
            unique_hop_payload_bps=ratio(d[17]*8,interval) if len(d)>17 else None,
            ack_failures=d[16] if len(d)>16 else None,active=bool(d[0]),
            source='FPGA_COUNTERS_AND_ARM_HOP_ACCOUNTING'))
    return rows

def comparison(left,right):
    a=left.get('report') or {};b=right.get('report') or {}
    ca=a.get('config') or {};cb=b.get('config') or {}
    def leaves(obj,prefix=''):
        result={}
        for k,v in obj.items():
            key=prefix+k
            if isinstance(v,dict):result.update(leaves(v,key+'.'))
            else:result[key]=v
        return result
    ca,cb=leaves(ca),leaves(cb)
    changed={k:dict(left=ca.get(k),right=cb.get(k)) for k in set(ca)|set(cb) if ca.get(k)!=cb.get(k)}
    constraints={k:dict(left=a.get(k),right=b.get(k)) for k in ('seed','duration_s','ideal','version','protocol','arm_build','image_hashes','telemetry_rounds','repeat_media','source_media_sha256') if a.get(k)!=b.get(k)}
    def summary(r):
        s=r.get('final') or {};n=s.get('generated',0)
        links=s.get('links') or []
        tb=sum(x[7] for x in links);te=sum(x[8] for x in links)
        pb=sum(x[13] for x in links);pe=sum(x[14] for x in links)
        return dict(delivery=ratio(s.get('delivered',0),n),timely_delivery=ratio(s.get('timely_delivered',0),n),
                    pre_ber=ratio(pe,pb) if pb else None,post_ber=ratio(te,tb) if tb else None,
                    fec_corrected_bits=None,  # Different coded/decoded bit domains; subtraction is invalid.
                    p95_upper_ms=s.get('p95_upper_ms'),max_ms=s.get('delay_max_ns',0)/1e6,
                    mean_ms=ratio(s.get('delay_sum_ns',0)/1e6,s.get('delivered',0)),
                    payload_bps=ratio(s.get('payload_bytes',0)*8,s.get('round',0)/10),
                    wall_seconds=r.get('wall_total_seconds'))
    sa,sb=summary(a),summary(b)
    traces=bool((a.get('final') or {}).get('command_results') or (b.get('final') or {}).get('command_results'))
    # A final command ledger can roll over. Only complete UART history can
    # establish that no external load/geometry/channel intervention occurred.
    histories=[x.get('control_history') for x in (left,right)]
    history_known=all(x is not None for x in histories)
    actions=any(x for x in histories)
    controlled=bool(a and b and a.get('image_hashes') and b.get('image_hashes') and not constraints and len(changed)<=1 and not traces and history_known and not actions and a.get('config_sha256') and b.get('config_sha256'))
    return dict(left_id=left['id'],right_id=right['id'],left=sa,right=sb,
                delta={k:sb[k]-sa[k] if isinstance(sa[k],(int,float)) and isinstance(sb[k],(int,float)) else None for k in sa},
                changed_config=changed,changed_conditions=constraints,has_business_commands=traces,
                control_history_available=history_known,has_external_interventions=actions,
                controlled_single_setting_comparison=controlled,
                qualification='Same seed is necessary but does not imply equal RF energy or equal channel sample timing; different command histories are not a controlled single-variable comparison.')
