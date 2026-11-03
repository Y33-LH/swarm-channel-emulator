/* 每个功能模块一行固定说明：「这里做什么 · 你操作后哪里会变」。
   纯文案层：在所有布局脚本就位后注入，不改动任何数据与交互逻辑。 */
(() => {
 const notes = [
  // [容器选择器, 插入到哪个子元素之后, 文案]
  ['.channelPanel .channelHead', null,
   '这里显示所选链路实际应用的信道与接收质量。切换上方链路 → 六张图与参数按实收数据重绘。'],
  ['.nodePanel .sectiontitle', null,
   '查看所选节点的实收状态。下方可下发指令：经多跳链路送达，必须收到执行回执才算生效。'],
  ['.causal-lite', 'summary',
   '只改变一条链路的信号与噪声，观察地面真正收到的业务如何退化与恢复；过程自动记录可导出。'],
  ['#history .pageIntro', null,
   '每条记录含配置、种子与原始收发数据：载入后回第 2 页地图看回放；两组对比与证据导出在这里。']
 ];
 function inject() {
  let done = 0;
  for (const [sel, anchor, text] of notes) {
   const host = document.querySelector(sel);
   if (!host || host.dataset.noted) continue;
   host.dataset.noted = '1';
   const p = document.createElement('p');
   p.className = 'panel-note';
   p.textContent = text;
   const anchorEl = anchor ? host.querySelector(anchor) : null;
   (anchorEl || host).after(p);
   done++;
  }
  return done;
 }
 inject();
 let n = 0;
 const timer = setInterval(() => { if (!inject() && ++n > 8) clearInterval(timer); }, 800);
})();
