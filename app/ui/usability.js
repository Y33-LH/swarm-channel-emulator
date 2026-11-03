/* Presentation only. Actions still use the existing validated handlers. */
(()=>{
 const E=id=>document.getElementById(id),make=(tag,cls,html='')=>{const e=document.createElement(tag);e.className=cls;e.innerHTML=html;return e;};
 document.body.classList.add('usable-console');
 const bar=E('experimentModeBar');E('runDock').before(bar);
 bar.prepend(make('b','task-label','实验任务'));
 const modes={cxMode:['交互验证','改变链路 → 观察业务 → 采取措施'],lxMode:['单帧诊断','自定义信道 → 同帧收发 → 参数对照'],lxNetworkMode:['完整场景','编队运动 → 心跳告警 → 音视频回传']};
 for(const [id,[name,desc]] of Object.entries(modes)){E(id).innerHTML=`<strong>${name}</strong><small>${desc}</small>`;E(id).title=desc;}
 bar.querySelector(':scope > small').remove();
 bar.append(make('span','mode-lock'));bar.lastChild.id='modeLock';
 bar.addEventListener('click',e=>{if(S.busy&&e.target.closest('button')){e.stopImmediatePropagation();toast('当前任务占用板卡。可以切换观察页面；结束或中止后再换实验任务。',true);}},true);
 const rail=make('section','task-guide','<div><span id="taskState" class="task-state">准备实验</span><h2 id="taskHeadline"></h2><p id="taskHint"></p></div><button id="taskNext" class="primary"></button>');rail.id='taskGuide';rail.setAttribute('aria-label','当前任务与下一步');bar.after(rail);
 const trail=make('div','task-trail','<button data-dest="evidence">① 看信道与接收</button><span>→</span><button data-dest="mission">② 看节点与业务</button><span>→</span><button data-dest="history">③ 保存、对比、重现</button>');rail.after(trail);
 trail.onclick=e=>{const b=e.target.closest('button');if(b)showTab(b.dataset.dest);};
 const main=E('networkIntervention').querySelector('.cx-main'),status=main.children[0];
 const advanced=make('details','setup-advanced','<summary>场景、天气与复现选项</summary>');
 const cfg=E('cxSettings');E('cxLink').closest('label').after(advanced);
 for(const child of [...cfg.children])if(child!==advanced&&!child.contains(E('cxLink'))&&!child.contains(E('cxSeconds')))advanced.append(child);
 E('cxSetup').querySelector('summary').textContent='下一次实验设置';
 const business=E('cxBusiness').closest('section'),action=E('actionWorkspace'),frame=E('cxFrame').closest('section'),events=E('cxEvents').closest('section'),trends=main.querySelector('.cx-charts');
 const tabs=make('div','task-tabs');tabs.id='observationTabs';tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','本实验观测内容');status.after(tabs);
 const panes={};for(const [key,label] of [['impact','业务影响'],['technical','信道六图与同帧接收'],['action','措施执行与效果'],['timeline','操作时间线']]){
  const b=make('button','',label);b.type='button';b.id='tab-'+key;b.dataset.pane=key;b.setAttribute('role','tab');b.setAttribute('aria-controls','pane-'+key);tabs.append(b);
  const pane=make('div','observation-pane');pane.id='pane-'+key;pane.setAttribute('role','tabpanel');pane.setAttribute('aria-labelledby',b.id);panes[key]=pane;main.append(pane);b.onclick=()=>selectPane(key);
 }
 panes.impact.append(business,trends);panes.action.append(action);panes.timeline.append(events);
 const techHolder=make('div','task-technical');panes.technical.append(techHolder,frame);
 const bench=E('evidence').querySelector('.channel-workbench'),center=bench.querySelector('.channel-center'),modem=bench.querySelector('.modem-panel');
 const centerHome=document.createComment('shared instruments home'),modemHome=document.createComment('shared receiver home');center.before(centerHome);modem.before(modemHome);
 let paneName='impact',lastCausal=null;
 function selectPane(key){paneName=key;for(const [name,p] of Object.entries(panes)){p.hidden=name!==key;const b=E('tab-'+name);b.setAttribute('aria-selected',String(name===key));b.tabIndex=name===key?0:-1;}requestAnimationFrame(()=>{window.renderInstruments?.();window.dispatchEvent(new Event('resize'));});}
 tabs.onkeydown=e=>{const list=[...tabs.children],i=list.indexOf(document.activeElement);if(i<0)return;const n=e.key==='ArrowRight'?(i+1)%list.length:e.key==='ArrowLeft'?(i+list.length-1)%list.length:e.key==='Home'?0:e.key==='End'?list.length-1:-1;if(n>=0){e.preventDefault();selectPane(list[n].dataset.pane);list[n].focus();}};
 selectPane(paneName);
 const availability=make('p','availability');availability.id='actionAvailability';action.querySelector('h3').after(availability);
 const conditionHelp=make('p','availability');conditionHelp.id='conditionAvailability';E('cxCondition').before(conditionHelp);
 const configHelp=make('p','availability');configHelp.id='configAvailability';E('configFields').before(configHelp);
 const helpLink=make('button','wide','如何读这些图？');helpLink.id='explainCharts';center.querySelector('.chart-tabs').after(helpLink);
 const chartHelp=make('dialog','reading-guide','<h2>同一条链路，三种尺度</h2><dl><dt>01 / 02：此刻信道怎样改变信号</dt><dd>功率时延谱看各条路径的强弱与时延；频响看不同基带频率的衰减。两者从实际应用的系数推导，条件稳定时曲线变化可能很小。</dd><dt>03 / 04：这段时间发生了什么</dt><dd>抽头幅度看真实读回的变化，通信质量看逐窗捕获和确认比例。空窗没有数据，不补画曲线。固定条件、纠错和重传可能让轻微扰动不影响业务。</dd><dt>05 / 06：同一批接收符号恢复得怎样</dt><dd>比较均衡前后的星座；DBPSK 通常呈两个点簇。样本相同才可比较，未捕获则无有效接收星座。</dd></dl><p>要验证影响：主动减小幅度或增大噪声，先确认读回，再看捕获、失败帧、位置年龄与媒体进度。恢复后要等新心跳；不能只看图是否“动得明显”。</p><form method="dialog"><button class="primary">明白了</button></form>');document.body.append(chartHelp);helpLink.onclick=()=>chartHelp.showModal();
 const jumpPane=key=>{showTab('evidence');selectPane(key);tabs.scrollIntoView({behavior:'smooth',block:'start'});};window.openObservationPane=jumpPane;
 document.addEventListener('click',e=>{if(e.target.closest('[data-jump="action"],.action-detail'))selectPane('action');},true);
 // Archived actions stay inspectable. Opening a record never sends a command.
 const archiveNote=make('div','history-intro','<b>查看 ≠ 重新计算</b><p>查看记录只读保存的数据；实板重算重新运行并生成新记录；比较检查两次条件是否可比。未完成的记录不会被当作完整结果。</p>');E('history').prepend(archiveNote);
 const ai=E('question').closest('.assistantPanel');if(ai.querySelector('details'))ai.querySelector('details').open=true;
 const quick=make('div','question-examples','<span>用当前实验数据提问</span><button type="button">这条链路影响了哪些业务？</button><button type="button">刚才的措施执行了吗，有什么变化？</button>');E('question').closest('label').before(quick);quick.onclick=e=>{const b=e.target.closest('button');if(b){E('question').value=b.textContent;E('question').focus();}};
 E('ask').textContent='分析当前观测';E('question').placeholder='例如：节点5限速后，新增媒体、积压和心跳各有什么变化？';
 const mediaSummary=make('button','wide','查看收到的语音 / 视频');mediaSummary.id='openReceivedMedia';business.append(mediaSummary);mediaSummary.onclick=()=>{showTab('mission');document.querySelector('.received-files').open=true;document.querySelector('.received-files').scrollIntoView({behavior:'smooth',block:'center'});};
 E('cxStart').addEventListener('click',()=>selectPane('impact'));for(const id of ['cxChange','cxRestore','cxAdvance'])E(id).addEventListener('click',()=>selectPane('impact'));E('actionConfirm').addEventListener('click',()=>selectPane('action'));
 const mapState=make('p','map-state');mapState.id='mapObservationState';E('sharedMapPanel').querySelector('.mapheading').after(mapState);
 window.mapObservationLabel=()=>{
  if(pollFailed)return '连接中断 · 保留最后收到的位置，未确认新数据';
  if(E('lxMode').getAttribute('aria-pressed')==='true')return V.snapshot?'单帧诊断不更新编队 · 此处为最近网络记录的实收位置':'单帧诊断不更新编队 · 此处仅为配置预览';
  const cp=window.causalPresentation;
  if(history||cp?.active&&cp.history)return replayTimer?'历史回放 · 保存数据，不操作板卡':'历史定格 · 保存时刻的地面实收位置';
  if(!V.snapshot)return '配置预览 · 尚无实板接收位置';
  if(S.status==='stopped')return '已中止 · 部分实收结果，非完整实验';
  if(S.error||S.status==='error')return '实验中断 · 仅显示最后收到的位置';
  if(cp?.active&&cp.view?.phase==='waiting'||S.status==='paused')return '观测暂停 · 地面最后实收位置，等待下一步';
  if(S.busy)return '实板计算 · 地面实收位置；动画表示窗口通信关系';
  return '本次计算结束 · 地面最终实收位置，非正在飞行';
 };
 let nextAction=()=>{},lastText='';
 function guide(title,hint,state,label,action){E('taskHeadline').textContent=title;E('taskHint').textContent=hint;E('taskState').textContent=state;E('taskNext').textContent=label;nextAction=action;E('taskNext').disabled=false;}
 E('taskNext').onclick=()=>nextAction();
 function focus(id){const e=E(id);if(e.closest('details'))e.closest('details').open=true;e.scrollIntoView({behavior:'smooth',block:'center'});e.focus({preventScroll:true});}
 function refresh(){
  const cp=window.causalPresentation,causal=!!cp?.active,single=E('lxMode').getAttribute('aria-pressed')==='true',v=cp?.view,readonly=!!history||!!(causal&&cp.history);
  if(lastCausal!==causal){if(causal)techHolder.append(center,modem);else{centerHome.after(center);modemHome.after(modem);}lastCausal=causal;requestAnimationFrame(()=>window.renderInstruments?.());}
  document.body.classList.toggle('task-causal',causal);
  for(const id of Object.keys(modes)){E(id).disabled=!!S.busy;E(id).setAttribute('aria-pressed',String(id==='cxMode'?causal:id==='lxMode'?!causal&&single:!causal&&!single));}
  E('modeLock').textContent=S.busy?'任务进行中 · 可以切页观察':'三种任务共用一块板卡';
  E('configAvailability').textContent=readonly?'正在查看历史；这些配置不能改变已保存结果。':causal?'当前任务的场景在“信道与收发”的实验条件中设置；卡片可切换新实验段，原记录保留。':S.busy?'本轮配置已锁定；结束后更改，下一次开始生效。':'可修改下一轮场景；开始后固定到本次实验结束。';
  const waiting=causal&&['waiting','running'].includes(v?.phase)&&!readonly&&S.busy;
  E('conditionAvailability').textContent=readonly?'历史只读。到第三页选择实板重算，或返回当前任务。':waiting?'现在可修改：点击应用后，在下一轮实际发送前写入并读回。':v?.phase==='complete'?'本次已结束；展开上方设置，开始新实验后再改变条件。':S.busy?'正在收发；可提交下一项改变，在采集边界生效。':'开始实板实验后可随时修改信道。';
  E('sharedContext').querySelector('b').textContent='观测身份';
  document.querySelectorAll('.task-trail button').forEach(b=>b.classList.toggle('selected',b.dataset.dest===tab));
  const caption=window.mapObservationLabel();if(caption!==lastText){mapState.textContent=caption;lastText=caption;if(tab==='mission')drawMap();}
  if(readonly){guide('正在查看保存的实验','所有图表与业务对应保存时刻。可以拖动时间线，不能在历史中发送节点指令。','历史 · 只读','查看回放与重算',()=>showTab('history'));}
  else if(pollFailed){guide('显控服务暂未连接','保留旧观测，但不能当作实时结果。请通过固定入口启动服务，恢复后再检查板卡。','连接中断','查看连接位置',()=>focus('connect'));}
  else if(S.status==='stopped'){guide('实验已中止，部分结果已保留','没有把中止当作通过。可检查部分记录，或修改配置后重新开始；新的实验会单独保存。','已中止','核对下一次设置',()=>causal?(showTab('evidence'),focus('cxSetup')):single?(showTab('evidence'),focus('lxFields')):showTab('mission'));}
  else if(S.error){guide('本次任务未完成',S.error+'。部分结果保留，不计作完整通过。','需要处理','查看任务记录',()=>showTab('history'));}
  else if(!S.connected){guide('先连接板卡，再开始实验','接好电源、JTAG 与 USB TO UART；选择串口并检查连接。重新上电后先加载本版固件。','准备','检查连接',()=>{if(!E('connect').disabled)E('connect').click();});}
  else if(causal){
   if(waiting)guide('本轮已收到结果，现在由你决定下一步','可改变信道、核对业务影响，或发送节点措施。操作将在采集边界生效，指令必须取得接收与执行回执。','等待你的操作','查看业务影响',()=>jumpPane('impact'));
   else if(v?.phase==='complete')guide('实验已完成，结果已自动保存','核对最终与按时送达、措施回执及业务变化；随后保存对比或按原时间轴重新计算。','完成','查看保存与重现',()=>showTab('history'));
   else if(S.busy)guide('正在经 FPGA 计算通信','等本观察窗口结束再修改条件。可随时切页看节点、业务或同帧接收；发送指令前仍需确认。','计算中','查看六张技术图',()=>jumpPane('technical'));
   else guide('验证：一条链路变差，会影响谁？','从10秒基线开始；改变信道并核对读回，再观察位置与文件回传，恢复后验证新心跳。','交互验证','开始10秒基线',()=>{showTab('evidence');E('cxStart').click();});
  }else if(single){guide('诊断：你发的内容能否完整收到？','编辑正文和信道参数，再应用采集。此任务独立于编队网络；正文、读回与星座逐帧绑定。',S.busy?'采集中':'单帧诊断',S.busy?'查看接收结果':'设置并采集',()=>{showTab('evidence');focus(S.busy?'lxStatus':'lxApply');});}
  else if(S.busy){guide(S.status==='paused'?'整机已暂停':'完整场景正在运行','首页看信道与收发；第二页看实收位置、心跳、告警和媒体。暂停按通信批次完成，指令需收到执行回执才算确认。',S.status==='paused'?'暂停':'计算中',S.status==='paused'?'继续计算':'查看节点与业务',()=>S.status==='paused'?E('resume').click():showTab('mission'));}
  else if(V.snapshot){guide('完整场景结果已保留','最终送达不等于按时送达。地图为最后实收位置；可播放收齐的文件，或在第三页对比、重算。','结果','查看实收业务',()=>{showTab('mission');document.querySelector('.received-files').open=true;});}
  else guide('运行：检查整支编队的通信表现','先选择场景与编队，再开始。此模式支持运动和高度指令；不支持中途任意更改整轮场景。','完整场景','选择场景与编队',()=>showTab('mission'));
  // Keep disabled controls explainable without granting extra capabilities.
  for(const id of ['cxChange','cxRestore','cxAdvance','cxFinish']){E(id).title=E(id).disabled?E('conditionAvailability').textContent:'';E(id).setAttribute('aria-describedby','conditionAvailability');}
  E('actionPrepare').setAttribute('aria-describedby','actionAvailability');
  const supportedTarget=[1,5].includes(+E('actionTarget').value)||![3,4].includes(+E('actionOp').value);
  E('actionPrepare').disabled=!waiting||!supportedTarget;
  if(waiting&&!supportedTarget)E('actionAvailability').textContent='该节点没有媒体源。媒体操作只适用于节点1（语音）或节点5（视频）；其他节点可查询状态或调整心跳。';
 }
 const oldTab=showTab;showTab=id=>{oldTab(id);requestAnimationFrame(refresh);};
 window.addEventListener('experiment-view',()=>requestAnimationFrame(refresh));setInterval(refresh,450);refresh();
 // A concise, mode-aware guide is generated on open, after legacy handlers.
 E('help').addEventListener('click',()=>{
  E('guide').querySelector('h2').textContent='选择任务，然后沿同一条数据主线走';
  E('guide').querySelector('ol').innerHTML='<li><b>检查连接。</b>选择 USB TO UART 串口；重启开发板后加载本版固件。</li><li><b>选择一种实验任务。</b>交互验证看“改变条件→业务影响→采取措施”；单帧诊断看真实正文与接收；完整场景看编队、运动和音视频。</li><li><b>页面只改变观察角度。</b>01看信道与接收，02看节点与业务，03看保存、对比与重算；不会因切页自动开始另一实验。</li><li><b>操作必须看回执与效果。</b>等待本轮观察完成，再应用条件或核对节点指令。发出、执行回执、执行后窗口分开显示，改善与否由结果决定。</li><li><b>复现不用猜。</b>记录自动保存；查看记录不操作板卡，实板重算会重新运行。最终送达、按时送达及失败结果均保留。</li>';
 });
})();
