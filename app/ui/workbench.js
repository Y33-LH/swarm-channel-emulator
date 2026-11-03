'use strict';
const signed32=v=>v>=2147483648?v-4294967296:v;
const signed16=v=>v>=32768?v-65536:v;
window.currentLab=()=>!history&&['lab','labnoise'].includes(S.task)?S.lab:null;
window.observedChannel=id=>{
 const r=window.currentLab();if(!r)return V.scene?.find(x=>x.link_id===id);
 const a=r.applied_registers;if(!a)return null;
 return {lab_id:r.id,applied:true,gain0:a[64]/32768,gain1:a[120]/32768,sigma:a[68],
  cfo_hz:signed32(a[92])*8e6/2**32,phase_radians:a[84]*2*Math.PI/2**32,
  echo_cfo_hz:signed32(a[132])*8e6/2**32,echo_phase_radians:a[128]*2*Math.PI/2**32,delay_samples:a[112],echo_delay_samples:a[124]};
};
window.receiverPoints=()=>{
 const s=V.snapshot,id=Number($('linkSelect').value);
 if(!history&&['lab','labnoise'].includes(S.task)&&S.lab)return S.lab.iq;
 if(!s||s.watch_link!==id)return null;
 const decode=v=>[signed16(v&65535),signed16(v>>>16)];
 return {received:(s.watch_iq||[]).map(x=>decode(x[0])),equalized:(s.watch_iq||[]).map(x=>decode(x[1]))};
};
window.renderWorkbench=()=>{
 const s=V.snapshot,m=V.metrics||{},id=Number($('linkSelect').value),p=s?.watch_link===id?s.watch_phy:null;
 const cfg=s?.config||preview?.config||catalog?.defaults;
 if(cfg&&catalog){const changed=s&&preview&&Object.keys(preview.config).some(k=>preview.config[k]!==cfg[k]);$('sceneBrief').textContent=(s?'已应用：':'待运行：')+`${catalog.environment[cfg.environment].name} / ${catalog.weather[cfg.weather].name} / ${catalog.formation[cfg.formation].name}`+(changed?'。参数已修改，下次开始生效。':'');}
 let rows=[],age='尚无本链路的接收快照';
 if(!history&&['lab','labnoise'].includes(S.task)&&S.lab){
  const r=S.lab;rows=[['帧头捕获',r.registers?.['100']?'已捕获':'未捕获'],['完整接收',r.match?'成功':'未交付'],['估计频偏',num(r.estimated_cfo_hz,1)+' Hz'],['均衡后 EVM',num(r.payload_evm_percent,1)+'%']];
  age='单帧实测 · '+r.id;
 }else if(p?.[0]){
  rows=[['最近帧头',p[4]?'已捕获':'未捕获'],['完整接收',p[11]&4?'CRC / 格式通过':'未交付'],['估计频偏',p[4]?num(signed32(p[5])*8e6/2**32,1)+' Hz':'—'],['定时步长',p[4]?num(signed32(p[8])/65536,4)+' samples':'—']];
  age=`接收器：${p[1]/1000} 模型秒 / ${p[2]?'ACK':'DATA'}；I/Q：${s.watch_iq?.length?s.watch_iq_ms/1000+' 模型秒':'尚无采样'}。`;
 }else rows=[['帧头捕获','—'],['完整接收','—'],['估计频偏','—'],['定时步长','—']];
 $('receiverSummaryLive').innerHTML=rows.map(([k,v])=>`<div><span>${esc(k)}</span><strong>${esc(v)}</strong></div>`).join('')+`<p class="receiver-age">${esc(age)}</p>`;
 const stages=$('modemFlow').querySelectorAll('span');stages.forEach(x=>x.className='');
 const lab=!history&&['lab','labnoise'].includes(S.task)?S.lab:null;
 if(lab){const captured=lab.registers?.['100'];stages[0].className=captured?'pass':'fail';if(captured){stages[1].className=lab.phy?.timing_updates?'pass':'';stages[2].className=lab.phy?.evm_symbols?'pass':'';stages[3].className=lab.match?'pass':'fail';}}
 else if(p?.[0]){stages[0].className=p[4]?'pass':'fail';if(p[4]){stages[1].className=p[9]?'pass':'';stages[2].className='pass';stages[3].className=p[11]&4?'pass':'fail';}}
 let next='检查顶部设备连接；重新上电后先加载固件。';
 if(S.connected)next='保持默认参数，点击顶部“开始实板实验”。也可先发送一段文字检查收发。';
 if(S.busy)next=S.task==='network'?'实验正在计算。先看信道与接收，再到第二页查看心跳、告警和节点操作。':'当前独立测试正在占用板卡，完成后可继续网络实验。';
 if(S.error)next='操作未完成：'+S.error;
 if(history)next='当前为历史记录。图表来自保存数据；点击“返回当前实板”后才能操作硬件。';
 $('nextStep').textContent=next;
 let health='等待运行 · 心跳携带位置，告警描述故障与恢复';
 if(s){const stale=s.nodes.filter(n=>!nodeData(n[0]).fresh).length;health=`位置新鲜 ${16-stale}/16 · 实收心跳 ${num(s.hb)} · 告警 ${num(s.alarms)} · 待转发 ${num(s.pending)}`;$('globalHealth').classList.toggle('warn',stale>0||s.pending>30);}
 $('healthSummary').textContent=health;
 for(const name of ['labRun','labBatch','verify','capacityRun'])$(name).title=history?'历史回放不操作板卡':!S.connected?'请先检查板卡连接':S.busy?'当前任务正在使用板卡，完成或中止后可操作':'';
 $('openLab').textContent=S.busy&&S.task==='network'?'查看单链路实验（整机结束后可发送）':'发送一段文字，观察恢复效果';
 if(window.renderInstruments)window.renderInstruments();
};
action('editScenario',()=>showTab('mission'));
action('inspectBusiness',()=>showTab('mission'));
action('openLab',()=>{$('labDialog').showModal();drawTech();});
action('closeLab',()=>$('labDialog').close());
$('labDialog').addEventListener('close',()=>{if(tab==='evidence')drawTech();});
