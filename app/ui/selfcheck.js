/* 界面自检：把「改完到底有没有生效」变成点一下就能看到的结果。
   静态部分读 /api/selfcheck（只读，随时可跑）；
   实板部分复用界面上的两个场景预设，跑完直接给出与赛题口径一致的判定。 */
(function () {
  const $ = (id) => document.getElementById(id);
  const PASS = '[通过]', FAIL = '[未过]', WARN = '[提醒]';

  function api(path, body) {
    const opt = body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {};
    return fetch(path, opt).then(async (r) => {
      const t = await r.json();
      if (!r.ok || t.error) throw Error(t.error || ('HTTP ' + r.status));
      return t;
    });
  }
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  function line(verdict, name, detail) {
    return '<div class="scrow ' + (verdict === PASS ? 'ok' : verdict === FAIL ? 'bad' : 'warn') + '">' +
      '<span class="scv">' + verdict + '</span><span class="scn">' + name + '</span><span class="scd">' + detail + '</span></div>';
  }

  /* ------------------------------------------------ 静态自检 */
  async function renderStatic() {
    const box = $('scStatic');
    box.innerHTML = '<p class="hint">正在检查…</p>';
    let r;
    try {
      r = await api('/api/selfcheck');
    } catch (e) {
      box.innerHTML = line(FAIL, '自检接口', e.message);
      return;
    }
    const rel = r.release, fea = r.features, ctl = r.controls;
    let h = '';
    h += line(rel.verdict, '发布清单一致', rel.note +
      (rel.mismatched.length ? '<br>不符：' + rel.mismatched.join('、') : '') +
      (rel.missing.length ? '<br>缺失：' + rel.missing.join('、') : ''));
    h += line(fea.verdict, '补间与插值上限', '插值上限 ' + fea.interp_cap_ms + ' ms（需大于实际帧间隔）· 场景预设 ' + fea.presets + ' 个 · 动画可关闭：' + (fea.animation_closable ? '是' : '否'));
    h += line(ctl.verdict, '控件无空壳', ctl.note + (ctl.dead.length ? '<br>未接线：' + ctl.dead.join('、') : ''));
    if (rel.verdict === FAIL) {
      h += '<p class="hint">清单不一致会导致实验拒绝启动。命令行执行 <code>_resign_release.py</code> 重新签名即可。</p>';
    }
    box.innerHTML = h;
  }

  /* ------------------------------------------------ 实板对照 */
  function cfgFor(key) {
    // 借用界面自身的配置读写，保证与点预设按钮后跑出的结果完全一致
    const saved = readConfig();
    setConfig(Object.assign({}, catalog.defaults, SCENE_PRESETS[key].config));
    const cfg = readConfig();
    setConfig(saved);
    return cfg;
  }

  async function waitIdle() {
    for (let i = 0; i < 120; i++) {
      const s = await api('/api/state');
      if (s.error) throw Error(s.error);
      // 任务结束后 task 字段会残留上一次的 connect，不能用 task 判断
      if (!s.busy && ['complete', 'idle', 'error'].includes(s.status)) return s;
      await sleep(600);
    }
    throw Error('等待板卡空闲超时');
  }

  async function runOne(key, label, onProgress) {
    const st0 = await api('/api/state');
    if (!st0.connected) await api('/api/connect', { port: $('port').value });
    await waitIdle();
    await api('/api/start', {
      seconds: 90, ideal: 0, seed: 20261023,
      config: cfgFor(key), telemetry_rounds: 20
    });

    let seen = 0, stamps = [], last = null;
    for (let i = 0; i < 400; i++) {
      const s = await api('/api/state');
      if (s.error) throw Error(s.error);
      const snaps = s.snapshots || [];
      if (snaps.length > seen) {
        for (let k = seen; k < snaps.length; k++) stamps.push(Date.now());
        seen = snaps.length;
        last = snaps[snaps.length - 1];
        onProgress(seen);
      }
      if (!s.busy && ['complete', 'idle', 'error'].includes(s.status)) {
        last = snaps.length ? snaps[snaps.length - 1] : last;
        break;
      }
      await sleep(250);
    }
    if (!last) throw Error('没有收到任何采样点');
    const gaps = [];
    for (let i = 1; i < stamps.length; i++) gaps.push(stamps[i] - stamps[i - 1]);
    gaps.sort((a, b) => a - b);
    return {
      label, frames: seen,
      gapMed: gaps.length ? gaps[Math.floor(gaps.length / 2)] : 0,
      gapMax: gaps.length ? gaps[gaps.length - 1] : 0,
      generated: last.generated, delivered: last.delivered, pending: last.pending,
      rate: 100 * (last.delivered || 0) / Math.max(1, last.generated || 1),
      wall: (last.wall_ms || 0) / 1000
    };
  }

  async function runCompare() {
    const box = $('scLive'), btn = $('selfcheckRun');
    btn.disabled = true;
    try {
      box.innerHTML = '<p class="hint">正在跑「基准场景」，需要板卡空闲，约 30 秒…</p>';
      const a = await runOne('presetBaseline', '基准 · 晴 34 dB', (n) => {
        box.innerHTML = '<p class="hint">第 1/2 组 · 基准场景 · 已收到 ' + n + ' 个实采样点…</p>';
      });
      const b = await runOne('presetSevere', '极恶劣 · 大雪 18 dB', (n) => {
        box.innerHTML = '<p class="hint">第 2/2 组 · 极恶劣场景 · 已收到 ' + n + ' 个实采样点…</p>';
      });

      const rate = a.rate - b.rate;
      let h = '';
      h += line(a.frames >= 40 ? PASS : FAIL, 'A1 观感帧数', a.frames + ' 帧 / ' + b.frames + ' 帧（改前 5 帧），观感帧率 ' +
        (a.frames / Math.max(1, a.wall)).toFixed(2) + ' 帧/秒');
      h += line(a.gapMax <= 9000 ? PASS : FAIL, 'A2 帧间隔 ≤ 插值上限',
        '最大 ' + a.gapMax + ' ms（上限 9000 ms）→ 两帧之间不会停住');
      h += line(a.wall <= 120 && b.wall <= 120 ? PASS : FAIL, 'A3 墙钟门禁',
        a.wall.toFixed(1) + ' s / ' + b.wall.toFixed(1) + ' s，均需 ≤ 120 s');
      h += line(rate > 5 ? PASS : FAIL, 'B1 场景差异幅度',
        '送达率 ' + a.rate.toFixed(2) + '% → ' + b.rate.toFixed(2) + '%（落差 ' + rate.toFixed(1) +
        ' 个百分点）；积压 ' + a.pending + ' → ' + b.pending);
      h += '<div class="sctable"><div><span>基准场景</span><b>' + a.frames + '</b> 帧 · 送达 ' +
        a.delivered + '/' + a.generated + ' · 积压 ' + a.pending + ' · 墙钟 ' + a.wall.toFixed(1) + ' s</div>' +
        '<div><span>极恶劣场景</span><b>' + b.frames + '</b> 帧 · 送达 ' + b.delivered + '/' + b.generated +
        ' · 积压 ' + b.pending + ' · 墙钟 ' + b.wall.toFixed(1) + ' s</div></div>';
      h += '<p class="hint">两组均已落盘到 app/results/，可随时调阅原始逐帧记录。界面上的运动是两端实采样之间的插值，不外推。</p>';
      box.innerHTML = h;
      toast && toast('标准对照已完成，两组记录已落盘');
    } catch (e) {
      box.innerHTML = line(FAIL, '标准对照', e.message);
    } finally {
      btn.disabled = false;
    }
  }

  /* ------------------------------------------------ 装配 */
  document.addEventListener('DOMContentLoaded', () => {
    const btn = $('selfcheck');
    if (!btn) return;
    btn.addEventListener('click', () => {
      $('selfcheckDialog').showModal();
      renderStatic();
      $('scLive').innerHTML = '<p class="hint">点右侧按钮可实板跑一遍标准对照（基准 → 极恶劣），约 1 分钟。板卡必须先连接。</p>';
    });
    $('selfcheckRun').addEventListener('click', runCompare);
  });
})();
