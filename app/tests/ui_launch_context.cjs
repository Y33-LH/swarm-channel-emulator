const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),path=require('path');
const source=fs.readFileSync(path.join(__dirname,'../ui/app.js'),'utf8');
const lines=source.split('\n').filter(l=>l.startsWith('const labels=')||l.startsWith('function taskStatus(')||l.startsWith('async function launchNetwork('));
const calls=[],ctx={$:id=>({value:'4'}),api:async(route,body)=>{calls.push({route,body});return {ok:true};}};
vm.runInNewContext(lines.join('\n'),ctx);
(async()=>{
 const req={seconds:0};await ctx.launchNetwork(req);
 assert.equal(calls[0].route,'/api/watch');assert.equal(calls[0].body.link_id,4);
 assert.equal(calls[1].route,'/api/start');assert.equal(calls[1].body,req);
 calls.length=0;ctx.api=async route=>{calls.push(route);throw Error('watch failed');};
 await assert.rejects(ctx.launchNetwork(req),/watch failed/);assert.deepEqual(calls,['/api/watch']);
 assert.equal(ctx.taskStatus({status:'complete',task:'connect'}),'连接检查完成');
 assert.match(ctx.taskStatus({status:'complete',task:'network'}),/结果已保存/);
 console.log('LAUNCH_CONTEXT_PASS: selected link applied first, failure blocks start, connection is not an experiment');
})();
