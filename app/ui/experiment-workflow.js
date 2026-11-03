/* Question, command, and comparison all retain a verifiable experiment identity. */
(()=>{
 const E=id=>document.getElementById(id);let asking=false,lastJob=null,rows=[];
 const context=()=>window.actionContext?{...window.actionContext}:{record_id:history?.id||S.network_record_id,mode:history?'history':'current',model_ms:V.snapshot?.round*100,link:Number(E('linkSelect').value)};
 function relevant(job){const c=context();return c.record_id===job.record_id&&c.mode===job.context.mode&&c.model_ms===job.as_of_model_ms&&c.link===job.context.link;}
 function showAnswer(job,response,pending){
  lastJob=job;E('answer').replaceChildren();const title=document.createElement('p');title.className='wf-context';
  title.textContent=`${job.context.mode==='history'?'历史只读':'提问时刻'} · ${job.record_id} · ${job.as_of_model_ms/1000}s · 链路 ${job.context.link}${relevant(job)?'':' · 页面已前进或切换，请勿作为当前状态'}`;E('answer').append(title);
  E('assistantStatus').textContent=pending?'规则结论已就绪 · 本地模型正在筛选依据，不阻塞实验':response.model_used?'本地模型已参与证据筛选 · 数值与操作范围来自实板记录':'规则分析 · 本次未使用大模型';
  const text=document.createElement('p');text.textContent=response.answer;E('answer').append(text);
  for(const item of response.evidence||[]){if(!item.action)continue;const b=document.createElement('button');b.className='wide wf-proposal';b.textContent=`核对${commandName(item.action.opcode)} → 节点 ${item.action.target} · 参数 ${item.action.value}`;
   b.disabled=job.context.mode==='history';b.onclick=async()=>{try{if(!relevant(job))throw Error('页面时刻或链路已变化，请重新分析当前数据');const p=await api('/api/assistant/prepare',{id:job.id,evidence_id:item.id});prepareCommand(p.action);}catch(e){toast(e.message,true);}};E('answer').append(b);
  }
 }
 window.runExperimentAssistant=async()=>{
  if(asking)return;asking=true;E('ask').disabled=true;
  try{
   const c=context();if(!c.record_id||c.model_ms==null)throw Error('先运行实验或选择一条历史记录');
   const f=E('attachment')?.files?.[0];if(f&&f.size>128000)throw Error('请使用不超过128KB的小段文字资料');
   let job=await api('/api/assistant',{question:E('question').value,attachment:f?await f.text():'',context:c});
   showAnswer(job,job.provisional,true);
   for(let i=0;job.status==='working'&&i<90;i++){await new Promise(r=>setTimeout(r,500));job=await api('/api/assistant/job?id='+job.id);}
   if(job.status==='complete')showAnswer(job,job.result,false);
   else E('assistantStatus').textContent='规则结论保留；模型未及时完成，请稍后重新分析';
  }finally{asking=false;updateButtons();}
 };
 const weatherScope=document.createElement('p');weatherScope.className='weather-scope';weatherScope.id='weatherScope';document.querySelector('.mapPanel').append(weatherScope);
 const oldButtons=updateButtons;updateButtons=()=>{oldButtons();E('ask').disabled=asking||!!S.assistant_busy||!V.snapshot;};
 const boundary=document.createElement('div');boundary.className='wf-boundary';boundary.id='taskBoundary';boundary.innerHTML='<p>链路与措施任务固定几何条件；模拟高度调整请在结束后进入整机模式，选择非X形编队。高度变化不保证链路一定改善。</p><button id="openHeightTask">进入整机高度实验设置</button>';
 E('controlDetails').after(boundary);
 E('openHeightTask').onclick=()=>{if(S.busy){toast('先结束或中止当前实验，已采集数据会保留',true);return;}stopReplay();history=null;E('lxNetworkMode').click();showTab('mission');E('formation').value='4';E('formation').dispatchEvent(new Event('change',{bubbles:true}));E('commandOp').value='5';commandInput();E('controlDetails').open=true;toast('已打开整机模式：确认配置并开始实验后，再发送模拟高度指令');};
 const card=document.createElement('section');card.id='workflowComparison';card.className='panel';card.innerHTML=`<h2>比较两次完整实验</h2><p class="hint">先选基线，再只改一个设置。显示配置、固件、动作时间线差异；不把多个条件变化包装成单因素改善。</p><div class="two"><label>基线 A<select id="wfLeft"></select></label><label>实验 B<select id="wfRight"></select></label></div><div class="two"><button id="wfRefresh">刷新全部记录</button><button id="wfCompare" class="primary">比较并保存结果</button></div><div id="wfComparison" role="status"></div><details><summary>从基线创建“只改一个设置”的下一轮</summary><p class="hint">仅适用于无用户干预的完整链路实验；保持种子、链路、时长和其他配置不变。开始后先观察10秒，再运行到结束。</p><div class="two"><label>改变的设置<select id="wfField"><option value="weather">天气预设</option><option value="environment">场景预设</option><option value="formation">编队形状</option><option value="reference_snr_cdb">参考SNR</option><option value="jitter_percent">起伏尺度</option></select></label><label>新取值<select id="wfValue"></select></label></div><button id="wfVariant">核对下一轮设置</button></details>`;
 E('history').append(card);E('compare').closest('.panel').hidden=true;
 const dlg=document.createElement('dialog');dlg.className='wf-dialog';dlg.id='wfVariantDialog';dlg.innerHTML='<h2>确认单设置对照</h2><p id="wfVariantText"></p><div class="two"><button id="wfCancel">取消</button><button id="wfVariantConfirm">开始新实板实验</button></div>';document.body.append(dlg);let variant=null;
 const fmt=(k,v)=>k==='pre_ber'?(v==null?'—':v===0?'0':v.toExponential(3)):['delivery','timely_delivery'].includes(k)?pct(v):num(v,2);
 const names={delivery:'最终送达比例',timely_delivery:'按时送达比例',p95_upper_ms:'P95时延上界 / ms',max_ms:'最大时延 / ms',mean_ms:'平均时延 / ms',payload_bps:'有效业务吞吐 / bit/s',wall_seconds:'电脑总耗时 / s',pending:'结束时待转发 / 帧',heartbeat_received:'地面实收心跳 / 条',media_received_bytes:'媒体实收 / 字节',pre_ber:'纠错前编码位BER',evm_percent:'均衡后参考EVM / %'};
 async function refresh(){rows=await api('/api/experiments');for(const id of ['wfLeft','wfRight']){const prev=E(id).value;E(id).innerHTML=rows.filter(r=>r.complete).map(r=>`<option value="${esc(r.id)}">${esc(r.id)} · ${r.seconds}s · ${r.kind==='causal'?'链路任务':'整机任务'}${r.has_actions?' · 含措施':''}${r.previous_version?' · 上一版记录':''}</option>`).join('');if(rows.some(r=>r.id===prev))E(id).value=prev;}if(E('wfRight').value===E('wfLeft').value&&E('wfRight').options.length>1)E('wfRight').selectedIndex=1;}
 E('wfRefresh').onclick=()=>refresh().catch(e=>toast(e.message,true));
 E('wfCompare').onclick=async()=>{try{const a=E('wfLeft').value,b=E('wfRight').value;if(!a||!b)throw Error('请先完成两次实验');if(a===b)throw Error('请选择两条不同记录');const r=await api(`/api/experiments/compare?left=${encodeURIComponent(a)}&right=${encodeURIComponent(b)}&save=1`);window.lastWorkflowComparison=r;
  E('wfComparison').innerHTML=`<h3>${esc(r.label)}</h3><p>${esc(r.reasons.join('；'))} ${esc(r.preset_note)}</p><p>改变配置：${esc(JSON.stringify(r.changed_config))}</p><details><summary>固定条件差异与版本</summary><pre>${esc(JSON.stringify(r.changed_conditions,null,2))}</pre></details><div class="tablewrap"><table><tr><th>指标</th><th>A</th><th>B</th><th>B−A</th></tr>${Object.keys(names).map(k=>`<tr><td>${names[k]}</td><td>${fmt(k,r.left[k])}</td><td>${fmt(k,r.right[k])}</td><td>${fmt(k,r.delta[k])}</td></tr>`).join('')}</table></div><details><summary>所选链路最近DATA帧的实际参数</summary><p>分别读回各自最近发送帧，不将不同序号的帧当作同帧比较。</p><pre>A：${esc(JSON.stringify(r.left_channel_sample,null,2))}\nB：${esc(JSON.stringify(r.right_channel_sample,null,2))}</pre></details><p>${esc(r.qualification)}</p><small>已保存：${esc(r.saved_path)}</small>`;
 }catch(e){E('wfComparison').textContent=e.message;toast(e.message,true);}};
 function values(){if(!catalog)return;const k=E('wfField').value,opts=catalog[k]||({reference_snr_cdb:[18,26,34,40,45].map(v=>({id:v*100,name:v+' dB'})),jitter_percent:[0,50,100,150,200].map(v=>({id:v,name:v+'%'}))})[k];E('wfValue').innerHTML=opts.map(o=>`<option value="${o.id}">${esc(o.name)}</option>`).join('');}
 E('wfField').onchange=values;E('wfCancel').onclick=()=>dlg.close();
 E('wfVariant').onclick=()=>{const a=rows.find(r=>r.id===E('wfLeft').value);if(!a||a.kind!=='causal'||a.has_actions){toast('请选择无用户干预的完整链路基线',true);return;}if(S.busy){toast('请先结束当前实板任务',true);return;}variant={id:a.id,field:E('wfField').value,value:+E('wfValue').value};E('wfVariantText').textContent=`基线 ${a.id}，链路 ${a.link+1}→${a.link%4===3?'地面':a.link+2}，种子 ${a.seed}，时长 ${a.seconds}s。只把 ${E('wfField').selectedOptions[0].text} 从 ${a.config[variant.field]} 改为 ${E('wfValue').selectedOptions[0].text}；结果由实板决定。`;dlg.showModal();};
 E('wfVariantConfirm').onclick=async()=>{try{await api('/api/experiments/variant',variant);dlg.close();window.openCausalLive();}catch(e){toast(e.message,true);}};
 const oldTab=showTab;showTab=id=>{oldTab(id);if(id==='history'){values();refresh().catch(e=>toast(e.message,true));}};
 setInterval(()=>{const cfg=V.snapshot?.config||preview?.config;if(cfg){
  const ch=cfg.channel||{},terrain=ch.mode===1&&ch.reserved0;
  const weather=ch.mode===2?'自主抽头模式：天气不改变信道；AWGN由用户SNR控制。':ch.mode===1?'场景模式：雨衰依据载波与降雨强度计算；各场景的抽头、损耗与运动共同作用。':'旧版二径：天气使用等效附加损耗；保留基准回归口径。';
  weatherScope.textContent=`${catalog?.weather[cfg.weather]?.name||''} · ${weather} ${terrain?'程序地形参与单主导障碍绕射，不含建筑射线追踪与避障。':'地形遮挡关闭，地表仅辅助空间展示。'}`;
 }boundary.hidden=!window.actionContext;E('openHeightTask').disabled=!!S.busy;if(lastJob&&E('answer').firstChild){E('answer').firstChild.classList.toggle('stale-answer',!relevant(lastJob));E('answer').querySelectorAll('.wf-proposal').forEach(b=>b.disabled=!relevant(lastJob)||lastJob.context.mode==='history');}},500);
})();

window.drawWorkflowWeather=(g,w,h,weather,t)=>{
 if(!weather)return;g.save();g.fillStyle=weather===1?'#bfd1d71a':'#99bad808';g.fillRect(0,0,w,h);
 if(weather>=2){g.strokeStyle=weather>=5?'#dfedff44':'#9ec7e840';g.lineWidth=1;const count=[0,0,24,38,60,24,38,60][weather];for(let i=0;i<count;i++){const x=(i*137+23)%w,y=(i*79+47+t*5)%h;g.beginPath();if(weather>=5)g.arc(x,y,1.2,0,Math.PI*2);else{g.moveTo(x,y);g.lineTo(x-3,y+8);}g.stroke();}}g.restore();
};
