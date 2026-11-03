const {chromium}=require('C:/Users/yirui/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path');const out=path.resolve(__dirname,'../results/ui_stop_'+Date.now());fs.mkdirSync(out,{recursive:true});
(async()=>{const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try {const page=await browser.newPage();await page.goto('http://127.0.0.1:8873/');await page.locator('#duration').selectOption('120');await page.locator('#ideal').selectOption('1');await page.locator('#start').click();
 const state=async()=>await (await page.request.get('http://127.0.0.1:8873/api/state')).json();let s;
 for(let i=0;i<120;i++){s=await state();if(s.status==='running'&&s.snapshot?.round>=100)break;if(s.status==='error')throw Error(s.error);await page.waitForTimeout(250)}
 if(s.status!=='running')throw Error('No active run');await page.locator('#stop').click();
 for(let i=0;i<100;i++){s=await state();if(s.status==='stopped')break;await page.waitForTimeout(200)}
 if(s.status!=='stopped'||s.report||s.result_path)throw Error('Stop incorrectly published an accepted result');
 const stoppedRound=s.snapshot.round;await page.locator('#connect').click();await page.waitForFunction(()=>document.getElementById('message').textContent.includes('已确认真实板卡'));
 fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify({pass:true,stoppedRound,serial_reopened_after_stop:true,accepted_result_published:false},null,2));console.log('UI_STOP_PASS evidence='+out);
} finally {await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
