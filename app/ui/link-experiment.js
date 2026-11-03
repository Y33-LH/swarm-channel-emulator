/* One task, one immutable observation bundle. No model-generated IQ or live replay. */
(() => {
 const E=id=>document.getElementById(id);
 const panel=document.createElement('section');panel.id='linkExperiment';panel.hidden=true;
 const bar=document.createElement('div');bar.id='experimentModeBar';bar.className='experiment-mode-bar';
 bar.innerHTML='<button id="lxMode" aria-pressed="false">① 单链路 · 条件与接收</button><button id="lxNetworkMode" aria-pressed="true">② 整机 · 编队与业务</button><small>先验证一跳，再评估整个网络</small>';
 E('evidence').prepend(bar);
 const fields=[
  ['gain','主径幅度 / 线性',0,1,.01,.6],['sigma','噪声 σ / 每路I、Q码值',0,8192,1,0],
  ['delay','主径时延 / 样点',0,512,1,24],['cfo','两径频偏 / Hz',-6000,6000,1,400],
  ['phase','主径初相 / °',-180,180,1,25],['echo_gain','回波幅度 / 线性',0,1,.01,0],
  ['echo_delay','回波额外时延 / 样点',0,32,1,4],['echo_phase','回波初相 / °',-180,180,1,90]
 ];
 const input=f=>`<label>${f[1]}<input id="lx_${f[0]}" type="number" min="${f[2]}" max="${f[3]}" step="${f[4]}" value="${f[5]}"></label>`;
 panel.innerHTML=`
 <div class="lx-intro"><div><h2>改变信道条件，核对真实接收</h2><p>选择一跳 → 设置条件 → 读回确认 → 同帧观测 → 保存与重现。</p><p>独立单跳实验，测试正文实际经过共享 FPGA 收发核；不推进16节点网络，不执行节点指令。</p></div><span class="lx-badge" id="lxSource">尚未采集</span></div>
 <div class="lx-layout"><aside class="lx-panel lx-settings"><h3>1 / 设置本次条件</h3><fieldset id="lxFields">
 <label>有向逻辑链路<select id="lxLink">${Array.from({length:32},(_,i)=>{let a=i%16+1,b=a%4?a+1:0;if(i>=16)[a,b]=[b,a];return `<option value="${i}">${a||'地面'} → ${b||'地面'} · ${i%4===3?'空地':'空空'} #${i}</option>`}).join('')}</select></label>
 <label>测试正文<textarea id="lxText" maxlength="64">位置正常，保持通信</textarea></label>
 <div class="two"><label>发送帧数<input id="lxFrames" type="number" min="1" max="10" step="1" value="3"></label><label>噪声种子<input id="lxSeed" type="number" min="1" max="4294967295" step="1" value="20261020"></label></div>
 ${input(fields[0])}${input(fields[1])}
 <details id="lxAdvanced"><summary>时延、频偏与双径参数</summary>${fields.slice(2).map(input).join('')}</details>
 <label>纠错<select id="lxFec"><option value="1">完整纠错链</option><option value="0">关闭纠错 · 对照</option></select></label>
 <label>解调方案<select id="lxProfile"><option value="0">DBPSK 软判决</option><option value="1">DBPSK 硬判决扩展示例</option></select></label>
 </fieldset>
 <p id="lxDraft" class="lx-hint">参数修改后，点击下方按钮才会写入 FPGA。</p>
 <button class="primary wide" id="lxApply">应用条件并采集</button><button class="wide" id="lxAbort" disabled>中止本次采集</button>
 <p class="lx-hint">顶部选择串口并检查连接；需要时先加载固件。网络实验必须结束或中止后才能独立采集。参数在本帧发送前确认，本次结束后恢复原寄存器。</p>
 </aside><div class="lx-main">
 <section class="lx-panel"><div class="lx-result-title"><h3>2 / 生效与接收结果</h3><select id="lxFrame" aria-label="选择观测帧"><option>尚无观测</option></select></div>
 <div class="lx-steps" id="lxSteps"><span>计划已确定</span><span>寄存器已读回</span><span>同帧已核验</span><span>记录已保存</span></div>
 <div id="lxStatus" class="lx-status" role="status">先保持默认条件采集，再只改变噪声 σ，对照实际收包变化。</div>
 <p id="lxIdentity" class="lx-hint"></p>
 <div id="lxReadback" class="lx-readback"></div>
 <div id="lxMetrics" class="lx-metrics"></div>
 <div id="lxBusiness" class="lx-business"><b>这一跳实际交付了什么？</b><p>等待 FPGA 接收。错误帧不会作为有效正文交付。</p></div></section>
 <label class="lx-scale">星座显示范围（只影响绘图）<select id="lxIqRange"><option value="12000">I/Q ±12,000 · 细看聚散</option><option value="32768">I/Q ±32,768 · 完整码域</option></select><span id="lxClip"></span></label>
 <div class="lx-charts">
 ${[['lxPdp','01 / 功率时延谱 PDP','由所选帧实际读回的抽头系数推导，横轴为相对主径时延。'],['lxCfr','02 / 信道频率响应 CFR','由实际系数推导的帧起始频响；不是接收机估计。'],['lxBefore','03 / 接收星座 · 均衡前','该帧 FPGA 接收缓存；I/Q等比例。'],['lxAfter','04 / 接收星座 · 均衡后','与均衡前相同帧、相同符号索引；I/Q等比例。']].map(([id,title,note])=>`<section class="lx-chart"><h3>${title}</h3><canvas id="${id}" aria-label="${title}"></canvas><p>${note}</p></section>`).join('')}
 </div>
 <section class="lx-panel"><h3>3 / 保存、对照与重新计算</h3><p class="lx-hint">每次采集自动保存全部帧及失败结果。“查看”只读，“实板重算”使用原始发送字节、寄存器值和噪声种子，生成新记录。</p>
 <div class="lx-history-tools"><select id="lxRecords" aria-label="选择单链路记录"><option value="">尚无记录</option></select><button id="lxRefresh">刷新</button><button id="lxView">查看记录</button><button id="lxReproduce">按原条件实板重算</button><button id="lxExport">导出记录</button></div>
 <div class="lx-history-tools" style="margin-top:10px"><button id="lxUse">把所选记录条件载入编辑区</button><button id="lxCompare">与当前观测比较</button><button id="lxLive">返回最新采集</button></div>
 <div id="lxCompareResult" class="lx-compare">比较时会核对链路、发送字节、种子和变更参数；多项条件改变时不会声称单因素归因。</div>
 </section></div></div>`;
 bar.after(panel);
 panel.querySelector('.lx-charts').after(E('lxBusiness'));
 E('lxBusiness').classList.add('lx-panel');
 let current=null,view=null,frameIndex=-1,readOnly=false,active=false,lastKey='',stateBusy=false,connected=false,task=null,requesting=false;
 const percent=x=>x==null?'—':(x*100).toFixed(2)+'%',f=(x,n=2)=>Number.isFinite(x)?x.toLocaleString('zh-CN',{maximumFractionDigits:n}):'—';
 function mode(on){
  if(on&&history){E('returnLive').click();toast('已退出整机历史回放；单链路操作使用当前板卡。');}
  active=on;panel.hidden=!on;document.body.classList.toggle('link-mode',on);
  E('lxMode').setAttribute('aria-pressed',String(on));E('lxNetworkMode').setAttribute('aria-pressed',String(!on));
  if(on){showTab('evidence');if(!current&&!view)E('lxLink').value=E('linkSelect').value||'0';render();}else{renderView();}
 }
 E('lxMode').onclick=()=>mode(true);E('lxNetworkMode').onclick=()=>mode(false);
 E('openLab').addEventListener('click',e=>{e.preventDefault();e.stopImmediatePropagation();mode(true);},true);
 const showBase=showTab;
 showTab=id=>{
  if(id==='evidence'&&history&&!history.id?.startsWith('causal_')){active=false;panel.hidden=true;E('lxMode').setAttribute('aria-pressed','false');E('lxNetworkMode').setAttribute('aria-pressed','true');}
  showBase(id);document.body.classList.toggle('link-mode',active&&id==='evidence');
  if(id!=='evidence')renderView();
  if(active&&id==='evidence')render();
 };
 function request(){
  const config=Object.fromEntries(fields.map(x=>[x[0],Number(E('lx_'+x[0]).value)]));
  config.fec=Number(E('lxFec').value);config.modem_profile=Number(E('lxProfile').value);
  return {link_id:Number(E('lxLink').value),text:E('lxText').value,frames:Number(E('lxFrames').value),seed:Number(E('lxSeed').value),config};
 }
 function load(p){
  E('lxLink').value=p.link.link_id;E('lxText').value=p.text;E('lxFrames').value=p.frames;E('lxSeed').value=p.seed;
  fields.forEach(x=>E('lx_'+x[0]).value=p.config[x[0]]);E('lxFec').value=p.config.fec;E('lxProfile').value=p.config.modem_profile;
  draft();
 }
 let previewSeq=0;
 async function draft(){
  const seq=++previewSeq;
  try{const p=await api('/api/link/preview',request());if(seq!==previewSeq)return;
   E('lxDraft').textContent=`待应用：${p.link.tx||'地面'} → ${p.link.rx||'地面'}，${p.frames}帧；修改不会改变已经保存的观测。`;
   E('lxDraft').style.color='';
  }catch(e){if(seq!==previewSeq)return;E('lxDraft').textContent=e.message;E('lxDraft').style.color='#ffb0aa';}
 }
 E('lxFields').addEventListener('input',draft);
 function buttons(){
  E('lxFields').disabled=stateBusy||requesting;
  E('lxApply').disabled=stateBusy||!connected||requesting;
  E('lxAbort').disabled=!(stateBusy&&task==='link');
  E('lxReproduce').disabled=stateBusy||!connected||requesting||!E('lxRecords').value;
  E('lxUse').disabled=stateBusy||requesting||!E('lxRecords').value;
  E('lxApply').title=!connected?'先在顶部检查板卡连接':stateBusy?'等待当前任务完成或中止':'在发送前逐项读回确认参数';
 }
 function error(e){E('lxStatus').textContent=e.message;E('lxStatus').classList.add('error');toast(e.message,true);}
 async function run(fn){
  if(requesting)return;requesting=true;buttons();
  try{await fn();}catch(e){error(e);}finally{requesting=false;buttons();}
 }
 E('lxApply').onclick=()=>run(async()=>{
  const d=request();await api('/api/link/preview',d);await api('/api/link/start',d);
  readOnly=false;view=null;frameIndex=-1;render();E('lxStatus').textContent='请求已提交，等待实板写入；尚未确认参数生效。';
 });
 E('lxAbort').onclick=()=>run(()=>api('/api/stop',{}));
 async function refresh(){
  const rows=await api('/api/link/records');const prev=E('lxRecords').value;
  E('lxRecords').innerHTML=rows.length?rows.map(r=>`<option value="${esc(r.id)}">${esc(r.id)} · ${r.plan.link.tx||'地面'}→${r.plan.link.rx||'地面'} · ${r.summary.delivered}/${r.summary.attempts}${r.complete?'':' · 未完成'}</option>`).join(''):'<option value="">尚无记录</option>';
  if(rows.some(r=>r.id===prev))E('lxRecords').value=prev;buttons();
 }
 E('lxRefresh').onclick=()=>run(refresh);E('lxRecords').onchange=buttons;
 E('lxView').onclick=()=>run(async()=>{view=await api('/api/link/record?id='+encodeURIComponent(E('lxRecords').value));readOnly=true;frameIndex=-1;render();});
 E('lxLive').onclick=()=>{view=current;readOnly=false;frameIndex=-1;render();};
 E('lxUse').onclick=()=>run(async()=>{const r=await api('/api/link/record?id='+encodeURIComponent(E('lxRecords').value));load(r.plan);E('lxDraft').textContent+=' 已载入，尚未写入FPGA。';});
 E('lxExport').onclick=()=>run(async()=>{const r=await api('/api/link/export?id='+encodeURIComponent(E('lxRecords').value));E('lxCompareResult').textContent='已导出：'+r.path;});
 E('lxReproduce').onclick=()=>run(async()=>{
  await api('/api/link/reproduce',{id:E('lxRecords').value});readOnly=false;view=null;frameIndex=-1;render();
  E('lxStatus').textContent='已请求按原始字节与噪声种子重新计算；本次会生成新的实板记录。';
 });
 function comparison(c){
  const changed=Object.entries(c.changed_config).map(([k,v])=>`${k}：${v.before} → ${v.after}`).join('；')||'参数未改变';
  const heading=c.exact_measurement_reproduced?'重现一致：字节、I/Q、接收估计及计数均与原记录一致':c.single_setting_comparison?'单设置对照：输入字节、链路和种子一致':c.same_stimulus?'输入一致；请核对变更参数及逐帧结果':'输入条件不同，不作单因素归因';
  const explanation=c.single_setting_comparison&&c.left.delivered===c.right.delivered&&c.left.pre_ber!==c.right.pre_ber?'这组样本的最终交付数相同，但纠错前误码已变化；本次接收与纠错仍保住了正文，不能据此判断信道没有变化。':'交付数代表正文是否完整收到；误码与EVM用于解释接收难度。捕获失败单独计数，不记作零误码。';
  E('lxCompareResult').innerHTML=`<b>${esc(heading)}</b><p>${esc(changed)} · ${c.same_firmware?'固件一致':'固件未证实一致，不能作受控对照'}</p><table><tr><th>本次观测</th><th>所选记录</th><th>当前记录</th></tr>${[['完整交付',`${c.left.delivered}/${c.left.attempts}`,`${c.right.delivered}/${c.right.attempts}`],['交付业务字节',c.left.delivered_payload_bytes,c.right.delivered_payload_bytes],['捕获',c.left.captured,c.right.captured],['纠错前 BER（已捕获帧）',percent(c.left.pre_ber),percent(c.right.pre_ber)],['均衡后参考 EVM',f(c.left.payload_evm_percent)+'%',f(c.right.payload_evm_percent)+'%'],['纠错后 BER（已捕获帧）',percent(c.left.post_ber),percent(c.right.post_ber)]].map(r=>`<tr>${r.map(x=>`<td>${esc(x)}</td>`).join('')}</tr>`).join('')}</table><p>${esc(explanation)}</p><p>${esc(c.caveat)}</p>`;
 }
 E('lxCompare').onclick=()=>run(async()=>{if(!view?.id)throw Error('先采集或查看一个当前观测');comparison(await api('/api/link/compare?left='+encodeURIComponent(E('lxRecords').value)+'&right='+encodeURIComponent(view.id)));});
 E('lxFrame').onchange=()=>{frameIndex=Number(E('lxFrame').value);render();};
 E('lxIqRange').onchange=()=>render();
 function axes(id,xlabel,ylabel,xmin,xmax,ymin,ymax,equal=false){
  const c=E(id),r=c.getBoundingClientRect();if(r.width<20)return null;
  const scale=devicePixelRatio||1;c.width=Math.round(r.width*scale);c.height=Math.round(r.height*scale);
  const g=c.getContext('2d');g.scale(scale,scale);const w=r.width,h=r.height;
  const pw=equal?Math.min(w-80,h-60):w-75,ph=equal?pw:h-60,x=equal?(w-pw)/2:56,y=23;
  g.font='10px Consolas';g.fillStyle='#a6c5d3';g.fillText(ylabel,6,12);
  for(let i=0;i<=4;i++){let py=y+ph-i*ph/4;g.strokeStyle='#244552';g.beginPath();g.moveTo(x,py);g.lineTo(x+pw,py);g.stroke();g.textAlign='right';g.fillText(f(ymin+i*(ymax-ymin)/4,2),x-7,py+3);g.textAlign='center';g.fillText(f(xmin+i*(xmax-xmin)/4,2),x+i*pw/4,y+ph+15);}
  g.textAlign='right';g.fillText(xlabel,w-4,h-3);g.textAlign='left';
  return {g,x,y,pw,ph,xy:(a,b)=>[x+(a-xmin)*pw/(xmax-xmin),y+ph-(b-ymin)*ph/(ymax-ymin)]};
 }
 function chartLine(a,points,color,joined=false){
  if(!a)return;const {g}=a;g.save();g.beginPath();g.rect(a.x,a.y,a.pw,a.ph);g.clip();g.strokeStyle=color;g.fillStyle=color;g.lineWidth=1.5;
  if(joined){g.beginPath();points.forEach((p,i)=>{const v=a.xy(...p);i?g.lineTo(...v):g.moveTo(...v)});g.stroke();}
  else for(const p of points){const v=a.xy(...p);g.beginPath();g.arc(...v,2.2,0,Math.PI*2);g.fill();}
  g.restore();
 }
 function draw(o){
  const channel=o?.channel,st=channel?ChannelMath.statistics(channel):null;
  const pdp=axes('lxPdp','额外时延 / μs','|h|²',0,4,0,1.1);
  if(st&&pdp)for(const [i,p] of st.powers.entries()){const x=i?channel.echo_delay_samples/8:0;chartLine(pdp,[[x,0],[x,p]],i?'#b1a4ff':'#6de7d7',true);chartLine(pdp,[[x,p]],i?'#b1a4ff':'#6de7d7');}
  const cfr=axes('lxCfr','频率 / MHz','幅度 / dB',-4,4,-60,6);
  if(channel)chartLine(cfr,Array.from({length:181},(_,i)=>{const x=-4+i*8/180;return[x,Math.max(-60,20*Math.log10(Math.max(1e-12,ChannelMath.response(channel,x*1e6))))]}),'#6de7d7',true);
  const limit=Number(E('lxIqRange').value);let clipped=0;
  for(const [id,bank] of [['lxBefore','received'],['lxAfter','equalized']]){
   const a=axes(id,'I / 定点码值','Q / 定点码值',-limit,limit,-limit,limit,true);
   clipped+=(o?.iq?.[bank]||[]).filter(p=>p.some(v=>Math.abs(v)>limit)).length;
   if(o?.iq?.[bank]?.length)chartLine(a,o.iq[bank],'#6de7d7');
   else if(a){a.g.fillStyle='#a7bac5';a.g.fillText(o?'本帧没有有效采样':'等待同帧实测',a.x+10,a.y+a.ph/2);}
  }
  E('lxClip').textContent=clipped?`${clipped} 个点超出显示范围，请切换完整码域`:'前后同一坐标范围；保留全部原始样本';
 }
 function render(){
  if(!active||tab!=='evidence')return;
  const r=view,obs=r?.observations||[],idx=frameIndex<0?obs.length-1:Math.min(frameIndex,obs.length-1),o=obs[idx],s=r?.summary;
  panel.dataset.experimentId=r?.id||'';
  panel.dataset.phase=r?.phase||(r?.complete?'complete':'');
  E('lxIdentity').textContent=r?`当前观测记录：${r.id} · 计划 ${r.plan.plan_sha256.slice(0,12)}`:'尚未取得本次观测';
  E('lxSource').textContent=readOnly?'历史实板观测 · 只读':stateBusy&&task==='link'?'实板采集中':r?'最新实板观测':'尚未采集';
  E('sourceLabel').textContent='独立单跳实验 · 参数、I/Q和业务按帧关联；不推进整机网络';
  E('lxFrame').innerHTML=obs.length?obs.map((x,i)=>`<option value="${i}" ${i===idx?'selected':''}>第 ${i+1} 帧 · ${x.delivered?'完整交付':'未交付'}</option>`).join(''):'<option value="">尚无观测</option>';
  const steps=E('lxSteps').children;[!!r,!!o?.config_verified,!!o?.same_frame_verified,!!r?.report?.execution_completed].forEach((v,i)=>steps[i].classList.toggle('done',v));
  if(r){
   const phase=r.phase|| (r.complete?'complete':'error'),names={preparing:'正在检查实板与保存计划',applying:'正在写入参数，尚未确认生效',applied:'本帧全部参数读回一致，即将发送',observed:'已采集并保存本帧',complete:'采集完成；完整与失败结果均已保存',error:'实验未完成',stopped:'已中止；已完成帧保留'};
   E('lxStatus').classList.toggle('error',!!r.failure);
   E('lxStatus').textContent=`${r.plan.link.tx||'地面'} → ${r.plan.link.rx||'地面'} · ${names[phase]||phase} · ${obs.length}/${r.plan.frames} 帧${r.failure?'：'+r.failure.error:''}${o?`。当前显示第 ${idx+1} 帧，采样帧号 ${o.generation}；正文与前后I/Q关联一致。`:''}`;
  }
  const c=o?.channel;
  E('lxReadback').innerHTML=o?[['主径幅度',f(c.gain0,6)],['噪声σ',f(c.sigma,0)],['主径延时',c.delay_samples+' 样点'],['实际频偏',f(c.cfo_hz,2)+' Hz'],['回波幅度',f(c.gain1,6)],['回波额外延时',c.echo_delay_samples+' 样点'],['前后采样',o.sample_count+' 对'],['配置核对','全部寄存器读回一致']].map(([k,v])=>`<div>${k}<b>${esc(v)}</b></div>`).join(''):'';
  E('lxMetrics').innerHTML=s?[['本次完整交付',`${s.delivered}/${s.attempts}`],['本次捕获',`${s.captured}/${s.attempts}`],['有效业务字节',s.delivered_payload_bytes],['本次失败帧',s.failed]].map(([k,v])=>`<div><span>${k}</span><b>${esc(v)}</b></div>`).join(''):'';
  if(o){
   const evm=o.phy.evm_symbols?100*Math.sqrt(o.phy.evm_error_sum/(o.phy.evm_symbols*8192**2)):null;
   const estimate=o.phy.timing_updates?o.phy.cfo_phase_step*8e6/2**32:null;
   E('lxBusiness').innerHTML=`<b>${o.delivered?'本帧业务已完整交付':'本帧业务没有交付'}</b><p>发送：${esc(r.plan.text)}</p><pre>${o.delivered?esc(o.received_text):'未交付错误正文'}</pre><p>${o.delivered?`96字节帧与独立CRC核验一致，接收 ${o.payload_bytes} 个有效业务字节。`:o.failure_stage==='frame_capture'?'PN帧头未捕获；本帧计入失败，不能用零误码率表示成功。':'已捕获，但接收／译码／CRC未通过；保留失败结果。'}</p><p>接收估计频偏 ${f(estimate,2)} Hz · 均衡后参考 EVM ${f(evm,2)}%<br>纠错前 BER ${o.captured&&o.phy.pre_bits?percent(o.phy.pre_errors/o.phy.pre_bits):'—'} → 纠错后 BER ${o.captured&&o.phy.post_bits?percent(o.phy.post_errors/o.phy.post_bits):'—（无有效位数）'}</p><p class="lx-hint">这是该逻辑边上的单跳载荷核验，未执行中继、ACK或节点业务状态机。${s.attempts}帧结果不足以证明长期可靠率。</p>`;
  }else E('lxBusiness').innerHTML='<b>这一跳实际交付了什么？</b><p>本次还没有完整观测；不沿用上一实验的正文。</p>';
  draw(o);buttons();
 }
 let refreshing=false;
 async function pollLink(){
  try{
   const d=await api('/api/link/state');connected=d.connected;stateBusy=d.busy;task=d.task;
   const next=d.experiment,key=next?`${next.id}:${next.updated_at}`:'';
   if(key!==lastKey){lastKey=key;const was=current?.id;current=next;
    if(!readOnly){view=next;if(was!==next?.id)frameIndex=-1;render();}
    if(next?.phase==='complete'&&!refreshing){refreshing=true;try{await refresh();if(next.report?.reproduction)comparison(next.report.reproduction);}finally{refreshing=false;}}
   }
   buttons();
  }catch(e){connected=false;buttons();if(active){E('lxStatus').textContent='无法获取显控服务状态：'+e.message;E('lxStatus').classList.add('error');}}
  setTimeout(pollLink,700);
 }
 const base=window.renderWorkbench;
 window.renderWorkbench=()=>{base();if(active)render();};
 window.setLinkExperimentMode=mode;
 window.addEventListener('resize',()=>render());
 refresh().catch(error);draft();pollLink();
 if(location.hash==='#link')mode(true);
})();
