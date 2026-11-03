/* One mission, many observations. Buttons delegate to real protocol handlers. */
(()=>{
 const E=id=>document.getElementById(id),make=(tag,html)=>{const x=document.createElement(tag);x.innerHTML=html;return x;};
 const story=make('section',`<div class="story-heading"><div><small>任务：编队信息回传与通信保障</small><h2>让地面收到消息，并知道何时可以相信它</h2></div><span id="storyClock">等待实板观测</span></div><p>节点1回传语音、节点5回传视频，各节点回传位置心跳。你可以了解现场、询问建议、下发指令，再主动测试一条链路的承受能力。</p><div id="storySteps"></div><div class="story-main"><b id="storyTitle"></b><span id="storyWhy"></span><button id="storyGo" class="primary"></button></div><div class="story-tools"><button id="storyScene">现场与回传</button><button id="storyTech">信道与接收</button><button id="storyAdvice">询问AI / 看建议</button><button id="storyCommand">下发节点指令</button><button id="storyMore">继续观察10秒</button><button id="storySave">保存 / 重现</button></div><p id="storyIdentity"></p>`);story.id='missionStory';E('taskGuide').before(story);
 const engineering=make('details','<summary>工程专项工具（主线任务无需切换）</summary>');engineering.id='engineeringModes';story.before(engineering);engineering.append(E('experimentModeBar'));
 const continuous=make('label','<input type="checkbox" id="storyContinuous" checked> 持续实板演示（手动暂停/结束）');continuous.className='continuous-choice';story.querySelector('.story-tools').append(continuous);let autoRound=-1;
 const stages=['开始回传','了解现场','改变链路','诊断影响','采取措施','恢复通信','完成与重现'];let manual=0,record='',next=()=>{};
 E('storySteps').innerHTML=stages.map((s,i)=>`<button data-step="${i}">${i+1} ${s}</button>`).join('');
 E('storySteps').onclick=e=>{const b=e.target.closest('button');if(b){manual=+b.dataset.step;update();}};
 const scene=()=>showTab('mission'),tech=()=>window.openObservationPane('technical'),action=()=>window.openObservationPane('action');
 function ask(q){scene();document.querySelector('[data-side="advice"]').click();E('question').value=q;E('question').focus();if(!E('ask').disabled)E('ask').click();}
 E('storyScene').onclick=scene;E('storyTech').onclick=tech;E('storyAdvice').onclick=()=>ask('当前链路影响哪些业务，下一步应该观察什么？');E('storyCommand').onclick=action;E('storySave').onclick=()=>showTab('history');E('storyMore').onclick=()=>{E('cxWindow').value=10;if(!E('cxAdvance').disabled)E('cxAdvance').click();};E('storyGo').onclick=()=>next();
 const intel=make('section','<h3>现场简报与回传信息</h3><div id="missionIntel"></div><div class="intel-questions"><button data-q="当前天气和地形对通信意味着什么？">分析环境</button><button data-q="节点5的位置还新鲜吗？是否需要查询状态？">检查位置时效</button><button data-q="把节点5媒体生成速率设为1分片/秒，会改变什么？">讨论业务安排</button><button data-q="节点5心跳周期设为2000毫秒会有什么影响？">讨论心跳频率</button></div><small>环境来自本轮场景设置；位置来自实收心跳。没有气象或地形传感器，不将场景分析冒充无人机实测。</small>');intel.id='missionIntelPanel';intel.className='panel';document.querySelector('.rightcolumn').prepend(intel);intel.onclick=e=>{const b=e.target.closest('[data-q]');if(b)ask(b.dataset.q);};
 const recent=make('div','');recent.id='liveObservation';E('appliedTicker').after(recent);let prevKey='',lastAt=performance.now();
 function update(){
  const cp=window.causalPresentation,v=cp?.view,s=V.snapshot,readonly=!!history||!!cp?.history,waiting=cp?.active&&!readonly&&['waiting','running'].includes(v?.phase),id=v?.id||S.network_record_id||'';
  story.hidden=!cp?.active;document.body.classList.toggle('story-mode',!!cp?.active);
  if(id&&id!==record){record=id;manual=1;autoRound=-1;E('storyContinuous').checked=window.liveModeEnabled!==false;}
  if(readonly||!v||['complete','stopped','error'].includes(v.phase))E('storyContinuous').checked=false;

  const phase=v?.phase||'ready';E('storyClock').textContent=`${s?(s.round/10).toFixed(1):0} 模型秒 · ${readonly?'历史只读':phase==='waiting'?'观测暂停，等待你选择下一步':phase==='complete'?'已结束并保存':S.busy?'正在实板计算':'准备中'}`;
  E('storyIdentity').textContent=id?`本次任务 ${id} · 所选链路 ${(v?.plan?.link??4)+1}→${(v?.plan?.link??4)%4===3?'地面':(v?.plan?.link??4)+2} · 三页共享此记录`:'整个流程在同一次实验内完成；下方专项诊断仅供工程人员使用。';
  const descriptions=[['建立正常通信基线','先连接板卡。确认场景后持续计算，随时修改信道或暂停。','开始正常回传',()=>{showTab('evidence');E('cxSetup').open=true;if(!S.connected){E('connect').click();return;}if(!E('cxStart').disabled){E('cxStart').click();manual=1;}}],['了解编队正在传回什么','查看新心跳、位置和文件进度；环境简报依据本轮配置，可以主动向AI提问。','查看现场简报',scene],['让所选链路变差','只有点击应用才改变信道；先确认参数读回，再判断业务影响。','应用明显衰减（持续生效）',()=>{E('cxWindow').value=20;E('cxSevere').click();E('cxChange').click();manual=3;}],['把技术变化与业务影响对应起来','查看同一帧的信道与接收，再看位置年龄、重传和视频积压。','查看六图与接收',tech],['发送一项真实措施','建议给节点5降低媒体速率；必须检查执行回执与前后窗口，不能把入队当成功。','核对节点5限速指令',()=>{action();E('actionTarget').value=5;E('actionOp').value=4;E('actionOp').dispatchEvent(new Event('change'));E('actionValue').value=1;E('actionPrepare').click();}],['恢复条件，核对新心跳','先恢复信道，看到新消息后，可在指令面板把节点5媒体速率恢复为5。','恢复正常信道（持续观察）',()=>{E('cxWindow').value=20;E('cxRestore').click();}],['完成文件回传，保存与重现','结束后检查最终/按时送达、完整音视频；到第三页按原操作时间线重算。',phase==='complete'?'查看记录并实板重现':'运行到结束并保存',()=>phase==='complete'?showTab('history'):E('cxFinish').click()]];
  if(!v)manual=0;const [title,why,button,fn]=descriptions[manual];E('storyTitle').textContent=title;E('storyWhy').textContent=why;E('storyGo').textContent=button;next=fn;
  E('storyGo').disabled=readonly||([2,4,5].includes(manual)&&!waiting)||(manual===6&&phase!=='complete'&&!waiting)||(manual===0&&S.busy);E('storyMore').disabled=!waiting;
  E('storySteps').querySelectorAll('button').forEach((b,i)=>{b.classList.toggle('selected',i===manual);b.setAttribute('aria-current',i===manual?'step':'false');});
  const cfg=s?.config||preview?.config||catalog?.defaults;if(cfg){const env=cfg.environment||[1,3,4][Math.min(2,Math.floor((s?.round||0)/3000))],n=nodeData(selected),name=catalog?.environment.find(x=>x.id===env)?.name||'场景',weather=catalog?.weather.find(x=>x.id===cfg.weather)?.name||'晴天';
   E('missionIntel').innerHTML=`<p><b>${esc(name)} / ${esc(weather)}</b><br>场景设定 · ${s?'当前模型 '+s.round/10+' 秒':'尚未开始'}</p><p><b>节点 ${selected} ${n?.known?'已回传位置':'等待位置回传'}</b><br>${n?.known?`X ${n.xyz[0].toFixed(1)} / Y ${n.xyz[1].toFixed(1)} / Z ${n.xyz[2].toFixed(1)} 米<br>消息年龄 ${n.age.toFixed(1)} 秒 · ${n.fresh?'新鲜':'过期，不代表已知当前位置'}`:'不以模型真值替代实收位置'}</p><p>${[4,5].includes(env)?'复杂场景：重点检查回波、位置时效和重传。':'开阔或低复杂度场景：仍需以接收结果判断链路。'}${cfg.weather>=4?' 强降水/降雪预设：关注业务积压；不要仅凭天气名称认定失联。':''}</p>`;
  }
  const o=s?.observation,key=[id,s?.round,o?.meta?.[15]].join(':');if(key!==prevKey){prevKey=key;lastAt=performance.now();}
  recent.textContent=`观测 ${s?s.round/10:'—'} 模型秒 · 帧 ${o?.meta?.[15]??'—'} · ${phase==='waiting'?'已暂停：点击继续观察可获得新样本':phase==='complete'||readonly?'保存的观测，数值不会继续变化':`距最近观测更新 ${((performance.now()-lastAt)/1000).toFixed(1)} 秒`} · 无有效帧时不补画星座`;
  window.missionStoryState={record:id,phase,stage:manual,readonly,round:s?.round,observationKey:key};
 }
 E('cxLink').value='4';E('cxSeconds').value='900';
 setInterval(update,300);window.addEventListener('experiment-view',update);update();
})();
