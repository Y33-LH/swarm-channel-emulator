/* One selected experiment/time/link drives the three pages. No synthesized execution. */
(()=>{
 const E=id=>document.getElementById(id);
 const block=document.createElement('section');block.id='actionWorkspace';block.className='cx-card';
 block.innerHTML=`<h3>采取措施 → 确认执行 → 比较实际效果</h3><p class="cx-note">下行指令经过 FPGA 逐跳传给节点，执行回执再返回地面。查询状态只用于诊断；限速会延长媒体完成时间。</p>
 <div id="actionAdvice"></div><fieldset id="actionFields"><div class="action-fields">
 <label>目标节点<select id="actionTarget">${Array.from({length:16},(_,i)=>`<option value="${i+1}">节点 ${i+1}${[9,13].includes(i+1)?' · FPGA端点':''}</option>`).join('')}</select></label>
 <label>操作<select id="actionOp"><option value="4">媒体生成速率</option><option value="3">媒体暂停 / 恢复</option><option value="2">心跳周期</option><option value="1">查询节点状态</option></select></label>
 <label>参数<input id="actionValue" type="number" value="1" min="1" max="5" step="1"></label>
 </div><p id="actionHelp" class="cx-note"></p><button id="actionPrepare" class="primary">核对并发送节点指令</button></fieldset>
 <p id="actionMessage" role="status"></p><div id="actionResults"></div>`;
 E('cxBusiness').closest('section').after(block);
 const dialog=document.createElement('dialog');dialog.id='actionDialog';dialog.innerHTML='<h2>确认本次措施</h2><div id="actionConfirmText"></div><div class="two"><button id="actionCancel">取消</button><button id="actionConfirm" class="primary">确认发送</button></div>';document.body.append(dialog);
 const strip=document.createElement('div');strip.id='sharedContext';strip.innerHTML='<b>同一次实验 · 同一观测时刻</b><span id="sharedIdentity">尚无实板观测</span><div><button data-jump="evidence">信道与接收</button><button data-jump="action">采取措施</button><button data-jump="mission">节点与业务</button><button data-jump="history">保存与重现</button></div>';E('sourcebar').after(strip);
 const archive=E('cxRecords').closest('section');archive.id='actionArchive';E('history').prepend(archive);
 let input=null,data=null,serial=0,pending=null,submitting=false,identity='';
 window.actionContext=null;
 const live=()=>input?.active&&input.view&&!input.history&&['waiting','running'].includes(input.view.phase)&&!input.view.replaying&&!submitting;
 function help(){const op=+E('actionOp').value,v=E('actionValue');const q={1:[0,0,0,1,'无参数；只返回当前状态，不改变业务。'],2:[100,10000,2000,100,'毫秒；观察收到的新心跳次数及位置年龄。'],3:[0,1,1,1,'1暂停、0恢复；仅节点1语音、节点5视频有效，已经排队的分片仍会传输。'],4:[1,5,1,1,'每模型秒生成1–5个64字节分片；仅节点1语音、节点5视频有效。']}[op];[v.min,v.max,v.value,v.step]=q.slice(0,4);v.disabled=op===1;E('actionHelp').textContent=q[4];}
 E('actionOp').onchange=help;help();
 function prepare(a){if(!live()||!data?.context){toast('请在当前实验观测暂停后操作；历史记录不可发送',true);return;}
  pending={...a,id:input.view.id,observed_round:data.snapshot.round};
  E('actionConfirmText').textContent=`实验 ${pending.id}，观测 ${data.context.model_ms/1000} 秒。${a.kind==='command'?`节点 ${a.command.target}，${({1:'查询状态',2:'心跳周期(ms)',3:'媒体暂停(1)/恢复(0)',4:'媒体速率(片/秒)'})[a.command.opcode]} = ${a.command.value}`:'恢复当前场景信道条件'}。执行后观察 ${a.window_s} 模型秒；发送入队不代表执行成功。`;
  dialog.showModal();
 }
 E('actionPrepare').onclick=()=>prepare({kind:'command',window_s:10,command:{target:+E('actionTarget').value,opcode:+E('actionOp').value,value:+E('actionValue').value,ttl_ms:10000}});
 E('actionCancel').onclick=()=>dialog.close();
 E('actionConfirm').onclick=async()=>{if(submitting)return;submitting=true;E('actionConfirm').disabled=true;try{await api('/api/causal/action',pending);dialog.close();E('actionMessage').textContent='电脑已入队。继续观察下行接收、执行回执与业务变化。';}catch(e){E('actionMessage').textContent=e.message;toast(e.message,true);}finally{submitting=false;E('actionConfirm').disabled=false;}};
 function adviceHTML(rows){return rows.map((a,i)=>`<article class="action-advice"><h4>${esc(a.title)}</h4><p>${esc(a.advice)}</p><small>${esc(a.effect)}<br>依据：${data.context.model_ms/1000}s · 所选链路失败 ${a.evidence.failed_frames}/${a.evidence.attempts} 次 · 网络积压 ${a.evidence.network_pending} 帧</small>${a.action?`<button data-action-proposal="${i}" ${live()?'':'disabled'}>核对这项措施</button>`:''}</article>`).join('');}
 function bindAdvice(container,rows){container.innerHTML=adviceHTML(rows);container.querySelectorAll('[data-action-proposal]').forEach(b=>b.onclick=()=>prepare(rows[+b.dataset.actionProposal].action));}
 function resultsHTML(rows){return rows.map(c=>`<article class="action-result"><div class="action-result-title"><b>#${c.id} · 节点 ${c.target} · ${esc(c.operation)}</b><span>${({confirmed:'执行回执已收到',in_transit:'等待执行回执',unconfirmed:'超过有效期 · 尚未确认',expired:'节点拒绝：已过期',rejected:'节点拒绝执行'})[c.status]}</span></div>
 <div class="action-stages"><span>① 地面入队<br><b>${c.issued_ms/1000}s</b></span><span>② 目标接收槽（诊断）<br><b>${c.node_received_ms==null?'尚无证据':c.node_received_ms/1000+'s'}</b></span><span>③ 地面收到执行回执<br><b>${c.confirmed_ms==null?'尚未收到':c.confirmed_ms/1000+'s'}</b></span><span>④ 业务观测<br><b>${c.after?'已有执行后窗口':'等待至少5秒'}</b></span></div>
 <p>${esc(c.explanation)}</p>${c.downlink_route?`<small>下行：${c.downlink_route.map(x=>x||'地面').join(' → ')}；回执：${c.receipt_route.map(x=>x||'地面').join(' → ')}</small><br>`:''}${c.readback?`<small>回执参数：心跳 ${c.readback.heartbeat_ms}ms · 媒体 ${c.readback.media_paused?'暂停':'运行'} · ${c.readback.media_rate}片/秒</small>`:''}
 ${c.before&&c.after?`<table class="action-metrics"><thead><tr><th>同长度窗口</th><th>操作前 ${c.before.start_ms/1000}–${c.before.end_ms/1000}s</th><th>回执后 ${c.after.start_ms/1000}–${c.after.end_ms/1000}s</th></tr></thead><tbody>${[['源端新媒体 / 片每秒','generated_fragments_per_s'],['地面收媒体 / 字节每秒','received_bytes_per_s'],['地面新增心跳 / 条','heartbeat_updates'],['最新位置年龄 / ms','latest_position_age_ms'],['网络积压 / 帧','pending_end']].map(([n,k])=>`<tr><td>${n}</td><td>${c.before[k]??'不适用'}</td><td>${c.after[k]??'不适用'}</td></tr>`).join('')}</tbody></table>`:''}</article>`).join('')||'<p class="cx-note">尚未发送节点措施。完成基线后，可以先验证媒体速率调整。</p>';}
 function compactCommands(){const rows=(data?.commands||[]).filter(x=>x.target===selected);E('commandStatus').innerHTML=rows.map(c=>`<article class="action-advice"><b>#${c.id} · ${esc(c.operation)}</b><p>${c.status==='confirmed'?'已收到执行回执 · '+c.confirmed_ms/1000+'s':'尚未确认执行'}</p><small>${esc(c.explanation)}</small><button class="action-detail">查看信道页的前后对比</button></article>`).join('');E('commandStatus').querySelectorAll('.action-detail').forEach(b=>b.onclick=()=>{showTab('evidence');block.scrollIntoView({behavior:'smooth',block:'start'});});}
 function decorate(){if(!input?.active)return;
  document.body.classList.add('shared-experiment');strip.hidden=false;
  E('actionFields').disabled=!live();
  E('actionAvailability')&&(E('actionAvailability').textContent=live()?'现在可操作：确认后自动观察 10 模型秒，再核对回执与前后变化。':input.history?'历史记录只读，不能向当前板卡发送指令。':input.view?.phase==='complete'?'实验已结束。查看已有执行记录，或开始新实验后采取措施。':'需等待本轮观察结束；此时的模型时间暂停，才能安全提交下一项措施。');
  if(!data?.context){E('sharedIdentity').textContent='尚无实板观测';return;}
  const c=data.context;window.actionContext=c;
  E('sharedIdentity').textContent=`${c.mode==='history'?'历史只读':'当前实板'} · ${c.record_id} · ${c.model_ms/1000}s · ${c.link+1}→${c.link%4===3?'地面':c.link+2}${c.frame_ms!=null?' · 同帧采样 '+c.frame_ms/1000+'s':''}`;
  document.querySelectorAll('.page').forEach(p=>{p.dataset.experiment=c.record_id;p.dataset.modelMs=c.model_ms;p.dataset.link=c.link;});
  E('linkSelect').value=String(c.link);E('linkSelect').disabled=true;
  E('sourceLabel').textContent=`${c.mode==='history'?'历史只读':'当前实板'} · ${c.record_id} · ${c.model_ms/1000}s`;E('returnLive').hidden=true;E('replayControls').hidden=true;
  E('actionResults').innerHTML=resultsHTML(data.commands||[]);bindAdvice(E('actionAdvice'),data.recommendations||[]);bindAdvice(E('advice'),data.recommendations||[]);
  compactCommands();
  E('sendCommand').disabled=!live();
 }
 const oldRender=render,oldRenderView=renderView,oldPrepare=prepareCommand,oldButtons=updateButtons,oldNode=renderNode;
 updateButtons=()=>{oldButtons();if(input?.active){E('sendCommand').disabled=!live();E('configFields').disabled=true;E('signalControls').disabled=true;E('commandOp').querySelector('option[value="5"]').disabled=true;}else E('commandOp').querySelector('option[value="5"]').disabled=false;};
 renderNode=()=>{oldNode();if(input?.active&&data?.context)compactCommands();};
 prepareCommand=a=>{if(input?.active)prepare({kind:'command',window_s:10,command:a});else oldPrepare(a);};
 render=()=>{if(input?.active&&data?.context){V=data;renderView();}else oldRender();};
 renderView=()=>{if(input?.active&&data?.context)V=data;oldRenderView();decorate();};
 window.setActionContext=async value=>{
  input=value;
  if(!input.active){++serial;document.body.classList.remove('shared-experiment');strip.hidden=true;window.actionContext=null;E('linkSelect').disabled=false;data=null;identity='';return;}
  const view=input.view,key=(view?.id||'')+':'+(view?.latest?.round||0)+':'+(input.history?'H':'C');
  if(key===identity){decorate();return;}identity=key;const ticket=++serial;
  try{
   const query=input.history?'?id='+encodeURIComponent(view.id)+'&index='+(input.trace.length-1):'';
   const next=await api('/api/causal/context'+query);if(ticket!==serial||!input?.active)return;
   if(next.context&&next.context.record_id!==view?.id)return;
   const changed=data?.context?.record_id!==next.context?.record_id;data=next;
   if(changed&&data.context){selected=data.context.link+1;E('actionTarget').value=String(Math.floor(data.context.link/4)*4+1);setConfig(data.snapshot.config);E('seconds').value=String(data.snapshot.duration_s);}
   if(input.history){history={id:view.id,report:data.report,snapshots:input.trace};}else if(history?.id?.startsWith('causal_'))history=null;
   if(data.context){V=data;if(!input.history){S.report=data.report;S.network_record_id=data.context.record_id;}}
   renderView();
  }catch(e){E('sharedIdentity').textContent='观测暂不可用：'+e.message;}
 };
 strip.querySelectorAll('[data-jump]').forEach(b=>b.onclick=()=>{if(b.dataset.jump==='action'){showTab('evidence');block.scrollIntoView({behavior:'smooth',block:'start'});}else showTab(b.dataset.jump);});
 window.addEventListener('resize',decorate);strip.hidden=true;
})();
