/* Keep all existing controls and event IDs; change their placement, not their contracts. */
(() => {
 const el=id=>document.getElementById(id), make=(tag,cls,html='')=>{const e=document.createElement(tag);e.className=cls;e.innerHTML=html;return e;};
 const home=el('evidence'),mission=el('mission');
 // layout.js 负责生成这些容器；若页面结构不同则安全跳过，避免连带崩溃
 const left=home?.querySelector('.channel-input'),center=home?.querySelector('.channel-center'),right=home?.querySelector('.modem-panel');
 if(!home||!mission||!left||!center||!right){console.warn('instrument-layout: 未找到工作台结构，跳过图表重排');return;}
 document.title='蜂群信道实验平台 · 信道与收发工作台';
 document.body.classList.add('instrument-console');
 const map=el('sharedMapPanel');if(!map)return;map.classList.remove('compact-map');el('sceneMapSlot')?.append(map);el('homeMapSlot')?.remove();
 const risk=make('section','risk-overview','<div class="section-caption"><b>节点通信状态</b><span id="riskSource">配置预览</span></div><canvas id="riskMap" aria-label="只读节点状态概览"></canvas><div class="risk-key"><span class="ok">● 位置新鲜</span><span class="warn">● 过期 / 降级</span><span class="bad">● 本窗通信失败</span><span class="unknown">● 未知 / 预览</span></div>');
 left.querySelector('.panel-title').after(risk);
 left.querySelector('h2').textContent='实验条件与态势';
 left.querySelector('.purpose').remove();left.querySelector('.parameter-key').remove();
 const details=make('details','applied-details','<summary>已应用信道参数 <span class="value-type">寄存器读回</span></summary>');
 details.append(el('channelDetails'));left.append(details);
 const observation=center.querySelector('.channel-observation');
 const toolbar=make('div','instrument-toolbar','<div><span class="eyebrow">CHANNEL / BASEBAND OBSERVATORY</span><h2>信道响应与接收质量</h2></div>');toolbar.append(el('linkSelect').closest('label'));center.prepend(toolbar);
 const grid=make('div','instrument-charts');
 const chart=(id,title,subtitle)=>{const panel=make('section','chart-card',`<div class="chart-heading"><h3>${title}</h3><span id="${id}Value">—</span></div><div class="chart-area"></div><p>${subtitle}</p>`);const c=el(id)||make('canvas','plot');c.id=id;c.setAttribute('aria-label',title);panel.querySelector('.chart-area').append(c);grid.append(panel);};
 chart('cir','01 / 功率时延谱 PDP','应用抽头系数 → 功率；横轴为相对主径的额外时延。亮色为最新读回，淡色为最近实收读回的历史叠加（全部来自实收系数，非推测曲线）；回波极弱时会标注近似单径。');
 chart('cfr','02 / 信道频率响应 CFR','复数二径系数计算的频响；并非接收机信道估计。');
 chart('envelope','03 / 抽头幅度变化','最近120次实收采样，连线仅辅助观察趋势，不是额外测量。');
 chart('linkQuality','04 / 逐窗通信质量','所选链路：PN 捕获率 / 逐跳 ACK 成功率，分母不同。');
 chart('iqBefore','05 / 接收星座 · 均衡前','FPGA 接收缓存 I/Q；空白表示尚无此链路样本。');
 chart('iqAfter','06 / 接收星座 · 均衡后','同批符号样本；数字基带 DBPSK，非 16QAM。');
 const large=make('dialog','chart-dialog','<div class="dialog-heading"><h2 id="largeChartTitle"></h2><button type="button" id="closeLargeChart">关闭 ×</button></div><div class="large-chart-area"></div><p id="largeChartNote" class="hint"></p>');large.id='chartDialog';document.body.append(large);let enlarged=null;
 large.querySelector('#closeLargeChart').onclick=()=>large.close();large.addEventListener('close',()=>{if(enlarged){enlarged.holder.append(enlarged.canvas);enlarged=null;requestAnimationFrame(()=>window.renderInstruments?.());}});
 for(const card of grid.children){const button=make('button','expand-chart','↗');button.type='button';button.title='放大此图';button.setAttribute('aria-label','放大'+card.querySelector('h3').textContent);card.querySelector('.chart-heading').append(button);button.onclick=()=>{const canvas=card.querySelector('canvas');enlarged={canvas,holder:canvas.parentElement};large.querySelector('h2').textContent=card.querySelector('h3').textContent;large.querySelector('p').textContent=card.querySelector('p').textContent;large.querySelector('.large-chart-area').append(canvas);large.showModal();requestAnimationFrame(()=>window.renderInstruments?.());};}
 const strip=make('div','technical-strip','<span><b>DBPSK</b> 差分调制</span><span>Fs <b>8 MHz</b></span><span>Rs <b>2 Msym/s</b></span><span><b>4</b> 点 / 符号</span><span><b>二径复系数 + AWGN</b></span><span>PL <b>62.5 MHz</b></span>');
 const ticker=make('div','applied-ticker');ticker.id='appliedTicker';
 const chartTabs=make('div','chart-tabs','<button class="selected" data-chart-view="all">全部六图</button><button data-chart-view="core">01 / 02 / 05 / 06 信道与星座</button><button data-chart-view="dynamics">03 / 04 动态与质量</button><span>实测 / 系数推导均标注来源</span>');
 for(const card of grid.children){card.dataset.chartView=['envelope','linkQuality'].includes(card.querySelector('canvas').id)?'dynamics':'core';card.hidden=false;}
 chartTabs.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;chartTabs.querySelectorAll('button').forEach(x=>x.classList.toggle('selected',x===b));for(const card of grid.children)card.hidden=b.dataset.chartView!=='all'&&card.dataset.chartView!==b.dataset.chartView;grid.classList.toggle('dynamic-view',b.dataset.chartView==='dynamics');grid.classList.toggle('all-view',b.dataset.chartView==='all');requestAnimationFrame(()=>window.renderInstruments?.());});
 grid.classList.add('all-view');center.append(strip,ticker,chartTabs,grid,el('channelSource'));observation.remove();toolbar.append(el('openLab'));
 const iq=right.querySelector('.live-iq');if(iq)iq.remove();right.querySelector(':scope > .hint')?.remove();
 right.querySelector('h2').textContent='解调与链路指标';
 const stats=make('section','derived-metrics','<div class="section-caption"><b>信道统计</b><span>系数推导</span></div><div id="channelStatistics" class="metric-pairs"></div>');
 right.querySelector('.modem-fixed').before(stats);
 const quality=make('section','window-metrics','<div class="section-caption"><b>选中链路 · 本窗口</b><span>实测统计</span></div><div id="linkStatistics" class="metric-pairs"></div>');stats.after(quality);
 const tdma=make('section','tdma-panel','<div class="section-caption"><b>固定 TDMA</b><span>100 ms / 轮</span></div><div class="tdma-slots">'+Array.from({length:20},(_,i)=>`<span class="${i<16?'data-slot':'retry-slot'}" title="${i<16?'节点 '+(i+1)+' 优先发送':i===16?'地面下行优先，否则第1组重传':'第'+(i-15)+'组重传'}">${i<16?i+1:i===16?'G/R':'R'}</span>`).join('')+'</div><p>每格 5 ms；16 个节点槽 + 4 个重传槽（首槽兼地面下行）。图为调度结构，非逐槽遥测。</p><div id="tdmaReadback"></div>');right.append(tdma);
 const unsupported=make('details','method-notes','<summary>读图口径与当前能力边界</summary><p>当前为可控二径复数信道；不声明已实现标准 3GPP TDL、Rayleigh/Rician 统计分布或 MIMO。频偏包含振荡器差与运动项，不能直接当作多普勒展宽。</p><p>现有遥测为抽取后的符号点，不能重建连续采样眼图；未输出接收估计抽头，因此不生成 NMSE。相干时间及 MIMO 条件数不作无依据显示。</p><p>容量看第三页实测对比及研究工具；不把 Shannon 上界当作可达到吞吐量。</p></details>');right.append(unsupported);
 left.querySelector('#signalControls').after(tdma);
 home.querySelector('.workflow').remove();
 const bottom=mission.querySelector('.bottomgrid'),media=bottom.children[0],events=bottom.children[1],setup=mission.querySelector('.setup');
 const mediaDetails=make('details','panel received-files','<summary>业务文件回传 <span class="tag">逐字节校验</span></summary><p class="hint">节点 1 → 2 → 3 → 4 → 地面：语音测试文件；节点 5 → 6 → 7 → 8 → 地面：视频测试片段。用于验证分片、多跳转发与重组，不是实时摄像头直播。</p>');
 mediaDetails.append(media);setup.after(mediaDetails);const leftColumn=make('aside','mission-left');setup.before(leftColumn);leftColumn.append(setup,mediaDetails);bottom.remove();
 media.querySelector('h2').textContent='收齐后播放';media.querySelectorAll('.eyebrow')[0].textContent='节点 1 · 语音测试文件';media.querySelectorAll('.eyebrow')[1].textContent='节点 5 · 视频测试片段';
 const rightColumn=mission.querySelector('.rightcolumn');const node=rightColumn.querySelector('.nodePanel'),advice=rightColumn.querySelector('.advicePanel'),ai=rightColumn.querySelector('.assistantPanel');
 const tabs=make('div','side-tabs','<button data-side="node" class="selected">节点 / 控制</button><button data-side="advice">建议 / AI</button><button data-side="events">事件</button>');
 const groups={node:[node],advice:[advice,ai],events:[events]};rightColumn.prepend(tabs);
 for(const [key,items] of Object.entries(groups)){const pane=make('div','side-pane');pane.dataset.pane=key;pane.hidden=key!=='node';pane.append(...items);rightColumn.append(pane);}
 tabs.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;tabs.querySelectorAll('button').forEach(x=>x.classList.toggle('selected',x===b));rightColumn.querySelectorAll('.side-pane').forEach(x=>x.hidden=x.dataset.pane!==b.dataset.side);});
 const choiceTabs=make('div','choice-tabs','<button type="button" data-choice="environment" class="selected">场景</button><button type="button" data-choice="weather">天气</button><button type="button" data-choice="formation">编队</button>');
 const choices=make('div','visual-choices');choices.append(choiceTabs);
 for(const kind of ['environment','weather','formation']){const pane=make('section','choice-pane',`<div id="${kind}Cards" class="option-cards"></div><div id="${kind}Description" class="choice-description"></div>`);pane.dataset.choicePane=kind;pane.hidden=kind!=='environment';choices.append(pane);el(kind).closest('label').classList.add('native-choice');}
 el('configFields').before(choices);el('configFields').before(choiceTabs);
 choiceTabs.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;choiceTabs.querySelectorAll('button').forEach(x=>x.classList.toggle('selected',x===b));choices.querySelectorAll('.choice-pane').forEach(x=>x.hidden=x.dataset.choicePane!==b.dataset.choice);});
 const tilt=make('select','');tilt.id='mapPerspective';tilt.setAttribute('aria-label','地图视角');tilt.innerHTML='<option value="3d">立体态势</option><option value="2d">俯视平面</option>';map.querySelector('.mapoptions').prepend(tilt);tilt.onchange=()=>drawMap();
 el('map').setAttribute('aria-label','编队立体通信态势，点击节点查看三维坐标');
 map.querySelector('.maplegend').innerHTML='<span class="ok">›› 近期上行成功</span><span style="color:#7dbbff">‹‹ 下行指令</span><span class="warn">›› 部分失败</span><span class="bad">╌ ⚠ ╌ 本窗无 ACK</span><span>◇ 中继 · ★ 地面</span>';
 map.querySelector('.mapstamp small').textContent='高度按 3 倍突出显示 · 不含真实地形高程';
 const replay=el('replayControls');document.querySelector('.global-timeline').after(replay);
})();
