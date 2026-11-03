// Regression: old animation callbacks may not overwrite a newly selected record.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),path=require('path');
let now=0,queued=[];
const win={requestAnimationFrame:fn=>queued.push(fn)},ctx={window:win,performance:{now:()=>now}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../ui/smooth-values.js'),'utf8'),ctx);
const el=()=>({textContent:'',dataset:{},classList:{add(){},remove(){}},removeAttribute(k){delete this[k]},value:0});
function advance(ms){now+=ms;const q=queued;queued=[];for(const f of q)f();}
const label=el();win.setSmooth(label,1,String);win.setSmooth(label,134,String);advance(100);
assert.notEqual(label.textContent,'134');
win.measurementReplayActive=true;win.setSmooth(label,1,String);advance(2000);
assert.equal(label.textContent,'1','future sample animation leaked into early history');
win.measurementReplayActive=false;win.setSmooth(label,1,String);win.setSmooth(label,134,String);
win.setPlain(label,'00:01');advance(2000);assert.equal(label.textContent,'00:01');
const progress=el();win.setSmoothValue(progress,1);win.setSmoothValue(progress,134);advance(100);
win.measurementReplayActive=true;win.setSmoothValue(progress,1);advance(2000);assert.equal(progress.value,1);
win.measurementReplayActive=false;win.setSmoothValue(progress,1);win.setSmoothValue(progress,100);advance(50);
win.setSmoothValue(progress,10);advance(2000);advance(2000);assert.equal(progress.value,10);
console.log('HISTORY_ANIMATION_CONTEXT_PASS: no stale label, plain time, history progress, latest target');
