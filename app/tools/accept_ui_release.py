"""Qualify this UI revision without relabelling old physics evidence as a new algorithm test."""
from pathlib import Path
import json,hashlib,datetime,shutil
root=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
m=read(root/'release.json');digest=sha(root/'release.json')
for a in m['artifacts']:assert sha(root/a['path'])==a['sha256'],a['path']
ui=read(root/'results/instrument_ui/acceptance.json');assert ui['pass'] and not ui['errors']
candidates=sorted((root/'results').glob('instrument_hardware_*/acceptance.json'))
candidate=next((p for p in reversed(candidates) if read(p).get('pass') and read(p).get('manifest_sha256')==digest),None)
assert candidate,'A complete hardware/UI check against this exact manifest is required'
hw=read(candidate);assert hw['delivery']>.99 and hw['live_animation'] and hw['pause_freezes_animation'] and not hw['errors']
for name in ('bit','elf','init'):assert sha(root/m[name])==hw['image_hashes'][name]
shutil.copy2(root/'release.json',root/'results/instrument_tested_manifest.json')
result=dict(accepted=True,scope='UI revision qualified with identical parent FPGA/ARM firmware; no new radio or statistical channel certification',
            accepted_at=datetime.datetime.now().isoformat(),version=m['version'],tested_manifest_sha256=digest,
            ui='results/instrument_ui/acceptance.json',hardware=candidate.relative_to(root).as_posix(),
            hardware_full_run=hw['full_run'],wall_seconds=hw['wall_seconds'],delivery=hw['delivery'],timely=hw['timely'],
            strict_120s_pass=hw['performance_gates']['complete_within_120s'],human_usability_verified=False)
p=root/'results/instrument_acceptance.json';p.write_text(json.dumps(result,indent=2),encoding='utf-8')
m.update(accepted=True,development=False,acceptance_file=p.relative_to(root).as_posix(),acceptance_sha256=sha(p),tested_manifest_sha256=digest,accepted_at=result['accepted_at'])
(root/'release.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
print('INSTRUMENT_RELEASE_ACCEPTED',json.dumps(result))
