/* Continuous real-board operation. Records remain bounded and independently replayable. */
(()=>{
 const E=id=>document.getElementById(id);window.liveModeEnabled=true;
 let ended=false,pendingScene=null,restarting=false,lastId='',segment=1,continueRun=false,lastCondition=null;
 const status=document.createElement('div');status.id='liveControl';status.innerHTML='<strong>持续实板实验</strong><button id="livePause">暂停观察</button><button id="liveEnd">结束并保存</button><span id="liveFeedback" role="status">开始后持续采集；改条件会在下一采集边界生效。</span>';E('missionStory').prepend(status);
 E('storyContinuous').closest('label').hidden=true;E('cxSeconds').closest('label').hidden=true;E('cxWindow').closest('label').hidden=true;E('cxAdvance').hidden=true;E('cxFinish').hidden=true;E('cxStart').textContent='开始持续实板实验';E('storyMore').hidden=true;
 const notify=s=>{E('liveFeedback').textContent=s;};
 async function send(kind){const v=window.causalPresentation?.view;if(!v)throw Error('请先开始实板实验');const r=await api('/api/causal/action',{id:v.id,kind,window_s:60});notify(kind==='pause'?'正在完成当前采集，随后暂停':'操作已入队，等待下一采集边界');return r;}
 E('livePause').onclick=async()=>{try{const v=window.causalPresentation?.view;await send(v?.phase==='waiting'?'resume':'pause');}catch(e){notify(e.message);}};
 E('liveEnd').onclick=async()=>{ended=true;continueRun=false;window.liveModeEnabled=false;try{await api('/api/stop',{});notify('正在停止实板并保存本段已收到的数据；部分记录不标为完整验收。');}catch(e){notify(e.message);}};
 E('cxStart').addEventListener('click',()=>{ended=false;continueRun=true;window.liveModeEnabled=true;});
 E('cxStop').addEventListener('click',()=>{continueRun=false;});
 // A scene change starts a labelled new record; never pretend an immutable plan changed in-place.
 window.requestSceneChoice=(kind,id,name)=>{if(!S.busy){const target=E({environment:'cxEnvironment',weather:'cxWeather',formation:'cxFormation'}[kind]);if(![...target.options].some(o=>+o.value===id))target.add(new Option(name,id));target.value=id;E(kind).value=id;window.renderInstruments?.();notify(`已选择${name}，下次开始实板实验生效。`);return;}pendingScene={kind,id,name};const d=E('liveSceneDialog');E('liveSceneText').textContent=`切换为${name}：保存当前段并开始新记录。原记录和实板证据保留；网络队列与模型时间从新场景重新开始。`;d.showModal();};
 const dlg=document.createElement('dialog');dlg.id='liveSceneDialog';dlg.innerHTML='<h3>切换实验场景</h3><p id="liveSceneText"></p><button id="liveSceneCancel">取消</button><button id="liveSceneApply">保存当前段并切换</button>';document.body.append(dlg);
 E('liveSceneCancel').onclick=()=>{pendingScene=null;dlg.close();};
 E('liveSceneApply').onclick=async()=>{dlg.close();restarting=true;try{await api('/api/stop',{});for(let i=0;i<180;i++){const st=await api('/api/state');if(!st.busy)break;await new Promise(r=>setTimeout(r,250));}const map={environment:'cxEnvironment',weather:'cxWeather',formation:'cxFormation'},el=E(map[pendingScene.kind]);if(![...el.options].some(o=>+o.value===pendingScene.id))el.add(new Option(pendingScene.name,pendingScene.id));el.value=pendingScene.id;pendingScene=null;continueRun=true;window.liveModeEnabled=true;for(let i=0;i<20&&E('cxStart').disabled;i++)await new Promise(r=>setTimeout(r,200));E('cxStart').click();notify('已提交新场景，等待实板配置和首批数据；新记录独立保存。');}catch(e){notify(e.message);}finally{restarting=false;}};
 // Auto-next is explicit segmentation to respect the verified firmware's 900-second limit.
 async function tick(){try{const cp=window.causalPresentation,v=cp?.view;if(!cp?.active||cp.history)return;
 if(v?.id!==lastId){lastId=v?.id||'';if(v){if(!ended&&v.plan?.continuous&&v.phase==='running')continueRun=true;notify(`第${segment}段 · ${v.id} · 持续采集实际数据`);}}
 E('livePause').textContent=v?.phase==='waiting'?'继续实板观察':'暂停观察';E('livePause').disabled=!v||!['running','waiting'].includes(v.phase);E('liveEnd').disabled=!v||!['running','waiting','queued','preparing'].includes(v.phase);
 if(v?.phase==='running'){E('storyClock').textContent=`${(v.latest?.round||0)/10} 模型秒 · 持续实板计算`;E('liveFeedback').textContent=`第${segment}段 · 实收${(v.latest?.round||0)/10}模型秒 · 每段独立保存，900秒后自动新段；可随时暂停/结束` ;}
 if(v?.phase==='complete'&&continueRun&&!restarting&&!v.replaying){restarting=true;segment++;lastCondition=[...(v.events||[])].reverse().find(e=>['change','restore'].includes(e.action.kind))?.action;notify('本段已完成，正在自动开始下一实板段（时间与队列重置，非同一连续仿真）。');for(let i=0;i<20&&E('cxStart').disabled;i++)await new Promise(r=>setTimeout(r,200));if(!continueRun)return;E('cxStart').click();if(lastCondition?.kind==='change'){for(let i=0;i<200;i++){await new Promise(r=>setTimeout(r,200));const n=window.causalPresentation?.view;if(n?.id!==v.id&&n?.phase==='running'){await api('/api/causal/action',{...lastCondition,id:n.id});break;}}}restarting=false;}
 }catch(e){restarting=false;continueRun=false;notify('持续运行已停：'+e.message);}finally{setTimeout(tick,250);}}tick();
 // Preset controls act now, rather than silently editing inputs.
 for(const id of ['cxMild','cxSevere'])E(id).addEventListener('click',()=>{if(!E('cxChange').disabled){E('cxChange').click();notify('预设已提交；以寄存器读回确认实际生效。');}else notify('条件已填入；开始实验后点击应用。');});
 // Every unavailable control explains why instead of swallowing clicks.
 document.addEventListener('pointerdown',e=>{const el=e.target.closest('button,input,select');if(el?.disabled)notify(window.causalPresentation?.history?'当前为历史只读。返回当前实验后操作。':S.busy?'当前阶段暂不可用；信道可实时修改，场景卡片可另开新段。':'先连接板卡并开始实验；记录类操作需先选中记录。');},true);
})();
