const {chromium}=require(process.env.SWARM_PLAYWRIGHT || 'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const R=path.resolve(__dirname,'..'),out=path.join(R,'results','action_ui');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.SWARM_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const url='http://127.0.0.1:8883',get=async()=>await(await page.request.get(url+'/api/causal/state')).json();
 const wait=async pred=>{const stop=Date.now()+240000;while(Date.now()<stop){const d=await get();if(d.experiment?.phase==='error')throw Error(d.experiment.error);if(pred(d))return d;await page.waitForTimeout(300);}throw Error('Board wait timeout');};
 try{
  await page.goto(url+'/#causal');await page.waitForTimeout(1700);assert.deepEqual(errors,[]);console.log('UI_LOADED');
  if(process.argv.includes('--smoke')){await page.screenshot({path:path.join(out,'entry.png'),fullPage:true});console.log('UI_SMOKE_OK');return;}
  await page.locator('#connect').click();await wait(d=>d.connected&&!d.busy);
  await page.locator('#cxLink').selectOption('4');await page.locator('#cxSeconds').fill('120');
  const prior=(await get()).experiment?.id;await page.locator('#cxStart').click();let d=await wait(d=>d.experiment?.id!==prior&&d.experiment?.phase==='waiting');const id=d.experiment.id;console.log('BASELINE',id);
  await page.locator('#cxWindow').fill('10');await page.locator('#cxAdvance').click();d=await wait(d=>d.experiment?.latest?.round===200&&d.experiment.phase==='waiting');
  await page.waitForFunction(()=>window.actionContext?.model_ms===20000);
  const invalid=await page.request.post(url+'/api/causal/action',{data:{id,kind:'command',observed_round:190,command:{target:5,opcode:4,value:1,ttl_ms:10000}}});assert(!invalid.ok());assert.equal((await get()).experiment.commands.length,0);
  await page.locator('#actionTarget').selectOption('5');await page.locator('#actionValue').fill('1');await page.locator('#actionPrepare').click();
  assert((await page.locator('#actionConfirmText').innerText()).includes(id));await page.locator('#actionConfirm').click();
  d=await wait(d=>d.experiment?.latest?.round===300&&d.experiment.phase==='waiting');assert.equal(d.experiment.commands[0].status,'confirmed');
  assert.equal(d.experiment.commands[0].before.generated_fragments_per_s,5);assert.equal(d.experiment.commands[0].after.generated_fragments_per_s,1);
  await page.waitForFunction(()=>window.actionContext?.model_ms===30000);
  for(const t of ['evidence','mission','history']){
   await page.locator(`#sharedContext [data-jump="${t}"]`).click();await page.waitForTimeout(700);
   const ctx=await page.evaluate(()=>window.actionContext);assert.equal(ctx.record_id,id);assert.equal(ctx.model_ms,30000);assert.equal(ctx.link,4);
   await page.screenshot({path:path.join(out,t+'.png'),fullPage:true});
  }
  await page.locator('#sharedContext [data-jump="evidence"]').click();
  await page.locator('#actionValue').fill('5');await page.locator('#actionPrepare').click();await page.locator('#actionConfirm').click();
  d=await wait(d=>d.experiment?.latest?.round===400&&d.experiment.phase==='waiting');assert.equal(d.experiment.commands[1].after.generated_fragments_per_s,5);
  await page.locator('#cxFinish').click();d=await wait(d=>d.experiment?.phase==='complete'&&!d.busy);assert(d.experiment.report.all_media_complete);console.log('COMPLETE',id);
  await page.locator('#sharedContext [data-jump="history"]').click();await page.locator('#cxRefresh').click();await page.locator('#cxRecords').selectOption(id);await page.locator('#cxView').click();
  await page.locator('#cxReplayRange').fill('24');await page.locator('#cxReplayRange').dispatchEvent('input');await page.waitForFunction(()=>window.actionContext?.mode==='history'&&window.actionContext.model_ms===25000);
  assert.equal(await page.locator('#video').getAttribute('src'),null,'Past snapshots cannot expose future completed media');
  for(const t of ['evidence','mission','history']){await page.locator(`#sharedContext [data-jump="${t}"]`).click();await page.waitForTimeout(400);const c=await page.evaluate(()=>window.actionContext);assert.equal(c.model_ms,25000);assert.equal(c.record_id,id);assert(await page.locator('#actionPrepare').isDisabled());}
  console.log('HISTORY_SYNCHRONIZED');await page.locator('#cxReproduce').click();await wait(d=>d.experiment?.id!==id);console.log('RECOMPUTE_STARTED');d=await wait(d=>d.experiment?.id!==id&&d.experiment?.phase==='complete'&&!d.busy);assert(d.experiment.report.reproduction.exact_match);
  await page.setViewportSize({width:1366,height:768});await page.locator('#sharedContext [data-jump="evidence"]').click();await page.waitForTimeout(500);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({pass:true,original:id,recomputed:d.experiment.id,errors,reproduction:d.experiment.report.reproduction,actions:d.experiment.commands},null,2));
  console.log('ACTION_UI_PASS',id,d.experiment.id);
 }catch(e){await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
