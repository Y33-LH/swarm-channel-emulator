const {chromium}=require('C:/Users/yirui/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path');const root=path.resolve(__dirname,'..'),out=path.join(root,'results','ui_final_'+Date.now());fs.mkdirSync(out,{recursive:true});let browser;
(async()=>{
 browser=await chromium.launchPersistentContext(path.join(out,'profile'),{executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,viewport:{width:1920,height:1080}});const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));const base='http://127.0.0.1:8876';
 const state=async()=>(await page.request.get(base+'/api/state')).json();async function wait(pred){let end=Date.now()+60000;while(Date.now()<end){let s=await state();if(s.status==='error')throw Error(s.error);if(pred(s))return s;await page.waitForTimeout(400)}throw Error('UI timeout')}
 await page.goto(base,{waitUntil:'networkidle'});await page.locator('#connect').click();await wait(s=>s.connected&&!s.busy);
 await page.locator('#preset').selectOption('120');await page.locator('#start').click();const n=await wait(s=>s.task==='network'&&s.status==='complete'&&!s.busy);
 if(n.network_record_id!==n.record_id||!n.report.pass)throw Error('Network identity');const id=n.network_record_id;
 await page.locator('[data-tab="measurements"]').click();await page.locator('#capacity').click();await wait(s=>s.task==='capacity'&&s.capacity?.model_s>=10);await page.locator('#stop').click();const c=await wait(s=>s.status==='stopped'&&!s.busy);
 if(c.network_record_id!==id||c.record_id===id)throw Error('Network identity overwritten by other task');
 await page.locator('[data-tab="network"]').click();await page.waitForTimeout(600);
 if(!(await page.locator('#audio').getAttribute('src')).includes(id))throw Error('Audio associated with wrong record');
 const media=await page.request.get(base+(await page.locator('#audio').getAttribute('src')));if(!media.ok())throw Error('Received media no longer accessible');
 await page.locator('[data-tab="measurements"]').click();await page.locator('#studyDetails summary').click();await page.waitForFunction(()=>document.getElementById('studyChart').naturalWidth>1000);
 await page.screenshot({path:path.join(out,'study.png'),fullPage:true});
 await page.locator('[data-tab="records"]').click();await page.waitForTimeout(700);await page.locator('#recordSelect').selectOption('network_20261012_171115_adcb2c');await page.locator('#loadReplay').click();await page.locator('#replaySeek').fill('44');await page.locator('#replaySeek').dispatchEvent('input');await page.waitForTimeout(600);await page.screenshot({path:path.join(out,'overview.png'),fullPage:true});
 if(!(await page.locator('#sourceBadge').innerText()).includes('历史'))throw Error('Historical record label missing');
 await page.locator('#exitReplay').click();await page.locator('[data-tab="records"]').click();await page.screenshot({path:path.join(out,'resources.png'),fullPage:true});
 if(!(await page.locator('#memory').innerText()).includes('4,328'))throw Error('Runtime memory evidence missing');
 if(errors.length)throw Error(errors.join('\n'));fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({pass:true,errors,network_record:id,other_record:c.record_id,media_identity_preserved:true,study_plot_loaded:true},null,2));
 await browser.close();console.log('UI_FINAL_SMOKE_PASS '+out);
})().catch(async e=>{console.error(e);if(browser)await browser.close();process.exit(1)});
