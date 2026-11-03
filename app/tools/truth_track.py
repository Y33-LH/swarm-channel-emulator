"""Dense display geometry from recorded ARM runtime, never a received position."""
import math,sys,hashlib,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
from product_scene import position

def track(snapshots,config,seed,duration,protocol,t,span=10):
    if not math.isfinite(t):raise ValueError('轨迹时间必须是有限数值')
    if not snapshots:raise ValueError('缺少本次实验的实板快照')
    confirmed=float(snapshots[-1]['round'])/10
    # duration=0 means continuous operation, not a zero-length trajectory.
    horizon=float(duration) if duration and duration>0 else confirmed+3.0
    t=max(0,min(t,horizon))
    times=[t+k for k in range(span) if t+k<=horizon]
    if times[-1]<horizon and len(times)<span:times.append(horizon)
    rows=[];runtimes=[]
    for tt in times:
        # Next snapshot contains the executed transitions before its boundary.
        # Each transition carries its own time; future commands do not leak back.
        s=next((s for s in snapshots if s['round']/10>=tt),snapshots[-1])
        runtime=dict(s.get('scene_runtime') or {})
        ext=runtime.get('external')
        if ext and ext[4]>tt*max(1,config.get("reserved",0)):
            earlier=[q['scene_runtime']['external'] for q in snapshots
                     if q.get('scene_runtime',{}).get('external') and q['scene_runtime']['external'][4]<=tt*max(1,config.get('reserved',0))]
            runtime['external']=earlier[-1] if earlier else None
        rows.append([list(position(n,tt,seed,config,protocol,runtime)) for n in range(1,17)])
        runtimes.append(runtime)
    return dict(t0=times[0],times=times,end_s=times[-1],step=1.,protocol=protocol,duration_s=duration,
                source='ARM_MODEL_REFERENCE_WITH_EXECUTED_STATE_NOT_RX',
                executed_state_available=bool(snapshots[-1].get('scene_runtime')),
                confirmed_model_s=snapshots[-1]['round']/10,
                extrapolated=times[-1]>snapshots[-1]['round']/10,
                runtime_id=hashlib.sha256(json.dumps(runtimes,sort_keys=True).encode()).hexdigest()[:16],samples=rows)
