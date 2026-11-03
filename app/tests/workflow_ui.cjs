const {chromium}=require(process.env.SWARM_PLAYWRIGHT || 'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),out=path.join(root,'results','workflow_ui');fs.mkdirSync(out,{recursive:true});
const url=(process.env.SWARM_TEST_URL || 'http://127.0.0.1:18878'),phase=process.argv[2]||'all',phases=phase==='all'?['causal','comparison','height','full']:phase.split(',');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.SWARM_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const get=async p=>{const r=await page.request.get(url+p),d=await r.json();assert(r.ok(),JSON.stringify(d));return d;};
 const post=async(p,data)=>{const r=await page.request.post(url+p,{data}),d=await r.json();assert(r.ok(),JSON.stringify(d));return d;};
 const wait=async(fn,endpoint='/api/state',ms=240000)=>{const until=Date.now()+ms;while(Date.now()<until){const s=await get(endpoint);if(s.status==='error'||s.experiment?.phase==='error')throw Error(s.error||s.experiment.error);if(fn(s))return s;await page.waitForTimeout(300);}throw Error('Timeout '+endpoint);};
 const causal=fn=>wait(fn,'/api/causal/state');
 const save=(name,obj)=>fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify({...obj,release_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'release.json'))).digest('hex')},null,2));
 async function ask(question){
  await page.locator('[data-side="advice"]').click();
  await page.locator('.assistantPanel details').evaluate(e=>e.open=true);await page.locator('#question').fill(question);
  const start=Date.now(),request=page.waitForResponse(r=>r.url().endsWith('/api/assistant')&&r.request().method()==='POST');await page.locator('#ask').click();
  const response=await request,job=await response.json();assert(response.ok(),JSON.stringify(job));assert(job.provisional);
  const initial_seconds=(Date.now()-start)/1000;assert(initial_seconds<3,'Immediate facts must not wait for the model');
  await page.waitForFunction(()=>!document.getElementById('assistantStatus').textContent.includes('正在筛选'),null,{timeout:40000});
  const done=await get('/api/assistant/job?id='+job.id);assert.equal(done.status,'complete');assert.equal(done.actions_executed,0);assert(done.result.model_used,'Real local model should participate');
  return {...done,initial_seconds,total_seconds:(Date.now()-start)/1000};
 }
 try{
  await page.goto(url+'/#causal');await page.waitForFunction(()=>typeof catalog!=='undefined'&&catalog&&document.getElementById('configHash').textContent.includes('校验通过'));
  await page.locator('#connect').click();await wait(s=>s.connected&&!s.busy);assert.deepEqual(errors,[]);
  if(phases.includes('causal')){
   await page.locator('#cxLink').selectOption('4');await page.locator('#cxSeconds').fill('120');await page.locator('#cxStart').click();let s=await causal(s=>s.experiment?.phase==='waiting');const id=s.experiment.id;
   await page.locator('#cxWindow').fill('10');await page.locator('#cxAdvance').click();await causal(s=>s.experiment?.latest?.round===200&&s.experiment.phase==='waiting');await page.waitForFunction(()=>window.actionContext?.model_ms===20000);
   await page.locator('[data-tab="mission"]').click();const rate=await ask('把节点5媒体生成速率降到1分片/秒，这能改善什么，不能改善什么？');assert.equal(rate.record_id,id);assert.equal(rate.as_of_model_ms,20000);
   assert.equal((await get('/api/causal/state')).experiment.commands.length,0);
   await page.locator('#answer .wf-proposal').first().click();await page.locator('#actionDialog').waitFor({state:'visible'});await page.locator('#actionConfirm').click();
   s=await causal(s=>s.experiment?.latest?.round===300&&s.experiment.phase==='waiting');assert.equal(s.experiment.commands[0].status,'confirmed');assert.equal(s.experiment.commands[0].after.generated_fragments_per_s,1);
   const stale=await page.request.post(url+'/api/assistant/prepare',{data:{id:rate.id,evidence_id:'command_proposal'}});assert(!stale.ok());
   await page.waitForFunction(()=>window.actionContext?.model_ms===30000);const effect=await ask('节点5降低媒体速率后积压和心跳改善了吗？');assert(effect.result.answer.includes('源端生成速率'));
   const radio=await ask('当前链路实际应用的幅度、噪声和频偏是多少？');const applied=radio.result.evidence.find(x=>x.id==='applied_frame');assert(applied,'Current-frame applied parameters must be explained');
   const observed=(await get('/api/causal/state')).experiment.latest.observation;assert.deepEqual(applied.evidence.registers,observed.applied);assert.equal(applied.evidence.generation,observed.meta[15]);
   const height=await ask('让节点9高度设为450米');assert(height.result.answer.includes('固定几何'));assert(!height.result.evidence.some(x=>x.action?.opcode===5));
   await page.locator('#sharedContext [data-jump="action"]').click();await page.locator('#actionTarget').selectOption('5');await page.locator('#actionValue').fill('5');await page.locator('#actionPrepare').click();await page.locator('#actionConfirm').click();await causal(s=>s.experiment?.latest?.round===400&&s.experiment.phase==='waiting');
   await page.locator('#cxFinish').click();s=await causal(s=>s.experiment?.phase==='complete'&&!s.busy);assert(s.experiment.report.all_media_complete);
   await page.locator('#sharedContext [data-jump="history"]').click();await page.locator('#cxRefresh').click();await page.locator('#cxRecords').selectOption(id);await page.locator('#cxView').click();await page.locator('#cxReplayRange').fill('24');await page.locator('#cxReplayRange').dispatchEvent('input');await page.waitForFunction(()=>window.actionContext?.model_ms===25000&&window.actionContext.mode==='history');
   await page.locator('#sharedContext [data-jump="mission"]').click();const past=await ask('节点5的媒体措施执行了吗，效果怎样？');assert.equal(past.as_of_model_ms,25000);assert(past.result.evidence.every(x=>!x.action));assert.equal(await page.locator('#video').getAttribute('src'),null);
   const future=await page.request.post(url+'/api/assistant/prepare',{data:{id:past.id,evidence_id:'command_proposal'}});assert(!future.ok());
   await page.screenshot({path:path.join(out,'history_assistant.png'),fullPage:true});
   await page.locator('#sharedContext [data-jump="history"]').click();await page.locator('#cxReproduce').click();s=await causal(s=>s.experiment?.id!==id&&s.experiment?.phase==='complete'&&!s.busy);assert(s.experiment.report.reproduction.exact_match);
   save('causal',{pass:true,id,recomputed:s.experiment.id,reproduction:s.experiment.report.reproduction,rate,effect,radio,height,past,errors});console.log('CAUSAL_AI_PASS',id);
  }
  if(phases.includes('comparison')){
   await page.evaluate(()=>window.openCausalLive());await page.locator('#cxSetup').evaluate(e=>e.open=true);await page.locator('#cxLink').selectOption('4');await page.locator('#cxSeconds').fill('120');await page.locator('.setup-advanced').evaluate(e=>e.open=true);await page.locator('#cxWeather').selectOption('0');await page.locator('#cxFormation').selectOption('4');await page.locator('#cxStart').click();let s=await causal(s=>s.experiment?.phase==='waiting');const left=s.experiment.id;
   await page.locator('#cxFinish').click();await causal(s=>s.experiment?.phase==='complete'&&!s.busy);await page.waitForFunction(()=>!S.busy);
   await page.locator('[data-tab="history"]').click();await page.locator('#wfRefresh').click();await page.locator('#wfLeft').selectOption(left);await page.locator('#workflowComparison details').last().evaluate(e=>e.open=true);await page.locator('#wfField').selectOption('weather');await page.locator('#wfValue').selectOption('4');await page.locator('#wfVariant').click();await page.locator('#wfVariantDialog').waitFor({state:'visible'});assert((await page.locator('#wfVariantText').innerText()).includes('大雨'));await page.locator('#wfVariantConfirm').click();
   s=await causal(s=>s.experiment?.id!==left&&s.experiment?.phase==='waiting');const right=s.experiment.id;assert.equal(s.experiment.plan.config.weather,4);await page.locator('#cxFinish').click();s=await causal(s=>s.experiment?.phase==='complete'&&!s.busy);
   await page.locator('[data-tab="history"]').click();await page.locator('#wfRefresh').click();await page.locator('#wfLeft').selectOption(left);await page.locator('#wfRight').selectOption(right);await page.locator('#wfCompare').click();await page.waitForFunction(()=>window.lastWorkflowComparison?.mode==='single_setting');const comparison=await page.evaluate(()=>window.lastWorkflowComparison);assert.deepEqual(Object.keys(comparison.changed_config),['weather']);assert(comparison.composite_preset);assert(fs.existsSync(comparison.saved_path));
   await page.screenshot({path:path.join(out,'comparison.png'),fullPage:true});
   await page.locator('[data-tab="mission"]').click();await page.waitForFunction(()=>window.offlineMapStatus?.().length===7);assert.equal(await page.evaluate(()=>V.snapshot.config.weather),4);
   const images=await page.evaluate(()=>window.offlineMapStatus());const offline=[];page.on('request',r=>{if(!r.url().startsWith(url)&&!r.url().startsWith('data:'))offline.push(r.url());});await page.reload();await page.waitForFunction(()=>window.offlineMapStatus?.().length===7);assert.deepEqual(offline,[]);
   save('comparison',{pass:true,left,right,comparison,images,external_requests:offline,errors});console.log('COMPARISON_PASS',left,right);
  }
  if(phases.includes('height')){
   await page.evaluate(()=>window.openCausalLive());
   if(!await page.evaluate(()=>window.actionContext)){const prior=(await get('/api/causal/records')).find(r=>r.complete);assert(prior);await page.locator('[data-tab="history"]').click();await page.locator('#cxRefresh').click();await page.locator('#cxRecords').selectOption(prior.id);await page.locator('#cxView').click();await page.waitForFunction(()=>window.actionContext);}
   await page.locator('[data-tab="mission"]').click();await page.locator('[data-side="node"]').click();await page.locator('#openHeightTask').click();await page.waitForFunction(()=>!document.getElementById('start').disabled);await page.locator('#seconds').selectOption('120');
   // Small batches keep live proposal freshness testable; the actual board still runs every hop.
   const previous=(await get('/api/state')).network_record_id,cfg=await page.evaluate(()=>readConfig());await post('/api/start',{seconds:120,seed:20261021,ideal:0,config:{...cfg,faults:0},telemetry_rounds:20});let s=await wait(s=>s.busy&&s.network_record_id!==previous&&s.network_record_id?.startsWith('network_')&&s.snapshot?.round>=100);
   await page.waitForFunction(id=>!window.actionContext&&S.network_record_id===id&&V.snapshot?.run_id===S.snapshot?.run_id,s.network_record_id);
   const id=s.network_record_id,round=s.snapshot.round;const job=await ask('让节点9高度设为450米');assert.equal(job.record_id,id);assert.equal(job.context.kind,'network');assert((await get('/api/state')).busy);const progressed=await wait(s=>s.busy&&s.snapshot?.round>round);assert(progressed);
   // Pause before regenerating a fresh proposal, so the confirmation is not based on old data.
   await post('/api/pause',{});s=await wait(s=>s.status==='paused');await page.waitForFunction(r=>V.snapshot?.round===r,s.snapshot.round);
   const fresh=await ask('让节点9高度设为450米');await page.locator('#answer .wf-proposal').first().click();await page.locator('#confirmDialog').waitFor({state:'visible'});await page.locator('#confirmCommand').click();await post('/api/resume',{});
   s=await wait(s=>s.commands?.some(c=>c[1]===9&&c[2]===5&&c[3]===450&&c[4]===2)&&s.snapshot.nodes[8][6]>440000);assert.equal(s.commands.filter(c=>c[2]===5).length,1);const executed=s.snapshot;
   s=await wait(s=>!s.busy);assert(s.report.pass);save('height',{pass:true,id,job,fresh,executed_node9:executed.nodes[8],commands:executed.command_results,report:s.report,errors});console.log('HEIGHT_AI_PASS',id);
  }
  if(phases.includes('full')){
   await page.evaluate(()=>window.openCausalLive());await page.locator('#lxNetworkMode').click();await page.locator('[data-tab="mission"]').click();await page.locator('#resetConfig').click();await page.waitForFunction(()=>!document.getElementById('start').disabled);
   await page.locator('#seconds').selectOption('900');const previous=(await get('/api/state')).network_record_id;
   await page.locator('#start').click();const running=await wait(s=>s.busy&&s.task==='network'&&s.network_record_id!==previous);const s=await wait(s=>!s.busy&&s.task==='network'&&s.network_record_id===running.network_record_id);assert(s.report.pass);assert.equal(s.report.duration_s,900);assert(s.report.all_media_complete);assert(s.report.performance_gates.delivery_above_99pct);assert(s.report.performance_gates.complete_within_120s);
   const snaps=fs.readFileSync(path.join(root,'results',s.network_record_id,'snapshots.jsonl'),'utf8').trim().split(/\r?\n/).map(JSON.parse),at=r=>snaps.find(x=>x.round===r);assert(at(3600).nodes[1][7]<330000);assert(at(4000).nodes[1][10]>370000);assert(at(6800).nodes[11][10]<=660000);assert(at(7600).nodes[11][10]>700000);
   assert.deepEqual(s.report.final.alarm_events.map(x=>x[0]),[1,2,3,4]);assert(s.report.final.nodes.every(n=>900000-n[10]<5000));assert.equal(s.report.memory_after.stack_guard_ok,1);assert.equal(s.report.memory_after.heap_failures,0);
   await page.screenshot({path:path.join(out,'full_scene.png'),fullPage:true});save('full',{pass:true,id:s.network_record_id,foreground_map:true,fault_and_recovery_checked:true,report:s.report,errors});console.log('FULL_SCENE_PASS',s.network_record_id,s.report.wall_total_seconds);
  }
  assert.deepEqual(errors,[]);
 }catch(e){await page.screenshot({path:path.join(out,'failure_'+phase+'.png'),fullPage:true});save('failure_'+phase,{error:String(e),errors});throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
