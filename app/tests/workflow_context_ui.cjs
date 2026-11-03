// Exercise a delayed context response crossing a mode switch without programming hardware.
const {chromium}=require(process.env.SWARM_PLAYWRIGHT || 'playwright');
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert');
const root=path.resolve(__dirname,'..'),url=(process.env.SWARM_TEST_URL || 'http://127.0.0.1:18878');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.SWARM_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const page=await browser.newPage();await page.goto(url+'/#network');await page.waitForFunction(()=>typeof S!=='undefined'&&S.network_record_id);
  const prior=await (await page.request.get(url+'/api/causal/context')).json();assert(prior.context);
  const identity=await page.evaluate(()=>S.network_record_id);assert.notEqual(identity,prior.context.record_id);
  let started,release;const requested=new Promise(r=>started=r),delayed=new Promise(r=>release=r);
  await page.route('**/api/causal/context',async route=>{started();await delayed;await route.fulfill({json:prior});});
  await page.evaluate(c=>{window.__switchTest=window.setActionContext({active:true,view:{id:c.record_id,latest:{round:c.model_ms/100}},history:false,trace:[]});},prior.context);
  await requested;await page.evaluate(()=>window.setActionContext({active:false}));release();await page.evaluate(()=>window.__switchTest);
  const after=await page.evaluate(()=>({context:window.actionContext,record_id:S.network_record_id}));assert.equal(after.context,null);assert.equal(after.record_id,identity);
  fs.writeFileSync(path.join(root,'results/workflow_context_ui.json'),JSON.stringify({pass:true,delayed_response_did_not_restore_old_experiment:true,after,release_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'release.json'))).digest('hex')},null,2));
  console.log('MODE_SWITCH_CONTEXT_PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
