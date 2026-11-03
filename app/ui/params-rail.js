/* 参数栏驱动：左栏固定调制解调链参数 + 本次场景配置，右栏选中链路的实收信道读回，第 2 页节点状态表。
   全部数据来自 V/S/catalog/observedChannel，不生成任何推测值。
   同时补回 workbench.js 移除后缺失的三个全局函数（instrument.js/app.js 依赖）。 */
(() => {
'use strict';
/* ── 补回 workbench.js 的全局函数（原样逻辑，勿改换算口径）── */
const signed32 = v => v >= 2147483648 ? v - 4294967296 : v;
window.currentLab = () => !history && ['lab', 'labnoise'].includes(S.task) ? S.lab : null;
const selectedObservation = id => Observation.select(V.phy_live,V.snapshot,id) || Observation.select(V.phy_links?.[id],V.snapshot,id);
window.frameObservation = () => selectedObservation(Number(document.getElementById('linkSelect')?.value||0));
window.observedChannel = id => {
  const r = window.currentLab();
  if (!r) return selectedObservation(id)?.channel || null;
  const a = r.applied_registers;
  if (!a) return null;
  return { lab_id: r.id, applied: true, gain0: a[64] / 32768, gain1: a[120] / 32768, sigma: a[68],
    cfo_hz: signed32(a[92]) * 8e6 / 2 ** 32, phase_radians: a[84] * 2 * Math.PI / 2 ** 32,
    echo_cfo_hz: signed32(a[132]) * 8e6 / 2 ** 32, echo_phase_radians: a[128] * 2 * Math.PI / 2 ** 32,
    delay_samples: a[112], echo_delay_samples: a[124] };
};
window.receiverPoints = () => {
  const r = window.currentLab();
  if (r) return r.iq;
  const id = Number(document.getElementById('linkSelect')?.value || 0);
  return selectedObservation(id);
};

const $ = id => document.getElementById(id);
const f2 = (v, n = 2) => Number.isFinite(v) ? Number(v).toFixed(n) : '—';
const rows = (el, pairs) => { if (el) el.innerHTML = pairs.map(([k, v]) => `<div class="prow"><span>${k}</span><b>${v}</b></div>`).join(''); };

/* ── 信道档案：固件同源环境参数表（与 sw/scene_product.c environments[8][10] 完全一致）──
   参数序：0 路径损耗指数η, 1 附加损耗dB, 2 回波相对功率dB, 3 回波超额时延μs, 4 衰落深度,
           5 衰落周期s, 6 噪声附加dB, 7 回波多普勒幅度Hz, 8 损耗起伏界dB, 9 位置扰动界m */
const CH_ENV = [null,[2,0,-18,.125,.05,8,0,1,.2,3],[2.1,1,-15,.1875,.075,7,.5,1.5,.4,6],[2.2,2,-12,.25,.1,6,1,2,.6,9],[2.4,4,-9,.5,.2,4,2,5,1.2,18],[2.3,3,-10,1,.18,5,1.5,4,1,12],[2.2,2,-13,.5,.12,6,1,3,.7,9],[2.05,.5,-16,.25,.08,7,.4,2,.35,5]];
const CH_WEATHER_LOSS = [0,.01,.02,.05,.15,.01,.03,.08];
function chSmooth(t,start){const u=Math.max(0,Math.min(1,(t-start)/20));return u*u*(3-2*u);}
function chParam(k,t,env){ // 与固件 parameter(k,t) 同逻辑：env=0 时三环境按模型时间混合
  if(env)return CH_ENV[env][k];
  const a=chSmooth(t,300),b=chSmooth(t,600);
  return CH_ENV[1][k]*(1-a)+CH_ENV[3][k]*(a-b)+CH_ENV[4][k]*b;
}
/* 信道档案的实时部分：固定环境的档案参数在固件里本来就是常量（这是事实，不是故障），
   但运行中每批都有 FPGA 寄存器读回（g0/g1/σ/时刻），必须在这里可见地滚动，
   否则用户看到的是一张死表。按 run_id+链路 记录本轮极值，换实验/换链路自动清零。 */
let _prof=null;
function drawChannelProfile() {
  const el = $('channelProfile'); if (!el) return;
  const cfg = V.snapshot?.config || preview?.config || S.config || {};
  const env = cfg.environment ?? 1;
  const t = V.snapshot ? V.snapshot.round / 10 : 0;
  const link = Number($('linkSelect')?.value || 0);
  const ag = link % 4 === 3; // 空地链路叠加规则与固件 scene_link() 一致
  const jp = (cfg.jitter_percent ?? 100) / 100;
  const c = window.observedChannel(link);
  const live = !!(c && c.applied !== false && !c.lab_id && Number.isFinite(c.gain0));
  const key = [history?.id || S.network_record_id,V.snapshot?.run_id,V.snapshot?.config_id,link].join(':');
  if (!_prof || _prof.key !== key) _prof = {key, n: 0, g0: [Infinity, -Infinity], g1: [Infinity, -Infinity]};
  const stamp = c ? [c.model_ms,c.generation].join(':') : null;
  if (live && _prof.stamp !== stamp) {
    _prof.stamp = stamp;
    _prof.n++;
    for (const [k, v] of [['g0', c.gain0], ['g1', c.gain1]]) {
      _prof[k][0] = Math.min(_prof[k][0], v); _prof[k][1] = Math.max(_prof[k][1], v);
    }
  }
  const range = k => _prof[k][0] <= _prof[k][1] ? `${f2(_prof[k][0], 4)} – ${f2(_prof[k][1], 4)}` : '—';
  const fixed = env !== 0;
  const note = fixed
    ? (catalog?.environment?.find(x => x.id === env)?.name || '环境 ' + env) + ' · 档案固定（固件常量）'
    : `三环境混合 · t=${f2(t, 0)}s`;
  const cc=cfg.channel,meta=c?.model_metadata;
  if(cc&&cc.mode!==0){
   rows(el,[['系数来源',cc.mode===2?'用户自主抽头':'场景驱动等效抽头'],['小尺度模型',['无随机衰落','Rayleigh SOS','Rician SOS'][cc.fading]],['传播路径数',c?.taps?.length??'待读回'],['平均功率损耗',meta?f2(meta[0],3)+' dB':'待同帧模型回执'],['标准雨衰',meta?f2(meta[1],6)+' dB/km':'待读回'],['散射上界',f2(cc.scatter_millihz/1000)+' Hz'],['时间演化','帧首 SOS；帧内幅相一阶推进'],['噪声','独立参考 SNR；不随天气改写'],['数字公共缩放',c?f2(c.digital_scale??1,6):'—'],['地形绕射',cc.reserved0&&c?.terrain?f2(c.terrain[0],3)+' dB':'关闭'],['主障碍净空',cc.reserved0&&c?.terrain?f2(c.terrain[2],1)+' m':'—'],['模型系数越界',c?c.coefficient_limited||0:'—'],['说明','等效路径，不是射线追踪；模型量非接收机估计']]);return;
  }
  rows(el, [
    ['当前档案', note + (ag ? ' · 空地叠加' : ' · 空空')],
    ['路径损耗指数 η', f2(chParam(0,t,env)+(ag?.2:0), 2)],
    ['附加损耗', f2(chParam(1,t,env)+(ag?2:0), 1) + ' dB'],
    ['回波相对功率', f2(chParam(2,t,env)+(ag?3:0), 1) + ' dB'],
    ['回波超额时延', f2(chParam(3,t,env)*(ag?2:1), 3) + ' μs'],
    ['衰落深度', f2(chParam(4,t,env)*(ag?1.5:1), 3)],
    ['衰落周期', f2(chParam(5,t,env)*(ag?.75:1), 1) + ' s'],
    ['噪声设定', (V.snapshot?.protocol>=20?'仅由用户参考 SNR 决定':'历史版本：随场景变化')],
    ['回波多普勒幅度', f2(chParam(7,t,env)*(ag?1.6:1), 1) + ' Hz'],
    ['损耗起伏界', f2(chParam(8,t,env)*(ag?1.5:1)*jp, 2) + ' dB'],
    ['天气附加损耗', f2(CH_WEATHER_LOSS[cfg.weather ?? 0], 2) + ' dB/km' + (ag ? '（空地×1.5）' : '')],
    ['实时读回 · 链路', live
      ? `#${link} ${c.tx} → ${c.rx === 0 ? '地面' : c.rx} · 模型 ${f2((c.model_ms || 0) / 1000, 1)} s`
      : (V.snapshot ? '等待本链路寄存器读回' : '开始实验后逐批滚动')],
    ['主径 g0 实读', live ? f2(c.gain0, 4) : '—'],
    ['回波 g1 实读', live ? f2(c.gain1, 4) : '—'],
    ['噪声 σ 实读', live ? f2(c.sigma, 1) : '—'],
    ['本轮 g0 范围', range('g0')],
    ['本轮 g1 范围', range('g1')],
    ['独立观测帧', _prof.n ? _prof.n + ' 帧' : '—'],
  ]);
}

/* ── 左栏 ①：调制解调链 · 固定参数（来自设计与文档，写死也如实标注"固定"）── */
function drawModemParams() {
  const cfg = V.snapshot?.config || preview?.config || S.config || {};
  const fs=V.snapshot?.sample_rate_hz||cfg.channel?.sample_rate_khz*1000||8e6;
  const carrier = cfg.carrier_mhz ? f2(cfg.carrier_mhz, 0) + ' MHz' : '2400 MHz';
  rows($('modemParams'), [
    ['调制方式', 'DBPSK 差分相移键控'],
    ['符号率', (fs/4e6)+' Msym/s'],
    ['调制位速率', (fs/4e6)+' Mbit/s · 非净荷吞吐'],
    ['等效采样率', (fs/1e6)+' MSa/s（4 点/符号）'],
    ['载波频率 · 场景', carrier],
    ['信道模型', cfg.channel?.mode?'1–8 复抽头 + AWGN':'二径复系数 + AWGN'],
    ['帧结构', '96 字节/帧 · 净荷 64 B'],
    ['帧校验', 'CRC-16'],
    ['纠错链', '扰码 → 交织 → 卷积 → Turbo'],
    ['判决', '软判决（硬判决可对照）'],
    ['同步', 'PN 帧头捕获 + 频偏估计'],
    ['定时', 'Gardner 插值定时恢复'],
    ['均衡', '训练辅助复数 DFE'],
    ['多址', 'TDMA 100 ms/轮 · 16+4 时隙'],
    ['硬件端点', '节点 9 / 13 在 PL 内'],
    ['实现', 'Zynq-7020 PL · Verilog'],
  ]);
}

/* ── 左栏 ②：场景参数 · 本次实验配置回执（优先显示当前编辑的预览配置，运行中显示实板实收配置）── */
function drawSceneParams() {
  const el = $('sceneParams');
  if (!el) return;
  const cfg = V.snapshot?.config || S.config || (typeof preview !== 'undefined' && preview?.config);
  if (!cfg) { rows(el, [['状态', '尚未取得配置']]); return; }
  const name = (kind, id) => catalog?.[kind]?.find(x => x.id === id)?.name ?? id;
  const live = !!V.snapshot;
  rows(el, [
    [live ? '实板正在跑' : '将下发', name('environment', cfg.environment) + ' · ' + name('weather', cfg.weather) + ' · ' + name('formation', cfg.formation)],
    ['间距 / 高度', f2(cfg.spacing_m, 0) + ' m / ' + f2(cfg.altitude_m, 0) + ' m'],
    ['速度 / 朝向', f2((cfg.speed_mmps || 0) / 1000, 1) + ' m/s · ' + f2(cfg.heading_deg, 0) + ' °'],
    ['SNR / 起伏', f2((cfg.reference_snr_cdb || 0) / 100, 1) + ' dB · ' + f2(cfg.jitter_percent, 0) + ' %'],
    ['故障注入', cfg.faults ? '开' : '关'],
    ['外部业务端', cfg.external_node ? '节点 ' + String(cfg.external_node).padStart(2, '0') : '无（业务报文不可用）'],
  ]);
}

/* ── 顶部「心跳 / 告警」横幅：运行后如实汇总（原 workbench.js 职责，模块移除后无人更新）── */
function drawHealth() {
  const el = $('healthSummary'); if (!el) return;
  const s = V.snapshot;
  if (!s) { el.textContent = '运行后由下方态势播报汇总真实状态'; $('globalHealth')?.classList.remove('warn'); return; }
  const fresh = s.nodes.filter(n => { const d = nodeData(n[0]); return d && d.fresh; }).length;
  el.textContent = `位置新鲜 ${fresh}/16 · 实收心跳 ${s.hb} · 告警 ${s.alarms} · 待转发 ${s.pending}`;
  $('globalHealth')?.classList.toggle('warn', fresh < 16 || s.pending > 30 || s.alarms > 0);
}

/* ── 右栏 ①：选中链路 · 动态信道读回（实收，随链路选择器联动）── */
function drawLiveLinkParams() {
  const el = $('liveLinkParams');
  if (!el) return;
  const id = Number($('linkSelect')?.value || 0);
  const c = window.observedChannel(id);
  if (!c || c.applied === false) {
    rows(el, [['状态', '该链路暂无实收信道记录'], ['提示', '开始实验后自动填充']]);
    return;
  }
  const a = id % 16 + 1, b = a % 4 ? a + 1 : 0;
  const [tx, rx] = id >= 16 ? [b, a] : [a, b];
  rows(el, [
    ['链路', c.lab_id ? '单帧文字收发' : `${tx === 0 ? '地面' : tx} → ${rx === 0 ? '地面' : rx} · ${id % 4 === 3 ? '空地' : '空空'}`],
    ['模型距离', c.lab_id ? '手动信道' : f2(c.distance_m, 1) + ' m'],
    ['主径增益 g0', f2(c.gain0, 4)],
    ['回波增益 g1', f2(c.gain1, 4)],
    ['噪声 σ / 路', f2(c.sigma, 1)],
    ['主径频偏 CFO', f2(c.cfo_hz, 1) + ' Hz'],
    ['回波频偏', f2(c.echo_cfo_hz, 1) + ' Hz'],
    ['主径相位', f2((c.phase_radians || 0) * 180 / Math.PI, 1) + ' °'],
    ['回波相位', f2((c.echo_phase_radians || 0) * 180 / Math.PI, 1) + ' °'],
    ['传播时延', c.delay_samples + ' 样本'],
    ['最大额外时延', (ChannelMath.taps(c).at(-1).delay_samples-ChannelMath.taps(c)[0].delay_samples) + ' 样本'],
    ['来源', c.lab_id ? '逐项写入并读回确认' : (c.reference || '').includes('READBACK') ? 'FPGA 寄存器实读回' : '场景模型参考'],
  ]);
}

/* ── 右栏 ②：物理层实况（最近一帧实收的 PHY 统计，批次边界轮询）── */
function drawPhyLive() {
  const el = $('phyLive');
  if (!el) return;
  const pl = window.frameObservation();
  if (!pl) { rows(el, [['状态', '本链路暂无同帧观测'], ['说明', history ? '历史缺少的原始数据不补造' : '下一个 DATA 帧完成后更新']]); return; }
  const ci = (e, n) => {const a=Observation.interval(e,n);return a?'['+a.map(v=>v.toExponential(1)).join(', ')+']':'—';};
  rows(el, [
    ['链路 / 帧 / 时间', `${pl.tx}→${pl.rx||'地面'} / #${pl.generation} / ${f2(pl.model_ms/1000,3)}s`],
    ['实测频偏 CFO', pl.cfo_hz != null ? f2(pl.cfo_hz, 1) + ' Hz' : '—'],
    ['均衡后 EVM', pl.evm_percent != null ? f2(pl.evm_percent, 2) + ' %' : '—'],
    ['编码位 BER', pl.pre_ber != null ? pl.pre_ber.toExponential(2) + ' ' + ci(pl.pre_errors, pl.pre_bits) : '未捕获'],
    ['信息位 BER', pl.post_ber != null ? pl.post_ber.toExponential(2) + ' ' + ci(pl.post_errors, pl.post_bits) : '未捕获'],
    ['区间口径', '95% Wilson · 二项近似'],
    ['观测距当前', f2(pl.age_ms/1000,1)+' 模型秒'],
    ['定时调整次数', pl.timing_updates ?? '—'],
    ['译码周期数', pl.decode_cycles ?? '—'],
    ['符号样本', (pl.received?.length || 0) + ' 点 / 帧'],
  ]);
}

/* ── 第 2 页左栏：节点状态表（16 行实收心跳 + 高度/速度）── */
function drawNodeList() {
  const body = $('nodeListBody');
  if (!body) return;
  // 速度：最近两个快照间实收/真值位置的位移速率（模型时间）
  const snaps = (history ? history.snapshots : S.snapshots) || [];
  const prev = snaps.length > 1 ? snaps[snaps.length - 2] : null, cur = snaps[snaps.length - 1];
  const dt = prev && cur ? (cur.round - prev.round) / 10 : 0;
  const speed = id => {
    if (!prev || !dt) return null;
    const a = prev.nodes?.find(n => n[0] === id), b = cur.nodes?.find(n => n[0] === id);
    if (!a || !b) return null;
    return Math.hypot(b[1] - a[1], b[2] - a[2], b[3] - a[3]) / 1000 / dt;
  };
  const rowsHtml = [];
  let any = false;
  for (let i = 1; i <= 16; i++) {
    const n = nodeData(i);
    if (!n) continue;
    any = true;
    const state = n.preview ? ['预览', 'unknown'] : !n.known ? ['无实收', 'unknown'] : n.fresh ? ['新鲜', 'ok'] : ['过期', 'warn'];
    const isRelay = i % 4 === 0;
    const v = speed(i);
    rowsHtml.push(`<tr data-node="${i}" class="${selected === i ? 'sel' : ''}"><td>${String(i).padStart(2, '0')}${isRelay ? ' ◇' : ''}</td><td>${Number.isFinite(n.xyz?.[2]) ? f2(n.xyz[2], 0) : '—'}</td><td>${v != null ? f2(v, 1) : '—'}</td><td>${n.updates || '—'}</td><td><span class="st-${state[1]}">${state[0]}</span></td></tr>`);
  }
  body.innerHTML = rowsHtml.join('') || '<tr><td colspan="5">尚无节点数据</td></tr>';
  body.querySelectorAll('tr[data-node]').forEach(tr => tr.onclick = () => {
    selected = Number(tr.dataset.node);
    const sel = $('nodeSelect'); if (sel) sel.value = selected;
    if (window.renderNodeNow) window.renderNodeNow();
  });
}

/* ── G1：多普勒频移醒目展示（导师点名"没看出来有的没标明"那条）。
   f_d = f_c·v/c，是派生值而非独立自由度——如实标注"实时算得"，不做成可输入项冒充可调。 ── */
const C_LIGHT = 299792458;
function updateDoppler() {
  const el = document.getElementById('dopplerDerived');
  if (!el) return;
  const id=Number($('linkSelect')?.value||0),o=window.frameObservation();
  const cfg=V.snapshot?.config || S.config;
  if(!o){el.textContent='待所选链路观测';return;}
  const oscillator=[0,-113,24,161,-203,-66,71,208,-156,-19,118,-246,-109,28,165,-199,-62];
  const meta=o.channel.model_metadata,fd=meta?meta[2]:o.channel.cfo_hz-(oscillator[o.tx]-oscillator[o.rx]);
  if(meta&&meta[4]===2){el.textContent='自主模式 · 用户频偏';el.title='几何不驱动自主信道；用户公共频偏与逐径频偏直接作用于 FPGA。';return;}
  el.textContent=fd.toFixed(1)+' Hz · 同帧几何值';
  el.title=meta?'同帧 ARM 位置导数计算的几何多普勒，不包含本振差和随机散射频偏。':'历史帧频偏读回减去节点本振差。';
}
document.addEventListener('input', e => {
  if (e.target?.id === 'carrier' || e.target?.id === 'speed') updateDoppler();
});

function drawAll() { updateDoppler(); drawModemParams(); drawSceneParams(); drawChannelProfile(); drawLiveLinkParams(); drawPhyLive(); drawNodeList(); drawHealth(); }

/* 挂到每次实板数据刷新之后（renderInstruments 在 renderView 尾部必被调用） */
const base = window.renderInstruments;
window.renderInstruments = () => { base?.(); drawAll(); };
/* 链路选择器切换时立即刷新右栏 */
document.addEventListener('change', e => { if (e.target?.id === 'linkSelect') drawLiveLinkParams(); });
/* 节点表点击 → 复用 app.js 的节点选择逻辑（renderNode 是全局函数） */
window.renderNodeNow = () => { if (typeof renderNode === 'function') { renderNode(); if (typeof drawMap === 'function') drawMap(); } };
document.addEventListener('DOMContentLoaded', drawAll);
})();
