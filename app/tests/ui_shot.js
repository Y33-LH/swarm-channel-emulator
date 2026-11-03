// 极简 CDP 截图工具（零第三方依赖，只用到 node 内置 http/crypto/fs）
// 用法:node ui_shot.js <url> <out.png> <width> <height> [setupJS] [waitMs]
//
// 前置：另开一个命令窗口启动无头浏览器（必须带全新的 --user-data-dir，
//       否则会命中缓存里的旧 JS，截出来的图不代表当前代码）：
//   msedge --headless=new --remote-debugging-port=9333 ^
//          --user-data-dir=%TEMP%\edgeheadless<N> --window-size=1920,1080 about:blank
//
// 例：截第 1 页并收集 JS 异常
//   node ui_shot.js http://127.0.0.1:18878/index.html p1.png 1920 1080 "" 4000
const http=require('http');
const crypto=require('crypto');
// CDP 端口：默认 9333，可用 SWARM_CDP 环境变量覆盖（与 ui_layout_probe.js 一致）。
// 为什么：换一个端口启动无头浏览器才不会命中旧实例的缓存，两个脚本才共用得起来。
const port=Number(process.env.SWARM_CDP||9333);
function jget(path){return new Promise((res,rej)=>{http.get({host:'127.0.0.1',port,path},r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>res(JSON.parse(d)));}).on('error',rej);});}
// minimal websocket client (no deps)
function wsConnect(url){
 return new Promise((resolve,reject)=>{
  const u=new URL(url);const key=crypto.randomBytes(16).toString('base64');
  const req=http.request({host:u.hostname,port:u.port,path:u.pathname+u.search,headers:{Connection:'Upgrade',Upgrade:'websocket','Sec-WebSocket-Key':key,'Sec-WebSocket-Version':13}});
  req.on('upgrade',(res,socket)=>{resolve(socket);});
  req.on('error',reject);req.end();
 });
}
function wsFrame(data){const p=Buffer.from(data);const mask=crypto.randomBytes(4);let h;
 if(p.length<126){h=Buffer.from([0x81,0x80|p.length]);}
 else if(p.length<65536){h=Buffer.alloc(4);h[0]=0x81;h[1]=0x80|126;h.writeUInt16BE(p.length,2);}
 else{h=Buffer.alloc(10);h[0]=0x81;h[1]=0x80|127;h.writeBigUInt64BE(BigInt(p.length),2);}
 const m=Buffer.from(p);for(let i=0;i<m.length;i++)m[i]^=mask[i%4];
 return Buffer.concat([h,mask,m]);}
class CDP{
 constructor(sock){this.sock=sock;this.id=0;this.buf=Buffer.alloc(0);this.waiters=new Map();
  sock.on('data',d=>{this.buf=Buffer.concat([this.buf,d]);this.drain();});}
 drain(){while(this.buf.length>=2){const b1=this.buf[1];let len=b1&0x7f,off=2;
   if(len===126){if(this.buf.length<4)return;len=this.buf.readUInt16BE(2);off=4;}
   else if(len===127){if(this.buf.length<10)return;len=Number(this.buf.readBigUInt64BE(2));off=10;}
   if(this.buf.length<off+len)return;
   const payload=this.buf.slice(off,off+len);this.buf=this.buf.slice(off+len);
   try{const msg=JSON.parse(payload.toString());if(msg.id&&this.waiters.has(msg.id)){this.waiters.get(msg.id)(msg);this.waiters.delete(msg.id);}}catch(e){}}}
 send(method,params={}){return new Promise((resolve)=>{const id=++this.id;this.waiters.set(id,resolve);this.sock.write(wsFrame(JSON.stringify({id,method,params})));});}
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const [url,out,W,H,setupJS,waitMs]=process.argv.slice(2);
 // find page target
 let targets;for(let i=0;i<30;i++){try{targets=await jget('/json/list');break;}catch(e){await sleep(500);}}
 let page=targets.find(t=>t.type==='page');
 const sock=await wsConnect(page.webSocketDebuggerUrl);
 const cdp=new CDP(sock);
 await cdp.send('Page.enable');
 await cdp.send('Emulation.setDeviceMetricsOverride',{width:+W,height:+H,deviceScaleFactor:1,mobile:false});
 await cdp.send('Page.navigate',{url});
 await sleep(3500);
 if(setupJS){await cdp.send('Runtime.evaluate',{expression:setupJS,awaitPromise:true});}
 await sleep(+(waitMs||1500));
 const shot=await cdp.send('Page.captureScreenshot',{format:'png'});
 require('fs').writeFileSync(out,Buffer.from(shot.result.data,'base64'));
 console.log('saved',out);
 process.exit(0);
})().catch(e=>{console.error('ERR',e.message);process.exit(1);});
