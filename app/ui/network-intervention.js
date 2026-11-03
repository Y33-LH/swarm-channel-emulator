/* A complete running-network task. UI labels report observations, never force outcomes. */
(()=>{
 const E=id=>document.getElementById(id),bar=E('experimentModeBar'),panel=document.createElement('section');
 panel.id='networkIntervention';panel.hidden=true;
 const modeButton=document.createElement('button');modeButton.id='cxMode';modeButton.textContent='① 链路与措施 → 业务效果';bar.prepend(modeButton);
 E('lxMode').textContent='② 单帧 · 信道与接收';E('lxNetworkMode').textContent='③ 整机 · 编队与业务';
 bar.querySelector('small').textContent='从改变条件，到业务恢复，再到实板重现';
 panel.innerHTML=`
 <div class="cx-heading"><div><span class="eyebrow">CHANNEL → RECEIVER → SERVICE</span><h2>这一条链路变差，会影响谁？</h2><p>16 节点仍逐跳通信。只改变一条有向链路的信号与噪声，观察地面真正收到的业务。</p></div><span id="cxSource" class="cx-tag">尚未开始</span></div>
 <div class="cx-journey"><span>01 观察正常业务</span><span>02 修改一条链路</span><span>03 检查实际影响</span><span>04 恢复并验证</span><span>05 保存与重现</span></div>
 <div class="cx-layout"><aside class="cx-card"><h3>实验条件</h3>
 <details id="cxSetup" open><summary>链路、场景与时间设置</summary><fieldset id="cxSettings"><label>修改哪一条上行链路？<select id="cxLink">${Array.from({length:16},(_,i)=>`<option value="${i}">节点 ${i+1} → ${i%4===3?'地面站':'节点 '+(i+2)} · ${i%4===3?'空地':'空空'}</option>`).join('')}</select></label>
 <label>场景<select id="cxEnvironment"><option value="1">旷野</option><option value="3">郊区</option><option value="4">城市</option></select></label>
 <div class="two"><label>天气<select id="cxWeather"><option value="0">晴天</option><option value="1">雾</option><option value="2">小雨</option><option value="3">中雨</option><option value="4">大雨</option><option value="5">小雪</option><option value="6">中雪</option><option value="7">大雪</option></select></label><label>编队<select id="cxFormation"><option value="0">X形</option><option value="1">横列</option><option value="2">纵列</option><option value="3">V形</option><option value="4">三角形</option><option value="5">梯形</option><option value="6">菱形</option><option value="7">方阵</option><option value="8">环形</option></select></label></div><label>参考SNR / dB<input id="cxSnr" type="number" min="0" max="45" step="1" value="34"></label><p class="cx-note">天气仅改变公开的等效损耗和部分编队位置扰动；不是实测气象模型。程序地形仅为场景示意，不参与传播计算。</p><label>随机种子<input id="cxSeed" type="number" min="1" max="4294967295" value="20261021"></label>
 <label>实验时长 / 模型秒<input id="cxSeconds" type="number" min="90" max="900" value="90"></label></fieldset></details><p id="cxConfiguration" class="cx-note"></p>
 <button id="cxStart" class="primary wide">开始：观察 10 秒基线</button>
 <p class="cx-note">使用现有固定路由、TDMA 和完整 DBPSK 纠错链；关闭预设故障。持续模式实时计算；操作在下一采集边界生效，暂停后仍可查看结果。</p>
 <hr><h3>下一轮改变什么？</h3><fieldset id="cxCondition">
 <div class="two"><button id="cxMild">轻度扰动</button><button id="cxSevere">明显衰减</button></div>
 <label>保留原信号幅度 / %<input id="cxGain" type="number" min="0" max="100" step="0.1" value="5"></label>
 <label>每路 I、Q 噪声 σ / 码值<input id="cxSigma" type="number" min="0" max="8192" step="1" value="8192"></label>
 <label>接着观察 / 模型秒<input id="cxWindow" type="number" min="1" max="60" step="1" value="20"></label>
 </fieldset><button id="cxChange" class="wide">应用条件，观察业务影响</button>
 <button id="cxRestore" class="wide cx-restore">恢复原场景条件并观察</button>
 <div class="two"><button id="cxAdvance">保持条件，继续观察</button><button id="cxFinish">运行到结束并保存</button></div>
 <button id="cxStop" class="wide danger">中止本次实验</button>
 <p class="cx-note">这是实验信道控制，不是飞行指令。恢复会重新采用当前时刻的场景参数；反向 ACK 与其他链路不跟随修改。</p>
 </aside><div class="cx-main">
 <section class="cx-card"><div class="cx-status-heading"><h3 id="cxTitle">先连接板卡，再开始实验</h3><strong id="cxTime">0 / 90 模型秒</strong></div>
 <progress id="cxProgress" max="90" value="0"></progress><p id="cxStatus" role="status">顶部检查连接；加载本版固件后，开始采集正常通信基线。</p>
 <div id="cxReceipt" class="cx-receipt">修改条件后，此处依次显示 ARM 接受 → FPGA 寄存器读回 → 该帧接收结果。</div>
 <div id="cxWindowStats" class="cx-kpis"></div></section>
 <section class="cx-card"><div class="cx-status-heading"><h3>地面收到的业务，有什么变化？</h3><span class="cx-note">位置时效来自实际接收心跳</span></div>
 <div id="cxBusiness" class="cx-business"><p>基线将显示受影响节点与另一条路径的对照节点。</p></div>
 <div class="cx-media"><div><b>节点 1 · 语音文件</b><progress id="cxAudioBar" value="0" max="1"></progress><span id="cxAudio">等待接收分片</span></div><div><b>节点 5 · 视频文件</b><progress id="cxVideoBar" value="0" max="1"></progress><span id="cxVideo">等待接收分片</span></div></div>
 <p class="cx-note" id="cxConclusion">失败接收不会交付正文；有旧位置不等于通信正常。恢复后必须收到恢复时刻之后生成的新心跳。</p>
 </section>
 <div class="cx-charts"><section class="cx-card"><h3>01 / 位置更新时间与操作时刻</h3><canvas id="cxAge" aria-label="心跳位置年龄趋势"></canvas><p class="cx-note">实线：受影响路径源节点；虚线：独立路径对照。纵轴是位置年龄，越小越新鲜。</p></section>
 <section class="cx-card"><h3>02 / 语音与视频接收进度</h3><canvas id="cxMedia" aria-label="业务接收进度趋势"></canvas><p class="cx-note">停滞意味着尚无新分片交付；上升来自地面收齐并接受的新数据。</p></section></div>
 <section class="cx-card"><div class="cx-status-heading"><h3>同一帧：实际信道 → 接收变化</h3><span id="cxFrameIdentity" class="cx-note">尚无观测帧</span></div>
 <div id="cxFrame" class="cx-receipt"></div>
 <div class="cx-iq"><div><h4>03 / 均衡前接收星座</h4><canvas id="cxBefore" aria-label="同帧均衡前星座"></canvas></div><div><h4>04 / 均衡后接收星座</h4><canvas id="cxAfter" aria-label="同帧均衡后星座"></canvas></div></div>
 <p class="cx-note">同一 DATA 帧的参数、接收缓存及 CRC；不混用 ACK。不捕获时清空星座，避免把旧成功帧当成新结果。</p>
 <details><summary>本帧实际发送与接收字节</summary><pre id="cxBytes">尚无数据</pre></details></section>
 <section class="cx-card"><h3>操作与生效记录</h3><div id="cxEvents" class="cx-events">等待操作</div></section>
 <section class="cx-card"><h3>保存并重现这次过程</h3><p class="cx-note">过程自动保存。查看记录不操作板卡；实板重算会按原模型时间执行全部变更，重新经过 FPGA，并比较每轮结果、失败帧、IQ 与接收文件。</p>
 <div class="cx-history"><select id="cxRecords" aria-label="选择链路干预记录"><option value="">暂无记录</option></select><button id="cxRefresh">刷新记录</button><button id="cxView">查看记录</button><button id="cxLive">返回当前实验</button></div>
 <div id="cxReplayBar" hidden><label>查看历史时刻<input id="cxReplayRange" type="range" min="0" max="0" value="0"></label><span id="cxReplayTime"></span></div>
 <div class="two"><button id="cxReproduce">按原时间轴实板重算</button><button id="cxExport">导出本次完整记录</button></div>
 <p id="cxSaved" class="cx-note"></p><p id="cxReproduction"></p></section>
 </div></div>`;
 bar.after(panel);
 let active=false,cur=null,historyRecord=null,view=null,trace=[],busy=false,connected=false,task=null,last='',inRequest=false,recordKey='';
 const guideTitle=E('guide').querySelector('h2'),guideList=E('guide').querySelector('ol');
 const oldGuideTitle=guideTitle.textContent,oldGuideList=guideList.innerHTML;
 const f=(x,n=1)=>x==null?'—':Number(x).toLocaleString('zh-CN',{maximumFractionDigits:n});
 function activate(on){
  active=on;if(on){if(history)E('returnLive').click();window.setLinkExperimentMode(false);showTab('evidence');}
  window.causalPresentation={active:on,view,history:!!historyRecord};window.dispatchEvent(new Event('experiment-view'));
  panel.hidden=!on;document.body.classList.toggle('causal-mode',on);modeButton.setAttribute('aria-pressed',String(on));
  guideTitle.textContent=on?'从链路变化到业务恢复':oldGuideTitle;
  guideList.innerHTML=on?'<li><b>加载固件并开始。</b>接好电源、JTAG、USB TO UART。顶部加载本版固件，开始观察10模型秒基线。</li><li><b>主动修改链路。</b>选择幅度和噪声，应用后检查 ARM 接受、FPGA 读回和同帧接收结果。</li><li><b>看具体业务。</b>关注受影响节点的位置年龄、语音进度，并与另一条路径比较。</li><li><b>恢复并验证。</b>恢复原场景条件，等待地面收到恢复之后产生的新心跳，观察分片继续交付。</li><li><b>保存与重现。</b>运行到结束。查看记录是只读；实板重算按原时间轴重新计算并比较结果。</li>':oldGuideList;
  if(on){E('lxMode').setAttribute('aria-pressed','false');E('lxNetworkMode').setAttribute('aria-pressed','false');render();}
  else {if(history?.id?.startsWith('causal_')){history=null;historyRecord=null;}window.setActionContext?.({active:false});renderView();}
 }
 window.openCausalLive=()=>{historyRecord=null;history=null;trace=[];view=cur;activate(true);};
 const previousShowTab=showTab;
 showTab=id=>{previousShowTab(id);document.body.classList.toggle('causal-mode',active&&id==='evidence');if(id==='evidence'&&active)render();};
 modeButton.onclick=()=>activate(true);
 ['lxMode','lxNetworkMode'].forEach(id=>E(id).addEventListener('click',()=>activate(false)));
 const fail=e=>{E('cxStatus').textContent=e.message;toast(e.message);};
 async function request(fn){inRequest=true;buttons();try{await fn();}catch(e){fail(e);}finally{inRequest=false;buttons();}}
 function buttons(){
  const live=cur&&!historyRecord,waiting=live&&['waiting','running'].includes(cur.phase)&&busy&&task==='causal'&&!cur.replaying;
  E('cxSettings').disabled=busy||!!historyRecord||inRequest;E('cxStart').disabled=busy||!!historyRecord||!connected||inRequest;
  E('cxCondition').disabled=!waiting||inRequest;
  ['cxChange','cxRestore','cxAdvance','cxFinish'].forEach(id=>E(id).disabled=!waiting||inRequest);
  E('cxStop').disabled=!busy||task!=='causal'||inRequest;
  E('cxReproduce').disabled=busy||!connected||!E('cxRecords').value||inRequest||E('cxRecords').selectedOptions[0]?.dataset.reproducible!=='1';
  E('cxView').disabled=!E('cxRecords').value;E('cxExport').disabled=!(historyRecord?.id||cur?.id)||inRequest;
 }
 E('cxStart').onclick=()=>request(async()=>{
  historyRecord=null;trace=[];last='';await api('/api/causal/start',{link:Number(E('cxLink').value),seed:Number(E('cxSeed').value),seconds:Number(E('cxSeconds').value),continuous:window.liveModeEnabled===true,
    config:{environment:Number(E('cxEnvironment').value),weather:Number(E('cxWeather').value),formation:Number(E('cxFormation').value),reference_snr_cdb:Math.round(Number(E('cxSnr').value)*100),faults:0}});
  E('cxSetup').open=false;
  E('cxStatus').textContent='正在上传业务文件并开始基线计算…';
 });
 const submit=kind=>request(async()=>{
  const response=await api('/api/causal/action',{id:cur.id,kind,window_s:Number(E('cxWindow').value),gain_permille:Math.round(Number(E('cxGain').value)*10),sigma:Number(E('cxSigma').value)});
  cur.phase='queued';E('cxStatus').textContent='操作已排队；等待 ARM 接受和实际 FPGA 读回。';buttons();
 });
 E('cxChange').onclick=()=>submit('change');E('cxRestore').onclick=()=>submit('restore');E('cxAdvance').onclick=()=>submit('advance');E('cxFinish').onclick=()=>submit('finish');
 E('cxMild').onclick=()=>{E('cxGain').value=70;E('cxSigma').value=1800;};
 E('cxSevere').onclick=()=>{E('cxGain').value=5;E('cxSigma').value=8192;};
 E('cxStop').onclick=()=>request(()=>api('/api/stop',{}));
 async function refresh(){
  const rows=await api('/api/causal/records'),old=E('cxRecords').value;
  E('cxRecords').innerHTML='<option value="">选择已保存实验</option>'+rows.map(r=>`<option value="${esc(r.id)}" data-reproducible="${r.reproducible?'1':'0'}">${esc(r.id)} · ${r.complete?'已完成':'部分记录'}${r.reproducible?'':' · 仅可查看'}${r.report?.reproduction?.exact_match?' · 重算一致':''}</option>`).join('');
  if(rows.some(r=>r.id===old))E('cxRecords').value=old;else if(cur&&rows.some(r=>r.id===cur.id))E('cxRecords').value=cur.id;
  buttons();
 }
 E('cxRefresh').onclick=()=>refresh().catch(fail);E('cxRecords').onchange=buttons;
 function historyAt(){
  const index=Number(E('cxReplayRange').value),s=historyRecord.snapshots[index];
  view={id:historyRecord.id,plan:historyRecord.plan,phase:'history',latest:s,view:historyRecord.views[index],events:historyRecord.events,
        report:historyRecord.report,error:historyRecord.failure?.error};
  trace=historyRecord.snapshots.slice(0,index+1);render();
 }
 E('cxView').onclick=()=>request(async()=>{
  const fromTab=tab,record=await api('/api/causal/record?id='+encodeURIComponent(E('cxRecords').value));
  if(!record.snapshots.length)throw Error('该记录尚无完整观测；可导出查看失败原因');
  if(!active)activate(true);
  historyRecord=record;
  E('cxReplayRange').max=historyRecord.snapshots.length-1;E('cxReplayRange').value=historyRecord.snapshots.length-1;historyAt();
  if(fromTab==='history')showTab('history');
 });
 E('cxReplayRange').oninput=historyAt;
 E('cxLive').onclick=()=>{historyRecord=null;history=null;trace=[];view=cur;render();};
 E('cxReproduce').onclick=()=>request(async()=>{
  const id=E('cxRecords').value;historyRecord=null;trace=[];last='';await api('/api/causal/reproduce',{id});
  E('cxStatus').textContent='重新计算原时间轴：所有业务重新经过实板，等待逐轮对比。';
 });
 E('cxExport').onclick=()=>request(async()=>{const d=await api('/api/causal/export?id='+encodeURIComponent(historyRecord?.id||cur.id));E('cxSaved').textContent='已导出：'+d.path;});
 const phaseNames={preparing:'准备实际收发',running:'正在计算通信',waiting:'本轮观察完成 · 等待你的下一步',queued:'操作排队，等待生效',complete:'本次实验完成，结果已保存',stopped:'已中止 · 保存部分结果',error:'实验中断，请查看原因',history:'历史记录 · 只读'};
 function syncSource(){
  if(!active||tab!=='evidence')return;
  E('sourceLabel').textContent=historyRecord?'历史链路干预记录 · 只读':cur?.replaying?'原时间轴 · 实板重新计算':cur?'当前链路干预任务 · 实板 UART':'链路干预 · 尚未开始';
  E('runStatus').textContent=historyRecord?historyRecord.id:cur?phaseNames[cur.phase]||cur.phase:'先检查设备，再观察基线';
  E('sourcebar').classList.toggle('history',!!historyRecord);E('returnLive').hidden=true;
 }
 const previousRenderView=renderView;
 renderView=()=>{previousRenderView();syncSource();};
 function render(){
  if(!historyRecord)view=cur;
  const v=view,b=v?.view,s=v?.latest,o=s?.observation,p=v?.plan;
  window.causalPresentation={active,view:v,history:!!historyRecord,trace};window.dispatchEvent(new Event('experiment-view')); 
  E('cxConfiguration').textContent=p?`当前：节点 ${p.link+1} → ${p.link%4===3?'地面站':'节点 '+(p.link+2)}；${({1:'旷野',3:'郊区',4:'城市'})[p.config.environment]||'自定义场景'}；${catalog?.weather[p.config.weather]?.name||''} / ${catalog?.formation[p.config.formation]?.name||''}；参考SNR ${p.config.reference_snr_cdb/100}dB；种子 ${p.seed}`:'';
  E('cxSource').textContent=historyRecord?'历史实板记录 · 只读':v?.replaying?'实板重新计算':v?'当前实板网络':'尚未开始';
  E('cxTitle').textContent=v?phaseNames[v.phase]||v.phase:'先连接板卡，再开始实验';
  if(v&&!historyRecord&&busy)E('cxSetup').open=false;
  E('cxTime').textContent=`${f(b?.model_s||0)} / ${p?.seconds||90} 模型秒`;
  E('cxProgress').max=p?.seconds||90;E('cxProgress').value=b?.model_s||0;
  E('cxStatus').textContent=v?.error||(!v?'顶部检查连接；加载本版固件后开始。':v.phase==='waiting'?'模型时间已暂停。可改变信道、恢复原场景，或保持条件继续观察。':v.phase==='complete'?'已保存完整时间轴。可查看各时刻，也可以用原条件实板重算。':v.phase==='history'?'只读保存时刻的真实结果；在第三页拖动时间线查看变化。':v.replaying?'正在按保存的操作时刻重新计算，尚未得出一致性结论。':'等待真实帧和地面接收结果。');
  const events=(v?.events||[]).filter(e=>!historyRecord||e.effective_round<=(s?.round||0)).map(e=>historyRecord&&e.readback_ms>(s?.round||0)*100?{...e,readback_ms:null}:e),applied=events.filter(e=>e.condition_id).at(-1);
  E('cxReceipt').textContent=applied?`操作 #${applied.condition_id}：${applied.action.kind==='restore'?'恢复场景条件':`保留幅度 ${applied.action.gain_permille/10}% / σ ${applied.action.sigma}`}；ARM 在 ${f(applied.effective_round/10)} 模型秒接受；${applied.readback_ms!=null?'FPGA 于 '+f(applied.readback_ms/1000,3)+' 秒帧读回确认':'尚待该链路实际发送并读回'}`:'基线：使用当前场景参数，尚未施加用户干预。';
  E('cxWindowStats').innerHTML=b?[['本窗口长度',f(b.window_s)+' s'],['所选跳尝试',b.attempts+' 帧'],['CRC 通过',b.crc_good+' 帧'],['接收失败',b.failed+' 帧'],['重复发送',b.retries+' 次'],['网络待转发',b.pending+' 帧']].map(([k,x])=>`<div><small>${k}</small><b>${x}</b></div>`).join(''):'';
  E('cxBusiness').innerHTML=b?b.nodes.map(n=>`<article class="${n.fresh?'good':'stale'}"><div><strong>节点 ${n.id}</strong><span>${n.control?'独立路径对照':'经过所选链路'}</span></div><h4>${n.recovered&&!n.control?'已收到恢复后的新心跳':n.fresh?'地面位置正在更新':n.age_ms==null?'尚未收到心跳':'位置已过期 · 通信受影响'}</h4><p>位置年龄 <b>${n.age_ms==null?'—':f(n.age_ms/1000)+' s'}</b> · 本窗口新增 <b>${n.new_updates}</b> 条心跳</p><small>地面累计收到 ${n.received_updates} 条 · 最新序号 ${n.sequence??'—'}<br>生成 ${f(n.generation_ms/1000,3)} s → 地面收到 ${f(n.received_ms/1000,3)} s</small></article>`).join(''):'等待真实业务';
  for(const [key,bytes,total,added] of [['Audio',b?.audio_bytes,b?.audio_total,b?.new_audio_bytes],['Video',b?.video_bytes,b?.video_total,b?.new_video_bytes]]){
   E('cx'+key+'Bar').max=total||1;E('cx'+key+'Bar').value=bytes||0;
   E('cx'+key).textContent=b?`${f(bytes,0)} / ${f(total,0)} 字节 · 本窗口新增 ${f(added,0)} 字节`:'等待接收分片';
  }
  if(b){const bad=b.nodes.filter(n=>!n.control&&!n.fresh),recovered=b.nodes.filter(n=>!n.control&&n.recovered);
   E('cxConclusion').textContent=bad.length?`节点 ${bad.map(n=>n.id).join('、')} 的地面位置已不新鲜。旧坐标仍保留，但不能作为当前位置；对照路径与接收分片可用于区分局部链路问题。`:recovered.length?`节点 ${recovered.map(n=>n.id).join('、')} 已交付恢复时刻之后生成的新位置。请同时观察语音分片继续增加；积压业务需要时间排空。`:'当前观察窗口内位置仍新鲜。轻度扰动可能被纠错和重传吸收；没有业务失败时不会人为制造异常。';}
  const ob=b?.observation;
  E('cxFrameIdentity').textContent=ob?`${f(ob.model_ms/1000,3)} s · ${({1:'心跳与位置',2:'告警',3:'语音分片',4:'视频分片',5:'普通数据',6:'下行指令',7:'执行回执'})[ob.kind]||'业务帧'} · 源节点 ${ob.origin} · 序号 ${ob.sequence} · 分片 ${ob.fragment} · FPGA帧 ${ob.generation}`:'尚无观测帧';
  E('cxFrame').textContent=ob?`读回：幅度 ${f(ob.gain,5)} / 噪声 σ ${ob.sigma} → ${ob.received?'捕获、译码、CRC 与字节核对通过':ob.captured?'已捕获，但该帧未通过接收校验':'PN 帧头未捕获，无有效正文'}。${ob.captured&&ob.pre_bits?`纠错前 BER ${f(100*ob.pre_errors/ob.pre_bits,3)}% → 纠错后 ${ob.post_bits?f(100*ob.post_errors/ob.post_bits,3)+'%':'无有效位数'}。`:''}`:'等待本次实板观测';
  E('cxBytes').textContent=o?`TX：${o.tx_hex}\nRX：${o.rx_hex||'未交付；不使用发送端字节补齐'}`:'尚无数据';
  E('cxEvents').innerHTML=events.length?events.map(e=>`<div><b>${f(e.effective_round/10)} s</b><span>${{change:'修改信道',restore:'恢复场景条件',advance:'保持条件继续观察',finish:'运行至结束',command:'发送节点措施'}[e.action.kind]}${e.action.kind==='change'?` · 幅度 ${e.action.gain_permille/10}% · σ ${e.action.sigma}`:''}</span><small>${e.condition_id?e.readback_ms!=null?'寄存器已确认':'等待实际帧确认':'不改信道'}</small></div>`).join(''):'尚无操作；基线数据也会保存。';
  E('cxReplayBar').hidden=!historyRecord;E('cxReplayTime').textContent=historyRecord?`${f(b?.model_s)} 模型秒，只读历史`:'';
  const rep=v?.report?.reproduction;
  E('cxReproduction').textContent=rep?rep.exact_match?`实板重算一致：${rep.compared_snapshots} 轮快照、失败结果、同帧 IQ 和接收文件均与原记录相符。`:`重算存在差异：${rep.mismatches.length} 轮，请保留记录排查。`:'';
  if(v?.phase==='complete')E('cxSaved').textContent='已自动保存：'+v.id;
  draw();buttons();syncSource();window.setActionContext?.({active,view,history:!!historyRecord,trace});
 }
 function canvas(id){
  const c=E(id),rect=c.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
  if(rect.width<1)return null;
  c.width=Math.round(rect.width*dpr);c.height=Math.round(rect.height*dpr);
  const ctx=c.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,rect.width,rect.height);return {c:ctx,w:rect.width,h:rect.height};
 }
 function plot(id,series,ymax,events){
  const obj=canvas(id);if(!obj)return;const {c,w,h}=obj,L=42,T=14,W=w-58,H=h-42,xmax=view?.plan.seconds||90;
  c.font='11px sans-serif';c.strokeStyle='#254451';c.fillStyle='#90b5c5';
  for(let i=0;i<=4;i++){let y=T+H*i/4;c.beginPath();c.moveTo(L,y);c.lineTo(L+W,y);c.stroke();c.fillText(f(ymax*(1-i/4)),3,y+4);}
  for(let i=0;i<=3;i++)c.fillText(f(xmax*i/3)+'s',L+W*i/3-8,h-8);
  for(const e of events||[]){c.strokeStyle=e.action.kind==='restore'?'#8ce6a9':'#f4b763';c.setLineDash([3,4]);c.beginPath();c.moveTo(L+W*e.effective_round/10/xmax,T);c.lineTo(L+W*e.effective_round/10/xmax,T+H);c.stroke();}
  series.forEach((s,i)=>{c.strokeStyle=i?'#a7b7ff':'#5be6cf';c.lineWidth=2;c.setLineDash(i?[4,3]:[]);c.beginPath();s.forEach(([x,y],j)=>{if(j===0)c.moveTo(L+W*x/xmax,T+H*(1-y/ymax));else c.lineTo(L+W*x/xmax,T+H*(1-y/ymax));});c.stroke();});c.setLineDash([]);
 }
 function iq(id,o,bank){
  const obj=canvas(id);if(!obj)return;const {c,w,h}=obj,size=Math.min(w-32,h-34),x=(w-size)/2,y=(h-size)/2;
  c.strokeStyle='#254451';c.fillStyle='#90b5c5';c.font='11px sans-serif';c.beginPath();c.moveTo(x,y+size/2);c.lineTo(x+size,y+size/2);c.moveTo(x+size/2,y);c.lineTo(x+size/2,y+size);c.stroke();
  c.fillText('I/Q ±32768',x,y+size+13);
  if(!o||!o.iq.length){c.fillText(o?'本帧未捕获 · 无接收星座':'等待真实采样',x,y+size/2-15);return;}
  c.fillStyle='#5be6cf';for(const row of o.iq){const v=row[bank]>>>0,I=(v&65535)<<16>>16,Q=v>>16;c.beginPath();c.arc(x+size*(.5+I/65536),y+size*(.5-Q/65536),2.5,0,Math.PI*2);c.fill();}
 }
 function draw(){
  if(!active)return;
  const group=Math.floor((view?.plan.link||0)/4),node=group*4+1,control=group===0?5:1;
  const ages=[node,control].map(id=>trace.filter(s=>s.nodes[id-1][9]).map(s=>[s.round/10,(s.round*100-s.nodes[id-1][10])/1000]));
  const max=Math.max(5,...ages.flat().map(p=>p[1]));
  plot('cxAge',ages,Math.ceil(max/5)*5,(view?.events||[]).filter(e=>!historyRecord||e.effective_round<=(view?.latest?.round||0)));
  plot('cxMedia',[0,2].map(i=>trace.map(s=>[s.round/10,s.media[i+1]?100*s.media[i]/s.media[i+1]:0])),100,(view?.events||[]).filter(e=>!historyRecord||e.effective_round<=(view?.latest?.round||0)));
  iq('cxBefore',view?.latest?.observation,0);iq('cxAfter',view?.latest?.observation,1);
 }
 async function poll(){
  try{
   const d=await api('/api/causal/state');busy=d.busy;connected=d.connected;task=d.task;
   const key=d.experiment?d.experiment.id+':'+d.experiment.updated:'';
   if(key!==last){
    last=key;const old=cur?.id;cur=d.experiment;
    if(!historyRecord){if(cur?.id!==old)trace=[];if(cur?.latest&&trace.at(-1)?.round!==cur.latest.round)trace.push(cur.latest);render();}
    if(cur?.phase==='complete'&&recordKey!==cur.id){recordKey=cur.id;await refresh();
     if(!historyRecord){const full=await api('/api/causal/record?id='+cur.id);trace=full.snapshots;render();}}
   }buttons();
  }catch(e){connected=false;buttons();if(active)E('cxStatus').textContent='未取得新观测：'+e.message;}
  setTimeout(poll,180);
 }
 window.addEventListener('resize',draw);refresh().catch(fail);poll();
 if(location.hash==='#causal'||!location.hash)activate(true);
})();
