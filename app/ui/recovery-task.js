/* Explicit user interventions; fault and recovery labels come from telemetry. */
(() => {
 const E=id=>document.getElementById(id);
 const advice=document.createElement('p');advice.id='recoveryAdvice';advice.style.whiteSpace='pre-line';document.querySelector('.advicePanel .sectiontitle').after(advice);
 E('recoveryCommands').innerHTML=`<h3>文字指令</h3><label>输入指令<input id="recoveryText" aria-label="处置文字指令" placeholder="节点 5 媒体速率 1"></label>
 <button id="recoveryParse">检查指令</button><p id="recoveryPlan"></p><button id="recoveryExecute" disabled>确认执行</button>
 <p id="recoveryReceipt"></p>`;
 const jump=document.createElement('button');jump.textContent='下一步建议 / 处置';jump.onclick=()=>{showTab('mission');[...document.querySelectorAll('.p2-right [role=tab]')].find(b=>b.textContent==='建议')?.click();advice.scrollIntoView({block:'nearest'});};document.querySelector('#alertCenter .ac-head')?.append(jump);
 let plan=null,key='',lastCommand=null;
 E('advice').addEventListener('click',e=>{
  const text=e.target.closest('button[data-draft]')?.dataset.draft;if(!text)return;
  [...document.querySelectorAll('.p2-right [role=tab]')].find(b=>b.textContent==='文字指令')?.click();
  E('recoveryText').value=text;E('recoveryText').dispatchEvent(new Event('input'));E('recoveryText').focus();
 });
 E('recoveryText').addEventListener('input',()=>{plan=null;E('recoveryPlan').textContent='';E('recoveryExecute').disabled=true;});
 const active=()=>S.busy&&S.task==='network'&&S.status==='running'&&!history&&!S.recomputing&&S.snapshot;
 const latest=()=>{const m=new Map();for(const x of S.interventions||[])m.set(x.link,x);return [...m.values()];};
 async function command(action){return api('/api/command',{record_id:S.network_record_id,run_id:S.snapshot.run_id,confirm:true,action:{...action,ttl_ms:10000}});}
 function remember(r){lastCommand=r.request?.command_id;E('recoveryPlan').textContent='已进入发送队列，等待节点收到、执行并回传结果。';}
 E('recoveryParse').onclick=async()=>{try{
  plan=null;lastCommand=null;E('recoveryReceipt').textContent='';E('recoveryExecute').disabled=true;const r=await api('/api/recovery/parse',{text:E('recoveryText').value});
  plan={...r.plan,record:S.network_record_id,run:S.snapshot?.run_id};
  if(plan.kind==='restore'&&!latest().some(x=>x.link===plan.link&&x.enabled))throw Error('该链路没有待撤销的人工扰动');
  E('recoveryPlan').textContent=`待确认：${plan.label}。${plan.kind==='command'?'通过真实下行链路送到节点，需回执确认。':'修改实验信道条件，需FPGA读回与新心跳确认。'}`;E('recoveryExecute').disabled=false;
 }catch(e){plan=null;E('recoveryPlan').textContent=e.message;}};
 E('recoveryExecute').onclick=async()=>{try{
  if(!plan||!active()||plan.record!==S.network_record_id||plan.run!==S.snapshot.run_id)throw Error('实验已改变，请重新检查指令');
  E('recoveryExecute').disabled=true;
  if(plan.kind==='restore'){await api('/api/watch',{link:plan.link});await api('/api/intervene',{link:plan.link,enabled:0,gain_permille:1000,sigma:0});E('recoveryPlan').textContent='信道参数恢复已排队，等待实测恢复。';}
  else {const result=await command(plan.action);remember(result);}
  plan=null;
 }catch(e){E('recoveryPlan').textContent=e.message;}};
 function render(){
  if(key!==S.network_record_id){key=S.network_record_id;plan=null;lastCommand=null;}
  E('recoveryExecute').disabled=!plan||!active();
  const s=V.snapshot,r=s?.recovery;
  advice.hidden=true;
  if(!s){E('recoveryReceipt').textContent='';return;}
  const c=(s.command_results||[]).find(x=>x[0]===lastCommand);
  E('recoveryReceipt').textContent=c?window.commandReceiptText(c,s):'';
  if(c&&c[4]!==1)E('recoveryPlan').textContent='';
 }
 setInterval(render,500);
})();
