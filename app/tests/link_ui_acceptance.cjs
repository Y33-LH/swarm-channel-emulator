/* Browser regression against the running local app. No simulated board replies. */
const {chromium}=require(process.env.SWARM_PLAYWRIGHT || 'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const out=path.resolve(__dirname,'../results/link_ui');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.SWARM_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[];
 page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.goto('http://127.0.0.1:8880/#link');await page.waitForTimeout(2500);
  assert.deepEqual(errors,[]);
  assert(await page.locator('#linkExperiment').isVisible());
  assert.equal(await page.locator('#lxLink option').count(),32);
  assert.equal(await page.locator('#linkExperiment canvas').count(),4);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  const runIds=[];
  const waitBoard=async predicate=>{
   const deadline=Date.now()+45000;
   while(Date.now()<deadline){
    const d=await (await page.request.get('http://127.0.0.1:8880/api/link/state')).json();
    if(predicate(d))return d;
    await page.waitForTimeout(200);
   }
   throw Error('Hardware completion condition not reached');
  };
  const runUi=async()=>{
   const before=(await (await page.request.get('http://127.0.0.1:8880/api/link/state')).json()).experiment?.id;
   await page.locator('#lxApply').click();
   const d=await waitBoard(d=>!d.busy&&d.experiment?.id!==before&&d.experiment?.phase==='complete');
   runIds.push(d.experiment.id);
   await page.waitForFunction(id=>{const p=document.getElementById('linkExperiment');return p.dataset.experimentId===id&&p.dataset.phase==='complete'&&document.getElementById('lxStatus').innerText.includes('采样帧号');},d.experiment.id,{timeout:15000});
   assert((await page.locator('#lxStatus').innerText()).includes('采样帧号'));
   return d.experiment;
  };
  await page.locator('#lxLink').selectOption('0');
  await page.locator('#lxText').fill('位置正常，保持通信');
  await page.locator('#lxFrames').fill('3');
  await page.locator('#lx_sigma').fill('0');
  await page.waitForFunction(()=>!document.getElementById('lxApply').disabled);
  const clean=await runUi();assert.equal(clean.summary.delivered,3);
  await page.locator('#lx_sigma').fill('2800');
  const noise=await runUi();
  assert(noise.summary.pre_ber>clean.summary.pre_ber);
  await page.locator('#lxRecords').selectOption(clean.id);
  await page.locator('#lxCompare').click();
  await page.waitForFunction(()=>document.getElementById('lxCompareResult').innerText.includes('单设置对照'));
  assert((await page.locator('#lxCompareResult').innerText()).includes('纠错前 BER'));
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(out,'noise-comparison.png'),fullPage:true});
  await page.locator('#lxReproduce').click();
  await waitBoard(d=>!d.busy&&!!d.experiment?.report?.reproduction?.exact_measurement_reproduced);
  await page.waitForFunction(()=>document.getElementById('lxCompareResult').innerText.includes('重现一致'),null,{timeout:15000});
  assert((await page.locator('#lxCompareResult').innerText()).includes('重现一致'));
  const available=await page.locator('#lxRecords option').count();
  if(available>1){
   await page.locator('#lxView').click();await page.waitForFunction(()=>document.getElementById('lxSource').innerText.includes('只读'));
   assert((await page.locator('#lxSource').innerText()).includes('只读'));
   assert((await page.locator('#lxStatus').innerText()).includes('采样帧号'));
   await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(out,'record.png'),fullPage:true});
   await page.locator('#lxFrame').selectOption('0');await page.waitForTimeout(200);
   assert((await page.locator('#lxStatus').innerText()).includes('第 1 帧'));
   await page.locator('#lxExport').click();await page.waitForTimeout(800);
   assert((await page.locator('#lxCompareResult').innerText()).includes('已导出'));
  }
  await page.locator('#lxNetworkMode').click();assert(!await page.locator('#linkExperiment').isVisible());
  await page.locator('#lxMode').click();assert(await page.locator('#linkExperiment').isVisible());
  await page.locator('[data-tab="mission"]').click();assert(await page.locator('#mission').isVisible());
  await page.waitForTimeout(900);
  assert(!(await page.locator('#sourceLabel').innerText()).includes('独立单跳'));
  await page.locator('[data-tab="evidence"]').click();assert(await page.locator('#linkExperiment').isVisible());
  await page.locator('[data-tab="history"]').click();
  await page.waitForTimeout(700);
  if(await page.locator('[data-record]').count()){
   await page.locator('[data-record]').first().click();
   await page.waitForFunction(()=>!document.getElementById('returnLive').hidden);
   assert(!await page.locator('#linkExperiment').isVisible());
   await page.locator('#lxMode').click();
   await page.waitForFunction(()=>document.getElementById('returnLive').hidden);
   assert(await page.locator('#linkExperiment').isVisible());
  }else await page.locator('[data-tab="evidence"]').click();
  await page.setViewportSize({width:1366,height:768});await page.waitForTimeout(300);
  assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),'horizontal overflow');
  await page.screenshot({path:path.join(out,'laptop.png'),fullPage:true});
  assert.deepEqual(errors,[]);
  const manifest_sha256=crypto.createHash('sha256').update(fs.readFileSync(path.resolve(__dirname,'../release.json'))).digest('hex');
  fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({pass:true,errors,source:'actual_local_HTTP_and_UART_board',scope:'real UI apply, change noise, same-frame view, compare, board reproduction, export, layout/navigation; not external-user usability',records_present:available>1,runIds,manifest_sha256},null,2));
  console.log('LINK_UI_PASS',out);
 }catch(e){
  const debug=await page.evaluate(()=>({status:document.getElementById('lxStatus')?.innerText,source:document.getElementById('lxSource')?.innerText,dataset:{...document.getElementById('linkExperiment')?.dataset},bodyClass:document.body.className}));
  const state=await (await page.request.get('http://127.0.0.1:8880/api/link/state')).json();
  console.error('UI_DEBUG',JSON.stringify({debug,errors,hardwareId:state.experiment?.id,hardwarePhase:state.experiment?.phase}));
  await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});
  fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),debug,errors,at:new Date().toISOString()},null,2));
  throw e;
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
