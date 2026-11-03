"""One-time candidate edits with exact source anchors."""
from pathlib import Path
r=Path(__file__).resolve().parents[1]
p=r/'sw/network.c';s=p.read_text()
s=s.replace('static void config_link(', '#include "link_control.h"\nstatic void config_link(',1)
s=s.replace(' /* Read back writable configuration', ' edge_apply(link);\n /* Read back writable configuration',1)
s=s.replace('if(!ack&&link==watch_link&&rd(100)', 'if(!observation_enabled&&!ack&&link==watch_link&&rd(100)',1)
s=s.replace(' if(!(rd(16)&4)){s->failed++;return 0;}', ' if(!ack)edge_observe(link,tx,source);\n if(!(rd(16)&4)){s->failed++;return 0;}',1)
s=s.replace('phy_snapshot[watch_link][i]);', '(observation_enabled&&observation_valid?observation_phy:phy_snapshot[watch_link])[i]);')
s=s.replace(' n+=snprintf(snapshot+n,sizeof(snapshot)-n,"}");\n if(n>=sizeof(snapshot))', ' n=edge_report(n);\n n+=snprintf(snapshot+n,sizeof(snapshot)-n,"}");\n if(n>=sizeof(snapshot))')
s=s.replace(' if(!strcmp(a[0],"NETWATCH")', ' if(edge_command(n,a))return 1;\n if(!strcmp(a[0],"NETWATCH")',1)
s=s.replace('watch_iq_count=watch_iq_ms=watch_iq_generation=0;}watch_link=v;', 'watch_iq_count=watch_iq_ms=watch_iq_generation=0;observation_valid=0;}watch_link=v;')
s=s.replace('command_count=command_trace_count=command_ack_drop=0;', 'edge_reset();command_count=command_trace_count=command_ack_drop=0;',1)
s=s.replace('while(batch--&&running){unsigned slot;', 'edge_trace_count=edge_trace_overflow=0;while(batch--&&running){unsigned slot;',1)
p.write_text(s)
p=r/'sw/main.c';s=p.read_text().replace('\\"protocol\\":17,\\"baud\\"','\\"protocol\\":17,\\"intervention_schema\\":1,\\"arm_build\\":\\"20261021-edge1\\",\\"baud\\"');p.write_text(s)
for name in ('build_sdk.tcl','rebuild_firmware.tcl'):
 p=r/name;s=p.read_text().replace('foreach name {','foreach name {link_control.h ');p.write_text(s)
p=r/'tools/seal_link_release.py';s=p.read_text().replace('parent_step21_release','parent_step22_release').replace("('results','exports','configs')","('results','exports','configs','sdk_workspace_product')").replace('Single-hop experiment/observation interface only; unchanged FPGA/ARM. Overall UI/network qualification is separate.','Directed-edge intervention and network business observation; ARM updated, FPGA unchanged. Acceptance requires new hardware evidence.');p.write_text(s)
# Keep runner generic: precise intervention hook can collect a full snapshot each batch.
p=r/'tests/network_acceptance.py';s=p.read_text().replace('batch=200,strict=True):','batch=200,strict=True,intervention=False):')
s=s.replace("ping=cmd('PING');assert ping['version']==0xd0003","ping=cmd('PING');assert ping['version']==0xd0003\n        if intervention:assert ping.get('intervention_schema')==1,'Load intervention firmware first'\n        cmd('LINKOBS '+str(int(intervention)))")
s=s.replace('full=not snapshots or','full=intervention or not snapshots or')
s=s.replace('if ideal and seconds<330:', 'if ideal and seconds<330 and not intervention:')
p.write_text(s)
print('Candidate ARM hooks and generic runner updated')
