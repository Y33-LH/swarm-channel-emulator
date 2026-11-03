/* Three separate UI-started 900 s experiments, one immutable build. Never replay. */
const fs=require('fs'),path=require('path'),crypto=require('crypto'),cp=require('child_process'),assert=require('assert');
const root=path.resolve(__dirname,'..'),sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const stamp=new Date().toISOString().replace(/[-:TZ.]/g,'');
const out=path.join(root,'results','freeze_stability_ui_'+stamp);fs.mkdirSync(out,{recursive:true});
const manifest=JSON.parse(fs.readFileSync(path.join(root,'release.json'),'utf8'));
const receipt={pass:false,release_sha256:sha(path.join(root,'release.json')),images:Object.fromEntries(['bit','elf','init'].map(k=>[k,sha(path.join(root,manifest[k]))])),runs:[]};
const save=()=>fs.writeFileSync(path.join(out,'acceptance.json'),JSON.stringify(receipt,null,2));
function intact(){assert.equal(sha(path.join(root,'release.json')),receipt.release_sha256);for(const f of manifest.artifacts)assert.equal(sha(path.join(root,f.path)),f.sha256,f.path);}
(async()=>{save();try{for(let i=1;i<=3;i++){
 intact();console.log('FROZEN_FULL_UI_BEGIN',i);
 const fd=fs.openSync(path.join(out,`run_${i}.log`),'w');
 const code=await new Promise((resolve,reject)=>{const p=cp.spawn(process.execPath,[path.join(__dirname,'workflow_ui.cjs'),'full'],{cwd:root,stdio:['ignore',fd,fd],windowsHide:true});p.on('error',reject);p.on('close',resolve);});fs.closeSync(fd);
 assert.equal(code,0,`Full UI run ${i} failed; original logs retained`);
 const report=JSON.parse(fs.readFileSync(path.join(root,'results/workflow_ui/full.json'),'utf8'));assert(report.pass);assert.equal(report.release_sha256,receipt.release_sha256);
 assert(!receipt.runs.some(x=>x.id===report.id));assert.equal(report.report.duration_s,900);
 assert(report.report.all_media_complete&&Object.values(report.report.performance_gates).every(Boolean));
 assert.deepEqual(report.report.image_hashes,receipt.images);assert.equal(report.report.final.pending,0);assert.equal(report.report.final.slot_misses,0);
 const evidence=path.join(root,'results',report.id);const meta=JSON.parse(fs.readFileSync(path.join(evidence,'metadata.json'),'utf8'));assert.equal(meta.release_sha256,receipt.release_sha256);
 fs.copyFileSync(path.join(root,'results/workflow_ui/full_scene.png'),path.join(out,`run_${i}.png`));
 receipt.runs.push({index:i,id:report.id,wall_seconds:report.report.wall_total_seconds,generated:report.report.final.generated,delivered:report.report.final.delivered,
  timely:report.report.final.timely_delivered,late:report.report.final.late_delivered,memory:report.report.memory_after,
  acceptance_sha256:sha(path.join(evidence,'acceptance.json')),snapshots_sha256:sha(path.join(evidence,'snapshots.jsonl')),uart_sha256:sha(path.join(evidence,'uart.jsonl'))});
 save();intact();console.log('FROZEN_FULL_UI_PASS',i,report.id,report.report.wall_total_seconds);
 }receipt.pass=true;receipt.source='three_consecutive_fresh_UI_started_physical_board_runs';save();console.log('FINAL_THREE_UI_PASS',out);
 }catch(e){receipt.failure=String(e);save();throw e;}})().catch(e=>{console.error(e);process.exitCode=1});
