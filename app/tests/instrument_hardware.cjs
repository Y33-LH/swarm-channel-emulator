const {chromium}=require(process.env.SWARM_PLAYWRIGHT || 'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const root=path.resolve(__dirname,'..'),out=path.join(root,'results','instrument_hardware_'+Date.now());fs.mkdirSync(out,{recursive:true});
const base='http://127.0.0.1:8879';let browser,page,errors=[];
(async()=>{browser=await chromium.launch({executablePath:process.env.SWARM_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});page=await browser.newPage({viewport:{width:1920,height:1080}});page.on('pageerror',e=>errors.push(String(e)));
const state=async()=>(await page.request.get(base+'/api/state')).json();
const wait=async(pred,ms=200000)=>{const end=Date.now()+ms;while(Date.now()<end){const s=await state();if(s.status==='error')throw Error(s.error);if(pred(s))return s;await page.waitForTimeout(400);}throw Error('Board operation timeout');};
await page.goto(base);await page.waitForTimeout(1800);await page.waitForFunction(()=>document.getElementById('configHash').textContent.includes('校验通过'));
await page.locator('#connect').click();await wait(s=>s.task==='connect'&&!s.busy&&s.connected);console.log('CONNECTED');
await page.locator('#openLab').click();await page.locator('#labText').fill('信道工作台：实板收发与星座验证');const labs=[];
for(const preset of ['ideal','echo']){const old=(await state()).lab?.id;await page.locator('#labPreset').selectOption(preset);await page.locator('#labRun').click();const s=await wait(s=>s.task==='lab'&&!s.busy&&s.lab?.id!==old);assert(s.lab.match);labs.push({id:s.lab.id,preset,match:s.lab.match,points:s.lab.iq.received.length});console.log('LAB_PASS',preset,s.lab.id);}
await page.locator('#closeLab').click();await page.waitForTimeout(800);await page.screenshot({path:path.join(out,'lab_echo_home.png'),fullPage:true});
await page.locator('[data-tab=mission]').click();await page.locator('#resetConfig').click();await page.waitForTimeout(500);await page.locator('[data-tab=evidence]').click();
await page.locator('#start').click();await wait(s=>s.task==='network'&&s.snapshot?.round>=1000);
await page.screenshot({path:path.join(out,'live_home.png'),fullPage:true});await page.locator('[data-tab=mission]').click();
const first=await page.locator('#map').screenshot();await page.waitForTimeout(180);const second=await page.locator('#map').screenshot();assert(!first.equals(second),'Live link markers must animate');
assert(await page.locator('#environmentCards button').first().isDisabled());
await wait(s=>s.snapshot?.round>=3600);await page.waitForTimeout(500);await page.screenshot({path:path.join(out,'live_fault.png'),fullPage:true});
await wait(s=>s.snapshot?.round>=6000);await page.locator('[data-tab=evidence]').click();
const done=await wait(s=>s.task==='network'&&!s.busy&&s.status==='complete');assert(done.report.pass&&done.report.all_media_complete);assert(done.report.final.delivered/done.report.final.generated>.99);assert.equal(done.report.final.slot_misses,0);
await page.waitForTimeout(1000);await page.screenshot({path:path.join(out,'complete_home.png'),fullPage:true});console.log('FULL_RUN_PASS',done.network_record_id,done.report.wall_total_seconds,done.report.final.delivered+'/'+done.report.final.generated);
await page.locator('[data-tab=mission]').click();await page.locator('.received-files summary').click();for(const id of ['audio','video']){const src=await page.locator('#'+id).getAttribute('src');assert(src.includes(done.network_record_id));assert((await page.request.get(base+src)).ok());}
// A short subsequent run validates pause/resume and a real downlink receipt in the new sidebar.
await page.locator('#seconds').selectOption('90');await page.locator('#start').click();await wait(s=>s.task==='network'&&s.status==='running'&&s.snapshot?.round>=200);
await page.locator('#pause').click();const paused=await wait(s=>s.status==='paused');await page.waitForTimeout(500);const a=await page.locator('#map').screenshot();await page.waitForTimeout(250);const b=await page.locator('#map').screenshot();assert(a.equals(b),'Paused map must not animate');assert.equal((await state()).snapshot.round,paused.snapshot.round);
await page.locator('#nodeSelect').selectOption('9');await page.locator('#controlDetails summary').click();await page.locator('#commandOp').selectOption('1');await page.locator('#sendCommand').click();await page.locator('#confirmCommand').click();await page.locator('#resume').click();
const receipt=await wait(s=>s.commands?.some(c=>c[1]===9&&c[4]===2));await page.waitForTimeout(500);assert((await page.locator('#commandStatus').innerText()).includes('已收到执行成功回报'));
const short=await wait(s=>s.task==='network'&&!s.busy&&s.status==='complete');
assert.deepEqual(errors,[]);const result={pass:true,scope:'New UI with unchanged d3 firmware; one full run and a short pause/command regression',full_run:done.network_record_id,wall_seconds:done.report.wall_total_seconds,delivery:done.report.final.delivered/done.report.final.generated,timely:done.report.final.timely_delivered/done.report.final.generated,performance_gates:done.report.performance_gates,image_hashes:done.report.image_hashes,labs,short_run:short.network_record_id,commands:receipt.commands,live_animation:true,pause_freezes_animation:true,errors,manifest_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'release.json'))).digest('hex')};fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify(result,null,2));console.log('INSTRUMENT_HARDWARE_PASS',out);await browser.close();
})().catch(async e=>{console.error(e);if(page){try{await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),errors},null,2));}catch{}}if(browser)await browser.close();process.exit(1);});
