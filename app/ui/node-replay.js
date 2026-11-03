/* 节点业务回放：画面与语音由该记录的地面实收快照生成；真值列为 ARM 模型参考。
 * 时长 = 实验时长；节点任选；音频由服务端从实收数据合成（心跳节拍 + 事件提示音 + 可选语音播报）。 */
(()=>{
'use strict';
const E=id=>document.getElementById(id);
const api=async(p,d)=>{const r=await fetch(p,d===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});const j=await r.json();if(!r.ok)throw Error(j.error||`请求失败 ${r.status}`);return j;};
let story=null,t=0,request=0,context='',raf=0;
const fmt=s=>`${String(Math.floor(s/60)).padStart(2,'0')}:${String(Math.floor(s%60)).padStart(2,'0')}`;
function currentRecord(){return (typeof history!=='undefined'&&history&&history.id)||(typeof S!=='undefined'&&S.network_record_id)||null;}
function key(){return (currentRecord()||'')+':'+E('replayNode').value;}

function narrAt(tt){if(!story)return'';let out='';for(const s of story.narration)if(s.t<=tt)out=s.text;return out;}

function draw(){
 const cv=E('nodeReplay');if(!cv)return;
 const w=cv.clientWidth||600,h=cv.clientHeight||260,dpr=devicePixelRatio||1;
 if(cv.width!==Math.round(w*dpr)||cv.height!==Math.round(h*dpr)){cv.width=w*dpr;cv.height=h*dpr;}
 const g=cv.getContext('2d');g.setTransform(dpr,0,0,dpr,0,0);
 g.fillStyle='#040f19';g.fillRect(0,0,w,h);
 if(!story){g.fillStyle='#8fa5b8';g.font='12px sans-serif';g.fillText('生成后显示该节点的全程航迹、链路质量与事件字幕',18,h/2);return;}
 const rows=story.samples;if(!rows.length)return;
 // 航迹（真值列，ARM 模型参考）
 const xs=rows.map(r=>r.truth[0]),ys=rows.map(r=>r.truth[1]);
 const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
 const sc=Math.min((w-120)/Math.max(1,x1-x0),(h-80)/Math.max(1,y1-y0));
 const px=v=>60+(v-x0)*sc,py=v=>h-40-(v-y0)*sc;
 g.strokeStyle='#284855';g.lineWidth=1;g.beginPath();
 rows.forEach((r,i)=>i?g.lineTo(px(r.truth[0]),py(r.truth[1])):g.moveTo(px(r.truth[0]),py(r.truth[1])));g.stroke();
 // 事件标记
 for(const s of story.narration){const eventTime=s.event_t??s.t;
  const r=rows.reduce((a,b)=>Math.abs(b.t-eventTime)<Math.abs(a.t-eventTime)?b:a,rows[0]);
  const bad=/未按时|拒绝/.test(s.text);g.fillStyle=bad?'#ff4d6a':'#2df5c6';
  g.beginPath();g.arc(px(r.truth[0]),py(r.truth[1]),4,0,7);g.fill();}
 // 当前位置：实收轨迹优先（验收依据），否则真值
 const cur=rows.findLast(r=>r.t<=t);
 if(!cur){g.fillStyle='#bed5db';g.font='12px sans-serif';g.fillText('等待此节点第一条实收快照',14,24);E('replayNarration').textContent=narrAt(t);return;}
 const useRx=cur.updates>0,p=useRx?cur.rx:cur.truth;
 g.fillStyle=useRx?'#2df5c6':'#7dbbff';g.strokeStyle='#e7f4ff';g.lineWidth=1.4;
 g.beginPath();g.arc(px(p[0]),py(p[1]),7,0,7);g.fill();g.stroke();
 // HUD
 g.fillStyle='#bed5db';g.font='11px Consolas';
 const qual=cur.attempts?Math.round(100*cur.ok/Math.max(1,cur.attempts)):null;
 g.fillText(`T+${fmt(t)}  X ${p[0].toFixed(0)}m  Y ${p[1].toFixed(0)}m  Z ${p[2].toFixed(0)}m`,14,18);
 g.fillText(`心跳实收 ${cur.updates} 次${qual===null?'':' · 上行逐跳确认 '+qual+'%'}${cur.retries?' · 重传 '+cur.retries:''}`,14,34);
 g.fillStyle='#5a7a88';g.fillText(`${useRx?'位置：地面实收':'位置：模型真值（尚未实收）'} · 节点 ${String(story.node).padStart(2,'0')} · 第 ${story.chain} 链路组`,14,h-12);
 // 字幕
 const sub=narrAt(t);
 E('replayNarration').textContent=sub?`【${fmt(t)}】${sub}`:'';
}

const player=E('nodeAudio');
function refresh(){
 if(!story)return;
 t=player.currentTime||0;E('replayScrub').value=t;
 E('replayPlayPause').textContent=player.paused?'播放':'暂停';
 E('replayTime').textContent=`${fmt(t)} / ${fmt(story.audio_duration_s)}`;
 draw();
}
function tick(){refresh();raf=player.paused?0:requestAnimationFrame(tick);}
function reset(){
 request++;context=key();story=null;player.pause();player.removeAttribute('src');player.load();
 E('replayPlayPause').disabled=true;E('replayPlayPause').textContent='播放';E('replayScrub').disabled=true;E('replayScrub').value=0;
 E('replayTime').textContent='--:-- / --:--';E('replaySource').textContent='';E('replayNarration').textContent='选择节点并生成这次记录的解说。';E('replayLoad').disabled=false;draw();
}
async function load(){
 reset();const version=request;
 try{
  const rid=currentRecord();if(!rid)throw Error('尚无实验记录，请先运行实验或载入历史记录');
  const query=`record=${encodeURIComponent(rid)}&node=${Number(E('replayNode').value)}`;
  E('replayLoad').disabled=true;E('replayNarration').textContent='正在读取地面记录，生成逐句解说…';
  const result=await api('/api/node_story?'+query+'&audio=1');
  if(version!==request||key()!==context)return;
  story=result;player.src='/api/node_audio?'+query+'&round='+result.round;player.preload='metadata';player.load();
  E('replayScrub').max=story.audio_duration_s;
  E('replaySource').textContent=`实收记录截至 ${fmt(story.duration_s)} · ${story.speech?'逐句语音与字幕':'当前电脑无可用中文播音，使用提示音与字幕'} · 片尾播报汇总`;
  refresh();
 }catch(e){if(version===request)E('replayNarration').textContent='生成失败：'+e.message;}
 finally{if(version===request)E('replayLoad').disabled=false;}
}
function boot(){
 const sel=E('replayNode');if(!sel)return;
 sel.innerHTML=Array.from({length:16},(_,i)=>`<option value="${i+1}">节点 ${String(i+1).padStart(2,'0')}</option>`).join('');
 context=key();sel.onchange=reset;E('replayLoad').onclick=load;
 E('replayPlayPause').onclick=()=>{if(!story)return;if(player.paused)player.play().catch(e=>E('replayNarration').textContent='播放失败：'+e.message);else player.pause();};
 E('replayScrub').oninput=()=>{if(story){player.currentTime=Number(E('replayScrub').value);refresh();}};
 player.addEventListener('loadedmetadata',()=>{if(story){E('replayScrub').disabled=false;E('replayPlayPause').disabled=false;refresh();}});
 player.addEventListener('error',()=>{if(story)E('replayNarration').textContent='音频未能加载，请重新生成回放。';});
 player.addEventListener('play',()=>{if(!raf)tick();});
 for(const name of ['pause','seeked','ended','timeupdate'])player.addEventListener(name,refresh);
 window.syncRecordReplay=()=>{if(context!==key())reset();};
}
document.readyState==='loading'?document.addEventListener('DOMContentLoaded',boot):boot();
})();
