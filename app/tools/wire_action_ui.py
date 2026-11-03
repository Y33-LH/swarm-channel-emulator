from pathlib import Path
r=Path(__file__).resolve().parents[1]
p=r/'ui/index.html';s=p.read_text(encoding='utf-8');s=s.replace('</head>','<link rel="stylesheet" href="action-context.css"></head>').replace('</body>','<script src="action-context.js"></script></body>');p.write_text(s,encoding='utf-8')
p=r/'ui/network-intervention.js';s=p.read_text(encoding='utf-8')
s=s.replace("modeButton.textContent='① 链路变化 → 业务影响'", "modeButton.textContent='① 链路与措施 → 业务效果'")
s=s.replace("else renderView();", "else {window.setActionContext?.({active:false});renderView();}")
s=s.replace("draw();buttons();syncSource();", "draw();buttons();syncSource();window.setActionContext?.({active,view,history:!!historyRecord,trace});")
s=s.replace("finish:'运行至结束'}", "finish:'运行至结束',command:'发送节点措施'}")
# The shared context card replaces ambiguous private replay navigation.
s=s.replace("E('cxLive').onclick=()=>{historyRecord=null;trace=[];view=cur;render();};", "E('cxLive').onclick=()=>{historyRecord=null;history=null;trace=[];view=cur;render();};")
p.write_text(s,encoding='utf-8')
print('Shared action UI installed')
