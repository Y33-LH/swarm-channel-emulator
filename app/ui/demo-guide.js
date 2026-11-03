/* User-driven guide. No scripted outcomes, page switching or time limit. */
(() => {
 'use strict';
 const E=id=>document.getElementById(id);
 let active=false,stage=0;
 const steps=[
  ['建立基线','evidence','先观察所选链路的实际抽头、接收星座、CRC 与逐跳确认；再到态势页核对心跳和收到的文件。'],
  ['观察传播变化','evidence','观察节点运动期间所选链路的增益、噪声和逐跳送达率。'],
  ['采取节点措施','mission','选择受影响节点，发送媒体限速、暂停或心跳调整。等待地面执行回执，再核对实际生成速率、位置年龄和积压；限速不能消除噪声。'],
  ['恢复并核对业务','mission','查看态势播报和位置时效。随后检查新产生的心跳、逐窗成功率和后续完整片段。恢复不会补造已经丢失的数据。'],
  ['保存并重现','history','手动中止本轮，等待结果保存。在回放页载入这条记录；回放只读，按原操作重新上板计算才是重新实验。']
 ];
 const dialog=document.createElement('dialog');dialog.className='instrument-details';dialog.id='taskGuide';
 dialog.innerHTML='<div class="dialog-heading"><h2>一条实验主线 · 由你推进</h2><button id="taskGuideClose">关闭 ×</button></div><div class="instrument-details-body"><div id="taskGuideSteps" class="rail-actions"></div><h3 id="taskGuideTitle"></h3><p id="taskGuideInstruction"></p><p id="taskGuideObserved" role="status"></p><div class="rail-actions"><button id="taskGuideGo">前往此步骤</button><button id="taskGuideExit">退出任务引导（实验继续）</button></div><p class="hint">每个阶段多久、是否继续，都由用户决定。引导不生成数据、不代替判断，也不会自动改变链路或宣布恢复。</p></div>';
 document.body.append(dialog);
 const launch=document.createElement('button');launch.id='taskGuideOpen';launch.textContent='任务步骤';launch.hidden=true;
 const mount=()=>{const parent=E('experimentCommands');if(parent)parent.insertBefore(launch,parent.querySelector('.command-connection'));};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
 steps.forEach((s,i)=>{const b=document.createElement('button');b.textContent=`${i+1} ${s[0]}`;b.onclick=()=>{stage=i;render();};E('taskGuideSteps').append(b);});
 function render(){
  E('taskGuideTitle').textContent=`${stage+1} · ${steps[stage][0]}`;E('taskGuideInstruction').textContent=steps[stage][2];
  [...E('taskGuideSteps').children].forEach((b,i)=>b.setAttribute('aria-pressed',String(stage===i)));
  const s=V?.snapshot,o=window.frameObservation?.();
  E('taskGuideObserved').textContent=s?`${history?'历史只读':'当前实验'} ${history?.id||S.network_record_id} · ${(s.round/10).toFixed(1)} 模型秒；已送达 ${s.delivered}/${s.generated}，积压 ${s.pending}。${o?`所选链路 DATA #${o.generation}：${o.crc_good?'CRC通过':'本帧未正确接收'}，采样时刻 ${(o.model_ms/1000).toFixed(3)}秒。`:'所选链路暂无同帧数据。'}`:'尚无本轮实板观测；请先检查连接并开始。';
 }
 launch.onclick=()=>{render();dialog.showModal();};E('taskGuideClose').onclick=()=>dialog.close();
 E('taskGuideGo').onclick=()=>{dialog.close();showTab(steps[stage][1]);};
 function stop(){active=false;launch.hidden=true;dialog.close();}
 E('taskGuideExit').onclick=stop;
 async function start(){
  if(history){toast('请先返回当前实板，历史记录不能开始新实验。',true);return;}
  if(!S.connected){toast('请先检查连接；上电后需加载当前固件。',true);return;}
  if(S.busy&&S.task!=='network'){toast('请等待当前任务结束。',true);return;}
  if(!S.busy){
   await previewConfig();if(!validConfig)return;
   E('seconds').value='0';E('telemetry').value='10';
   await launchNetwork({seconds:0,ideal:Number(E('ideal').value),seed:Number(E('seed').value),config:readConfig(),telemetry_rounds:10});
  }
  document.querySelectorAll('dialog[open]').forEach(d=>d.close());active=true;stage=0;launch.hidden=false;render();dialog.showModal();
  toast('持续实验已启动：条件保持到你修改；点击“任务步骤”查看操作主线。');
 }
 E('demoStart').onclick=()=>start().catch(e=>toast(e.message,true));
 setInterval(()=>{if(dialog.open)render();},1000);
 window.demoGuide={start,stop,get active(){return active;}};
})();
