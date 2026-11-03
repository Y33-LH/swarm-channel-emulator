/* Fixed uplink route, annotated only with the chosen snapshot's received telemetry. */
(() => {
 'use strict';
 const pad=id=>String(id).padStart(2,'0');
 const tags={good:'正常',bad:'异常',wait:'待实收'};
 function routeModel(s,windows,node){
  const issues=s?.recovery?.issues||[],end=Math.ceil(node/4)*4;
  const hardware=new Set((s?.hardware_nodes||[]).filter(h=>h[1]).map(h=>h[0]));
  const members=[],hops=[],messages=[];
  for(let id=node;id<=end;id++){
   const row=s?.nodes?.find(a=>a[0]===id);
   const count=row?.[9]||0,age=count?(s.round*100-row[10])/1000:null;
   const overdue=!!row&&(issues.some(i=>i.kind==='heartbeat'&&i.node===id)||(s.round>30&&(age===null||age>3)));
   const state=overdue?'bad':count?'good':'wait';
   if(overdue)messages.push(issues.find(i=>i.kind==='heartbeat'&&i.node===id)?.title ||
     (age===null?`${pad(id)} 尚未收到心跳`:`${pad(id)} 心跳已 ${age.toFixed(1)} 秒未更新`));
   members.push({id,state,count,age,xyz:count?row.slice(4,7).map(v=>Math.round(v/1000)):null,
    role:hardware.has(id)?'FPGA 实体':s?.config?.external_node===id?'外接节点':'ARM 虚拟',hardware:hardware.has(id)});
   const win=windows?.find(w=>w.link_id===id-1);
   const dst=id%4?id+1:0;
   const failed=issues.some(i=>i.kind==='link'&&i.link===id-1)||(win?.data_attempts>=2&&win.acked===0);
   const hop={id,dst,state:failed?'bad':win?.acked>0?'good':'wait',acks:win?.acked??null,attempts:win?.data_attempts??null};
   if(failed)messages.push(`${pad(id)} → ${dst?pad(dst):'地面'} 逐跳确认异常`);
   hops.push(hop);
  }
  const first=members[0];return {members,hops,first,hardware,messages,state:messages.length?'bad':first.count?'good':'wait'};
 }
 function diagram(model){
  const list=[...model.members,{id:0,state:model.first.state==='wait'?'wait':'good',role:'接收站'}];
  const margin=24,span=274,spacing=span/(list.length-1),pt=i=>[margin+spacing*i,61-19*Math.sin(i*Math.PI/(list.length-1))];
  const edges=model.hops.map((e,i)=>{
   const [x,y]=pt(i),[u,v]=pt(i+1),mid=(x+u)/2,my=(y+v)/2,rot=Math.atan2(v-y,u-x)*180/Math.PI;
   return `<g class="tr-${e.state}"><title>${pad(e.id)} → ${e.dst?pad(e.dst):'地面'}，本窗确认 ${e.acks??'—'} / 尝试 ${e.attempts??'—'}</title><path class="tr-edge" d="M${x},${y} L${u},${v}"/><path class="tr-arrow" transform="translate(${mid} ${my}) rotate(${rot})" d="M-4,-3 L1,0 -4,3"/></g>`;
  }).join('');
  const nodes=list.map((m,i)=>{
   const [x,y]=pt(i),shape=m.id===0?'<rect x="-9" y="-7" width="18" height="14" rx="3"/><path d="M-6 10 H6"/>':m.hardware?'<path d="M0 -12 L12 0 0 12 -12 0 Z"/><circle r="5"/>':'<circle r="8"/>';
   return `<g class="tr-${m.state}" transform="translate(${x},${y})"><text y="-18">${m.id?pad(m.id):'地面站'}</text>${shape}<text class="tr-role" y="27">${m.id?m.hardware?'FPGA':m.role.startsWith('ARM')?'ARM':'外接':'实收端'}</text></g>`;
  }).join('');
  return edges+nodes;
 }
 window.createLiveReturn=()=>{
  const panel=document.createElement('section');panel.className='panel return-topology';
  panel.innerHTML=`<h3>单节点实时回传</h3><label>观测节点 <select aria-label="实时回传观测节点"></select></label>
   <div class="tr-physical"></div><canvas class="node-motion" width="336" height="170" aria-label="所选节点的地面实收位置与航迹"></canvas><div class="monitor-caption"></div><svg viewBox="0 0 322 99" role="img" aria-label="所选节点沿固定上行路径到地面站"></svg>
   <div class="tr-state" role="status"></div><div class="tr-readout"></div><small class="tr-source"></small>`;
  const get=q=>panel.querySelector(q),selector=get('select'),chips=get('.tr-physical');
  const choose=id=>{const sel=document.getElementById('nodeSelect');sel.value=id;sel.dispatchEvent(new Event('change'));};
  selector.innerHTML=Array.from({length:16},(_,i)=>`<option value="${i+1}">节点 ${pad(i+1)}</option>`).join('');
  selector.onchange=()=>choose(Number(selector.value));
  const canvas=get('.node-motion'),ctx=canvas.getContext('2d'),tracks=new Map();let trackRun='',round=-1,raf=0,trackColor='#43edac';
  function paint(){
   raf=0;
   if(tab!=='mission'||panel.closest('[hidden]')||document.hidden)return;
   const w=336,h=170,cx=168,cy=84,k=.015;
   const xp=x=>cx+(x-5000)*k,yp=y=>cy-(y-5000)*k;
   ctx.clearRect(0,0,w,h);ctx.lineWidth=1;ctx.strokeStyle='#1e3b4c';ctx.beginPath();
   for(let i=-5;i<=5;i++){ctx.moveTo(cx+i*15,8);ctx.lineTo(cx+i*15,160);ctx.moveTo(8,cy+i*15);ctx.lineTo(328,cy+i*15);}ctx.stroke();
   for(const r of [30,60]){ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.stroke();}
   ctx.fillStyle='#eee9c6';ctx.font='12px sans-serif';ctx.fillText('★ 地面站',cx-5,cy+4);
   const t=tracks.get(selected);if(!t){ctx.fillStyle='#add1dd';ctx.fillText('等待第一条实收位置',10,20);return;}
   const f=history||!S.busy?1:Math.min(1,(performance.now()-t.at)/t.duration);
   const x=t.from[0]+(t.to[0]-t.from[0])*f,y=t.from[1]+(t.to[1]-t.from[1])*f;
   ctx.beginPath();ctx.strokeStyle=trackColor;ctx.globalAlpha=.50;
   t.trail.slice(0,-1).forEach((p,i)=>{if(i)ctx.lineTo(xp(p[0]),yp(p[1]));else ctx.moveTo(xp(p[0]),yp(p[1]));});ctx.lineTo(xp(x),yp(y));ctx.stroke();ctx.globalAlpha=1;
   ctx.fillStyle=trackColor;ctx.beginPath();ctx.arc(xp(x),yp(y),5,0,Math.PI*2);ctx.fill();
   ctx.font='bold 13px sans-serif';ctx.fillText(pad(selected),xp(x)+8,yp(y)-4);
   canvas.dataset.position=[x,y].map(v=>v.toFixed(1)).join(',');ctx.fillStyle='#9bbeca';ctx.font='11px sans-serif';ctx.fillText('俯视 · 1 格 = 1 km',8,163);
   if(f<1)raf=requestAnimationFrame(paint);
  }
  function updateMotion(s,model){
   const rid=(history?.id||S.network_record_id||'')+(history?':archive':':live');
   if(rid!==trackRun||(s&&s.round<round)){trackRun=rid;tracks.clear();round=-1;delete canvas.dataset.position;}
   if(s&&s.round>round){
    ReceivedTracks.append(tracks,history?.snapshots||S.snapshots||[s],round,s.round,performance.now());round=s.round;
   }
   trackColor=model.state==='bad'?'#ff586e':model.state==='good'?'#43edac':'#96adb8';
   if(!raf)paint();
  }
  let key='',lastCount=0,alarm=false,lastDrawing='',lastHardware;
  window.renderLiveReturn=()=>{
   if(!panel.isConnected)return;
   const s=V.snapshot,model=routeModel(s,V.link_windows,selected),m=model.first;
   const live=!history&&S.task==='network'&&S.busy&&S.status==='running'&&!pollFailed;
   updateMotion(s,model);
   const visible=tab==='mission'&&!panel.closest('[hidden]')&&!document.hidden;
   const identity=(history?.id||S.network_record_id||'')+':'+selected;
   if(key!==identity){key=identity;lastCount=0;alarm=false;window.returnSound.stop();}
   selector.value=String(selected);
   const hwIds=[...model.hardware].sort((a,b)=>a-b);
   const hwKey=hwIds.join(',');
   if(lastHardware!==hwKey){
    lastHardware=hwKey;chips.replaceChildren(document.createTextNode(hwIds.length?'板内实体 ': '板内实体 · 等待读回'));
    hwIds.forEach(id=>{const b=document.createElement('button');b.type='button';b.textContent='◇ '+pad(id);b.title='查看 FPGA 硬件节点 '+id;b.onclick=()=>choose(id);chips.append(b);});
   }
   const drawing=diagram(model);if(drawing!==lastDrawing){get('svg').innerHTML=drawing;lastDrawing=drawing;}
   const stateLabel=model.state==='bad'?model.messages.join('；'):model.state==='good'?'地面已收到该节点心跳':'等待地面收到该节点心跳';
   const lamp=get('.tr-state');lamp.dataset.state=model.state;
   if(lamp.textContent!==stateLabel)lamp.textContent=stateLabel;
   get('.tr-readout').textContent=`节点 ${pad(selected)} · ${s?m.role:'角色待实板确认'}　心跳 ${s?m.count:'—'} 次`+
    (m.xyz?`\n实收 X ${m.xyz[0]} / Y ${m.xyz[1]} / Z ${m.xyz[2]} m`:'');
   get('.tr-source').textContent=(history?'历史记录':live?'实板实时':S.status==='paused'?'实板暂停':s?'最近实板快照':'等待实板')+
    (s?` · 通信 ${(s.round/10).toFixed(1)} s`:'')+' · 绿正常 / 红异常 / 灰待观测';
   const sound=s?.heartbeat_audio?.find(a=>a[0]===selected&&a[1]===s.nodes.find(n=>n[0]===selected)?.[8]);
   get('.monitor-caption').textContent=sound?'地面已收节点 '+pad(selected)+' 心跳音样 · '+m.count+' 次心跳':'等待该节点的实收心跳音样';
   if(live&&visible&&sound&&m.count>lastCount)window.returnSound.packet(sound[2]);
   lastCount=m.count;
  };
  return panel;
 };
})();
