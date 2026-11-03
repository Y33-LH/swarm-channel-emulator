/* Instrument workspace: keep real controls/listeners; secondary tools open
 * explicit dialogs rather than being clipped below a fixed-height column. */
(() => {
 'use strict';
 const E=id=>document.getElementById(id);
 const left=document.querySelector('.param-rail:not(.right)'),right=document.querySelector('.param-rail.right');
 const blocks=[...document.querySelectorAll('.panel.rail-block')];
 const find=s=>blocks.find(b=>b.querySelector('h3')?.textContent.includes(s));
 function dialog(title,items){
  const d=document.createElement('dialog');d.className='instrument-details';
  const head=document.createElement('div');head.className='dialog-heading';
  const h=document.createElement('h2');h.textContent=title;const close=document.createElement('button');close.textContent='关闭 ×';close.onclick=()=>d.close();
  head.append(h,close);d.append(head);const body=document.createElement('div');body.className='instrument-details-body';
  items.filter(Boolean).forEach(b=>body.append(b));d.append(body);document.body.append(d);
  const b=document.createElement('button');b.type='button';b.textContent=title+' ↗';b.onclick=()=>{d.showModal();window.renderInstruments?.();};return {button:b,dialog:d};
 }
 const command=document.createElement('div');command.id='experimentCommands';
 const label=document.createElement('strong');label.textContent='实验控制';command.append(label);
 E('start').textContent='▶ 开始实板实验';
 for(const id of ['start','pause','resume','stop'])command.append(E(id));
 const configDialog=dialog('运行配置 / 保存载入',[document.querySelector('.setup')]);
 E('demoStart').textContent='按当前配置开始任务引导（持续运行）';
 command.append(configDialog.button);
 command.append(E('returnLive'));
 const applyDraft=document.createElement('button');applyDraft.type='button';applyDraft.id='applyPreparedConfig';
 applyDraft.textContent='结束本轮并应用参数';applyDraft.hidden=true;command.append(applyDraft);
 let applying=false;
 applyDraft.onclick=async()=>{
  if(applying||history||S.recomputing)return;
  await previewConfig();if(!validConfig)return;
  const request={seconds:Number(E('seconds').value),ideal:Number(E('ideal').value),seed:Number(E('seed').value),config:readConfig(),telemetry_rounds:Number(E('telemetry').value)};
  applying=true;applyDraft.disabled=true;
  try{
   toast('正在保存本轮结果；结束后以新参数建立一条独立实验记录。');
   await api('/api/stop',{});
   const deadline=Date.now()+120000;
   while(true){const st=await api('/api/state');if(!st.busy){if(st.error)throw Error(st.error);break;}if(Date.now()>deadline)throw Error('上一轮尚未完成保存；未开始新实验，请检查当前状态。');await new Promise(r=>setTimeout(r,500));}
   await launchNetwork(request);toast('已开始新参数实验。上一轮结果已单独保存，可在回放页对照。');
  }catch(e){toast(e.message,true);}finally{applying=false;update();}
 };
 const connection=document.createElement('span');connection.className='command-connection';
 connection.append(E('port'),E('connect'),E('program'));command.append(connection);
 document.querySelector('.topbar').after(command);
 const status=document.createElement('div');status.id='workspaceStatus';status.setAttribute('role','status');command.after(status);
 // Context and link selection are common to all plots, always visible.
 const context=document.createElement('div');context.id='frameContext';
 const linkLabel=document.createElement('label');linkLabel.textContent='观测链路';linkLabel.append(E('linkSelect'));context.append(linkLabel);
 const identity=document.createElement('span');identity.id='observationIdentity';context.append(identity);
 document.querySelector('.p1-center').prepend(context);
 const channel=find('信道设置');channel.classList.add('channel-primary');
 const chExtras=dialog('信道详细参数 / 模型边界',[find('路由选择'),find('信道档案'),find('信道统计'),E('channelFixed'),E('customGeometry')]);
 channel.querySelectorAll('.rail-input').forEach(l=>{const text=document.createElement('span');[...l.childNodes].filter(n=>n.nodeType===3||n.nodeName==='SUB').forEach(n=>text.append(n));l.prepend(text);});
 const sceneOriginal=find('场景选择');
 const sceneDetails=dialog('图形选项与几何配置',[sceneOriginal]);
 const scene=document.createElement('div');scene.className='panel scene-primary';scene.innerHTML='<h3>场景与编队</h3>';
 for(const [id,name] of [['environment','环境'],['weather','天气'],['formation','编队']]){
  const l=document.createElement('label');l.className='rail-input';l.append(name);const field=E(id);field.hidden=false;l.append(field);scene.append(l);
  field.addEventListener('change',()=>{previewConfig();window.syncChoices?.();});
 }
 const actions=document.createElement('div');actions.className='rail-actions';actions.append(sceneDetails.button,chExtras.button);scene.append(actions);
 left.replaceChildren(channel,scene,find('蜂群态势速览'));
 const modem=find('调制解调链');modem.classList.add('modem-primary');
 const rx=find('物理层实况');rx.classList.add('receiver-primary');
 const linkReadback=find('选中链路'),windowStats=find('本窗口实测');
 rx.querySelector('h3').textContent='接收实况 · 最近一帧';
 windowStats.querySelector('h3').textContent='逐跳统计 · 时间窗口';

 right.replaceChildren(modem,rx,windowStats,linkReadback);
 right.setAttribute('aria-label','调制解调与接收参数滚动栏');
 // Always retain all values; compact summary rows are duplicated read-only in
 // details only where necessary, never counterfeit input controls.
 const info=document.createElement('p');info.className='workspace-contract';info.textContent='输入 → 板卡实际读回 → 同帧接收观测 → 业务影响 → 保存重现';
 document.querySelector('.p1-center').append(info);
 const update=()=>{
  const o=window.frameObservation?.(),s=V?.snapshot;
  syncTxRx();
  status.classList.toggle('failed',!!S.error||pollFailed||(!history&&!validConfig&&!!E('configError').textContent));
  status.textContent=pollFailed?'显控服务未连接，当前显示的结果不会继续更新':S.error?'操作未完成：'+S.error:history?'只读回放 · '+history.id:taskStatus(S)+' · '+(S.connected?'板卡已检查':'请先检查连接')+' · '+(S.network_record_id||'尚未建立实验记录');
  const dirty=!!(S.snapshot&&S.config_sha256&&preview?.config_sha256&&S.config_sha256!==preview.config_sha256);
  for(const id of ['snr','jitter_percent','environment','weather','formation'])E(id).disabled=!!history;
  if(!history&&dirty)status.textContent+=' · 编辑参数尚未生效；图表仍对应原参数';
  if(!history&&!validConfig&&E('configError').textContent)status.textContent='参数未通过：'+E('configError').textContent;
  for(const id of ['customMode','presetBaseline','presetHarsh','presetSevere'])E(id).disabled=!!history;
  applyDraft.hidden=!!history||!dirty||!S.busy||S.task!=='network'||!!S.recomputing;
  applyDraft.disabled=applying||!validConfig;
  status.title=status.textContent;
  identity.textContent=o?`DATA #${o.generation} · 模型 ${(o.model_ms/1000).toFixed(3)} s · 距当前 ${(o.age_ms/1000).toFixed(1)} s · ${o.crc_good?'CRC 通过':'未正确接收'}`:s?'等待所选链路的同帧 DATA 样本':'尚未运行 · 输入参数后开始实板实验';
  identity.title=`记录 ${history?.id||S.network_record_id||'未建立'} / 配置 ${s?.config_id??'—'}`;
 };
 // Status is shared by all pages; graph painting is only active on page one.
 // Polling must still update completion/error/config state on the map/history.
 window.updateWorkspaceStatus=update;
 const previous=window.renderInstruments;window.renderInstruments=()=>{previous?.();update();};update();
})();
