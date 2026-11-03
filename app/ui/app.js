'use strict';
const $=id=>document.getElementById(id), esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=x=>x==null?'—':(x*100).toFixed(2)+'%', num=(x,n=0)=>x==null?'—':Number(x).toLocaleString('zh-CN',{maximumFractionDigits:n}), clock=t=>`${String(Math.floor(t/60)).padStart(2,'0')}:${String(Math.floor(t%60)).padStart(2,'0')}`;
/* 安全写入：面板精简后元素可能不存在。取不到元素时用一个空壳对象接收赋值，
   既不抛异常中断整段渲染，也不伪造任何数据（输出被丢弃）。 */
const DUMMY_EL={textContent:'',innerHTML:'',hidden:true,classList:{toggle(){},remove(){},add(){}}};
const elOf=id=>$(id)||DUMMY_EL;
const setT=(id,v)=>{const e=$(id);if(e)e.textContent=v;};
const setH=(id,v)=>{const e=$(id);if(e)e.innerHTML=v;};
const addH=(id,v)=>{const e=$(id);if(e)e.innerHTML+=v;};
let draftConfig=null;
let S={},V={},catalog,info,evidence,preview=null,selected=1,history=null,historyIndex=-1,records=[],tab='evidence',validConfig=false,pendingAction=null,configTimer,previewRequest=0,replayTimer=null,lastRenderKey='',wallStarted=null,pollFailed=false;
const geometry=['spacing_m','altitude_m','center_x_m','center_y_m','heading_deg','speed'];
const labels={idle:'准备就绪',preparing:'正在准备 / 校验',running:'实板计算中',paused:'已暂停模型时钟',complete:'本轮已结束 · 结果已保存',stopped:'已中止',error:'需要处理错误'};
function taskStatus(s){return s.status==='complete'&& !['network','causal','capacity','link'].includes(s.task)?({connect:'连接检查完成',firmware:'固件加载完成',verify:'收发自检完成',lab:'文字收发完成',labnoise:'噪声测试完成'}[s.task]||'操作完成'):(labels[s.status]||'准备就绪');}
async function launchNetwork(request){await api('/api/watch',{link_id:Number($('linkSelect').value)});return api('/api/start',{...request,heartbeat_drill:window.mountainDrillRequested?.(request)??false});}
async function resumeCurrentWorkspace(){
 S=await api('/api/state');setConfig(S.config||catalog.defaults);
 if(Number.isInteger(S.watch_link)&&S.watch_link>=0&&S.watch_link<32)$('linkSelect').value=String(S.watch_link);
 if([...$('port').options].some(o=>o.value===S.port))$('port').value=S.port;
 if(Number.isFinite(S.snapshot?.duration_s))$('seconds').value=String(S.snapshot.duration_s);
}
async function api(path,data){const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),data===undefined?12000:30000);try{const r=await fetch(path,{...(data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),signal:ctl.signal,cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error||`请求失败 ${r.status}`);return d;}catch(e){if(e.name==='AbortError')throw Error(`本地服务响应超时：${path}。${data===undefined?'可重试读取。':'请先检查操作状态，勿重复提交。'}`);throw e;}finally{clearTimeout(timer);}}
let toastTimer;function toast(text,error=false){$('toast').textContent=text;$('toast').hidden=false;$('toast').style.borderColor=error?'#ff7b87':'#397f94';clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,error?10000:6000);}
function action(id,fn){const el=$(id);if(!el)return;el.addEventListener('click',async()=>{try{await fn();}catch(e){toast(e.message,true);}});}
function showTab(id){tab=id;document.querySelectorAll('.page').forEach(x=>x.classList.toggle('active',x.id===id));document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x.dataset.tab===id));window.returnSound?.pauseHidden();window.renderLiveReturn?.();if(id==='history')refreshRecords();if(id==='evidence'){drawTech();if(window.renderInstruments)window.renderInstruments();}requestAnimationFrame(drawMap);}
function readConfig(){const c={...catalog.defaults};for(const key of ['environment','weather','formation','spacing_m','altitude_m','center_x_m','center_y_m','heading_deg','jitter_percent'])c[key]=Number($(key).value);c.speed_mmps=Math.round(Number($('speed').value)*1000);c.reference_snr_cdb=Math.round(Number($('snr').value)*100);c.carrier_mhz=Number($('carrier').value);c.faults=$('faults').checked?1:0;c.external_node=Number($('externalNode').value);c.reserved=Number($('sceneScale').value)||1;if(window.readChannelConfig)c.channel=window.readChannelConfig();return c;}
function setConfig(c){$('sceneScale').value=c.reserved||1;if(c.reserved>1)$('mapView').value='orbit';window.setChannelConfig?.(c.channel);for(const key of ['environment','weather','formation','spacing_m','altitude_m','center_x_m','center_y_m','heading_deg','jitter_percent'])$(key).value=c[key];$('speed').value=c.speed_mmps/1000;$('snr').value=c.reference_snr_cdb/100;$('carrier').value=c.carrier_mhz??2400;$('faults').checked=!!c.faults;$('externalNode').value=String(c.external_node||0);window.syncChoices?.();previewConfig();}
async function previewConfig(){const ticket=++previewRequest;validConfig=false;const c=readConfig();geometry.forEach(k=>$(k).disabled=!!history);$('weatherNotice').hidden=!catalog.severe_weather.includes(c.weather);try{const r=await api('/api/preview',{config:c,seed:Number($('seed').value)});if(ticket!==previewRequest)return;preview=r;validConfig=true;$('configError').textContent='';const stale=!!(S.snapshot&&S.config_sha256&&S.config_sha256!==r.config_sha256);$('configHash').textContent='配置校验通过 · '+r.config_sha256.slice(0,12)+(history?' · 历史记录配置（只读）':!S.snapshot?' · 尚未上板生效':stale?' · 已改动，将在下一次开始实验时生效':' · 与本轮已下发配置一致');
 const cs=$('configSummary');if(cs){const nm=(kind,id)=>catalog[kind]?.[id]?.name||id;cs.textContent=`${nm('environment',c.environment)} · ${nm('weather',c.weather)} · ${nm('formation',c.formation)} · 间距${c.spacing_m}m · 高度${c.altitude_m}m · ${c.speed_mmps/1000}m/s · SNR ${c.reference_snr_cdb/100}dB · 起伏${c.jitter_percent}% · ${c.faults?'含故障注入':'无故障'}${c.external_node?` · 外部业务端=${String(c.external_node).padStart(2,'0')}`:''}`;}
 renderView();}catch(e){if(ticket!==previewRequest)return;$('configError').textContent=e.message.replace('reference_snr_cdb 范围为 0–4500','参考 SNR 范围为 0–45 dB');$('configHash').textContent='请先修正参数';}updateButtons();if(window.renderWorkbench)window.renderWorkbench();}
function taskName(t){return t==='network'?'整机网络实验':t==='capacity'?'负载扫描':t==='connect'?'连接中':t||'未知任务';}
function updateButtons(){const busy=!!S.busy, modelBusy=!!S.assistant_busy, replay=!!history, connected=!!S.connected&&!pollFailed;
 // 每个禁用按钮都写明原因，避免「点了没反应、也说不清为什么」
 const setBtn=(id,disabled,reason)=>{const el=$(id);if(!el)return;el.disabled=!!disabled;if(disabled)el.title=reason||'当前不可用';else el.removeAttribute('title');};
 const busyR=busy?`正在运行（${taskName(S.task)}），结束后才可操作`:replay?'正在回放历史记录：请先点「返回当前实板」':'当前不可用';
 // Editing only prepares a draft. Hardware changes require a new experiment;
 // keeping draft controls usable also avoids a stale disabled state after stop.
 for(const id of ['configFields','signalControls'])setBtn(id,replay,'历史记录配置只读；请先返回当前实板');
 for(const id of geometry)$(id).disabled=replay;
 for(const id of ['resetConfig','connect','program'])setBtn(id,busy||replay,busyR);
 setBtn('start',busy||replay||!validConfig||!connected,busy?`正在运行（${taskName(S.task)}），请先中止`:replay?'正在回放历史记录：请先点「返回当前实板」':!connected?'尚未连接开发板：先选串口，再点「检查连接」':!validConfig?'当前配置未通过校验：请看下方提示':'当前不可用');
 setBtn('pause',!busy||S.task!=='network'||S.status==='paused'||S.pause_requested||replay,!busy?'实验未在运行':S.task!=='network'?'只有整机网络任务可暂停':(S.status==='paused'||S.pause_requested)?'已经处于暂停中':replay?'回放模式下不可用':'当前不可用');
 setBtn('resume',!busy||S.task!=='network'||!S.pause_requested||replay,!S.pause_requested?'只有先「暂停」过，才需要「继续」':replay?'回放模式下不可用':'当前不可用');
 setBtn('stop',!busy||S.task!=='network'||replay,!busy?'实验未在运行，无需中止':S.task!=='network'?'整机网络任务可在此中止；负载扫描请用「停止扫描」':replay?'回放模式下不可用':'当前不可用');
 setBtn('capacityStop',!busy||S.task!=='capacity'||replay,!busy?'负载扫描未在运行':S.task!=='capacity'?'仅负载扫描可在此停止':'当前不可用');
 for(const id of ['labRun','labBatch','verify','capacityRun'])setBtn(id,busy||replay||!connected,busy?`正在运行（${taskName(S.task)}）；单链路实验与整机任务互斥`:replay?'回放模式下不可用':!connected?'尚未连接开发板：先选串口，再点「检查连接」':'当前不可用');
 setBtn('sendCommand',!busy||S.task!=='network'||!S.snapshot||replay||pollFailed,!busy?'需要先开始整机实验，指令才有真实链路可走':S.task!=='network'?'仅整机网络任务期间可下发指令':!S.snapshot?'尚未收到第一帧实收数据，稍等':'当前不可用');
 setBtn('ask',modelBusy||window.isAssistantPending?.()||!V.snapshot,modelBusy?'本地模型正在生成回答，请稍候':!V.snapshot?'先运行实验或载入历史记录，再根据实收数据分析':'问题正在提交');
 if(window.syncInstrumentChoices&&typeof window.syncInstrumentChoices==='function')try{window.syncInstrumentChoices();}catch(e){}
 window.updateWorkspaceStatus?.();
 window.refreshAssistantContext?.();
}
function nodeData(n){const s=V.snapshot;if(!s){const p=preview?.nodes.find(x=>x.id===n);return p?{id:n,xyz:p.xyz_m,truth:p.xyz_m,preview:true,known:false,fresh:false,age:null}:null;}const v=s.nodes.find(x=>x[0]===n);if(!v)return null;const age=v[9]?s.round/10-v[10]/1000:null;return {id:n,xyz:v.slice(4,7).map(x=>x/1000),truth:v.slice(1,4).map(x=>x/1000),known:v[9]>0,fresh:age!==null&&age<=3,age,updates:v[9],arrival:v[7]/1000};}
function render(){if(history)return;V={snapshot:S.snapshot,phy_live:S.phy_live,phy_links:S.phy_links||{},metrics:S.metrics||{},scene:S.scene||[],link_windows:S.link_windows||[],advice:S.advice||[]};renderView();}
function renderView(){window.measurementReplayActive=!!history;const s=V.snapshot,m=V.metrics||{};const source=history?'历史实板记录 · 只读回放':window.currentLab?.()?'单帧实测信道与接收；网络计数和地图保留上一轮':s?'本轮实板结果 · UART 接收':'配置预览 · 尚未开始实板实验';setT('sourceLabel',source+(s?.scene_time_scale>1?` · 飞行场景时间 ${(s.scene_ms/1000).toFixed(1)} s / 网络仿真用时 ${(s.round/10).toFixed(1)} s · ${s.scene_time_scale}×场景扫描`:''));$('sourcebar')?.classList.toggle('history',!!history);const rl=$('returnLive');if(rl)rl.hidden=!history;$('replayControls').hidden=!history;setT('runStatus',history?history.id:(({'firmware':'固件加载','connect':'设备检查','network':'网络实验','lab':'文字收发','labnoise':'10帧噪声测试','capacity':'容量扫描','verify':'收发自检'}[S.task]||'')+' · '+(S.status==='stopped'?'已中止':S.error||taskStatus(S))));$('device').textContent=pollFailed?'显控服务未连接':S.connected?'板卡最近检查正常':'尚未检查板卡';$('device').className='badge '+(S.connected&&!pollFailed?'good':'warning');$('carrier').disabled=!!history;setSmooth($('delivery'),m.delivery,pct);$('deliveryDetail').textContent=s?`${num(s.delivered)} / ${num(s.generated)} 条唯一业务`:'等待实板数据';setSmooth($('timely'),m.timely_delivery,pct);const fresh=s?s.nodes.filter(n=>nodeData(n[0]).fresh).length:null;$('fresh').innerHTML=(fresh===null?'—':fresh)+'<em>/16</em>';setSmooth($('pending'),s?.pending,x=>num(x));$('lateDetail').textContent=s?`已送达但超时 ${num(s.late_delivered)} 条`:'同时关注延迟与积压';const scale=s?.scene_time_scale||s?.config?.reserved||Number($('sceneScale').value)||1,flight=s?(s.scene_ms!=null?s.scene_ms/1000:s.round/10*scale):0,limit=(s?s.duration_s:Number($('seconds').value))*scale;setPlain($('modelTime'),clock(flight));$('modelDuration').textContent=limit?clock(limit):(history?'连续实验记录':S.busy?'持续运行 · 手动结束':s?'连续实验 · 已结束':'持续运行 · 手动结束');$('progress').max=limit||Math.max(900*scale,flight);setSmoothValue($('progress'),flight);
const cfg=s?.config||preview?.config||catalog?.defaults;if(cfg){let name=catalog.environment[cfg.environment]?.name;if(cfg.environment===0&&s)name=['旷野','郊区','城市'][Math.min(2,Math.floor((s.scene_ms??s.round*100)/300000))]+' · 连续演示';$('sceneName').textContent=name+' / '+catalog.weather[cfg.weather].name+' / '+catalog.formation[cfg.formation].name;}
$('mapCaption').textContent=history?'历史回放：航标按模型真值轨迹连续移动（1 模型秒采样插值）；实心点为该记录的地面实收心跳。播放速度不代表当时计算速度。':s?'航标连续位置 = 模型真值轨迹（已标注）；实心圆点与尾迹 = 地面实收心跳（验收依据）；连线表示固定路由。':'配置预览只显示模型位置；运行后航标按真值轨迹连续移动，实收心跳以圆点叠加。';
renderNode();renderAdvice();renderEvents();renderBiz();updateButtons();drawMap();if(tab==='evidence')drawTech();if(window.renderWorkbench)window.renderWorkbench();$('exportRecord').textContent=currentRecordId()||'请先载入一条历史记录，或完成一次实板实验。';}
function renderNode(){window.renderLiveReturn?.();const n=nodeData(selected);$('selectedNodeTitle').textContent=`节点 ${String(selected).padStart(2,'0')}`;$('nodeSelect').value=selected;$('nodeState').textContent=!n?'等待数据':n.preview?'模型预览':!n.known?'尚无实收位置':n.fresh?'位置新鲜':'位置已过期';$('nodeState').className='badge '+(n?.fresh?'good':'warning');const xyz=n&&(n.preview||n.known)?n.xyz:null;const rows=[['角色',[9,13].includes(selected)?'FPGA 硬件端点':selected%4===0?'ARM 中继节点':'ARM 虚拟节点'],['固定路径',`${Math.floor((selected-1)/4)+1} 组 → 中继 ${Math.ceil(selected/4)*4}`],['X / Y（米）',xyz?`${num(xyz[0],1)} / ${num(xyz[1],1)}`:'无实收样本'],['高度（米）',xyz?num(xyz[2],1):'—'],['位置年龄',n?.age!=null?num(n.age,1)+' 通信秒':'—'],['实收心跳数',num(n?.updates)]];$('nodeDetails').innerHTML=rows.map(x=>`<div><span>${esc(x[0])}</span><b>${esc(x[1])}</b></div>`).join('');const names={1:'已进入发送队列',2:'已收到执行成功回报',3:'已收到拒绝回报',4:'已收到过期回报',5:'未获执行确认'};const cs=(V.snapshot?.command_results||S.commands||[]).filter(c=>c[1]===selected);$('commandStatus').innerHTML=cs.map(c=>`<div><b>指令 #${c[0]}</b> · ${names[c[4]]||'未知状态'}<br><small>操作 ${commandName(c[2])} · 参数 ${c[3]}</small></div>`).join('');}
function commandName(op){return {1:'查询状态',2:'心跳周期',3:'媒体暂停/恢复',4:'媒体速率',5:'模拟高度'}[op]||String(op);}
function prepareCommand(a){pendingAction=a;$('confirmText').innerHTML=`<p>目标：<b>节点 ${a.target}</b></p><p>操作：<b>${esc(commandName(a.opcode))}</b>；参数：<b>${a.value}</b></p><p>有效期 ${a.ttl_ms/1000} 模型秒。当前实验 <code>${esc(S.network_record_id)}</code></p>`;$('confirmDialog').showModal();}
function commandInput(){const op=Number($('commandOp').value),v=$('commandValue');const specs={1:[0,0,0,1,'无参数。目标回报经多跳链路返回。'],2:[100,10000,1000,100,'单位毫秒，100–10000，必须是100的倍数。'],3:[0,1,1,1,'1 暂停、0 恢复；只影响该节点支持的普通媒体业务。'],4:[1,5,2,1,'每模型秒1–5个媒体分片；不改变心跳和告警优先级。'],5:[100,800,450,1,'仅模拟高度；100–800米、单次变化不超过100米。节点执行后按场景时间平滑变化10秒；地面以实际收到的新心跳确认变化。']};const x=specs[op];if(op===5){const cfg=V.snapshot?.config;if(window.terrainModel?.enabled(cfg)){x[0]=Math.max(100,Math.ceil([37,15,28,37,21,233,125,118][cfg.environment]+.024*cfg.spacing_m+1));x[4]+=` 本区域最小允许高度 ${x[0]} m。`;}const n=nodeData(selected);if(n?.known)x[2]=Math.max(x[0],Math.min(800,Math.round(n.xyz[2])-50));}[v.min,v.max,v.value,v.step]=x.slice(0,4);v.disabled=op===1;$('commandHelp').textContent=x[4];}
function renderAdvice(){
 const box=$('advice'), issues=V.snapshot?.recovery?.issues||[];
 const rows=issues.map(i=>{
  if(i.kind==='congestion')return i.command?'建议'+i.command.replace('媒体速率','将媒体速率降至')+' 片/秒，优先传心跳。':'建议降低普通媒体速率，优先传心跳。';
  if(i.kind==='heartbeat')return i.slow_period_ms?(i.command?'建议节点'+i.node+'心跳间隔 1000毫秒，恢复每秒上报。':i.advice):'建议检查节点 '+i.node+' 至中继的上行接收。';
  if(i.kind==='link')return '建议检查 '+(i.link+1)+' → '+((i.link+1)%4?i.link+2:'地面')+' 的遮挡，先比较提高高度后的接收率。';
  return '';
 }).filter(Boolean);
 const command=issues.find(i=>i.slow_period_ms&&i.command)?.command;
 const html=[...new Set(rows)].map(r=>'<p>'+esc(r)+'</p>').join('')+
   (command&&S.busy&&!history?'<button type="button" data-draft="'+esc(command)+'">填写文字指令</button>':'');
 if(box.dataset.lastAdvice!==html){box.innerHTML=html;box.dataset.lastAdvice=html;}
}
function renderEvents(){const s=V.snapshot;const alarmNames={1:'节点2中断事件',2:'节点2恢复事件',3:'中继12异常事件',4:'中继12恢复事件'};let rows=[];for(const a of s?.alarm_events||[]){rows.push(`<div class="event"><time>模型 ${clock(a[2]/1000)}</time>${esc(alarmNames[a[0]]||'实收告警')} · 报告节点 ${a[1]}</div>`);}if(!history)for(const e of (S.events||[]).slice(-8))rows.push(`<div class="event ${esc(e.level)}"><time>电脑 ${esc(e.time)}</time>${esc(e.text)}</div>`);$('events').innerHTML=rows.reverse().slice(0,12).join('')||'<p class="empty">尚无接收告警。</p>';}
function currentRecordId(){return history?.id||S.network_record_id||S.record_id;}
/* 固定路由：节点 n 的下一跳是 n+1，遇 4 的倍数直连地面站 00（与固件 txrxPairs 一致） */
function hopPath(node){if(!node)return [];const path=[node];let cur=node;while(cur%4!==0){cur+=1;if(cur>16)break;path.push(cur);}path.push(0);return path;}
function pathText(node){const p=hopPath(node);return p.map(n=>String(n).padStart(2,'0')).join(' → ');}
function renderBiz(){const cfg=S.snapshot?.config||S.config||{},ext=cfg.external_node||0,running=!history&&S.busy&&S.task==='network'&&['running','paused'].includes(S.status);
 // 固件事实：EXTINJECT 只接受「本实验配置的外部业务端节点」注入；TX 选择不决定报文发送节点。
 const sender=ext,hops=sender?hopPath(sender).length-1:0;
 const state=$('bizState');
 if(state)state.innerHTML=sender
  ?(running?`发送节点 <b>${String(sender).padStart(2,'0')}</b> · 去向：<b>${pathText(sender)}</b>（${hops} 跳）· <b class="goodtext">可发送</b>`
           :`发送节点 <b>${String(sender).padStart(2,'0')}</b> · 去向：${pathText(sender)}（${hops} 跳）· 实验运行中才可发送`)
  :'未配置外部业务端 · 不可发送（开启顶部「运行配置 / 保存载入」选一个外部业务端节点，或到顶部「运行配置 / 保存载入」设置后重跑）';
 const send=$('bizSend');
 if(send){send.disabled=!(running&&sender);
  send.title=!sender?'本实验未配置外部业务端节点：报文无处注入。请在顶部「运行配置 / 保存载入」里选一个（除 9/13），重新开跑后可发送。':!running?'实验运行中才可发送':`文字将从节点 ${String(sender).padStart(2,'0')} 经 ${pathText(sender)} 到地面，逐字节核对`;}
 const msgs=S.business_messages||[];
 const box=$('bizList');if(!box)return;
 box.innerHTML=msgs.length?msgs.map(m=>{const dur=m.complete&&m.last_rx_model_ms?((m.last_rx_model_ms-m.injected_model_ms)/1000).toFixed(1)+' 模型秒':'—';
  return `<div class="bizitem ${m.complete?'ok':'warn'}"><b>报文 #${m.msg_id} ${m.complete?'✔ 地面实收与原文逐字节一致':'⚠ 未收齐'}</b>
   <p>发送：${esc(m.text)}</p>${m.complete?`<p><b>地面实收：</b>${esc(m.received_text||'')}</p>`:''}
   <p class="bizpath"><b>去向：</b>${pathText(m.node)} · ${hopPath(m.node).length-1} 跳 · 每跳由 FPGA 完成调制/信道/解调</p>
   <small>${m.frames_received}/${m.frames_total} 帧重组 · 注入于 ${(m.injected_model_ms/1000).toFixed(0)} 模型秒${m.complete?`，收齐于 ${(m.last_rx_model_ms/1000).toFixed(0)} 模型秒（全程 ${dur}）`:''}${m.complete?'':' · 实验结束时未收齐，缺失帧已留证'}</small></div>`;}).join('')
 :(sender?(running?'<p class="empty">尚无报文。输入文字点「发送」，文字将从节点 '+String(sender).padStart(2,'0')+' 经 '+pathText(sender)+' 到地面。</p>':'<p class="empty">开始实验后（运行中）才可发送真实报文。</p>'):'<p class="empty">未配置外部业务端节点：开启顶部「运行配置 / 保存载入 → 外部业务端节点」选一个（除 9/13），重新开跑后，文字报文将从该节点经 FPGA 多跳链路到地面并逐字节核对。</p>');}
function canvasSize(el){const rect=el.getBoundingClientRect(),dpr=window.devicePixelRatio||1;if(rect.width<1||rect.height<1)return null;const w=rect.width,h=rect.height;if(el.width!==Math.round(w*dpr)||el.height!==Math.round(h*dpr)){el.width=Math.round(w*dpr);el.height=Math.round(h*dpr);}const g=el.getContext('2d');g.setTransform(dpr,0,0,dpr,0,0);g.clearRect(0,0,w,h);return {g,w,h};}
let mapTargets=[];function drawMap(){if(window.drawInstrumentMap){window.drawInstrumentMap();return;}const ctx=canvasSize($('map'));if(!ctx)return;const {g,w,h}=ctx,pad=40;
const displayNodes=Array.from({length:16},(_,i)=>nodeData(i+1)).filter(Boolean),coords=displayNodes.filter(n=>n.preview||n.known).map(n=>n.xyz).concat([[5000,5000]]);
let xmin=0,xmax=10000,ymin=0,ymax=10000;
if($('mapView').value==='fleet'&&coords.length>1){const xs=coords.map(x=>x[0]),ys=coords.map(x=>x[1]);xmin=Math.max(0,Math.min(...xs)-300);xmax=Math.min(10000,Math.max(...xs)+300);ymin=Math.max(0,Math.min(...ys)-300);ymax=Math.min(10000,Math.max(...ys)+300);const cx=(xmin+xmax)/2,cy=(ymin+ymax)/2;let xr=Math.max(1600,xmax-xmin),yr=Math.max(1600,ymax-ymin);xr=Math.min(10000,Math.max(xr,yr*(w-2*pad)/(h-2*pad)));yr=Math.min(10000,Math.max(yr,xr*(h-2*pad)/(w-2*pad)));xmin=Math.max(0,Math.min(10000-xr,cx-xr/2));xmax=xmin+xr;ymin=Math.max(0,Math.min(10000-yr,cy-yr/2));ymax=ymin+yr;}
const scale=Math.min((w-2*pad)/(xmax-xmin),(h-2*pad)/(ymax-ymin)),ox=(w-(xmax-xmin)*scale)/2,oy=(h-(ymax-ymin)*scale)/2,xy=p=>[ox+(p[0]-xmin)*scale,oy+(ymax-p[1])*scale];
$('mapExtent').textContent=`视域 ${num((xmax-xmin)/1000,1)} × ${num((ymax-ymin)/1000,1)} km / 总场景 10 × 10 km`;mapTargets=[];g.fillStyle='#071722';g.fillRect(0,0,w,h);const cfg=V.snapshot?.config||preview?.config||catalog?.defaults;let env=cfg?.environment||0;if(!env)env=V.snapshot?([1,3,4][Math.min(2,Math.floor((V.snapshot.scene_ms??V.snapshot.round*100)/300000))]):1;
const mapped=window.drawOfflineMap?.(g,xy,w,h,env,cfg?.weather||0);
// Grid fallback remains explicit if offline imagery is unavailable.
if(!mapped&&(env===4||env===3||env===2)){g.fillStyle='#183047';for(let i=0;i<55;i++){const x=(i*371)%9500,y=(i*887)%9500;const [a,b]=xy([x,y]);g.fillRect(a,b,Math.max(2,scale*(env===4?260:150)),Math.max(3,scale*(120+(i%5)*60)));}}else if(!mapped&&env>=5){g.strokeStyle='#294039';for(let k=0;k<9;k++){g.beginPath();for(let i=0;i<=60;i++){const x=10000*i/60,y=1000+k*800+300*Math.sin(i*.19+k);const [a,b]=xy([x,y]);i?g.lineTo(a,b):g.moveTo(a,b);}g.stroke();}}
g.strokeStyle='#1a3445';g.lineWidth=.65;const grid=(xmax-xmin)>6000?1000:500;g.font='10px Consolas';g.fillStyle='#50748c';for(let x=Math.ceil(xmin/grid)*grid;x<=xmax;x+=grid){const [a,b]=xy([x,ymax]);g.beginPath();g.moveTo(a,oy);g.lineTo(a,oy+(ymax-ymin)*scale);g.stroke();g.fillText(num(x/1000,1),a-5,oy+(ymax-ymin)*scale+15);}for(let y=Math.ceil(ymin/grid)*grid;y<=ymax;y+=grid){const [a,b]=xy([xmin,y]);g.beginPath();g.moveTo(ox,b);g.lineTo(ox+(xmax-xmin)*scale,b);g.stroke();g.fillText(num(y/1000,1),ox-28,b+3);}g.strokeStyle='#346073';g.strokeRect(ox,oy,(xmax-xmin)*scale,(ymax-ymin)*scale);g.fillStyle='#658da3';g.font='11px Consolas';g.fillText('N ↑',w-45,29);
const nodes=Array.from({length:16},(_,i)=>nodeData(i+1)).filter(Boolean),byId=Object.fromEntries(nodes.map(n=>[n.id,n]));
for(const n of nodes){const to=n.id%4===0?0:n.id+1;const dest=to===0?{xyz:[5000,5000,0],preview:true,known:true,fresh:true}:byId[to];if(!dest||(!n.preview&&!n.known)||(!dest.preview&&!dest.known))continue;const a=xy(n.xyz),b=xy(dest.xyz),group=Math.floor((n.id-1)/4),colors=['#41d4cf','#569cf5','#af97ef','#f2b267'];const link=V.link_windows?.find(x=>x.link_id===n.id-1);g.strokeStyle=!n.preview&&!n.fresh?'#b66e4c':colors[group];g.globalAlpha=.45;g.setLineDash(n.id%4===0?[5,5]:[]);g.lineWidth=link?.active?1.5:1;g.beginPath();g.moveTo(...a);g.lineTo(...b);g.stroke();g.setLineDash([]);g.globalAlpha=1;const mid=[a[0]*.4+b[0]*.6,a[1]*.4+b[1]*.6],ang=Math.atan2(b[1]-a[1],b[0]-a[0]);g.beginPath();g.moveTo(mid[0]-6*Math.cos(ang-.5),mid[1]-6*Math.sin(ang-.5));g.lineTo(...mid);g.lineTo(mid[0]-6*Math.cos(ang+.5),mid[1]-6*Math.sin(ang+.5));g.stroke();}
if($('showTruth').checked&&V.snapshot){for(const n of nodes){const [x,y]=xy(n.truth);g.strokeStyle='#567485';g.setLineDash([2,3]);g.strokeRect(x-7,y-7,14,14);g.setLineDash([]);}}
for(const n of nodes){if(!n.preview&&!n.known)continue;const [x,y]=xy(n.xyz),color=n.preview?'#6b91a5':n.fresh?'#67e1e5':'#ffc26e';if(n.id===selected){g.fillStyle='#4bddee15';g.beginPath();g.arc(x,y,23,0,Math.PI*2);g.fill();g.strokeStyle='#4bddee80';g.stroke();}g.strokeStyle=color;g.fillStyle='#092238';g.lineWidth=1.5;g.beginPath();if(n.id%4===0){g.moveTo(x,y-9);g.lineTo(x+9,y);g.lineTo(x,y+9);g.lineTo(x-9,y);g.closePath();}else{g.arc(x,y,7,0,Math.PI*2);}g.fill();g.stroke();g.fillStyle=color;g.font='bold 11px Consolas';g.fillText(String(n.id).padStart(2,'0'),x+11,y+4);mapTargets.push({x,y,id:n.id});}
const [gx,gy]=xy([5000,5000]);g.font='22px sans-serif';g.fillStyle='#e3eff9';g.textAlign='center';g.fillText('★',gx,gy+6);g.font='10px '+getComputedStyle(document.body).fontFamily;g.fillText('地面站',gx,gy+23);g.textAlign='left';if(V.snapshot){const missing=nodes.filter(n=>!n.known).map(n=>n.id);if(missing.length){g.fillStyle='#f8bd74';g.font='11px '+getComputedStyle(document.body).fontFamily;g.fillText('尚无实收位置：'+missing.join(', '),18,h-42);}}}
function plotAxes(id,xlabel,ylabel){const c=canvasSize($(id));if(!c)return null;const {g,w,h}=c;g.strokeStyle='#243d50';g.lineWidth=1;g.beginPath();g.moveTo(35,16);g.lineTo(35,h-28);g.lineTo(w-14,h-28);g.stroke();g.fillStyle='#7c9db5';g.font='10px Consolas';g.fillText(xlabel,w-55,h-10);g.fillText(ylabel,5,13);return {...c,px:35,py:16,pw:w-49,ph:h-44};}
function drawIQ(id,points){const c=plotAxes(id,'I','Q');if(!c)return;const {g,px,py,pw,ph}=c;const bound=Math.max(800,...(points||[]).flat().map(Math.abs))*1.18;g.strokeStyle='#1f3649';g.beginPath();g.moveTo(px+pw/2,py);g.lineTo(px+pw/2,py+ph);g.moveTo(px,py+ph/2);g.lineTo(px+pw,py+ph/2);g.stroke();g.fillStyle='#64dedeb0';for(const p of points||[]){g.beginPath();g.arc(px+pw/2+p[0]/bound*pw*.46,py+ph/2-p[1]/bound*ph*.46,1.5,0,Math.PI*2);g.fill();}if(!points?.length){g.fillStyle='#7391a5';g.fillText('NO RX SAMPLES',px+20,py+ph/2);}}
function drawChannel(){const id=Number($('linkSelect').value),c=window.observedChannel?window.observedChannel(id):V.scene?.find(x=>x.link_id===id);if(!c||c.applied===false){setT('channelSource','等待实际应用参数；不使用旧实验值代替。');$('channelDetails').innerHTML='<p class="empty">尚无此链路应用记录</p>';plotAxes('cir','sample','|h|');plotAxes('cfr','MHz','dB');return;}const rows=[['链路',c.lab_id?'单链路文字收发':`${c.tx} → ${c.rx} / ${id%4===3?'空地':'空空'}`],['模型距离 / 米',c.lab_id?'手动信道，不绑定几何距离':num(c.distance_m,1)],['噪声标准差',num(c.sigma,1)],['主径频偏 / Hz',num(c.cfo_hz,1)],['主径 / 反射径增益',`${num(c.gain0,3)} / ${num(c.gain1,3)}`],['传播 / 反射时延',`${c.delay_samples} / ${c.echo_delay_samples} 样本`]];$('channelDetails').innerHTML=rows.map(x=>`<div><span>${x[0]}</span><b>${esc(x[1])}</b></div>`).join('');elOf('channelSource').textContent=(c.lab_id?'单帧 '+c.lab_id+' 参数写入并逐项读回确认。':c.reference?.includes('READBACK')?'FPGA 寄存器实读回；最近应用时刻 '+(c.model_ms/1000)+' 模型秒。':'该时刻的场景模型参考；不是本次寄存器实读回。')+' CIR/CFR 是应用系数的响应，不是接收估计。'+(c.lab_id?'':'寄存器快照最大间隔100模型秒。');/* PDP 实际绘制在 instrument.js（renderInstruments 会覆盖此处并带读回历史与动画） */
const a=plotAxes('cir','额外时延 / μs','dB');if(a){const {g,px,py,pw,ph}=a,m=Math.max(.01,c.gain0,c.gain1),delay=Math.max(4,c.echo_delay_samples*1.3);g.fillStyle='#83a7bd';g.font='10px sans-serif';g.fillText('相对主径时延',px+40,py+13);}
const b=plotAxes('cfr','MHz','dB');if(b){const {g,px,py,pw,ph}=b;g.strokeStyle='#5cd8e4';g.lineWidth=1.5;g.beginPath();for(let i=0;i<=160;i++){const f=-4e6+i/160*8e6,p0=c.phase_radians||0,p1=(c.echo_phase_radians||0)-2*Math.PI*f*c.echo_delay_samples/8e6;const real=c.gain0*Math.cos(p0)+c.gain1*Math.cos(p1),imag=c.gain0*Math.sin(p0)+c.gain1*Math.sin(p1),db=20*Math.log10(Math.max(.001,Math.hypot(real,imag)));const x=px+i/160*pw,y=py+ph-(Math.max(-40,Math.min(6,db))+40)/46*ph;i?g.lineTo(x,y):g.moveTo(x,y);}g.stroke();g.fillStyle='#779bb3';g.font='10px Consolas';g.fillText('-4',px,py+ph+14);g.fillText('0',px+pw/2,py+ph+14);g.fillText('+4',px+pw-10,py+ph+14);}}
/* 逐链路计数明细：10 模型秒滚动窗口增量。温和平场景下捕获率/确认率/BER 本来就恒为
   完美值，看上去「一动不动」是事实；这里把相对上一窗口发生变化的单元格高亮出来，
   并把变化项数写进标题，让「变/没变」一眼可判。面板已移到右栏最底部且默认收起。 */
const lwPrev = window._lwPrev || (window._lwPrev = { run: null, rows: {} });
function drawLinkTable(rows){
  const el = $('linkTable'); if (!el) return;
  const rid = V.snapshot?.run_id;
  if (lwPrev.run !== rid) { lwPrev.run = rid; lwPrev.rows = {}; }
  let changed = 0;
  /* 右栏宽度有限，列格式做紧凑化：百分比取整、BER 前后合并一格、类别放 title。 */
  const pc = v => v == null ? '—' : Math.round(v * 100) + '%';
  const br = v => v == null ? '—' : (v < 1e-6 ? '0' : v.toExponential(1));
  el.innerHTML = rows.map(r => {
    let tx = r.link_id % 16 + 1, rx = tx % 4 ? tx + 1 : 0;
    if (r.link_id >= 16) [tx, rx] = [rx, tx];
    const cur = [r.data_attempts, r.capture_rate, r.hop_success, r.retries, r.pre_ber, r.post_ber, r.evm_percent];
    const old = lwPrev.rows[r.link_id];
    const dif = i => old && old[i] !== cur[i];
    if ([0,1,2,3,4,5,6].some(dif)) changed++;
    lwPrev.rows[r.link_id] = cur;
    const c = (i, txt) => `<td class="${dif(i) ? 'chg' : ''}">${txt}</td>`;
    return `<tr><td title="${r.link_id % 4 === 3 ? '空地' : '空空'}${r.link_id >= 16 ? '下行' : '上行'}链路 ${r.link_id}">${tx}→${rx === 0 ? '地面' : rx}</td>`
      + c(0, r.data_attempts ?? 0) + c(1, pc(r.capture_rate)) + c(2, pc(r.hop_success)) + c(3, r.retries ?? 0)
      + c(4, br(r.pre_ber) + '→' + br(r.post_ber))
      + c(6, num(r.evm_percent, 1) + (r.evm_percent == null ? '' : '%')) + `</tr>`;
  }).join('');
  setT('linkWindow', rows.length
    ? `${rows[0].start_model_ms / 1000}–${rows[0].end_model_ms / 1000} 模型秒 · ${changed} 项变化`
    : '等待实测');
}
function drawTech(){const points=window.receiverPoints?window.receiverPoints():S.lab?.iq;drawIQ('iqBefore',points?.received);drawIQ('iqAfter',points?.equalized);drawChannel();drawLinkTable(V.link_windows||[]);
if(S.lab&&$('labResult')){const r=S.lab;$('labResult').innerHTML=`<b class="${r.match?'goodtext':'warntext'}">${r.match?'96 字节完全一致，CRC 独立核对通过':'本帧未成功接收，错误数据不交付'}</b><p>发送：${esc(r.text)}<br>接收：${esc(r.received_text||'无有效正文')}${r.failure_stage?'<br>原因：'+esc(r.failure_stage):''}</p><p>本帧种子 ${esc(r.config.seed)} · ${r.config.modem_profile?'DBPSK 硬判决扩展':'DBPSK 软判决'} · ${r.config.fec?'完整纠错':'关闭纠错对照'}<br>帧头 ${r.registers?.['100']?'已捕获':'未捕获'} · 纠错前编码位错误 ${num(r.phy.pre_errors)} / ${num(r.phy.pre_bits)} · 纠错后错误 ${num(r.phy.post_errors)} / ${num(r.phy.post_bits)}</p><span>估计频偏 ${num(r.estimated_cfo_hz,1)} Hz · EVM ${num(r.payload_evm_percent,2)}%</span><details><summary>本帧参数与原始收发字节</summary><p>增益 ${num(r.config.gain,3)} · 噪声 σ ${num(r.config.sigma)} · 标称复采样信噪比 ${num(r.nominal_sample_snr_db,2)} dB（不是 Eb/N0）</p><p>TX ${esc(r.tx_hex)}</p><p>RX ${esc(r.rx_hex||'未交付')}</p><p>记录 ${esc(r.id)}</p></details><p class="labwhy"><b>这帧结果对项目意味着什么：</b>${labWhy(r)}</p>`;}
/* 把单帧结果翻译成网络层后果：不然用户只看到「一致/不一致」，不知道它影响什么 */
function labWhy(r){
 const sig=r.config.sigma||0,snr=r.nominal_sample_snr_db,pre=r.phy?.pre_errors||0,post=r.phy?.post_errors||0;
 if(r.match&&!sig)return `本次零噪声、指定信道条件下，96 字节逐字节一致，完成了本帧收发验证。它是一个基准样本；接收范围和网络可靠性仍需多种条件、多帧及多跳实验确认。`;
 if(r.match&&sig)return `本次 σ=${sig}（标称复采样 SNR ${num(snr,1)} dB）下完整收到本帧；纠错前编码位错误 ${num(pre)}，纠错后错误 ${num(post)}。这不等于已经测出接收门限：固定条件、更换种子重复测试，才能统计失败率。多跳业务影响请看网络实测。`;
 if(!r.match&&sig)return `本次 σ=${sig}（标称复采样 SNR ${num(snr,1)} dB）下本帧失败${r.failure_stage?`（${esc(r.failure_stage)}）`:''}，错误正文未交付。一个失败样本不能确定门限；请保持其他参数不变，分组改变噪声并重复测试，再比较成功率与样本数量。`;
 return `本帧未成功接收。先确认参数是否越界（增益 0–1、σ 0–8192），再逐步加噪声定位门限。`;}
if(S.lab_batch&&$('labBatchResult')){const b=S.lab_batch;$('labBatchResult').innerHTML=`<b class="${b.finished&&b.target_met?'goodtext':'warntext'}">${b.finished?'测试完成':'测试进度'}：${b.completed}/10 帧，完整接收 ${b.delivered} 帧</b><p>${b.finished?'本轮成功率 '+pct(b.rate)+(b.target_met?'，达到9/10目标。':'，未达到9/10目标。'):'每帧只发送一次，不重传。'}${b.error?' 已中断：'+esc(b.error):''}</p><small>${b.rows.map((x,i)=>`${i+1}：${x.match?'成功':'失败'}`).join(' · ')}</small><details><summary>各帧种子和记录</summary>${b.rows.map(x=>`<p>${x.seed} · ${esc(x.id)} · ${x.match?'字节与CRC一致':esc(x.failure_stage)}</p>`).join('')}</details>`;}

if(S.capacity&&$('capacityResult')){const c=S.capacity;elOf('capacityResult').textContent=c.measured_sustainable_payload_bps!=null?`本次扫描：${num(c.measured_sustainable_payload_bps)} bit/s 附加业务容量。${c.scope}`:`扫描进行中：${JSON.stringify(c).slice(0,250)}`;}if(window.renderInstruments)window.renderInstruments();if(window.refreshStudy)window.refreshStudy();}
async function refreshRecords(){records=await api('/api/records');const network=records.filter(r=>r.kind==='network');$('records').innerHTML=network.slice(0,40).map(r=>`<article class="record"><div><b>${r.seconds?`${r.seconds} 模型秒`:'未完成实验'} · ${r.complete?'已留存结果':r.failed?'中止 / 错误':'记录中'}</b><small>${esc(r.id)}</small><small>${r.final?`最终送达 ${pct(r.final.delivered/r.final.generated)} · 种子 ${r.seed}`:'未形成完整统计'}</small></div><button data-record="${esc(r.id)}">查看 / 回放</button></article>`).join('')||'<p class="empty">暂无本版记录。</p>';$('records').querySelectorAll('[data-record]').forEach(b=>b.onclick=()=>loadRecord(b.dataset.record).catch(e=>toast(e.message,true)));for(const id of ['compareLeft','compareRight']){const old=$(id).value;$(id).innerHTML=network.filter(r=>r.complete).map(r=>`<option value="${esc(r.id)}">${esc(r.id)} · ${r.seconds}s</option>`).join('');if(network.some(r=>r.id===old))$(id).value=old;}if($('compareLeft').value===$('compareRight').value&&$('compareRight').options.length>1)$('compareRight').selectedIndex=1;}
async function loadRecord(id){if(S.busy)throw Error('请先结束或中止当前实板任务，再进入历史回放。');stopReplay();draftConfig=readConfig();history=await api('/api/record?id='+encodeURIComponent(id));if(!history.snapshots.length){history=null;throw Error('此记录没有网络采样点');}setConfig(history.report?.config||history.snapshots[0].config||catalog.defaults);historyIndex=history.snapshots.length-1;const last=history.snapshots[historyIndex];$('linkSelect').value=String(last.observation?.link??last.watch_link??0);$('replayRange').max=historyIndex;$('replayRange').value=historyIndex;await showHistory(historyIndex);showTab('evidence');toast('已进入只读历史模式，并选中记录中实际采样的链路；按钮不能操作板卡。');}
let historyRequest=0;async function showHistory(index){const ticket=++historyRequest,id=history?.id;if(!id)return;const view=await api(`/api/record_view?id=${encodeURIComponent(id)}&index=${index}`);if(ticket!==historyRequest||history?.id!==id)return;historyIndex=index;V=view;$('replayRange').value=index;renderView();$('wallTime').textContent='原始全流程 '+num(history.report?.wall_total_seconds,2)+' 秒';}
function stopReplay(){clearInterval(replayTimer);replayTimer=null;$('replayPlay').textContent='播放历史';}
function updateWall(){if(history)return;const r=S.report;if(S.busy&&S.started){$('wallTime').textContent='本任务已用 '+num((Date.now()/1000-S.started),1)+' 秒';}else if(r)$('wallTime').textContent='实测全流程 '+num(r.wall_total_seconds,2)+' 秒';else $('wallTime').textContent='尚无全流程耗时';}
async function poll(){
 try{S=await api('/api/state');pollFailed=false;}catch(e){pollFailed=true;$('device').textContent='显控服务未连接';elOf('runStatus').textContent=e.message;window.WorkbenchBoot?.warn('连接中断，正在重试读取；未发送任何重复命令。');setTimeout(poll,1500);return;}
 try{const key=[S.busy,S.status,S.report?.reproduction?.exact_match,S.snapshot?.run_id,S.snapshot?.round,S.events?.length,S.lab?.id,S.lab_batch?.completed,S.lab_batch?.finished,S.capacity?.rows?.length,S.connected,S.error].join(':');if(key!==lastRenderKey){render();lastRenderKey=key;}updateButtons();updateWall();window.WorkbenchBoot?.recovered();}catch(e){console.error('界面更新失败',e);window.WorkbenchBoot?.warn('界面更新失败：'+e.message+'；后台连接正常。');}
 setTimeout(poll,700);
}
function renderEvidence(){
 const r=info.resources;
 if(!r){elOf('resources').textContent='当前版本资源与时序尚未验收。';}
 else{
  const memory=r.runtime_measurement_pending?'运行栈堆等待当前版本整机测量':`栈保守峰值 ${num(r.stack_peak_bound_bytes)} / ${num(r.stack_reserved_bytes)} B；堆峰值 ${num(r.heap_peak_bytes)} / ${num(r.heap_reserved_bytes)} B`;
  elOf('resources').innerHTML=['LUT','FF','DSP48','BRAM36','Slice'].map(k=>`<div class="resource"><span>${k}</span><div class="bar"><i style="width:${r[k].used/r[k].available*100}%"></i></div><span>${pct(r[k].used/r[k].available)}</span></div>`).join('')+`<p class="hint">WNS ${r.WNS_ns} ns / WHS ${r.WHS_ns} ns<br>ARM 静态数据与 BSS ${num(r.ARM_ELF_data_bytes+r.ARM_ELF_bss_bytes)} 字节<br>${memory}</p>`;
 }
 const runs=evidence.ui_runs||[],current=evidence.version===info.firmware;
 if(current&&evidence.accepted&&runs.length===3){
  elOf('acceptanceEvidence').innerHTML=`<b>当前镜像 ${esc(evidence.version)}：三次整机验收通过</b><p>${runs.map(x=>`${num(x.wall_s,2)} 秒 · 最终送达 ${pct(x.delivery)}`).join('<br>')}<br>每次900模型秒；当前任务的结果另行显示。按时送达与最终送达分别统计。</p>`;
 }else{
  elOf('acceptanceEvidence').textContent=`${current?'当前':'历史'}镜像 ${evidence.version||'待记录'}：尚无本版完整整机验收结论，不沿用旧版通过状态。`;
 }
 if(evidence.noise_qualification){const n=evidence.noise_qualification;elOf('acceptanceEvidence').innerHTML+=`<p><b>噪声专项 · PL ${esc(n.version)}</b><br>${n.delivered}/${n.trials} 帧完整接收（${pct(n.rate)}），固定声明条件、不同种子、无重传；不是所有噪声条件的保证。</p>`;}
 elOf('capacityResult').textContent=evidence.capacity?`已记录实测：${num(evidence.capacity.payload_bps)} bit/s 附加业务容量。${evidence.capacity.scope}`:'等待当前版本容量测试。';
 const paired=evidence.paired_energy_comparison;
 elOf('receiverSummary').textContent=evidence.receiver?`已记录接收范围测试：${evidence.receiver.frames} 帧 / ${evidence.receiver.configurations} 组实板配置。${paired?.coding_benefit_at_tested_point?`另有同净荷、同总帧能量、同种子且无削顶的配对实板比较，在声明的${paired.payload_ebn0_db} dB工作点完整纠错接收${paired.summary['1'].delivered}/${paired.summary['1'].trials}、关闭纠错${paired.summary['0'].delivered}/${paired.summary['0'].trials}；该点收益不代表所有信道或完整编码增益曲线。`:'尚未完成同总帧能量纠错收益验证。'}失败点与捕获损失均保留。`:'等待当前版本接收范围测试。';
 const bw=evidence.model_bandwidth?.occupied_bandwidth_hz?.['90'];
 elOf('bandwidth').textContent=`数字基带模型：Fs 8 MHz、DBPSK 2 Msymbol/s、矩形四采样符号；参考主瓣零点间宽度 4 MHz。${bw?`参考 Welch 90%占用带宽 ${num(bw/1e6,3)} MHz。`:''}不是实测射频带宽，也不是持续板卡 I/O 速率。`;
 elOf('boundaries').innerHTML=(evidence.boundaries||[]).map(x=>`<li>${esc(x)}</li>`).join('');
}
async function init(){[catalog,info]=await Promise.all([api('/api/catalog'),api('/api/info')]);evidence={accepted:false};for(const name of ['environment','weather','formation'])$(name).innerHTML=catalog[name].map(x=>`<option value="${x.id}">${x.name}</option>`).join('');$('port').innerHTML=info.ports.length?info.ports.map(p=>`<option value="${p.port}" ${p.description.includes('CH340')?'selected':''}>${esc(p.port)} · ${esc(p.description)}</option>`).join(''):'<option>COM4</option>';$('nodeSelect').innerHTML=Array.from({length:16},(_,i)=>`<option value="${i+1}">${String(i+1).padStart(2,'0')}</option>`).join('');$('externalNode').innerHTML='<option value="0">无（默认）</option>'+Array.from({length:16},(_,i)=>i+1).filter(n=>n!==9&&n!==13).map(n=>`<option value="${n}">节点 ${String(n).padStart(2,'0')}（由外部业务端替代）</option>`).join('');$('linkSelect').innerHTML=Array.from({length:32},(_,i)=>{let a=i%16+1,b=a%4?a+1:0;if(i>=16)[a,b]=[b,a];return `<option value="${i}">${String(i).padStart(2,'0')} · ${a===0?'地面':a} → ${b===0?'地面':b} · ${i%4===3?'空地':'空空'}</option>`;}).join('');await resumeCurrentWorkspace();if(typeof suggestTelemetry==='function')suggestTelemetry();try{renderEvidence();}catch(e){console.error('辅助证据面板：',e);}commandInput();renderView();poll();window.WorkbenchBoot?.ready();api('/api/evidence').then(x=>{evidence=x;renderEvidence();}).catch(e=>{elOf('acceptanceEvidence').textContent='验收资料暂不可读；实时实验仍可使用。'+e.message;});try{if(!localStorage.getItem('swarm_guide_shown')){$('guide').showModal();localStorage.setItem('swarm_guide_shown','1');}}catch(e){console.warn('浏览器未允许保存使用指引状态；不影响实验。');}}
// User actions are deliberately distinct from evidence rendering and replay.
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>showTab(b.dataset.tab));for(const fieldset of ['configFields','signalControls','channelControls'])$(fieldset).addEventListener('input',()=>{validConfig=false;updateButtons();clearTimeout(configTimer);configTimer=setTimeout(previewConfig,250);});$('formation').addEventListener('change',()=>window.syncChoices?.());
action('resetConfig',()=>{setConfig(catalog.defaults);$('seed').value=20261009;$('seconds').value=0;$('telemetry').value=10;$('ideal').value=0;});
const SCENE_PRESETS={presetBaseline:{name:'基准对照',config:{environment:1,weather:0,formation:0,spacing_m:300,altitude_m:400,center_x_m:5000,center_y_m:5000,speed_mmps:12000,heading_deg:0,faults:1,jitter_percent:100},note:'旷野 · 晴天 · X形基准轨迹 · 含短时中断。几何参数可调并保存；SNR 由你在信道设置中独立调节，预设不改动它。'},presetHarsh:{name:'城市恶劣',config:{environment:4,weather:4,formation:8,spacing_m:800,altitude_m:400,center_x_m:5000,center_y_m:5000,speed_mmps:12000,heading_deg:0,faults:1,jitter_percent:150},note:'城市 · 大雨 · 环形编队 · 间距 800 m。预期出现重传、积压与送达时延上升；SNR 由你在信道设置中独立调节。'},presetSevere:{name:'极恶劣',config:{environment:4,weather:7,formation:8,spacing_m:1100,altitude_m:600,center_x_m:5000,center_y_m:5000,speed_mmps:16000,heading_deg:0,faults:1,jitter_percent:200},note:'城市 · 大雪 · 环形 · 间距 1100 m · 最大起伏。用于压力对照，不声称真实气象；SNR 由你在信道设置中独立调节。'}};
for(const id of Object.keys(SCENE_PRESETS))action(id,()=>{const p=SCENE_PRESETS[id];setConfig({...readConfig(),...p.config});toast('已填入「'+p.name+'」：'+p.note+' 参数在下一次开始的实验生效。');});
let telemetryTouched=false;$('telemetry').addEventListener('change',()=>{telemetryTouched=true;});
function suggestTelemetry(){$('telemetry').value='10';}
$('seconds').addEventListener('change',()=>{if(!telemetryTouched)suggestTelemetry();});action('connect',async()=>{try{return await api('/api/connect',{port:$('port').value});}catch(e){const m=e.message||'';throw Error(m+(/PING|deadline|超时|无响应|拒绝/i.test(m)?'。若板卡刚断电重上电，请先点顶栏「上电后加载固件」，再检查连接。':''));}});action('program',()=>api('/api/program',{port:$('port').value}));action('start',async()=>{await previewConfig();if(!validConfig)return;await launchNetwork({seconds:Number($('seconds').value),ideal:Number($('ideal').value),seed:Number($('seed').value),config:readConfig(),telemetry_rounds:Number($('telemetry').value)});toast('已开始准备。耗时包含参数核对、媒体上传、实际计算和读回。');});for(const id of ['pause','resume','stop'])action(id,()=>api('/api/'+id,{}));action('capacityStop',()=>api('/api/stop',{}));action('saveConfig',async()=>{const r=await api('/api/config/save',{config:readConfig()});toast('已保存：'+r.path);});action('importConfig',()=>$('configFile').click());$('configFile').onchange=async e=>{try{const f=e.target.files[0];if(!f||f.size>8192)throw Error('请选择小于8KB的配置JSON');const d=JSON.parse(await f.text());const cfg=(await api('/api/preview',{config:d.config||d})).config;setConfig(cfg);toast('配置已载入；开始前仍会由 ARM 校验。');}catch(e){toast(e.message,true);}finally{$('configFile').value='';}};
$('mapView').onchange=drawMap;$('showTruth').onchange=drawMap;$('map').onclick=e=>{const r=$('map').getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;let best=mapTargets.map(n=>({...n,d:Math.hypot(n.x-x,n.y-y)})).sort((a,b)=>a.d-b.d)[0];if(best&&best.d<25){selected=best.id;renderNode();drawMap();}};$('nodeSelect').onchange=()=>{selected=Number($('nodeSelect').value);renderNode();drawMap();};$('linkSelect').onchange=()=>{drawTech();renderBiz();if(window.renderWorkbench)window.renderWorkbench();syncTxRx();(!history?api('/api/watch',{link_id:Number($('linkSelect').value)}):Promise.resolve()).catch(e=>toast(e.message,true));};
/* TX/RX 用户自选（限固定路由 32 条有向链路），与链路选择器双向同步 */
const txrxPairs=[];for(let i=0;i<32;i++){let a=i%16+1,b=a%4?a+1:0;if(i>=16)[a,b]=[b,a];txrxPairs.push([a,b]);}
const nodeOpts='<option value="0">地面</option>'+Array.from({length:16},(_,i)=>`<option value="${i+1}">${String(i+1).padStart(2,'0')}</option>`).join('');
$('txNode').innerHTML=nodeOpts;$('rxNode').innerHTML=nodeOpts;
function rxOptions(tx,preferred){const el=$('rxNode'),peers=txrxPairs.filter(p=>p[0]===tx).map(p=>p[1]);if(el.dataset.tx!==String(tx)){el.innerHTML=peers.map(n=>`<option value="${n}">${n?String(n).padStart(2,'0'):'地面'}</option>`).join('');el.dataset.tx=String(tx);}el.value=String(peers.includes(preferred)?preferred:peers[0]);}
function syncTxRx(){const p=txrxPairs[Number($('linkSelect').value)||0];$('txNode').value=p[0];rxOptions(p[0],p[1]);}
function applyTxRx(){const a=Number($('txNode').value),b=Number($('rxNode').value);const i=txrxPairs.findIndex(p=>p[0]===a&&p[1]===b);if(i<0){toast('该 TX→RX 不在固定路由（4 条链 × 4 跳）内；中间处理由系统自动完成',true);syncTxRx();return;}$('linkSelect').value=String(i);$('linkSelect').dispatchEvent(new Event('change'));}
$('txNode').onchange=()=>{rxOptions(Number($('txNode').value),Number($('rxNode').value));applyTxRx();};$('rxNode').onchange=applyTxRx;syncTxRx();
/* 自主设置模式：信道只由用户显式填写的抽头、损耗和频偏决定。 */
$('customMode').onchange=e=>{window.setChannelMode?.(e.target.checked?2:1);previewConfig();};
/* ── 自主设置模式：左栏几何参数与第 2 页隐藏字段双向同步，确保真正下发 ── */
const RAIL_PAIRS=[['rail_spacing_m','spacing_m'],['rail_altitude_m','altitude_m'],['rail_center_x_m','center_x_m'],
 ['rail_center_y_m','center_y_m'],['rail_heading_deg','heading_deg'],['rail_seed','seed'],
 ['rail_external_node','externalNode'],['rail_seconds','seconds']];
function syncRailFromConfig(){for(const [a,b] of RAIL_PAIRS){const ra=$(a),rb=$(b);if(ra&&rb&&rb.value!=='')ra.value=rb.value;}$('rail_faults').checked=$('faults').checked;}
let railGuard=false;
for(const [a,b] of RAIL_PAIRS){const ra=$(a);if(!ra)continue;ra.addEventListener('change',()=>{if(railGuard)return;const rb=$(b);if(!rb)return;rb.value=ra.value;rb.dispatchEvent(new Event('change',{bubbles:true}));rb.dispatchEvent(new Event('input',{bubbles:true}));previewConfig();});}
$('rail_faults').addEventListener('change',()=>{$('faults').checked=$('rail_faults').checked;$('faults').dispatchEvent(new Event('change',{bubbles:true}));previewConfig();});
for(const b of ['spacing_m','altitude_m','center_x_m','center_y_m','heading_deg','seed','externalNode','seconds','faults']){const rb=$(b);if(!rb)continue;rb.addEventListener('change',()=>{if(!$('customMode').checked)return;syncRailFromConfig();});}
/* ── 文字实测两块切换（单帧物理层 / 多跳组网业务）── */
const labPanes={frame:$('labFramePane'),hop:$('labHopPane')};
document.querySelectorAll('#labTabs button').forEach(btn=>btn.onclick=()=>{
 document.querySelectorAll('#labTabs button').forEach(b=>b.classList.toggle('selected',b===btn));
 for(const [k,el] of Object.entries(labPanes))if(el)el.hidden=(k!==btn.dataset.lab);
});
/* 固化实验记录图：点击放大 */
$('rxStudyCanvas')?.addEventListener('click',()=>{
 const dlg=$('chartDialog');if(!dlg)return;
 $('largeChartTitle').textContent='实板接收范围与纠错性能对照（历史实验基线）';
 const area=dlg.querySelector('.large-chart-area');area.replaceChildren();
 const big=document.createElement('canvas');big.style.cssText='width:100%;height:auto;display:block;border-radius:8px';
 area.append(big);
 if(window.drawStudy)window.drawStudy(big); // 高分辨率重绘，含实时工作点
 $('largeChartNote').textContent='历史基线单链路实验。网络送达率与单帧接收率定义不同，不叠加为同一种工作点；请核对基线使用的固件版本。';
 dlg.showModal();});
/* 场景复杂度 → 速度/间距联动建议（导师纪要：复杂度不同，速度距离应适当调整） */
const ENV_SUGGEST={1:[12,600],2:[11,550],3:[10,500],4:[8,400],5:[7,350],6:[9,450],7:[12,600]};
const MOUNTAIN_X_SPACING_M=900;
function applySceneGeometry(event){
 if($('customMode').checked)return;
 const environment=Number($('environment').value),s=ENV_SUGGEST[environment];
 if(!s)return;
 const mountain=environment===5,finalFormation=mountain&&Number($('formation').value)===0&&Number($('weather').value)===0;
 if(event.target.id!=='environment'&&!mountain)return;
 if(event.target.id==='environment'&&$('speed').dataset.manual!=='1')$('speed').value=s[0];
 if($('spacing_m').dataset.manual!=='1')$('spacing_m').value=finalFormation?MOUNTAIN_X_SPACING_M:s[1];
 syncRailFromConfig();
}
for(const id of ['environment','weather','formation'])$(id).addEventListener('change',applySceneGeometry);
$('commandOp').onchange=commandInput;action('sendCommand',()=>prepareCommand({target:selected,opcode:Number($('commandOp').value),value:Number($('commandValue').value),ttl_ms:10000}));action('confirmCommand',async()=>{const r=await api('/api/command',{confirm:true,run_id:S.snapshot?.run_id,record_id:S.network_record_id,action:pendingAction});$('confirmDialog').close();toast(`指令 #${r.request.command_id} 已排队；尚未确认执行。`);});
action('ask',()=>window.runExperimentAssistant());
action('bizSend',async()=>{const ext=Number(S.snapshot?.config?.external_node||S.config?.external_node||0);if(!ext)throw Error('本实验未配置外部业务端节点，报文无处注入。开启顶部「运行配置 / 保存载入」选一个外部业务端节点（除 9/13），或到顶部「运行配置 / 保存载入」设置后重新开跑。');const r=await api('/api/business/message',{text:$('bizText').value,node:ext});toast(`报文 #${r.msg_id} 已注入：节点 ${String(r.node).padStart(2,'0')} → ${pathText(r.node)}（${hopPath(r.node).length-1} 跳）· ${r.frames} 帧，收齐后逐字节核对。请在实验中段发送，尾声可能来不及。`);});

action('mapCapture',async()=>{const r=await api('/api/capture',{png:$('map').toDataURL('image/png')});toast('地图已保存：'+r.path);});action('refreshRecords',refreshRecords);action('returnLive',()=>{stopReplay();history=null;historyRequest++;if(draftConfig)setConfig(draftConfig);render();});$('replayRange').oninput=()=>{stopReplay();showHistory(Number($('replayRange').value)).catch(e=>toast(e.message,true));};action('replayPlay',async()=>{if(replayTimer){stopReplay();return;}if(historyIndex>=history.snapshots.length-1)await showHistory(0);$('replayPlay').textContent='暂停回放';const duration=history.report?.duration_s||900,step=135*1000/Math.max(1,history.snapshots.length-1);replayTimer=setInterval(()=>{if(!history||historyIndex>=history.snapshots.length-1){stopReplay();return;}showHistory(historyIndex+1).catch(e=>{stopReplay();toast(e.message,true);});},step);});
action('compare',async()=>{const r=await api(`/api/compare?left=${encodeURIComponent($('compareLeft').value)}&right=${encodeURIComponent($('compareRight').value)}`);const names={delivery:'最终送达',timely_delivery:'按时送达',pre_ber:'纠错前 BER',post_ber:'纠错后 BER',fec_corrected_bits:'纠错链纠正位数',p95_upper_ms:'P95上界 / ms',max_ms:'最大时延 / ms',mean_ms:'平均时延 / ms',payload_bps:'有效吞吐 / bit/s',wall_seconds:'全流程 / s'},fmt=(k,v)=>v==null?'—':['delivery','timely_delivery'].includes(k)?pct(v):['pre_ber','post_ber'].includes(k)?(v===0?'0':Number(v).toExponential(2)):num(v,2);$('compareResult').innerHTML=`<div class="resultbox"><b class="${r.controlled_single_setting_comparison?'goodtext':'warntext'}">${esc(r.label||'描述性对比')}</b><p>${esc((r.reasons||[]).join('；'))}</p><p>变更配置：${Object.keys(r.changed_config||{}).length?esc(JSON.stringify(r.changed_config)):'无配置字段变化'}</p><p>${esc(r.preset_note||'')}</p></div><div class="tablewrap"><table><tr><th>指标</th><th>A</th><th>B</th><th>B − A</th></tr>${Object.keys(names).filter(k=>r.left[k]!=null||r.right[k]!=null).map(k=>`<tr><td>${names[k]}</td><td>${fmt(k,r.left[k])}</td><td>${fmt(k,r.right[k])}</td><td>${fmt(k,r.delta[k])}</td></tr>`).join('')}</table></div><p class="hint">${esc(r.qualification||'相同种子不等于相同能量口径；重传可能改变采样时刻。')}</p>`;});document.querySelectorAll('[data-export]').forEach(b=>b.onclick=async()=>{try{const id=currentRecordId();if(!id)throw Error('请先选择记录');const view=$('exportView');view.innerHTML='<p class="empty">读取证据中…</p>';const kind=b.dataset.export;
if(kind==='report'){const html=await (await fetch(`/api/report?id=${encodeURIComponent(id)}&preview=1`)).text();view.innerHTML='';const f=document.createElement('iframe');f.className='evidence-frame';f.srcdoc=html;view.append(f);}
else if(kind==='csv'){const text=await (await fetch(`/api/csv?id=${encodeURIComponent(id)}&preview=1`)).text();const rows=text.trim().split('\n').map(l=>l.split(','));view.innerHTML=`<div class="tablewrap"><table>${rows.map((r,i)=>`<tr>${r.map(c=>i?`<td>${esc(c)}</td>`:`<th>${esc(c)}</th>`).join('')}</tr>`).join('')}</table></div>`;}
else{const d=await api(`/api/record_evidence?id=${encodeURIComponent(id)}`);const a=d.acceptance||{};view.innerHTML=`<div class="resultbox"><b>记录 ${esc(d.id)}</b> · ${d.complete?'实验记录完整':'未形成完整记录'}<br>时长 ${a.duration_s??'—'} 模型秒 · 墙钟 ${num(a.wall_total_seconds,1)} s · 加速 ${num(a.acceleration,2)}× · 送达 ${a.delivered??'—'}/${a.generated??'—'} · 媒体齐 ${a.all_media_complete?'是':'否'}</div><div class="tablewrap"><table><tr><th>证据文件</th><th>字节</th><th>SHA-256</th></tr>${d.files.map(f=>`<tr><td>${esc(f.name)}</td><td>${num(f.bytes)}</td><td class="hashcell">${f.sha256}</td></tr>`).join('')}</table></div><p class="hint">以上为当前文件摘要；UART 与快照摘要还会在重算前核对。完整文件位于 ${esc(d.id)} 记录目录与 exports。</p>`;}
}catch(e){toast(e.message,true);$('exportView').innerHTML='<p class="empty">证据读取失败：'+esc(e.message)+'</p>';}});
action('labRun',()=>{if($('labNewSeed').checked){let seed=0;while(!seed)seed=crypto.getRandomValues(new Uint32Array(1))[0];$('labSeed').value=seed;}const seed=Number($('labSeed').value);if(!Number.isInteger(seed)||seed<1||seed>4294967295)throw Error('种子须为1–4294967295的整数');const cfg=window.readLabParameters();return api('/api/lab',{text:$('labText').value,...cfg,fec:Number($('labFec').value),seed});});action('labBatch',()=>{$('labPreset').value='noise';window.labPresetValues();return api('/api/lab/batch',{text:$('labText').value,fec:Number($('labFec').value)});});action('verify',()=>api('/api/verify',{}));action('capacityRun',()=>api('/api/capacity',{}));action('help',()=>$('guide').showModal());action('fullscreen',()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen());window.addEventListener('resize',()=>{drawMap();if(tab==='evidence')drawTech();if(window.renderInstruments)window.renderInstruments();});
/* ── 跨模块小函数（原来散在已移除的 usability.js / live-control.js / workbench.js，统一收在这里）── */
/* 地图左下角观测来源标签：instrument.js / terrain-view.js 都引用它 */
window.mapObservationLabel=()=>{
 const s=V.snapshot;
 if(history)return '历史实收 · 只读回放';
 if(!s)return '配置预览 · 尚无实板接收位置';
 const known=s.nodes.filter(n=>n[9]>0).length;
 return `地面实收 · 通信 ${Math.floor(s.round/10)} 秒 · ${known}/16 节点有实收位置`;
};
/* 运行中点击场景卡片：不能静默，要告诉用户何时生效 */
window.requestSceneChoice=(kind,id,name)=>{
 if(S.busy){toast(`实验运行中，场景选择已锁定。「${name}」未生效；请先中止或等实验结束后再选择。`,true);}
 else toast('正在回放历史记录：请先点「返回当前实板」再改场景。',true);
};
let startupAttempt=0;async function bootWorkbench(){try{await init();}catch(e){console.error('界面初始化失败',e);window.WorkbenchBoot?.fail('界面初始化失败：'+e.message);if(++startupAttempt<3)setTimeout(bootWorkbench,1500);}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bootWorkbench,{once:true});else setTimeout(bootWorkbench,0);

for(const id of ['speed','spacing_m'])document.getElementById(id).addEventListener('input',e=>{e.currentTarget.dataset.manual='1';});
