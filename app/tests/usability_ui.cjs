const {chromium}=require(process.env.SWARM_PLAYWRIGHT || 'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),url=(process.env.SWARM_TEST_URL || 'http://127.0.0.1:18878'),out=path.join(root,'results/usability_ui');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.SWARM_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[],checks=[];page.on('pageerror',e=>errors.push(String(e)));
 try{
  await page.goto(url+'/#causal');await page.waitForFunction(()=>typeof catalog!=='undefined'&&catalog&&window.openObservationPane);
  await page.locator('[data-tab="history"]').click();await page.locator('#cxRefresh').click();
  await page.locator('#cxRecords').selectOption('causal_20261021_095426_a6288a');await page.locator('#cxView').click();await page.waitForFunction(()=>window.actionContext?.mode==='history');
  await page.locator('#cxReplayRange').fill('29');await page.locator('#cxReplayRange').dispatchEvent('input');await page.waitForFunction(()=>window.actionContext?.model_ms===30000);
  const identity=await page.evaluate(()=>window.actionContext);
  for(const size of [{width:1920,height:1080},{width:1600,height:1000},{width:1366,height:768}]){
   await page.setViewportSize(size);await page.locator('[data-tab="evidence"]').click();await page.locator('#tab-technical').click();await page.waitForTimeout(650);
   assert.equal(await page.locator('#pane-technical .chart-card:visible').count(),6);
   const boxes=await page.locator('#pane-technical .chart-card canvas').evaluateAll(es=>es.map(e=>({id:e.id,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height,pixels:[e.width,e.height]})));
   assert(boxes.every(b=>b.width>160&&b.height>70&&b.pixels[0]>0),JSON.stringify(boxes));
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert(!overflow,'Horizontal overflow '+size.width);
   await page.locator('#tab-technical').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'technical_'+size.width+'.png')});
   await page.locator('[data-tab="mission"]').click();await page.waitForTimeout(650);
   assert((await page.locator('#mapObservationState').innerText()).includes('历史'));
   assert.deepEqual(await page.evaluate(()=>window.actionContext),identity);
   const map=await page.evaluate(()=>({w:document.getElementById('map').getBoundingClientRect().width,h:document.getElementById('map').getBoundingClientRect().height,points:mapTargets}));
   assert.equal(map.points.length,16);assert(map.points.every(p=>p.x>20&&p.x<map.w-20&&p.y>20&&p.y<map.h-40),'Clipped node');
   assert(!await page.locator('#sendCommand').isEnabled());assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1));
   await page.locator('#sharedMapPanel').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'map_'+size.width+'.png')});
   checks.push({size,boxes,map_width:map.w,map_height:map.h,nodes:map.points.length,horizontal_overflow:false});
  }
  await page.locator('[data-tab="evidence"]').click();await page.locator('#tab-action').click();assert(!await page.locator('#actionPrepare').isEnabled());assert((await page.locator('#actionAvailability').innerText()).includes('历史'));
  await page.locator('#tab-impact').focus();await page.keyboard.press('ArrowRight');assert.equal(await page.locator('#tab-technical').getAttribute('aria-selected'),'true');
  await page.locator('#explainCharts').click();assert(await page.locator('.reading-guide').isVisible());await page.keyboard.press('Escape');
  await page.locator('button[data-chart-view="dynamics"]').click();assert.equal(await page.locator('#pane-technical .chart-card:visible').count(),2);await page.locator('[data-chart-view="all"]').click();
  await page.locator('.expand-chart').first().click();assert(await page.locator('#chartDialog').isVisible());await page.keyboard.press('Escape');await page.waitForFunction(()=>document.querySelectorAll('#pane-technical .chart-card canvas').length===6);
  await page.locator('[data-tab="history"]').click();await page.locator('#cxLive').click();await page.locator('#lxNetworkMode').click();await page.locator('[data-tab="evidence"]').click();assert.equal(await page.locator('.channel-workbench .chart-card:visible').count(),6);
  await page.locator('[data-tab="history"]').click();await page.locator('#cxRecords').selectOption('causal_20261021_095426_a6288a');await page.locator('#cxView').click();await page.waitForFunction(()=>window.causalPresentation?.active&&window.actionContext?.mode==='history');assert.equal(await page.locator('#cxMode').getAttribute('aria-pressed'),'true');
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'layout.json'),JSON.stringify({pass:true,checks,read_only_actions_blocked:true,keyboard_tabs:true,shared_identity:identity,errors,manifest_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'release.json'))).digest('hex')},null,2));console.log('USABILITY_LAYOUT_PASS');
 }catch(e){await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
