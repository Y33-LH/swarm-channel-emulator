"""Full media runs and a deliberately weak experiment; failed delivery stays visible."""
from pathlib import Path
import sys,time,json,uuid,hashlib
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests')]
from firmware_contract import VERSION,PROTOCOL,VERSION_HEX
from network_acceptance import run
from product_metrics import comparison
from product_config import validate
cases=[('open_clear',90,dict(environment=1,formation=7,faults=0)),
       ('open_rain',90,dict(environment=1,formation=7,weather=4,faults=0)),
       ('city_diamond_rain',900,dict(environment=4,formation=6,weather=4,spacing_m=250)),
       ('weak_channel',90,dict(environment=4,formation=8,spacing_m=1000,weather=4,reference_snr_cdb=1800,faults=0))]
reports=[]
for name,seconds,cfg in cases:
    if '--resume' in sys.argv:
        current=json.loads((ROOT/'release.json').read_text());hashes={k:hashlib.sha256((ROOT/current[k]).read_bytes()).hexdigest() for k in ('bit','elf','init')}
        matched=[]
        for p in (ROOT/'results').glob('network_*/acceptance.json'):
            r=json.loads(p.read_text())
            if r.get('duration_s')==seconds and r.get('seed')==20261013 and r.get('config')==validate(cfg) and r.get('image_hashes')==hashes:matched.append((p,r))
        if matched:
            p,r=max(matched,key=lambda x:x[0].stat().st_mtime);reports.append(dict(id=p.parent.name,name=name,report=r));print('REUSE_MATCHING_MEASUREMENT',name,p.parent.name,flush=True);continue
    rid='network_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6];out=ROOT/'results'/rid;out.mkdir()
    (out/'metadata.json').write_text(json.dumps(dict(id=rid,kind='network',source='hardware_uart',board_version=VERSION_HEX,scenario=name)))
    r,p=run('COM4',seconds,0,20261013,output=out,config=cfg,strict=False)
    reports.append(dict(id=rid,name=name,report=r))
    print('PRODUCT_SCENARIO',name,r['final']['delivered'],r['final']['generated'],r['wall_total_seconds'],flush=True)
assert reports[0]['report']['all_media_complete'] and reports[1]['report']['all_media_complete']
assert reports[2]['report']['all_media_complete'] and all(reports[2]['report']['performance_gates'].values())
compare=comparison(reports[0],reports[1]);assert compare['controlled_single_setting_comparison']
weak=reports[3]['report'];assert weak['final']['delivered']<weak['final']['generated']
summary=dict(**{'pass':True},scope='4 selected physical-board experiments, not all preset combinations',runs=[dict(id=x['id'],name=x['name'],wall=x['report']['wall_total_seconds'],gates=x['report']['performance_gates'],media_complete=x['report']['all_media_complete']) for x in reports],controlled_comparison=compare)
(ROOT/'results/product_scenarios_acceptance.json').write_text(json.dumps(summary,indent=2))
print('PRODUCT_SCENARIOS_PASS',flush=True)
