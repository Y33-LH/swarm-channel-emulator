const {chromium}=require('C:/Users/yirui/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..'),out=path.join(root,'results','ui_release_'+Date.now());fs.mkdirSync(out,{recursive:true});
const base='http://127.0.0.1:8876';let browser;
(async()=>{
 browser=await chromium.launchPersistentContext(path.join(out,'profile'),{executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,viewport:{width:1920,height:1080}});
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
 const get=async p=>(await page.request.get(base+p)).json();
 async function wait(pred,timeout=40000){const end=Date.now()+timeout;while(Date.now()<end){const s=await get('/api/state');if(s.status==='error')throw Error(s.error);if(pred(s))return s;await page.waitForTimeout(400)}throw Error('Timeout waiting for UI/board');}
 const completed=t=>s=>s.task===t&&!s.busy&&s.status==='complete';
 async function shot(name){await page.waitForTimeout(400);if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Horizontal overflow');await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});}
 await page.goto(base,{waitUntil:'networkidle'});await page.locator('#connect').click();await wait(completed('connect'));
 // Live pause freezes the model; abort must not publish a successful record.
 await page.locator('#start').click();await wait(s=>s.task==='network'&&s.snapshot?.round>=200);
 await page.locator('#pause').click();const paused=await wait(s=>s.status==='paused');await page.waitForTimeout(800);
 if((await get('/api/state')).snapshot.round!==paused.snapshot.round)throw Error('Model advanced while paused');
 await page.locator('#pause').click();await wait(s=>s.status==='running'&&s.snapshot.round>paused.snapshot.round);
 await page.locator('#stop').click();const stopped=await wait(s=>s.status==='stopped'&&!s.busy);if(stopped.report)throw Error('Aborted run marked accepted');
 await page.locator('[data-tab="channel"]').click();await page.locator('#message').fill('故障恢复与接收数据验证');await page.locator('#lab_sigma').fill('3000');await page.locator('#send').click();const lab=await wait(completed('lab'));
 if(!lab.lab.match||lab.lab.phy.turbo_iterations!==2||lab.lab.phy.post_errors)throw Error('Full noisy FEC failed');
 await page.locator('[data-tab="measurements"]').click();await shot('receiver');
 await page.locator('[data-tab="overview"]').click();await page.locator('#preset').selectOption('900');
 const start=Date.now();await page.locator('#start').click();const network=await wait(completed('network'),160000);const clickSeconds=(Date.now()-start)/1000;
 if(!network.report.pass||!Object.values(network.report.performance_gates).every(Boolean)||clickSeconds>120)throw Error('Live performance gate '+clickSeconds);
 if(network.report.final.alarms!==4||network.report.video_decoded_frames!==20)throw Error('Missing alarms or media');
 for(const tab of ['overview','channel','network']){await page.locator(`[data-tab="${tab}"]`).click();await shot(tab);}
 const media={};for(const id of ['audio','video']){media[id]=await page.locator('#'+id).evaluate(async e=>{e.load();await new Promise((ok,bad)=>{e.onloadedmetadata=ok;e.onerror=()=>bad(Error('Media decode failed'));setTimeout(()=>bad(Error('Media timeout')),12000)});return e.duration;});if(!(media[id]>0))throw Error('Empty media');}
 // Re-run the load scan through the same UI and actual hardware path.
 await page.locator('[data-tab="measurements"]').click();await page.locator('#capacity').click();const capacity=await wait(completed('capacity'),240000);if(!capacity.capacity.pass||capacity.capacity.rows.length!==7)throw Error('Capacity scan failed');await shot('capacity');
 await page.locator('[data-tab="records"]').click();await page.waitForTimeout(600);await page.locator('#recordSelect').selectOption(network.record_id);await page.locator('#loadReplay').click();
 const record=await get('/api/record?id='+network.record_id);const i=record.snapshots.findIndex(s=>s.round>=6800);await page.locator('#replaySeek').fill(String(i));await page.locator('#replaySeek').dispatchEvent('input');await shot('fault_record');
 if(!(await page.locator('#sourceBadge').innerText()).includes('历史'))throw Error('Replay mislabeled');await page.locator('#exitReplay').click();
 await page.locator('[data-tab="records"]').click();await page.locator('#recordSelect').selectOption(network.record_id);
 for(const id of ['exportZip','exportCsv','exportReport']){await page.locator('#'+id).click();await page.waitForTimeout(700);if(!(await page.locator('#exportInfo').innerText()).includes('已保存'))throw Error('Export failed '+id);}
 await shot('records');if(errors.length)throw Error(errors.join('\n'));
 fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({pass:true,source:'live_UI_and_real_board',errors,click_to_complete_seconds:clickSeconds,network:network.record_id,capacity:capacity.capacity.id,lab:lab.lab.id,media,aborted_record:stopped.record_id,pause_round:paused.snapshot.round},null,2));
 console.log('UI_RELEASE_PASS '+out);await browser.close();
})().catch(async e=>{console.error(e);if(browser)await browser.close();process.exit(1)});
