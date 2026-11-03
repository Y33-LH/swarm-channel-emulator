from pathlib import Path
r=Path(__file__).resolve().parents[1]
p=r/'ui/app.js';s=p.read_text(encoding='utf-8');s=s.replace("const report=history?.report||S.report,rid=", "const report=history?history.report:S.report,rid=");p.write_text(s,encoding='utf-8')
p=r/'ui/action-context.js';s=p.read_text(encoding='utf-8').replace('② 目标收到（诊断）','② 目标接收槽（诊断）');p.write_text(s,encoding='utf-8')
p=r/'ui/network-intervention.js';s=p.read_text(encoding='utf-8')
s=s.replace(".filter(e=>!historyRecord||e.effective_round<=(s?.round||0)),applied=", ".filter(e=>!historyRecord||e.effective_round<=(s?.round||0)).map(e=>historyRecord&&e.readback_ms>(s?.round||0)*100?{...e,readback_ms:null}:e),applied=")
s=s.replace("view?.events);", "(view?.events||[]).filter(e=>!historyRecord||e.effective_round<=(view?.latest?.round||0)));")
p.write_text(s,encoding='utf-8')
print('Historical media and future readbacks isolated')
