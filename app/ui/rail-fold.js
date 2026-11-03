/* G5「一屏看全」：折叠非核心面板 + 高块合并成 tab（均按 HANDOFF/10 裁决 6 执行）。
 *
 * 做了什么（2026-10-31 依据实测块高定）：
 *   ① 折叠（默认收起、点击展开，内容不删）：
 *      左栏 路由选择/信道档案/信道统计；右栏 选中链路·信道读回/物理层实况/本窗口实测
 *   ② tab 合并（裁决 6 第④步：两块合并成带 tab 的一块）：
 *      左栏 [信道设置 | 场景选择 | 态势速览]，右栏 [调制解调链 | 链路干预]
 *      —— 实测这两栏即使全部折叠次要块也塞不进 885px 视口，只能 tab 化。
 *   ③ 干预面板里的「怎么修·分层处置」参考清单再折叠一层（参考信息，点开即看）。
 *
 * 不做违反裁决的事：不缩字号、不把多普勒等关键参数藏进折叠块、不删信息。
 * 所有元素仍在 DOM 里，实板数据照常刷新，tab/折叠只是显示切换。
 */
(function () {
  'use strict';

  const FOLD = ['路由选择', '信道档案', '信道统计', '选中链路', '物理层实况', '本窗口实测'];
  /* 第 2 页：次要看板折叠（裁决 6 第①步）。业务回放/建议/AI 都还在，点标题即展开。 */
  const P2_FOLD_TEXT = ['节点业务回放'];
  const P2_FOLD_CLASS = ['advicePanel', 'assistantPanel'];
  const TABS = [
    { col: '.param-rail', items: [['信道设置', '信道设置'], ['场景选择', '场景选择'], ['蜂群态势速览', '态势速览']] },
    { col: '.param-rail.right', items: [['调制解调链', '调制解调链'], ['链路干预', '链路干预']] },
  ];

  const CSS = `
    .rail-fold{border:1px solid var(--line);border-radius:10px;background:var(--panel);overflow:hidden}
    .rail-fold>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:8px;
      padding:11px 16px;font-size:16px;color:var(--text);user-select:none}
    .rail-fold>summary::-webkit-details-marker{display:none}
    .rail-fold>summary h3{margin:0;font-size:16px}
    .rail-fold>summary:hover{color:var(--cyan)}
    .rail-fold .fold-hint{margin-left:auto;font-size:14px;color:var(--muted)}
    .rail-fold[open] .fold-hint{color:var(--cyan)}
    .rail-fold>.rail-fold-body{border:0;box-shadow:none;border-radius:0;background:transparent}
    .rail-tabs{border:1px solid var(--line);border-radius:10px;background:var(--panel);overflow:hidden}
    .rail-tabbar{display:flex;gap:4px;padding:6px 8px;border-bottom:1px solid var(--line)}
    .rail-tab{flex:1;font-size:14px;padding:7px 4px;background:transparent;border:1px solid transparent;
      border-radius:6px;color:var(--muted);cursor:pointer}
    .rail-tab.active{background:#103759;border-color:#296390;color:var(--cyan)}
    .rail-tabpane>.panel{border:0;box-shadow:none;border-radius:0;background:transparent}
    .iv-fix-fold{margin-top:8px;border:1px dashed #235a58;border-radius:8px}
    .iv-fix-fold>summary{list-style:none;cursor:pointer;padding:8px 10px;font-size:14px;color:#9fd0c8;user-select:none}
    .iv-fix-fold>summary::-webkit-details-marker{display:none}
    .iv-fix-fold>summary:hover{color:var(--cyan)}
    .iv-fix-fold[open]>summary{border-bottom:1px dashed #235a58}
    .iv-fix-fold .iv-fix-title{display:none}`;

  function injectCss() {
    if (document.getElementById('railTidyStyle')) return;
    const st = document.createElement('style');
    st.id = 'railTidyStyle';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  function makeFold(block) {
    const h3 = block.querySelector(':scope > h3');
    const details = document.createElement('details');
    details.className = 'rail-fold';
    const summary = document.createElement('summary');
    summary.innerHTML = `<h3>${h3 ? h3.innerHTML : block.id || '详情'}</h3><span class="fold-hint">点击展开</span>`;
    block.parentNode.insertBefore(details, block);
    details.appendChild(summary);
    if (h3) h3.remove();
    details.appendChild(block);
    block.classList.add('rail-fold-body');
    details.addEventListener('toggle', () => {
      summary.querySelector('.fold-hint').textContent = details.open ? '点击收起' : '点击展开';
    });
  }

  function foldBlocks() {
    let n = 0;
    document.querySelectorAll('.panel.rail-block').forEach(block => {
      if (block.closest('details') || block.closest('.rail-tabs')) return;
      const h3 = block.querySelector(':scope > h3');
      if (!h3) return;
      const title = h3.textContent.trim();
      if (!FOLD.some(k => title.includes(k))) return;
      makeFold(block);
      n++;
    });
    /* 第 2 页列内折叠 */
    document.querySelectorAll('.p2-left > .panel, .p2-right > .panel').forEach(block => {
      if (block.closest('details')) return;
      const h3 = block.querySelector(':scope > h3');
      const t = h3 ? h3.textContent.trim() : '';
      const byClass = P2_FOLD_CLASS.some(c => block.classList.contains(c));
      if (!byClass && !P2_FOLD_TEXT.some(k => t.includes(k))) return;
      makeFold(block);
      n++;
    });
    return n;
  }

  function findBlock(col, key) {
    return [...col.querySelectorAll('.panel.rail-block')].find(b => {
      if (b.closest('details') || b.closest('.rail-tabs')) return false;
      const h = b.querySelector(':scope > h3');
      return h && h.textContent.trim().includes(key);
    });
  }

  function buildTabs(spec) {
    const col = document.querySelector(spec.col);
    if (!col || col.querySelector('.rail-tabs')) return;
    const blocks = spec.items.map(([k]) => findBlock(col, k));
    if (blocks.filter(Boolean).length < 2) return;

    const wrap = document.createElement('div');
    wrap.className = 'rail-tabs';
    const bar = document.createElement('div');
    bar.className = 'rail-tabbar';
    wrap.appendChild(bar);

    const panes = [];
    blocks.forEach((b, i) => {
      if (!b) return;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'rail-tab' + (i === 0 ? ' active' : '');
      btn.textContent = spec.items[i][1];
      const pane = document.createElement('div');
      pane.className = 'rail-tabpane';
      if (i > 0) pane.hidden = true;
      const h3 = b.querySelector(':scope > h3');
      if (h3) h3.remove();                       // 标题已进 tab 按钮
      pane.appendChild(b);
      wrap.appendChild(pane);
      panes.push({ btn, pane });
      btn.addEventListener('click', () => {
        panes.forEach(p => { p.pane.hidden = p.pane !== pane; p.btn.classList.toggle('active', p.btn === btn); });
      });
      bar.appendChild(btn);
    });
    col.insertBefore(wrap, col.firstChild);
  }

  function foldFixList() {
    const fix = document.getElementById('ivFix');
    if (!fix || fix.closest('details')) return;
    const d = document.createElement('details');
    d.className = 'iv-fix-fold';
    d.innerHTML = '<summary>怎么修 · 分层处置（点开展开）<span class="fold-hint" style="margin-left:auto">展开</span></summary>';
    fix.parentNode.insertBefore(d, fix);
    d.appendChild(fix);
    d.addEventListener('toggle', () => {
      d.querySelector('.fold-hint').textContent = d.open ? '收起' : '展开';
    });
  }

  function run() {
    injectCss();
    foldBlocks();
    TABS.forEach(buildTabs);
    foldFixList();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run);
  else run();
  setTimeout(run, 1200);   // dom-shim/异步渲染兜底（run 幂等）
})();
