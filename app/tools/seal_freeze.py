"""Pin a fresh-build candidate. Acceptance is a separate, evidence-backed record."""
from pathlib import Path
import hashlib, json, datetime
R = Path(__file__).resolve().parents[1]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
build = json.loads((R/'docs/product_build.json').read_text())
b = Path(build['build']).resolve()
assert b.is_relative_to((R/'results').resolve()) and b.name.startswith('board_')
assert build['rtl_verified'] and build['ps_init_identical'] and build['wns_ns'] >= 0 and build['whs_ns'] >= 0
assert sha(R/'ready/system_wrapper.bit') == build['bit_sha256']
assert sha(R/'ready/system.hdf') == build['hdf_sha256']
for p in (R/'sw').iterdir():
    if p.is_file(): assert sha(p) == sha(R/'sdk_workspace_product/swarm_app/src'/p.name), p.name
assert sha(R/'ready/swarm_app.elf') == sha(R/'sdk_workspace_product/swarm_app/Debug/swarm_app.elf')
m = dict(schema=1, name=R.name, development=True, accepted=False, version='000d0003', protocol=17,
         pl_hz=62500000, bit='ready/system_wrapper.bit', elf='ready/swarm_app.elf', init='ready/ps7_init.tcl',
         toolchain='Vivado + SDK 2018.3', part='xc7z020clg400-2', created=datetime.datetime.now().isoformat(),
         parent_manifest_sha256=sha(R/'docs/parent_step26_release.json'),
         acceptance_scope='Clean-source FPGA and ARM rebuild; fresh physical-board, UI and three consecutive 900-second acceptance required.',
         artifacts=[])
for p in sorted(R.rglob('*')):
    if not p.is_file() or p.name == 'release.json' or p.suffix == '.pyc': continue
    rel = p.relative_to(R)
    if rel.parts[0] in ('results', 'exports', 'configs', 'sdk_workspace_product') or '__pycache__' in rel.parts: continue
    m['artifacts'].append(dict(path=rel.as_posix(), sha256=sha(p)))
(R/'release.json').write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding='utf-8')
print('FROZEN_CANDIDATE', sha(R/'release.json'), len(m['artifacts']))
