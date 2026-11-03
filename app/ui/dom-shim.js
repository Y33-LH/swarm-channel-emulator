/* 兜底层：补齐各模块引用但当前页面结构中不存在的元素。
 * 目的：任何一个模块都不再因为缺 DOM 节点而抛异常——一旦抛异常，
 * 该模块后续所有逻辑（包括按钮状态更新）都会静默失效。
 * 这不是伪造数据：这些节点只是容器，内容仍由各模块按实收数据写入。
 * 本脚本必须在所有业务脚本之前加载。 */
(() => {
  const specs = {
    // 模块会在其上挂 onclick / textContent 的容器类节点
    signalControls: 'div',
    appliedTicker: 'div',
    tdmaReadback: 'div',
    receiverSummaryLive: 'div',
    measureSource: 'div',
    phyStats: 'div',
    capacityStatus: 'div',
    capacityTable: 'div',
    sceneBrief: 'b',
    nextStep: 'b',
    openLab: 'button',
    closeLab: 'button'
  };
  const root = document.createElement('div');
  root.id = 'domShimRoot';
  root.hidden = true;
  const missing = [];
  for (const [id, tag] of Object.entries(specs)) {
    if (document.getElementById(id)) continue;
    const el = document.createElement(tag);
    el.id = id;
    root.appendChild(el);
    missing.push(id);
  }
  // 对话框类：openLab 依赖 labDialog.showModal()
  if (!document.getElementById('labDialog')) {
    const dialog = document.createElement('dialog');
    dialog.id = 'labDialog';
    dialog.innerHTML = '<form method="dialog"><h2>单链路实验</h2>'
      + '<p class="hint">此对话框需要页面中的「亲手发送一段文字」面板才能工作；'
      + '请到「技术证据」页使用该功能。</p><button class="primary wide">关闭</button></form>';
    root.appendChild(dialog);
    missing.push('labDialog');
  }
  if (missing.length) root.appendChild(document.createComment('补齐元素：' + missing.join(', ')));
  document.body.appendChild(root);
  window.__domShim = missing;
  if (missing.length) console.warn('[dom-shim] 已补齐缺失节点（否则模块会静默崩溃）：', missing.join(', '));
})();
