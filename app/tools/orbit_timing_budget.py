"""Read-only orbit timing budget; never changes board state or fabricates motion."""
import sys,json,math,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from product_config import formation_points

def budget(config,model_seconds,wall_seconds,target=135):
    c=config
    fleet=max(math.hypot(x,y) for x,y in formation_points(c['formation']))*c['spacing_m']
    available=min(c['center_x_m'],10000-c['center_x_m'],c['center_y_m'],10000-c['center_y_m'])
    radius=max(0,.9*available-fleet-400)
    speed=c['speed_mmps']/1000
    if not speed or radius<=1:raise ValueError('No nonzero orbit')
    elapsed_rate=model_seconds/wall_seconds if wall_seconds else 0
    two=4*math.pi*radius/speed
    return dict(orbit_radius_m=radius,formation_radius_m=fleet,physical_speed_mps=speed,two_orbits_model_seconds=two,measured_model_per_wall_second=elapsed_rate,estimated_two_orbits_wall_seconds=two/elapsed_rate if elapsed_rate else None,required_speedup_over_current=two/elapsed_rate/target if elapsed_rate else None,target_wall_seconds=target,scope='Timing budget only; not measured two-orbit acceptance. Recent average rate may change with workload.')
if __name__=='__main__':
    state=json.load(urllib.request.urlopen('http://127.0.0.1:18878/api/state',timeout=20))
    snap=state.get('snapshot') or {}
    result=budget(state['config'],snap.get('round',0)/10,snap.get('wall_ms',0)/1000)
    result['record_id']=state.get('network_record_id')
    print(json.dumps(result,ensure_ascii=False,indent=2))
