/* 态势播报与处置闭环（全部内容来自实收数据，不编造状态）：
   - 只在「状态迁移」时播报：实收告警帧（故障出现 / 故障恢复）与节点位置过期；
   - 每条播报回答四件事：谁出了问题、什么时候、什么问题、你可以怎么修；
   - [问 AI] 把问题交给本地证据助手（只引用本次实收证据）；
   - [去处理] 跳到指令面板并预选节点与操作，指令必须等执行回执才算生效；
   - 恢复后卡片变绿并给出中断持续时长，与你的指令回执对应起来。

   诚实边界：ALARM 表里的 1/3 两类告警来自**场景模型在固定模型秒预设的失效与衰减窗口**
   （固件 scene_node_off：节点 2 在 330–370 模型秒失联；涉及节点 12 的链路在 660–700 模型秒
   附加 12 dB 损耗，开关是第 2 页的「短时故障」配置项 faults）。它们的开始与结束都按时间表走，
   与任何节点的实收行为无关，**不代表系统具备故障自检或自恢复能力**。文案必须写明这一点，
   并且告诉用户可以把它关掉。 */
(() => {
 const E = id => document.getElementById(id);
 // 实收告警类型（与 app.js renderEvents 的口径一致）
 const ALARM = {
 1: { group: 'n2',  node: 2,  what: '通信中断', fault: true, scripted: true,
       fix: '【这是场景剧本，不是真实故障】固件在 330–370 模型秒按时间表把节点 2 置为失联（scene_node_off），开关是第 2 页的「短时故障」。开始与结束都由模型时间决定，与任何遥测或系统行为无关，不代表系统有故障自检测能力。你真正要做的只有核对：窗口结束后产生的新心跳才是有效位置。想让演示没有剧本，把「短时故障」设为 0 再开跑。' },
 2: { group: 'n2',  node: 2,  what: '通信恢复', fault: false, scripted: true },
 3: { group: 'r12', node: 12, what: '链路异常', fault: true, scripted: true,
       fix: '【这也是场景剧本】固件在 660–700 模型秒给经过节点 12 的链路附加 12 dB 损耗，同样由「短时故障」开关控制。中继 12 劣化会波及途经它的整组节点；你能做的是核实与减负：查询节点 12，业务拥挤时给节点 5 降媒体速率，窗口过去后调回。改善来自时间窗结束，不来自任何系统动作。' },
 4: { group: 'r12', node: 12, what: '链路恢复', fault: false, scripted: true }
 };
 const CMD_NAME = { 1: '查询状态', 2: '调整心跳周期', 3: '媒体暂停/恢复', 4: '调整媒体速率', 5: '调整模拟高度' };
 const CMD_STATE = { 1: '已进入发送队列', 2: '已收到执行成功回执', 3: '已收到拒绝回报', 4: '已收到过期回报', 5: '未获执行确认' };

 const bar = document.createElement('section');
 bar.id = 'alertCenter'; bar.className = 'alert-center';
 bar.innerHTML =
  '<div class="ac-head"><span class="ac-beacon ok" id="acBeacon"></span><b>态势播报</b>' +
  '<span id="acSummary">等待实板数据 · 出现故障时这里会说明是谁、什么时候、怎么修</span>' +
  '<button id="acToggle" type="button">详情</button></div>' +
  '<div class="ac-body" id="acBody" hidden><div id="acCards"></div>' +
  '<p class="ac-note">只播报实收告警帧与位置时效代表的状态迁移；没有新事件时不重复提示。<b>节点 2 与中继 12 的中断 / 衰减是场景模型按固定模型秒预设的事件（开关：第 2 页「短时故障」），不由实收行为驱动，不代表系统具备故障自检测能力。</b></p></div>';
 (E('globalHealth') || E('sourcebar') || document.querySelector('.scopebar') || document.body).after(bar);
 E('acToggle').onclick = () => { const b = E('acBody'); b.hidden = !b.hidden; E('acToggle').textContent = b.hidden ? '详情' : '收起'; };

 let recordKey = '', seen = new Set(); const incidents = new Map();
 let staleCard = null; // 位置过期的聚合卡片（就地更新，不逐节点刷屏）

 const fmtT = ms => (ms / 1000).toFixed(1) + ' 模型秒';
 const readonly = () => !!history || !!window.causalPresentation?.history;

 /* 本地模型没装时不许甩一句「AI 不可用」了事：用本次实收证据立刻给出规则诊断，
    并把问题原样留在输入框，用户在意的是答案不是借口。 */
 function localDiagnose(q) {
  const s = V?.snapshot;
  if (!s) return '尚无实收数据，无法诊断。请先在第 2 页开始一次实板实验。';
  const L = [];
  L.push(`模型时刻 ${(s.round / 10).toFixed(1)} s · 地面已收 ${s.delivered}/${s.generated} 条（${(100 * s.delivered / Math.max(1, s.generated)).toFixed(1)}%）。`);
  const stale = [], unknown = [];
  for (let n = 1; n <= 16; n++) { const d = nodeData(n); if (!d) continue; if (!d.known) unknown.push(n); else if (!d.fresh) stale.push(n); }
  if (stale.length) L.push(`位置已过期的节点：${stale.join('、')}——旧坐标保留但不可当作当前位置。`);
  if (unknown.length) L.push(`尚无实收位置的节点：${unknown.join('、')}。`);
  const lw = (S.link_windows || []).filter(x => x && x.data_attempts > 0);
  if (lw.length) {
   const worst = lw.slice().sort((a, b) => (b.retries / Math.max(1, b.data_attempts)) - (a.retries / Math.max(1, a.data_attempts)))[0];
   if (worst) L.push(`本窗口重传最重的链路 ${String(worst.link_id).padStart(2, '0')}：重传率 ${(100 * worst.retries / Math.max(1, worst.data_attempts)).toFixed(1)}%${worst.pre_ber != null ? `，纠错前 BER ${Number(worst.pre_ber).toExponential(2)}` : ''}。`);
  }
  if (s.pending) L.push(`等待转发积压 ${s.pending} 条，最大时延 ${((s.delay_max_ns || 0) / 1e6).toFixed(1)} ms。`);
  L.push('建议操作：先「查询状态」确认是真失联还是采样滞后；确为拥塞时再降低普通媒体速率给心跳与告警让路——链路未恢复前重复查询不会改善结果。');
  L.push('（本地模型未安装，以上为只引用本次实收证据的规则诊断，未调用任何大模型。）');
  return L.join('\n');
 }
 function askAI(q) {
  showTab('mission'); [...document.querySelectorAll('.p2-right [role=tab]')].find(b=>b.textContent==='AI问答')?.click();
  const box = E('question'); if (box) box.value = q;
  const btn = E('ask');
  if (btn && !btn.disabled) { btn.click(); return; }
  // 助手不可用时就地给出答案，而不是弹一句「不可用」
  const ans = E('answer'); if (ans) { ans.textContent = localDiagnose(q); ans.hidden = false; }
  const st = E('assistantStatus'); if (st) st.textContent = '本地模型未安装 · 已按实收证据给出规则诊断（下方即答案）';
  const det = document.querySelector('.assistantPanel details'); if (det) det.open = true;
  const an2 = E('answer'); if (an2) an2.scrollIntoView({ behavior: 'smooth', block: 'center' });
 }
 function gotoFix(node, op) {
  if (readonly()) { toast && toast('历史记录只读：请返回当前实板后再下发指令', true); return; }
  if (window.causalPresentation?.active) {
   window.openObservationPane?.('action');
   const t = E('actionTarget'); if (t) t.value = String(node);
   const o = E('actionOp'); if (o) { o.value = String(op); o.dispatchEvent(new Event('change')); }
  } else {
   showTab('mission'); document.querySelector('[data-side="node"]')?.click();
   const ns = E('nodeSelect'); if (ns) { ns.value = String(node); ns.dispatchEvent(new Event('change')); }
   const cd = E('controlDetails'); if (cd) cd.open = true;
   const co = E('commandOp'); if (co) { co.value = String(op); co.dispatchEvent(new Event('change')); }
   E('selectedNodeTitle')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
 }
 function aiText(kind, node, ms) {
  if (kind === 'stale') return `节点 ${node} 的地面位置已过期。请结合当前实收数据说明：它们还能相信吗？我下一步该做什么操作？`;
  return `节点 ${node} 在模型时刻约 ${(ms / 1000).toFixed(0)} 秒报告${ALARM[kind].what}。请结合当前实收数据说明：现在恢复了吗？位置是否新鲜？我该怎么处理？`;
 }
 function commandNote(node, sinceMs) {
  const rows = (V.snapshot?.command_results || S.commands || []).filter(c => c[1] === node);
  if (!rows.length) return '';
  const latest = rows[rows.length - 1];
  return `你的指令 #${latest[0]}（${CMD_NAME[latest[2]] || latest[2]}）：${CMD_STATE[latest[4]] || '状态未知'}`;
 }
 function addCard(o) {
  const cards = E('acCards'); if (!cards) return;
  const el = document.createElement('article');
  el.className = 'ac-card ' + o.level;
  el.innerHTML = `<div class="ac-card-head"><b>${o.title}</b><time>${o.time}</time></div>` +
   `<p></p><div class="ac-actions"></div><small class="ac-cmd"></small>`;
  // 正文两行截断节省版面，悬停 title 看全文
  const p = el.querySelector('p'); p.textContent = o.body; p.title = o.body;
  const actions = el.querySelector('.ac-actions');
  if (o.ai) { const b = document.createElement('button'); b.textContent = '问 AI：具体情况与操作说明'; b.onclick = () => askAI(o.ai); actions.append(b); }
  // 「去处理」必须给出能真正改变状态的动作，只预选「查询状态」等于什么都没做
  const fixes = o.fixes || (o.fixNode != null ? [{ node: o.fixNode, op: o.fixOp || 1, label: o.fixLabel || ('查询节点 ' + o.fixNode) }] : []);
  for (const f of fixes) { const b = document.createElement('button'); b.className = 'ac-fix'; b.textContent = f.label; b.onclick = () => gotoFix(f.node, f.op); actions.append(b); }
  el._cmd = { node: o.fixNode, since: o.sinceMs };
  cards.prepend(el);
  while (cards.children.length > 6) cards.lastChild.remove();
  return el;
 }
 function onAlarm(a) {
  const spec = ALARM[a[0]]; if (!spec) return;
  const ms = a[2];
  if (spec.fault) {
   const card = addCard({
    level: 'fault', title: `${spec.scripted ? '［场景剧本］' : ''}${spec.node === 12 ? '中继节点 12' : '节点 ' + spec.node} · ${spec.what}`,
    time: fmtT(ms) + ' · 实收告警帧', body: spec.fix,
    ai: aiText(a[0], spec.node, ms), fixNode: spec.node, fixOp: 1, sinceMs: ms,
    fixes: [{ node: spec.node, op: 1, label: `去处理：查询节点 ${String(spec.node).padStart(2, '0')}（确认是否真中断）` },
            { node: 1, op: 4, label: '减负：节点 01 媒体降到 1 片/秒（给恢复让路）' },
            { node: 5, op: 4, label: '减负：节点 05 媒体降到 1 片/秒' }]
   });
   incidents.set(spec.group, { startMs: ms, card, node: spec.node });
   // New incidents update the compact banner; details open only on request.
  } else {
   const inc = incidents.get(spec.group);
   const dur = inc ? (ms - inc.startMs) / 1000 : null;
   // 节点已恢复：撤下原故障卡片，只保留「已恢复」消息（故障详情不再占版面）
   if (inc) inc.card.remove();
   addCard({
    level: 'ok', title: `✔ ${spec.node === 12 ? '中继节点 12' : '节点 ' + spec.node} · 已恢复正常`,
    time: fmtT(ms) + ' · 实收恢复帧',
    body: (dur != null ? `中断持续 ${dur.toFixed(1)} 模型秒。` : '') + '请核对恢复时刻之后的新心跳；恢复不代表积压业务立即排空。',
    ai: `节点 ${spec.node} 刚报告恢复。请结合实收数据确认：恢复后的新心跳到了吗？业务积压还有吗？`,
    fixNode: null
   });
   incidents.delete(spec.group);
  }
 }
 function updateStale(s) {
  const stale = [];
  for (let n = 1; n <= 16; n++) { const d = nodeData(n); if (d && d.known && !d.fresh) stale.push(n); }
  if (!stale.length) {
   if (staleCard) { staleCard.remove(); staleCard = null; }
   return;
  }
  const names = stale.join('、');
  const body = `节点 ${names} 的地面位置已超过时效（依据实收心跳年龄）。旧坐标保留在地图上但不能当作当前位置。建议：选中节点发「查询状态」确认；若伴随中断告警，先处理告警。`;
  if (!staleCard) {
   staleCard = addCard({
    level: 'warn', title: `● 位置过期 · ${stale.length} 个节点`, time: '持续观测 · 实收心跳年龄',
    body, ai: aiText('stale', names), fixNode: stale[0], fixOp: 1,
    fixes: [{ node: stale[0], op: 1, label: `确认：查询节点 ${String(stale[0]).padStart(2, '0')}` },
            { node: stale[0], op: 2, label: `处置：节点 ${String(stale[0]).padStart(2, '0')} 心跳放宽到 2000 ms` },
            { node: 1, op: 4, label: '减负：节点 01 媒体降到 1 片/秒（给心跳让路）' }]
   });
  } else {
   staleCard.querySelector('b').textContent = `● 位置过期 · ${stale.length} 个节点`;
   staleCard.querySelector('p').textContent = body;
  }
 }
 function tick() {
  const key = (history?.id || S.network_record_id || '') + '';
  if (key !== recordKey) { recordKey = key; seen = new Set(); incidents.clear(); if (staleCard) { staleCard.remove(); staleCard = null; } const c = E('acCards'); if (c) c.innerHTML = ''; }
  const s = V?.snapshot;
  const beacon = E('acBeacon'), summary = E('acSummary'); if (!beacon || !summary) return;
  if (!s) { beacon.className = 'ac-beacon'; summary.textContent = '等待实板数据 · 出现故障时这里会说明是谁、什么时候、怎么修'; return; }
  for (const a of (s.alarm_events || [])) { const k = a.join(':'); if (!seen.has(k)) { seen.add(k); onAlarm(a); } }
  if (!readonly() && !s.recovery) updateStale(s);
  // 指令回执闭环：故障卡片上实时显示用户指令的状态
  E('acCards')?.querySelectorAll('.ac-card').forEach(card => {
   const meta = card._cmd; if (!meta || meta.node == null) return;
   const note = commandNote(meta.node, meta.since);
   const small = card.querySelector('.ac-cmd'); if (small && note) small.textContent = note;
  });
  const active = [...incidents.values()];
  if (active.length) {
   beacon.className = 'ac-beacon bad';
   const i = active[active.length - 1];
   summary.textContent = `进行中：节点 ${i.node} 异常 · 始于 ${fmtT(i.startMs)} · 点「详情」看处置建议`;
  } else if (staleCard) {
   beacon.className = 'ac-beacon warn';
   summary.textContent = '有节点位置过期 · 点「详情」查看是谁、该怎么办';
  } else {
   beacon.className = 'ac-beacon ok';
   const last = seen.size ? ' · 已记录 ' + seen.size + ' 条实收事件' : '';
   summary.textContent = (readonly() ? '历史记录 · 事件为保存时刻的实收结果' : '当前无进行中的异常') + last;
  }
 }
 const diagnosis=document.createElement('div');E('acBody').prepend(diagnosis);
 let lastDetail='';
 setInterval(()=>{
  tick();
  const issues=V?.snapshot?.recovery?.issues||[],bad=issues.length>0;
  bar.classList.toggle('has-observed-fault',bad);
  if(bad){E('acSummary').textContent='实测异常 · '+issues[0].title+(issues.length>1?' · 共 '+issues.length+' 项':'');E('acBeacon').className='ac-beacon bad';}
  else if(!readonly()&&S.snapshot?.recovery?.healthy){const last=(S.mission_timeline||[]).filter(e=>e.kind==='recover'||e.kind==='fault').at(-1);if(last?.kind==='recover')E('acSummary').textContent='实测恢复 · '+last.label;}
  const detail=issues.map(x=>x.title+'\n'+x.advice).join('\n\n')||'当前没有观测到新的业务异常。';
  if(detail!==lastDetail){diagnosis.textContent=detail;lastDetail=detail;}
 }, 600);
 window.alertCenter = { askAI, gotoFix };
})();
