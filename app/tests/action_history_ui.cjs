const {chromium}=require(process.env.SWARM_PLAYWRIGHT || 'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const R=path.resolve(__dirname,'..'),out=path.join(R,'results','action_history_ui');fs.mkdirSync(out,{recursive:true});
(async()=>{const browser=await chromium.launch({executablePath:process.env.SWARM_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
try{await page.goto('http://127.0.0.1:8883/#causal');await page.waitForTimeout(1500);
const rec=JSON.parse(fs.readFileSync(path.join(R,'results/action_ui/acceptance.json'))),id=rec.original;
await page.locator('#sharedContext [data-jump="history"]').click();await page.locator('#cxRefresh').click();await page.locator('#cxRecords').selectOption(id);await page.locator('#cxView').click();
await page.locator('#cxReplayRange').fill('24');await page.locator('#cxReplayRange').dispatchEvent('input');await page.waitForFunction(()=>window.actionContext?.mode==='history'&&window.actionContext.model_ms===25000);
const ids=[];
for(const tab of ['evidence','mission','history']){await page.locator(`#sharedContext [data-jump="${tab}"]`).click();await page.waitForTimeout(500);
const d=await page.evaluate(()=>({context:window.actionContext,round:V.snapshot.round,applied:V.scene[4].sigma,actual:V.snapshot.observation.applied[5],environment:document.getElementById('environment').value,media:document.getElementById('video').getAttribute('src')}));
assert.equal(d.context.record_id,id);assert.equal(d.round,250);assert.equal(d.applied,d.actual);assert.equal(d.environment,'1');assert(!d.media,'No future completed video in an earlier snapshot');ids.push(d);
assert(await page.locator('#actionPrepare').isDisabled());await page.screenshot({path:path.join(out,tab+'.png'),fullPage:true});}
const commands=await page.request.get('http://127.0.0.1:8883/api/causal/context?id='+id+'&index=24');const d=await commands.json();assert.equal(d.commands.length,1);assert.equal(d.commands[0].after,null);assert.equal(d.report,null);
await page.locator('#cxLive').click();await page.waitForFunction(()=>window.actionContext?.mode==='current');assert.equal(await page.locator('#actionPrepare').isDisabled(),true);
assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({pass:true,id,identities:ids,errors,future_media_hidden:true,future_commands_hidden:true},null,2));console.log('HISTORY_CONTEXT_PASS');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
