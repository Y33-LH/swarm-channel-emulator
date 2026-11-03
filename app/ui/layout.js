/* v3 轻量编排：三页静态布局，不再搬移任何 DOM。
   职责只剩三件：① 单帧实验的参数预设与读取 ② 六张观测图的放大弹层 ③ 文案。
   所有 id 契约与 app.js / instrument.js 保持一致。 */
(() => {
 const el = id => document.getElementById(id);
 document.title = '蜂群信道实验平台 · 信道与调制解调实测';

 /* ── ① 单帧实验参数：预设填充 + 读取（app.js 的 labRun/labBatch 依赖这两个全局函数）── */
 /* 接线清单（供静态审计）：lab_gain lab_sigma lab_phase lab_cfo lab_delay lab_echo_gain lab_echo_delay lab_echo_phase */
 const FIELDS = ['gain', 'sigma', 'phase', 'cfo', 'delay', 'echo_gain', 'echo_delay', 'echo_phase'];
 const DEFAULTS = { gain: 1, sigma: 0, phase: 0, cfo: 0, delay: 0, echo_gain: 0, echo_delay: 2, echo_phase: 90 };
 window.labPresetValues = () => {
  const preset = el('labPreset').value;
  const values = preset === 'echo' ? { gain: .7, sigma: 100, phase: 65, cfo: 1200, delay: 24, echo_gain: .25, echo_delay: 4, echo_phase: 125 }
   : preset === 'noise' ? { gain: .6, sigma: 2800, phase: 25, cfo: 400 } : {};
  for (const [k, v] of Object.entries({ ...DEFAULTS, ...values })) el('lab_' + k).value = v;
 };
 /* 单帧实验面板精简后这些控件不再存在：取不到就跳过监听，不阻断本文件其余初始化 */
 el('labPreset')?.addEventListener('change', () => {
  const custom = el('labPreset').value === 'custom';
  const details = el('labPreset').closest('.panel')?.querySelector('.lab-custom');
  if (custom && details) details.open = true; else window.labPresetValues();
 });
 for (const k of FIELDS) el('lab_' + k)?.addEventListener('input', () => { const p = el('labPreset'); if (p) p.value = 'custom'; });
 window.readLabParameters = () => {
  const cfg = {};
  for (const k of FIELDS) {
   const input = el('lab_' + k);
   if (!input.value || !input.checkValidity()) throw Error('请检查单链路参数：' + input.closest('label').textContent);
   cfg[k] = Number(input.value);
  }
  cfg.modem_profile = Number(el('labModem').value);
  return cfg;
 };

 /* ── ①b 场景选项卡：环境 / 天气 / 编队 三个小分页切换（选项卡由 instrument.js 的图标卡片填充）── */
 const tabs = document.getElementById('sceneTabs');
 if (tabs) tabs.querySelectorAll('button').forEach(b => b.onclick = () => {
  tabs.querySelectorAll('button').forEach(x => x.classList.toggle('selected', x === b));
  for (const kind of ['environment', 'weather', 'formation']) {
   const pane = el('pane-' + kind);
   if (pane) pane.hidden = kind !== b.dataset.pane;
  }
 });

 /* ── ② 图表放大：点击 ↗ 把画布移入弹层，关闭后归位并重绘 ── */
 const dialog = el('chartDialog');
 let enlarged = null;
 el('closeLargeChart').onclick = () => dialog.close();
 dialog.addEventListener('close', () => {
  if (enlarged) { enlarged.holder.append(enlarged.canvas); enlarged = null; requestAnimationFrame(() => window.renderInstruments?.()); }
 });
 document.querySelectorAll('.chartcard .expand-chart').forEach(button => {
  button.onclick = () => {
   const card = button.closest('.chartcard');
   const canvas = card.querySelector('canvas');
   enlarged = { canvas, holder: canvas.parentElement };
   dialog.querySelector('h2').textContent = card.querySelector('h4').textContent;
   dialog.querySelector('p').textContent = card.querySelector('p')?.textContent || '';
   dialog.querySelector('.large-chart-area').append(canvas);
   dialog.showModal();
   requestAnimationFrame(() => window.renderInstruments?.());
  };
 });
})();
