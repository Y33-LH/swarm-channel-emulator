/* Real browser + real serial service. No mocked hardware values. */
const {chromium}=require(process.env.SWARM_PLAYWRIGHT || 'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),out=path.join(root,'results','intervention_ui');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.SWARM_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[];
 page.on('pageerror',e=>errors.push(String(e)));const url='http://127.0.0.1:8881';
 const get=async()=>await(await page.request.get(url+'/api/causal/state')).json();
 const wait=async(predicate,ms=120000)=>{
  const until=Date.now()+ms;
  while(Date.now()<until){const d=await get();if(d.experiment?.phase==='error')throw Error(d.experiment.error);if(predicate(d))return d;await page.waitForTimeout(250);}
  throw Error('Timed out waiting for real board');
 };
 try{
  await page.goto(url+'/#causal');await page.waitForTimeout(2000);
  assert.deepEqual(errors,[]);assert(await page.locator('#networkIntervention').isVisible());
  if(! (await get()).connected){
   await page.locator('#connect').click();await wait(d=>d.connected&&!d.busy);
  }
  await page.waitForFunction(()=>!document.getElementById('cxStart').disabled);
  await page.screenshot({path:path.join(out,'entry.png'),fullPage:true});
  const before=(await get()).experiment?.id;
  await page.locator('#cxStart').click();
  let d=await wait(d=>d.experiment?.id!==before&&d.experiment?.phase==='waiting');
  const original=d.experiment.id;
  assert.equal(d.experiment.latest.round,100);assert(d.experiment.view.nodes.every(n=>n.fresh));
  await page.waitForFunction(()=>!document.getElementById('cxChange').disabled);
  await page.locator('#cxSevere').click();await page.locator('#cxChange').click();
  d=await wait(d=>d.experiment?.phase==='waiting'&&d.experiment.latest.round===300);
  assert(!d.experiment.view.nodes[0].fresh);assert(d.experiment.view.nodes[1].fresh);
  assert.equal(d.experiment.view.audio_bytes,1600);
  await page.waitForFunction(()=>document.getElementById('cxBusiness').innerText.includes('位置已过期'));
  await page.locator('#cxBusiness').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'degraded.png'),fullPage:true});
  await page.locator('#cxRestore').click();
  d=await wait(d=>d.experiment?.phase==='waiting'&&d.experiment.latest.round===500);
  assert(d.experiment.view.nodes[0].recovered);assert.equal(d.experiment.view.audio_bytes,6678);
  await page.waitForFunction(()=>document.getElementById('cxBusiness').innerText.includes('已收到恢复后的新心跳'));
  await page.screenshot({path:path.join(out,'restored.png'),fullPage:true});
  await page.locator('#cxFinish').click();
  d=await wait(d=>!d.busy&&d.experiment?.phase==='complete');
  assert(d.experiment.report.intervention.effect_observed&&d.experiment.report.intervention.recovery_observed);
  await page.locator('#cxRefresh').click();
  await page.locator('#cxRecords').selectOption(original);
  await page.locator('#cxView').click();
  await page.waitForFunction(()=>document.getElementById('cxSource').innerText.includes('只读'));
  await page.locator('#cxReplayRange').fill('29');await page.locator('#cxReplayRange').dispatchEvent('input');
  assert((await page.locator('#cxBusiness').innerText()).includes('位置已过期'));
  assert(await page.locator('#cxChange').isDisabled());
  await page.locator('#cxReproduce').click();
  d=await wait(d=>!d.busy&&d.experiment?.id!==original&&d.experiment?.phase==='complete');
  assert(d.experiment.report.reproduction.exact_match);
  await page.waitForFunction(()=>document.getElementById('cxReproduction').innerText.includes('实板重算一致'));
  await page.screenshot({path:path.join(out,'reproduced.png'),fullPage:true});
  await page.locator('#cxExport').click();
  await page.waitForFunction(()=>document.getElementById('cxSaved').innerText.includes('已导出'));
  await page.locator('#lxMode').click();assert(await page.locator('#linkExperiment').isVisible());assert(!(await page.locator('#networkIntervention').isVisible()));
  await page.locator('#cxMode').click();assert(await page.locator('#networkIntervention').isVisible());
  await page.setViewportSize({width:1366,height:768});await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:path.join(out,'laptop.png'),fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);
  assert(!overflow,'Horizontal overflow');assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({pass:true,original,recomputed:d.experiment.id,errors,
   release_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'release.json'))).digest('hex'),
   checks:['real browser start/change/restore/finish','history reflects failure and is read-only','actual replay exact match','export','single-frame mode coexistence','1366px no horizontal overflow']},null,2));
  console.log('INTERVENTION_UI_PASS',original,d.experiment.id);
 }catch(e){await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
