// Regression for an HTTP-200 state containing a task error. Read-only UI fixture;
// this does not claim a physical USB unplug or a completed hardware experiment.
const {chromium}=require(process.env.SWARM_PLAYWRIGHT || 'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{const browser=await chromium.launch({executablePath:process.env.SWARM_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{const page=await browser.newPage();let fixture={status:'stopped',task:'network',busy:false,connected:true,error:'Run stopped; no acceptance result published',snapshot:null,metrics:{},scene:[],events:[],commands:[],snapshots:[]};
 await page.route('**/api/state',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(fixture)}));
 await page.goto('http://127.0.0.1:8878');await page.waitForFunction(()=>document.getElementById('configHash').textContent.includes('校验通过'));
 assert(await page.locator('#connect').isEnabled());assert(await page.locator('#start').isEnabled());
 fixture={...fixture,status:'error',connected:false,error:'Serial adapter disconnected'};await page.waitForTimeout(1200);
 assert(await page.locator('#connect').isEnabled());assert(await page.locator('#start').isDisabled());
 fixture={...fixture,status:'complete',connected:true,error:null};await page.waitForTimeout(1200);assert(await page.locator('#start').isEnabled());
 const dest=path.resolve(__dirname,'../results/ui_error_recovery.json');fs.writeFileSync(dest,JSON.stringify({pass:true,scope:'browser state fixture, not a physical unplug test',stopped_error_recovered:true,serial_error_recovered:true},null,2));console.log('UI_ERROR_STATE_RECOVERY_PASS');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
