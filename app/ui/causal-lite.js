/* 链路干预实验（精简版）：一个面板、四个按钮，替代旧版 7 步链条。
   功能不减：开始（记录基线）→ 施加/更新条件 → 恢复基线 → 停止 → 导出记录。
   全部走 /api/causal/* 实测接口，条件由 ARM 在窗口边界应用、FPGA 帧读回确认。 */
(() => {
 const E = id => document.getElementById(id);
 const say = t => { E('cxStatus').textContent = t; };
 const api = async (path, body) => {
  const r = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined);
  const d = await r.json().catch(() => ({}));
  if (!r.ok || d.error) throw new Error(d.error || ('HTTP ' + r.status));
  return d;
 };
 const sel = E('cxLink');
 if (!sel) return;
 sel.innerHTML = Array.from({ length: 32 }, (_, i) => {
  let a = i % 16 + 1, b = a % 4 ? a + 1 : 0;
  if (i >= 16) [a, b] = [b, a];
  return `<option value="${i}">${String(i).padStart(2, '0')} · ${a === 0 ? '地面' : a} → ${b === 0 ? '地面' : b} · ${i % 4 === 3 ? '空地' : '空空'}</option>`;
 }).join('');

 let curId = null, timer = null;
 const wrap = fn => async () => { try { await fn(); } catch (e) { say('未完成：' + e.message); } };

 function poll() {
  clearInterval(timer);
  timer = setInterval(async () => {
   try {
    const d = await api('/api/causal/state');
    if (!d.busy) { clearInterval(timer); timer = null; say('干预实验已结束并保存记录：' + (curId || '') + '；可点「导出记录」。'); }
   } catch (e) { clearInterval(timer); timer = null; }
  }, 1500);
 }

 E('cxStart').onclick = wrap(async () => {
  const r = await api('/api/causal/start', {
   link: Number(sel.value), seed: (Math.random() * 4294967295 | 0) || 1,
   seconds: Number(E('cxSeconds').value), continuous: false
  });
  curId = r.id || r.experiment?.id || null;
  say('已按场景基线开始：' + (curId || '记录中') + '。用「施加条件」改变该链路的信号与噪声，观察业务变化。');
  poll();
 });
 E('cxApply').onclick = wrap(async () => {
  if (!curId) throw Error('请先开始干预实验');
  await api('/api/causal/action', { id: curId, kind: 'change', window_s: 10, gain_permille: Math.round(Number(E('cxGain').value) * 10), sigma: Number(E('cxSigma').value) });
  say(`已提交：保留幅度 ${E('cxGain').value}% / 噪声 σ ${E('cxSigma')}；ARM 将在窗口边界应用，FPGA 帧读回确认。`);
 });
 E('cxRestore').onclick = wrap(async () => {
  if (!curId) throw Error('请先开始干预实验');
  await api('/api/causal/action', { id: curId, kind: 'restore', window_s: 10, gain_permille: 1000, sigma: 0 });
  say('已提交恢复场景条件；观察业务回到基线所需的时间。');
 });
 E('cxStop').onclick = wrap(async () => { await api('/api/stop', {}); say('已请求停止；实验收尾后自动保存。'); });
 E('cxExport').onclick = wrap(async () => {
  if (!curId) throw Error('暂无可导出的记录');
  const d = await api('/api/causal/export?id=' + encodeURIComponent(curId));
  E('cxSaved').textContent = '已导出：' + d.path;
 });
})();
