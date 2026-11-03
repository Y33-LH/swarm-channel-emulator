/* 链路干预面板（嵌入业务主线版）：运行中对一条有向链路施加/撤销幅度与噪声干预。
   机制与「进阶 · 链路干预对照实验」完全相同（固件 LINKCOND，批次边界应用，PL 帧读回确认），
   但不中断主实验：退化与恢复直接反映在地图链路颜色、逐窗质量、星座墙与 BER 表上。

   本版补上三件过去缺失的事：
   ① 过程可见：把「提交 → 批次边界生效 → 读回确认 → 指标退化 → 上层受影响 → 撤除注入 → 回到基线」
      做成显式阶段机，每一步都给出「现在依据什么」「接下来会发生什么」「还要等多久」；
   ② 处置可用：给出分层操作（撤销注入 / 业务侧减压 / 查询源端），全部走真实多跳下行指令，标明作用与代价；
   ③ 回落可量化：按窗口累积该链路指标轨迹，量化「注入撤除后从最差点回到场景基线」用了多少模型秒。

   诚实边界（不要在文案里越线）：整个流程的起点（施加）与终点触发（撤除）都是操作员按按钮，
   固件里既没有故障自动检测，也没有注入到期自动失效，更没有自动重路由。
   系统侧真正无人值守的行为只有两类：config_link() 每帧按节点几何与场景现算链路参数，
   以及 LLP 对失败分片的自动重传。所以这里量的是 recovery time（注入撤除后的回落时间），
   不是 autonomous self-healing，UI 文案必须照此表述。 */
(() => {
 const E = id => document.getElementById(id);
 const linkSel = E('ivLink');
 if (!linkSel) return;
 linkSel.innerHTML = Array.from({ length: 16 }, (_, i) => {
  const a = i + 1, b = a % 4 ? a + 1 : 0;
  return `<option value="${i}">${String(i).padStart(2, '0')} · ${a} → ${b || '地面'} · ${i % 4 === 3 ? '空地' : '空空'}</option>`;
 }).join('');
 linkSel.value = '5'; // 默认 06→07：中段链路，退化可见但不立刻掐断整组

 const post = async body => {
  const r = await fetch('/api/intervene', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok || d.error) throw new Error(d.error || ('HTTP ' + r.status));
  return d;
 };
 const wrap = fn => async () => { try { await fn(); } catch (e) { toast(e.message, true); } };

 /* ── 干预影响对比 + 回落轨迹 ── */
 let watch = null;          // 本次观测：{link, mode, before, atRound, after}
 let trace = [];            // 按窗口累积的该链路指标序列
 let lastTraceRound = -1;   // 同一 round 不重复取样（窗口数据每 10 模型秒才换一茬）
 let healStart = null;      // 提交恢复的模型秒（回落计时起点）
 let healed = null;         // 回落结论：{startMs, endMs, peak, base}
 let healPending = false;   // 恢复样本足够却未回落：如实标注，不下假结论
 let sceneBase = null;      // 施加干预「之前」的场景基线，是回落的归位目标
 let impactAt = null;       // 最近一次「上层受影响」的模型时刻（粘住：事实发生过就不该被滚动窗口抹掉）
 const BASE_KEY = link => 'ivSceneBase:' + (S.network_record_id || 'na') + ':' + link;

 const rowOf = link => (S.link_windows || [])[link] || null;
 const metricOf = w => w ? { evm: w.evm_percent, pre: w.pre_ber, post: w.post_ber, retries: w.retries, hop: w.hop_success, data: w.data_attempts } : null;
 const roundNow = () => (V?.snapshot?.round ?? 0);
 const msNow = () => roundNow() * 100;
 const srcNode = link => link + 1;                                   // 固件 txrxPairs：链路 i 的源是节点 i+1
 const linkLabel = link => { const a = srcNode(link), b = a % 4 ? a + 1 : 0; return `${String(link).padStart(2, '0')} · ${String(a).padStart(2, '0')} → ${b ? String(b).padStart(2, '0') : '地面'}`; };
 function focusLink(link) {
  const sel = E('linkSelect'); if (!sel) return;
  sel.value = String(link); sel.dispatchEvent(new Event('change'));
 }
 const pctFmt = v => v == null ? '—' : (v * 100).toFixed(1) + '%';        // 比率 0–1 → 百分比
 const evmFmt = v => v == null ? '—' : Number(v).toFixed(2) + '%';        // evm_percent 本身已是百分数，不可再乘 100
 const berFmt = v => v == null ? '—' : (v === 0 ? '0' : Number(v).toExponential(2));
 const numFmt = v => v == null ? '—' : String(v);
 const secFmt = ms => (ms / 1000).toFixed(1) + ' 模型秒';

 /* 最近一条对该链路有效的干预记录 */
 function lastIv(link) {
  const list = S.interventions || [];
  for (let i = list.length - 1; i >= 0; i--) if (list[i].link === link) return list[i];
  return null;
 }
 function ivEnabled(link) { const iv = lastIv(link); return !!(iv && iv.enabled && iv.response?.ok === 1); }

 /* 场景基线：施加干预「之前」的窗口读数，才是回落要回到的位置。
    页面刷新后仍可找回，否则刷新一次就再也量化不了回落。 */
 function baseOf(link) {
  if (!sceneBase) { try { const raw = sessionStorage.getItem(BASE_KEY(link)); if (raw) sceneBase = JSON.parse(raw); } catch (e) { } }
  return (sceneBase && sceneBase.link === link) ? sceneBase.metrics : null;
 }
 function rememberBase(link) {
  const m = metricOf(rowOf(link)); if (!m) return;
  sceneBase = { link, metrics: m };
  try { sessionStorage.setItem(BASE_KEY(link), JSON.stringify(sceneBase)); } catch (e) { }
 }

 /* ── 阶段机：每一步都要有实据，不靠猜 ── */
 function phase() {
  const link = watch?.link ?? Number(linkSel.value);
  const iv = lastIv(link);
  const active = ivEnabled(link);
  const r = roundNow();
  const eff = iv?.response?.effective_round;
  const rowsB = watch?.before;
  const src = baseOf(link);   // 场景基线（干预之前的读数）才是回落的归位目标
  const cur = trace.length ? trace[trace.length - 1] : null;

  // 施加后尚未到生效轮：ARM 还没应用
  if (active && eff != null && r < eff)
   return { id: 'pending', name: '① 已入队 · 等待批次边界' };
  // 已过生效轮但新窗口样本还不够：等PL读回+首足够样本
  const samplesSince = trace.filter(p => eff != null && p.round >= eff).length;
  if (active && samplesSince < 1)
   return { id: 'applied', name: '② 已生效 · 等待首个有效窗口' };
  // 恢复提交 / 恢复中：已无干预；没拿到可信场景基线时不下回落结论，只能说「尚无基线」
  if (!active && cur) {
   if (!src || src.evm == null) return healed ? { id: 'healed', name: '⑥ 已回到场景基线' } : { id: 'recovering', name: '⑤ 回落中 · 缺场景基线' };
   const backAtBase = Math.abs((cur.evm ?? 0) - src.evm) <= Math.max(1.0, Math.abs(src.evm) * 0.25);
   if (!healed && !backAtBase) return { id: 'recovering', name: '⑤ 回落中 · 指标正在恢复' };
   return { id: 'healed', name: '⑥ 已回到场景基线' };
  }
  // 处在干预中且已经能看出变差：区分「仅 PHY 变差」与「已影响到上层」
  // 注意：σ 一上去纠错前 BER 立刻就是 1e-2 量级，那属于物理层范畴；
  // 只有「LLP 开始重传」或「逐跳成功率掉下来」才说明已经咬到上层，不能用 BER 门槛判定。
  if (active && cur && baseOf(link)) {
   const src = baseOf(link);
   const worse = (cur.evm != null && src.evm != null && cur.evm - src.evm > 1)
    || ((cur.pre || 0) - (src.pre || 0) > 1e-6)
    || (cur.hop != null && src.hop != null && src.hop - cur.hop > 0.02);
   if (!worse) return { id: 'applied', name: '② 已生效 · 等待指标反映' };
   // 干预仍在且曾经咬到上层：粘住不退回，避免滚动窗口换茬后阶段来回跳
   if (impactAt != null) return { id: 'impact', name: '④ 已退化 · 上层受影响' };
   const upstream = (cur.retries ?? 0) > 0
    || (cur.hop != null && src.hop != null && src.hop - cur.hop > 0.02);
   if (upstream) impactAt = cur.t;
   return { id: upstream ? 'impact' : 'degraded', name: upstream ? '④ 已退化 · 上层受影响' : '③ 已退化 · 物理量变差' };
  }
  if (active) return { id: 'applied', name: '② 已生效 · 等待首批样本' };
  return { id: 'idle', name: '未施加干预' };
 }

 /* 每一步的「现在依据」与「接下来会经历什么」——措辞严格对应固件真实机制 */
 function narrative(p, link) {
  const iv = lastIv(link);
  const eff = iv?.response?.effective_round;
  const r = roundNow();
  const cur = trace.length ? trace[trace.length - 1] : null;
  const b = watch?.before;
  const src = baseOf(link);
  const waitRounds = eff != null ? Math.max(0, eff - r) : null;
  const step = (stage, title, now, next, eta) => ({ stage, title, now, next, eta });
  switch (p.id) {
   case 'pending':
    return step(1, '① 已入队 · 等待批次边界',
     `ARM 已受理 #${iv?.serial ?? '—'}，将在第 ${eff} 轮（当前 ${r} 轮）批次边界写入该链路 COND 参数。`,
     '条件写成功后，PL 帧会读回实际应用值；紧接着下一个观测窗口开始出现新的误码与重传。',
     waitRounds != null ? `约 ${waitRounds} 轮（≈ ${secFmt(waitRounds * 100)}）后生效` : '等待生效');
   case 'applied':
    return step(2, '② 已生效 · 等待指标反映',
     `已是第 ${r} 轮，干预已过生效轮${eff != null ? `（第 ${eff} 轮）` : ''}；观测窗口每 10 模型秒结一茬，需要新样本才能定论。`,
     '首个足够样本的窗口里，这条链路的 EVM 与纠错前 BER 会抬升；LLP 随即对失败分片自动重传，重传计数上升。',
     '再 1–2 个观测窗口（10–20 模型秒）可见');
   case 'degraded':
    return step(3, '③ 已退化 · 物理量变差',
     cur && src ? `EVM ${evmFmt(src.evm)} → ${evmFmt(cur.evm)}，纠错前 BER ${berFmt(src.pre)} → ${berFmt(cur.pre)}（窗口实读）；目前还没有重传、逐跳成功率未下降。` : '窗口样本尚未齐备。',
     '维持下去，LLP 会开始自动重传失败分片，逐跳成功率随之下降；路由上游节点的业务将开始积压，延迟上升。',
     '持续施加则上层影响可在数十模型秒内出现');
   case 'impact': {
     const nowTxt = cur && src ? `本窗口：重传 ${numFmt(cur.retries)} 次 · 逐跳成功率 ${pctFmt(src.hop)} → ${pctFmt(cur.hop)} · EVM ${evmFmt(cur.evm)}。` : '窗口样本计算中。';
     const latch = impactAt != null ? `最近一次上层受影响发生在 ${secFmt(impactAt)}（此后窗口可能已归于平静，但这次影响确实发生过）。` : '';
     return step(4, '④ 已退化 · 上层受影响', nowTxt + latch,
     '分片等待重传会抬高业务积压与延迟；若这条链路是某群组的必经段，下游的心跳与媒体也开始迟到。此刻若要止损，只能由操作员撤除注入（见下方处置清单）——LLP 的自动重传一直在跑，但停下这个注入源需要人动手。',
     '越晚恢复，积压排空越久');
   }
   case 'recovering':
    return step(5, p.id === 'recovering' && !src ? '⑤ 回落中 · 缺场景基线' : '⑤ 回落中 · 指标正在恢复',
     !src || src.evm == null
      ? '本次会话没有留下「施加干预之前」的窗口基线（例如页面刷新过或跨实验），因此无法量化回落幅度。'
      : `已撤销干预（第 ${r} 轮）；ARM 正在按场景条件重算这组链路参数，当前 EVM ${evmFmt(cur?.evm)}（目标基线 ${evmFmt(src.evm)}）。`,
     '每个批次重算一次；EVM 与 BER 通常在一到三个观测窗口内回到场景值，积压随重传排空逐步清零。注意：参数重算是 ARM 每帧的固有路径，不需要人工重配置；但「撤除注入」是你刚才手动触发的——固件没有故障自动检测，也没有自动重路由。',
     '预计 10–30 模型秒回到基线');
   case 'healed':
    return step(6, '⑥ 已回到场景基线',
     healed ? `回落耗时 ${healDurationText()}（自操作员撤销注入起计）：EVM 自峰值 ${evmFmt(healed.peak)} 回落到 ${evmFmt(cur?.evm)}（场景基线 ${evmFmt(healed.base)}）。` : `指标已回到场景条件（当前 EVM ${cur ? evmFmt(cur.evm) : '—'}）。`,
     '无需继续操作。这是「注入撤除后的回落时间」，不等同于无人机值守的自动修复；全过程曲线保留在上方轨迹图。',
     '已完成');
   default:
    return step(0, '未施加干预', '该链路按场景条件运行。',
     '点「施加」后：ARM 在下一个批次边界写入干预参数 → 该链路 EVM/BER 抬升 → LLP 自动重传 → 上层开始积压。起止都由你按按钮决定；系统侧无需人参与的只有每帧信道重算与链路层自动重传。',
     '待操作');
  }
 }

 /* ── 回落轨迹：每冒出新的一茬窗口数据就记一个点 ── */
 function pushSample() {
  if (!watch) return;
  const r = roundNow();
  if (r === lastTraceRound) return;
  const row = rowOf(watch.link); if (!row) return;
  const endMs = row.end_model_ms ?? msNow();
  // 窗口是 10 模型秒滚动的，用窗口末端对齐，天然降采样
  if (trace.length && Math.abs(endMs - trace[trace.length - 1].t) < 1000) { lastTraceRound = r; return; }
  lastTraceRound = r;
  trace.push({ t: endMs, round: r, evm: row.evm_percent, pre: row.pre_ber, retries: row.retries, hop: row.hop_success, link: watch.link });
  if (trace.length > 180) trace.shift();
  judgeHeal();
 }
 /* 回落判定：撤销干预后，指标首次「回到场景基线」容差内。
    基线必须是干预之前的场景读数，而不是撤销那一刻的恶化值——否则会把退化态当成目标。 */
 function judgeHeal() {
  if (!watch || !healStart || healed || trace.length < 2) return;
  const base = baseOf(watch.link);
  if (!base || base.evm == null) return;            // 没有可信基线就不下回落结论
  const afterHeal = trace.filter(p => p.t >= healStart);
  if (!afterHeal.length) return;
  const tol = Math.max(1.0, Math.abs(base.evm) * 0.25);
  const back = afterHeal.find(p => p.evm != null && Math.abs(p.evm - base.evm) <= tol);
  const worst = afterHeal.reduce((m, p) => (p.evm != null && (m == null || p.evm > m) ? p.evm : m), null);
  if (back) { healed = { startMs: healStart, endMs: back.t, peak: worst, base: base.evm }; healPending = false; return; }
  // 样本已经够了却一直没落回来：如实说明，不下假结论
  if (afterHeal.length >= 4) healPending = true;
 }
 /* 观测窗口是 10 模型秒一茬，落在一茬之内完成的回落不能谎报成 0 秒 */
 function healDurationText() {
  if (!healed) return '';
  const d = healed.endMs - healed.startMs;
  return d < 1000 ? '在本观测窗口内完成（窗口分辨率 10 模型秒，无法分辨更细）' : secFmt(d);
 }

 function startWatch(link, mode) {
  watch = { link, mode, before: metricOf(rowOf(link)), atRound: roundNow(), after: null };
  trace = []; lastTraceRound = -1; healPending = false; impactAt = null;
  if (mode === 'restore') { healStart = msNow(); healed = null; }
  else {
   healStart = null; healed = null;
   rememberBase(link);   // 施加干预的这一刻，场景条件读数就是将来「回落」要回到的位置
  }
  focusLink(link);
 }

 function drawTrace() {
  const cv = E('ivTrace'); if (!cv) return;
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth || 280, h = 74;
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); cv.style.height = h + 'px'; }
  const g = cv.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);
  if (trace.length < 2) return;
  const vals = trace.map(p => p.evm).filter(v => v != null);
  if (!vals.length) return;
  const b = watch?.before?.evm;
  let lo = Math.min(...vals, b ?? Infinity), hi = Math.max(...vals, b ?? -Infinity);
  if (hi - lo < 2) { const m = (hi + lo) / 2; lo = m - 1; hi = m + 1; }
  const pad = (hi - lo) * 0.15; lo -= pad; hi += pad;
  const t0 = trace[0].t, t1 = trace[trace.length - 1].t;
  const X = t => 4 + (t1 === t0 ? 0 : (t - t0) / (t1 - t0) * (w - 8));
  const Y = v => h - 14 - (v - lo) / (hi - lo) * (h - 26);
  // 基线
  if (b != null && b >= lo && b <= hi) {
   g.strokeStyle = '#3f6f8a'; g.setLineDash([3, 3]); g.lineWidth = 1;
   g.beginPath(); g.moveTo(0, Y(b)); g.lineTo(w, Y(b)); g.stroke(); g.setLineDash([]);
   g.fillStyle = '#6f93ab'; g.font = '9px Consolas'; g.textAlign = 'left';
   g.fillText('场景基线 ' + evmFmt(b), 3, Math.max(9, Y(b) - 3));
  }
  // 恢复提交点
  if (healStart != null && healStart >= t0) {
   g.strokeStyle = '#7ff0d4'; g.setLineDash([2, 3]); g.lineWidth = 1;
   g.beginPath(); g.moveTo(X(healStart), 0); g.lineTo(X(healStart), h - 14); g.stroke(); g.setLineDash([]);
   g.fillStyle = '#7ff0d4'; g.font = '9px sans-serif'; g.textAlign = 'left';
   g.fillText('撤销干预', Math.min(w - 52, X(healStart) + 2), h - 4);
  }
  // EVM 曲线
  g.strokeStyle = '#ffb02e'; g.lineWidth = 1.6; g.beginPath();
  let started = false;
  for (const p of trace) { if (p.evm == null) continue; const x = X(p.t), y = Y(p.evm); started ? g.lineTo(x, y) : (g.moveTo(x, y), started = true); }
  g.stroke();
  for (const p of trace) { if (p.evm == null) continue; g.fillStyle = '#ffcf7a'; g.beginPath(); g.arc(X(p.t), Y(p.evm), 1.7, 0, Math.PI * 2); g.fill(); }
  // 回落完成点
  if (healed) {
   const x = X(healed.endMs), y = Y(trace.find(p => p.t === healed.endMs)?.evm ?? healed.base ?? 0);
   g.strokeStyle = '#2df5c6'; g.lineWidth = 1.4;
   g.beginPath(); g.arc(x, y, 4, 0, Math.PI * 2); g.stroke();
   g.fillStyle = '#2df5c6'; g.font = 'bold 9px sans-serif'; g.textAlign = 'right';
   g.fillText('回落', x - 6, Math.max(9, y - 6));
  }
  g.fillStyle = '#5f7f96'; g.font = '9px Consolas'; g.textAlign = 'right';
  g.fillText('EVM % · ' + (t0 / 1000).toFixed(0) + '–' + (t1 / 1000).toFixed(0) + ' 模型秒', w - 3, h - 4);
 }

 /* ── 生命周期卡片 ── */
 const STAGES = ['① 入队生效', '② 等待样本', '③ 物理退化', '④ 上层受影响', '⑤ 撤除注入', '⑥ 回到基线'];
 function renderLifecycle() {
  const box = E('ivLifecycle'); if (!box) return;
  const link = watch?.link ?? Number(linkSel.value);
  const p = phase(), n = narrative(p, link);
  const active = ivEnabled(link);
  const cur = trace.length ? trace[trace.length - 1] : null;
  const stageIdx = Math.max(0, Math.min(STAGES.length - 1, n.stage - 1));
  const bar = STAGES.map((s, i) => `<span class="iv-step ${i < stageIdx ? 'done' : i === stageIdx && p.id !== 'idle' ? 'now' : ''}">${s}</span>`).join('<i class="iv-arrow">›</i>');
  const cls = { idle: '', pending: 'info', applied: 'info', degraded: 'warn', impact: 'alert', recovering: 'good', healed: 'ok' }[p.id] || '';
  box.className = 'iv-lifecycle ' + cls;
  box.innerHTML =
   `<div class="iv-head"><b>${esc(n.title)}</b><span class="tag ${cls}">${p.id === 'idle' ? '待操作' : active ? '干预中' : '恢复后'}</span></div>` +
   `<div class="iv-steps">${p.id === 'idle' ? '<span class="iv-step">尚未施加干预</span>' : bar}</div>` +
   `<div class="iv-now"><em>依据</em>${esc(n.now)}</div>` +
   `<div class="iv-next"><em>接下来</em>${esc(n.next)}</div>` +
   (n.eta ? `<div class="iv-eta"><em>预计</em>${esc(n.eta)}</div>` : '') +
   (cur ? `<div class="iv-reading">窗口实读 · EVM <b>${evmFmt(cur.evm)}</b> · 纠错前 BER <b>${berFmt(cur.pre)}</b> · 重传 <b>${numFmt(cur.retries)}</b> · 逐跳 <b>${pctFmt(cur.hop)}</b></div>` : '');
 }

 /* ── 回落结论 ── */
 function renderHeal() {
  const box = E('ivHeal'); if (!box) return;
  if (!watch) { box.innerHTML = ''; return; }
  if (healed) {
   box.className = 'iv-heal ok';
   box.innerHTML = `<b>✔ 已回到场景基线</b>：自 <b>${secFmt(healed.startMs)}</b> 操作员撤销注入，到 <b>${secFmt(healed.endMs)}</b> 回到场景基线，` +
    `耗时 <b>${healDurationText()}</b>；EVM 峰值 ${evmFmt(healed.peak)} → 当前 ${evmFmt(trace[trace.length - 1]?.evm)}（场景基线 ${evmFmt(healed.base)}）。` +
    `<small>准确含义：注入撤除后，ARM 按场景条件每帧重算该链路参数使其自行回到基线，期间没有人工重配置、没有重新组网。<b>触发这一步的是人的点击，不是系统自己检测到故障</b>——固件没有故障自动检测、没有到期自动失效、没有自动重路由。</small>`;
   return;
  }
  if (healStart) {
   const elapsed = msNow() - healStart;
   const base = baseOf(watch.link);
   box.className = 'iv-heal good';
   box.innerHTML = `<b>⟳ 回落进行中</b>：已撤销干预 ${secFmt(elapsed)}，` +
    `当前 EVM ${evmFmt(trace[trace.length - 1]?.evm)}${base ? `，场景基线 ${evmFmt(base.evm)}` : '（无场景基线可比对）'}。` +
    (healPending
     ? '<small>已有足够窗口样本但仍未回落到基线容差内：可能积压尚未排空，或同组还有其他链路在退化，请继续观察沿途窗口。</small>'
     : '<small>继续观察这条链路的 EVM 曲线，回落到场景基线即判定回落完成。</small>');
   return;
  }
  box.className = 'iv-heal'; box.innerHTML = '';
 }

 /* ── 操作员可做的事：全部走真实多跳下行指令，标明作用与代价 ── */
 function canSend() {
  return !!(S.snapshot && S.task === 'network' && ['running', 'paused'].includes(S.status) && !history);
 }
 function renderFix() {
  const box = E('ivFix'); if (!box) return;
  const link = watch?.link ?? Number(linkSel.value);
  const active = ivEnabled(link);
  const p = phase();
  if (p.id === 'idle') { box.className = 'iv-fix'; box.innerHTML = ''; return; }
  const node = srcNode(link);
  const mediaNode = node === 1 ? '语音' : node === 5 ? '视频' : null;
  const off = !canSend();
  const thereReason = off ? (history ? '历史记录只读' : !S.busy ? '实验未运行' : '当前不可下发') : '';
  const cmdBtn = (label, opcode, value, ttl, note) =>
   `<button data-op="${opcode}" data-val="${value}" data-ttl="${ttl}" data-node="${node}" ${off ? 'disabled' : ''} title="${off ? esc(thereReason) : esc(note)}">${esc(label)}</button>`;
  const items = [];
  if (active) items.push({
   tier: '根因', name: '撤掉你自己注入的劣化（这是唯一能真正解除的手段）',
   how: '撤销后 ARM 每帧按场景条件重算该链路参数，指标自行回落——注意触发者是你，不是系统检测到故障。',
   cost: '无副作用；需 10–30 模型秒回到场景基线。',
   btns: `<button id="ivFixUndo" ${off ? 'disabled' : ''}>由我撤销注入</button>`
  });
  if (active) {
   const btns = [cmdBtn(`查询节点 ${String(node).padStart(2, '0')} 状态`, 1, 0, 10000, '只诊断，不改变业务；回执经这条链路返回，同时验证链路还能不能走通。')];
   btns.push(cmdBtn(`放宽心跳到 2000 ms`, 2, 2000, 10000, '降低该源节点发帧密度，给重传留出空隙；代价是位置刷新变慢。'));
   if (mediaNode) btns.push(cmdBtn(`媒体降速到 1 片/秒`, 4, 1, 10000, `减轻该 ${mediaNode} 源在这条路上的压力；代价是媒体完成时间变长。`));
   if (mediaNode) btns.push(cmdBtn(`暂停 ${mediaNode}源`, 3, 1, 10000, '停止新增分片，让已有积压排空；代价是该源业务中断。'));
   items.push({
    tier: '减压（暂不撤销时）', name: mediaNode ? `给源节点 ${String(node).padStart(2, '0')} 降压 / 降速` : `给源节点 ${String(node).padStart(2, '0')} 放宽心跳`,
    how: '不动链路本身，从业务侧减少这条链路的单位时间负载，为重传腾出窗口。',
    cost: '会牺牲位置刷新频率' + (mediaNode ? '或媒体速率' : '') + '；下行与回执仍走真实多跳链路。',
    btns: btns.join('')
   });
  }
  if (!healed && healStart) items.push({
   tier: '核验', name: '确认回落是否已经落地',
   how: '向该链路源端下发查询，回执若能经这条链路返回，说明通路已经恢复正常。',
   cost: '无副作用。',
   btns: cmdBtn(`查询节点 ${String(node).padStart(2, '0')} 状态`, 1, 0, 10000, '回执往返本身就是链路已通的证据。')
  });
  if (healed) items.push({
   tier: '复检', name: '回落后再核一次，确认不是偶发回落',
   how: '向该链路源端下发查询或用不舒服的窗口继续观察；回执正常说明这条链路确实可用了。',
   cost: '无副作用。',
   btns: cmdBtn(`查询节点 ${String(node).padStart(2, '0')} 状态`, 1, 0, 10000, '回执往返即链路恢复的独立佐证。')
  });
  if (!items.length) { box.className = 'iv-fix'; box.innerHTML = ''; return; }
  box.className = 'iv-fix show';
  box.innerHTML = `<div class="iv-fix-title">操作员可以做的 · 分层${off ? ` <small>（当前不可下发：${esc(thereReason)}）</small>` : ''}</div>` +
   items.map((it, idx) => `<div class="iv-fixitem"><div class="iv-fixtag">${esc(it.tier)}</div><div><b>${esc(it.name)}</b><p>${esc(it.how)}</p><small>代价：${esc(it.cost)}</small><div class="iv-fixbtns">${it.btns}</div></div></div>`).join('');
  const undo = E('ivFixUndo'); if (undo) undo.onclick = () => E('ivRestore')?.click();
  box.querySelectorAll('[data-op]').forEach(b => b.onclick = () => {
   const a = { target: Number(b.dataset.node), opcode: Number(b.dataset.op), value: Number(b.dataset.val), ttl_ms: Number(b.dataset.ttl) };
   if (typeof window.prepareCommand === 'function') window.prepareCommand(a);
   else toast('指令通道不可用', true);
  });
 }

 function deltaCell(before, after, kind) {
  if (before == null || after == null) return '<td class="flat">—</td>';
  let d;
  if (kind === 'ber') d = after - before;
  else if (kind === 'evm') d = (after - before);
  else d = after - before;
  if (!isFinite(d)) return '<td class="flat">—</td>';
  const eps = kind === 'ber' ? 1e-9 : 0.05;
  const cls = Math.abs(d) < eps ? 'flat' : (kind === 'hop' ? (d > 0 ? 'down' : 'up') : (d > 0 ? 'up' : 'down'));
  let txt;
  if (kind === 'ber') txt = (d >= 0 ? '+' : '') + Number(d).toExponential(2);
  else if (kind === 'evm') txt = (d >= 0 ? '+' : '') + d.toFixed(2) + ' pp';
  else if (kind === 'hop') txt = (d >= 0 ? '+' : '') + (d * 100).toFixed(1) + ' pp';
  else txt = (d >= 0 ? '+' : '') + d;
  return `<td class="${cls}">${txt}</td>`;
 }
 function renderCompare() {
  const box = E('ivCompare'); if (!box) return;
  if (!watch) {
   const act = (S.interventions || []).filter(x => x.enabled).length;
   box.innerHTML = act ? `<p class="hint">有 ${act} 条链路处于干预中；选它并点「恢复」即可回到场景条件。</p>` : '<p class="empty">尚未施加干预。施加后这里显示：干预前 → 现在（EVM / 纠错前 BER / 重传 / 逐跳成功率）。</p>';
   return;
  }
  const cur = metricOf(rowOf(watch.link)); if (cur) watch.after = cur;
  const b = watch.before, a = watch.after;
  if (!a) { box.innerHTML = `<p class="hint">已对链路 ${linkLabel(watch.link)} 提交${watch.mode === 'apply' ? '干预' : '恢复'}，等待下个批次边界生效后即可看到前后对比…</p>`; return; }
  const rows = [
   ['EVM', evmFmt(b.evm), evmFmt(a.evm), deltaCell(b.evm, a.evm, 'evm')],
   ['纠错前 BER', berFmt(b.pre), berFmt(a.pre), deltaCell(b.pre, a.pre, 'ber')],
   ['纠错后 BER', berFmt(b.post), berFmt(a.post), deltaCell(b.post, a.post, 'ber')],
   ['本窗重传', numFmt(b.retries), numFmt(a.retries), deltaCell(b.retries, a.retries, 'num')],
   ['逐跳成功率', pctFmt(b.hop), pctFmt(a.hop), deltaCell(b.hop, a.hop, 'hop')]
  ];
  const worse = (a.evm != null && b.evm != null && a.evm - b.evm > 1) || ((a.pre || 0) - (b.pre || 0) > 1e-6);
  const better = (b.evm != null && a.evm != null && b.evm - a.evm > 1) || ((b.pre || 0) - (a.pre || 0) > 1e-6);
  const verdict = watch.mode === 'apply'
   ? (worse ? '<p class="verdict">✔ 干预已生效：该链路质量明显变差（见上表），中央八图与星座墙同步切到这条链路。</p>'
    : better ? '<p class="verdict">⚠ 指标反而变好：本窗口样本太少或干预尚未生效，请再等一个批次。</p>'
     : '<p class="verdict">本窗口尚无显著差异：干预在下个批次边界生效，请稍候再观察。</p>')
   : (better ? '<p class="verdict">✔ 已恢复：该链路指标回到场景条件。</p>' : '<p class="verdict">等待恢复生效并积累新样本…</p>');
  const baseRow = (watch.mode === 'restore' && sceneBase && sceneBase.link === watch.link)
   ? `<tr class="iv-baserow"><td>场景基线参照</td><td>${evmFmt(sceneBase.metrics.evm)}</td><td>${berFmt(sceneBase.metrics.pre)}</td><td class="flat">干预前</td></tr>` : '';
  const expandable = healed ? `<p class="verdict ok">回落 ${healDurationText()}（详见上方过程卡与轨迹图）。</p>` : '';
  box.innerHTML = `<div class="iv-cmp-head">链路 ${linkLabel(watch.link)} · ${watch.mode === 'apply' ? '干预前 → 现在' : '恢复前 → 现在'}</div>` +
   `<table><tr><th>指标</th><th>之前</th><th>现在</th><th>变化</th></tr>${rows.map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td>${r[3]}</tr>`).join('')}${baseRow}</table>${verdict}${expandable}`;
 }

 E('ivApply').onclick = wrap(async () => {
  const link = Number(linkSel.value);
  await post({ link, enabled: 1, gain_permille: Math.round(Number(E('ivGain').value) * 10), sigma: Number(E('ivSigma').value) });
  startWatch(link, 'apply');
  toast(`已由你注入劣化：链路 ${linkLabel(link)} 幅度保留 ${E('ivGain').value}% + 噪声 σ ${E('ivSigma').value}。` +
   `接下来：ARM 在下个批次边界写入 → 1–2 个窗口内 EVM/BER 抬升 → LLP 自动重传（系统自己的行为）→ 上层积压。退化由这个注入造成，不是系统故障。`);
 });
 E('ivRestore').onclick = wrap(async () => {
  const link = Number(linkSel.value);
  await post({ link, enabled: 0, gain_permille: 1000, sigma: 0 });
  startWatch(link, 'restore');
  toast(`已由你撤销注入：链路 ${linkLabel(link)} 的叠加系数不再生效。接下来 ARM 每帧按场景条件重算参数，指标在 10–30 模型秒内回到场景基线；轨迹图会标出这段回落耗时（起点是你的撤销动作）。`);
 });

 // 干预记录列表：随全局状态刷新
 function render() {
  const list = S.interventions || [];
  const el = E('ivList');
  const state = E('ivState');
  // 按链路取「最后一条」记录，否则恢复之后还会显示成干预中
  const lastByLink = new Map();
  for (const x of list) lastByLink.set(x.link, x);
  const active = [...lastByLink.values()].filter(x => x.enabled && x.response?.ok === 1);
  if (state) { state.textContent = active.length ? `干预中 · ${active.map(x => String(x.link).padStart(2, '0')).join('/')}` : '未施加'; state.className = 'tag' + (active.length ? ' warn' : ''); }
  // 每次状态刷新先攒一个窗口样本，再渲染过程卡
  pushSample();
  renderLifecycle(); drawTrace(); renderHeal(); renderCompare(); renderFix();
  if (!list.length) { el.innerHTML = '<p class="empty">尚无干预；实验运行中可施加。</p>'; return; }
  el.innerHTML = list.slice(-6).reverse().map(iv => {
   const ok = iv.response?.ok === 1;
   return `<div class="bizitem ${ok ? 'ok' : 'warn'}"><p><b>#${iv.serial} ${iv.enabled ? '⚠ 施加干扰' : '✔ 恢复链路'}</b> · 链路 ${linkLabel(iv.link)}</p>` +
    `<small>${iv.wall || ''} · 模型时刻 ${iv.round != null ? (iv.round / 10).toFixed(0) + ' s' : '—'} · ${ok ? `ARM 已受理，第 ${iv.response.effective_round} 轮起生效（等 PL 帧读回确认）` : '拒绝：' + esc(iv.response?.error || '未知')}</small></div>`;
  }).join('');
 }
 const base = window.renderInstruments;
 window.renderInstruments = () => { base?.(); render(); };
 // 切换观察链路：丢弃上一条链路的观测上下文，避免把 A 链路的回落证据套到 B 链路上
 linkSel.addEventListener('change', () => {
  const link = Number(linkSel.value);
  if (watch && watch.link === link) return;
  watch = null; trace = []; lastTraceRound = -1; healStart = null; healed = null; healPending = false;
  render();
 });
 render();
})();
