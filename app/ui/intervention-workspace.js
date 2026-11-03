/* Actual readback + clean windows, without promising degradation or recovery. */
(() => {
 'use strict';
 const E=id=>document.getElementById(id),sel=E('ivLink');if(!sel)return;
 const label=i=>`${String(i).padStart(2,'0')} · ${i+1} → ${(i+1)%4?i+2:'地面'}`;
 sel.innerHTML=Array.from({length:16},(_,i)=>`<option value="${i}">${label(i)}</option>`).join('');sel.value='4';
 let context=null,watch=null,baseline=null,trace=[],restore=null,submitted=null,readbacks=new Map();
 const fmt=(x,n=2)=>Number.isFinite(x)?x.toFixed(n):'—';
 const pct=x=>Number.isFinite(x)?(100*x).toFixed(1)+'%':'—';
 const ber=x=>Number.isFinite(x)?x.toExponential(2):'—';
 const row=link=>(V.link_windows||S.link_windows||[]).find(x=>x.link_id===link);
 const canOperate=()=>S.busy&&S.task==='network'&&!S.recomputing&&!history&&!!S.snapshot;
 const last=link=>[...(S.interventions||[])].reverse().find(x=>x.link===link);
 function reset(){watch=null;baseline=null;trace=[];restore=null;submitted=null;readbacks.clear();}
 async function change(enabled,keepNoise=false){
  try{
   if(!canOperate())throw Error('请先开始普通实板实验；历史回放和原条件重算期间不可改变条件');
   const link=Number(sel.value),before=last(link);
   if(enabled&&(!watch||watch.link!==link||!before?.enabled)){baseline=row(link)?{...row(link)}:null;trace=[];restore=null;}
   const body={link,enabled,gain_permille:enabled?Math.round(Number(E('ivGain').value)*10):1000,sigma:enabled?(keepNoise?8193:Number(E('ivSigma').value)):0};
   await api('/api/intervene',body);watch={link};submitted={afterSerial:before?.serial||0,enabled};
   if(!enabled)restore={requestedMs:S.snapshot.round*100};
   E('linkSelect').value=link;E('linkSelect').dispatchEvent(new Event('change'));
   toast('已排队；等待 ARM 受理、FPGA 同帧读回，以及后续业务实测。');render();
  }catch(e){toast(e.message,true);}
 }
 E('ivSevere').onclick=()=>{E('ivGain').value='1';change(1,true);};
 E('ivApply').onclick=()=>change(1);E('ivRestore').onclick=()=>change(0);
 sel.onchange=()=>{reset();render();};
 function chart(){
  const cv=E('ivTrace'),w=cv.clientWidth||400,h=90,d=devicePixelRatio||1;
  if(cv.width!==Math.round(w*d)||cv.height!==h*d){cv.width=Math.round(w*d);cv.height=h*d;cv.style.height=h+'px';}
  const g=cv.getContext('2d');g.setTransform(d,0,0,d,0,0);g.clearRect(0,0,w,h);if(trace.length<2)return;
  const a=trace[0].end_model_ms,b=trace.at(-1).end_model_ms;
  g.strokeStyle='#2df5c6';g.lineWidth=1.5;g.beginPath();let started=false;
  for(const p of trace){if(p.hop_success==null){started=false;continue;}const x=8+(p.end_model_ms-a)/Math.max(1,b-a)*(w-16),y=70-60*p.hop_success;started?g.lineTo(x,y):g.moveTo(x,y);started=true;}
  g.stroke();g.fillStyle='#9eb9c8';g.font='11px sans-serif';g.fillText(`逐跳 ACK 成功率 · ${(a/1000).toFixed(1)}–${(b/1000).toFixed(1)} 模型秒 · 实测点连线`,8,86);
 }
 function render(){
  const key=history?.id||S.network_record_id||'none';if(context!==key){context=key;reset();}
  for(const id of ['ivApply','ivRestore','ivSevere']){E(id).disabled=!canOperate();E(id).title=canOperate()?'持续生效，直到恢复或结束实验':'需要活动实板实验；重算和历史只读';}
  if(history){E('ivState').textContent='历史只读';E('ivLifecycle').textContent='历史回放只呈现记录。不能沿用上次实时操作面板的恢复结论。';E('ivCompare').innerHTML='';E('ivFix').innerHTML='';E('ivList').textContent='请查看对应实验的操作记录与实测曲线。';E('ivHeal').textContent='';chart();return;}
  const link=watch?.link??Number(sel.value),iv=last(link),s=V.snapshot,c=row(link),o=S.phy_links?.[String(link)]||window.frameObservation?.();
  if(o&&iv&&o.link_id===link&&o.condition_id===iv.serial&&o.model_ms>=iv.response.effective_round*100)readbacks.set(iv.serial,{ms:o.model_ms,generation:o.generation,sigma:o.channel.sigma,gain:o.channel.gain0});
  if(watch&&c&&trace.at(-1)?.end_model_ms!==c.end_model_ms){trace.push({...c});if(trace.length>300)trace.shift();}
  const rb=iv&&readbacks.get(iv.serial),effective=iv?.response?.effective_round*100;
  const accepted=iv&&iv.response?.ok===1&&(!submitted||iv.serial>submitted.afterSerial);if(accepted)submitted=null;
  const clean=accepted&&c&&c.start_model_ms>=effective&&c.data_attempts>=10;
  const source=Math.floor(link/4)*4+1,node=s?.nodes?.find(n=>n[0]===source),age=node?.[9]?s.round*100-node[10]:null;
  const freshAfter=age!=null&&age<=2000&&node[10]>=effective;
  const lower=baseline?.hop_success!=null&&c?.hop_success!=null&&c.hop_success<baseline.hop_success-.05;
  const recovered=clean&&rb&&!iv.enabled&&baseline?.hop_success!=null&&c.hop_success!=null&&c.hop_success>=baseline.hop_success-.05&&freshAfter;
  if(recovered&&restore&&!restore.completedMs)restore.completedMs=c.end_model_ms;
  let title='尚未施加干预',detail='选择链路后施加条件，比较寄存器、同帧接收与真实业务。';
  if(submitted){title='① 已提交，等待 ARM 受理';detail='尚不能认定板卡条件改变。';}
  else if(accepted&&!rb){title='② ARM 已受理，等待同帧读回';detail=`第 ${iv.response.effective_round} 轮起应用；切到这条链路后等待 DATA 帧返回。`;}
  else if(rb&&!clean){title='③ FPGA 读回已确认，积累后续窗口';detail=`帧 #${rb.generation}，${(rb.ms/1000).toFixed(3)} 秒，主径 ${fmt(rb.gain,4)} / σ ${rb.sigma}。需完全位于操作后的窗口且至少 10 次 DATA 尝试。`;}
  else if(clean&&rb){
   title=iv.enabled?(lower?'④ 已观测到逐跳成功率下降':'④ 条件已改变，尚无明显逐跳退化'):recovered?'⑥ 链路与新心跳均出现恢复证据':'⑤ 条件已恢复，业务效果继续观察';
   detail=`本窗口 ${c.start_model_ms/1000}–${c.end_model_ms/1000} 秒：${c.data_attempts} 次 DATA，ACK 成功 ${pct(c.hop_success)}，重传 ${c.retries} 次。参考源节点 ${source} 的位置年龄 ${age==null?'未知':fmt(age/1000,1)+' 秒'}。效果由实际样本决定。`;
  }
  if(submitted&&!S.busy){title='实验已结束';detail='未取得此请求的板卡受理回执。请开始新的持续实验再试。';} E('ivState').textContent=title;E('ivLifecycle').innerHTML=`<b>${esc(title)}</b><p>${esc(detail)}</p>`;
  const values=[['ACK 成功率',pct(baseline?.hop_success),pct(c?.hop_success)],['纠错前 BER',ber(baseline?.pre_ber),ber(c?.pre_ber)],['EVM / %',fmt(baseline?.evm_percent),fmt(c?.evm_percent)],['DATA 次数',baseline?.data_attempts??'—',c?.data_attempts??'—']];
  E('ivCompare').innerHTML=`<table><tr><th>指标</th><th>首次改变前</th><th>当前滚动窗</th></tr>${values.map(x=>'<tr>'+x.map(v=>`<td>${esc(v)}</td>`).join('')+'</tr>').join('')}</table><p class="hint">不同窗口尝试次数可能不同。EVM 只统计有效观测，完全失捕时不可用；不能凭 EVM 单独判恢复。</p>`;
  E('ivHeal').textContent=restore?.completedMs?`撤销后 ${(restore.completedMs-(iv?.response?.effective_round*100||restore.requestedMs))/1000} 模型秒时首次达到观测恢复条件（分辨率取决于窗口）；不代表未来一定可靠。`:restore?'撤销条件后，等待新心跳、完整窗口和逐跳送达恢复。':'参数持续生效，不按短倒计时自动恢复。';
  const mediaSource=Math.floor(link/4)===0?1:Math.floor(link/4)===1?5:null;
  E('ivFix').innerHTML=accepted?'<p>业务措施只能调整负载，不能消除噪声或代替撤销注入。确认回执后再看生成速率、积压和心跳时效。</p>'+ (mediaSource?`<button id="ivRate">节点 ${mediaSource} 媒体降至 1 片/秒</button><button id="ivRateRestore">恢复 5 片/秒</button>${window.commandFeedbackHtml?.(mediaSource)||''}`:'<p>此链路没有媒体源，不能给它发送无效媒体指令。</p>'):'';
  for(const [id,value] of [['ivRate',1],['ivRateRestore',5]])if(E(id)){E(id).disabled=!canOperate();E(id).onclick=()=>prepareCommand({target:mediaSource,opcode:4,value,ttl_ms:10000});}
  E('ivList').innerHTML=(S.interventions||[]).slice(-5).reverse().map(x=>`<p>#${x.serial} · ${label(x.link)} · ${x.enabled?'附加条件':'恢复场景'} · 生效轮 ${x.response.effective_round} · ${readbacks.has(x.serial)?'DATA 读回已见':'ARM 回执，未在此视图记录 DATA'}</p>`).join('');chart();
 }
 const previous=window.renderInstruments;window.renderInstruments=()=>{previous?.();render();};render();
})();
