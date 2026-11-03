// 三页「一屏看全」+ 字号合规探测（本次实测数据出处）
//
// 为什么把这份脚本放进项目：
//   要判断"页面是否一眼看全"，不能靠肉眼看本机窗口，必须固定分辨率实测
//   scrollHeight / clientHeight。原先它只存在于项目外的工具目录，换机器就拿不到。
//
// 前置：
//   1) 服务已启动： python portable_server.py --http 18878 --port COM5
//   2) 无头浏览器已启动：
//      msedge --headless=new --remote-debugging-port=9333 ^
//             --user-data-dir=%TEMP%\edgeheadless_probe --window-size=1920,1080 about:blank
//   3) 需要 Node（可选依赖，普通运行 UI 不需要）
//
// 用法：
//   node app/tests/ui_layout_probe.js                   默认 http://127.0.0.1:18878/
//   node app/tests/ui_layout_probe.js 1920 1080 http://127.0.0.1:18878/
//
// 达标口径（2026-10-31 定，避免各人各说）：
//   G5 一屏看全 —— 每个可滚动容器的 scrollHeight 不得超过 clientHeight + 2px；
//                  即本脚本输出的 needsScroll / rail.scrolls 必须全为 false。
//   G6 字号统一 —— 除允许的特例外，可见文本元素全部 >= 14px（五号≈14px）；
//                  本脚本输出 below14 应为 0。
const http = require('http'), crypto = require('crypto');
const CDP_PORT = Number(process.env.SWARM_CDP || 9333);
const WIDTH = Number(process.argv[2] || 1920);
const HEIGHT = Number(process.argv[3] || 1080);
const TARGET = process.argv[4] || 'http://127.0.0.1:18878/';

function jget(p) {
  return new Promise((res, rej) => {
    http.get({ host: '127.0.0.1', port: CDP_PORT, path: p }, r => {
      let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d)));
    }).on('error', rej);
  });
}
function wsConnect(url) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const key = crypto.randomBytes(16).toString('base64');
    const req = http.request({
      host: u.hostname, port: u.port, path: u.pathname + u.search,
      headers: { Connection: 'Upgrade', Upgrade: 'websocket', 'Sec-WebSocket-Key': key, 'Sec-WebSocket-Version': '13' }
    });
    req.on('upgrade', (res, socket) => resolve(socket));
    req.on('error', reject);
    req.end();
  });
}
function wsFrame(data) {
  const p = Buffer.from(data); const mask = crypto.randomBytes(4); let h;
  if (p.length < 126) { h = Buffer.from([0x81, 0x80 | p.length]); }
  else if (p.length < 65536) { h = Buffer.alloc(4); h[0] = 0x81; h[1] = 0x80 | 126; h.writeUInt16BE(p.length, 2); }
  else { h = Buffer.alloc(10); h[0] = 0x81; h[1] = 0x80 | 127; h.writeBigUInt64BE(BigInt(p.length), 2); }
  const m = Buffer.from(p); for (let i = 0; i < m.length; i++) m[i] ^= mask[i % 4];
  return Buffer.concat([h, mask, m]);
}
class CDP {
  constructor(sock) { this.sock = sock; this.id = 0; this.buf = Buffer.alloc(0); this.waiters = new Map(); sock.on('data', d => { this.buf = Buffer.concat([this.buf, d]); this.drain(); }); }
  drain() {
    while (this.buf.length >= 2) {
      const b1 = this.buf[1]; let len = b1 & 0x7f, off = 2;
      if (len === 126) { if (this.buf.length < 4) return; len = this.buf.readUInt16BE(2); off = 4; }
      else if (len === 127) { if (this.buf.length < 10) return; len = Number(this.buf.readBigUInt64BE(2)); off = 10; }
      if (this.buf.length < off + len) return;
      const payload = this.buf.slice(off, off + len); this.buf = this.buf.slice(off + len);
      try { const msg = JSON.parse(payload.toString()); if (msg.id && this.waiters.has(msg.id)) { this.waiters.get(msg.id)(msg); this.waiters.delete(msg.id); } } catch (e) { }
    }
  }
  send(method, params = {}) {
    return new Promise(resolve => {
      const id = ++this.id; this.waiters.set(id, resolve);
      this.sock.write(wsFrame(JSON.stringify({ id, method, params })));
    });
  }
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  let targets;
  for (let i = 0; i < 40; i++) {
    try { targets = await jget('/json/list'); if (targets && targets.length) break; } catch (e) { }
    await sleep(500);
  }
  if (!targets || !targets.length) { console.error('无法连接无头浏览器调试端口 ' + CDP_PORT + '，请先按文件头注释启动 msedge。'); process.exit(2); }
  const page = targets.find(t => t.type === 'page');
  const sock = await wsConnect(page.webSocketDebuggerUrl); const cdp = new CDP(sock);
  await cdp.send('Page.enable');
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: WIDTH, height: HEIGHT, deviceScaleFactor: 1, mobile: false });
  await cdp.send('Page.navigate', { url: TARGET });
  await sleep(4000);
  const evalJs = async expr => {
    const r = await cdp.send('Runtime.evaluate', { expression: expr, returnByValue: true });
    if (r.result?.exceptionDetails) return 'EXC: ' + JSON.stringify(r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text);
    return r.result?.result?.value;
  };
  await evalJs("document.getElementById('guide')?.close()");

  const probe = `(()=>{
   const out={};
   for (const id of ['evidence','mission','history']) {
     const tab=document.querySelector('[data-tab="'+id+'"]');
     if(tab) tab.click();
     else { out[id]={error:'找不到标签页 '+id}; continue; }
     const sec=document.getElementById(id);
     const vis=sec&&sec.offsetParent!==null;
     out[id]={
       visible:vis,
       pageScroll:sec.scrollHeight,
       viewport:innerHeight,
       needsScroll:sec.scrollHeight>innerHeight,
       rails:[...sec.querySelectorAll('aside,.p1-center,.p2-center')].map(a=>({cls:a.className.split(' ')[0],sh:a.scrollHeight,ch:a.clientHeight,scrolls:a.scrollHeight>a.clientHeight+2}))
     };
   }
   const small={};let total=0,below14=0;
   const els=document.querySelectorAll('p,span,td,th,label,button,div,small,h3,h4,li,input,select,option');
   const offenders=[];
   for(const e of els){
     if(!e.offsetParent||!e.textContent.trim())continue;
     const fs=parseFloat(getComputedStyle(e).fontSize); if(!fs)continue; total++;
     if(fs<14){below14++; if(offenders.length<40)offenders.push((e.id?'#'+e.id:'.'+(e.className||'').toString().split(' ')[0])+' '+fs+'px');}
     const k=fs.toFixed(1); small[k]=(small[k]||0)+1;
   }
   out.fonts={total,below14,dist:small,offenders};
   const mt=document.getElementById('mapMiniTop'),mp=document.getElementById('mapMiniTopo');
   out.minimaps={top:!!mt&&mt.width>0,topo:!!mp&&mp.width>0};
   out.bees=!!document.querySelector('.brandbees');
   out._target={width:WIDTH,height:HEIGHT};
   return JSON.stringify(out,null,1);
  })()`.replace(/WIDTH/g, String(WIDTH)).replace(/HEIGHT/g, String(HEIGHT));

  const raw = await evalJs(probe);
  console.log(raw);
  try {
    const o = JSON.parse(raw);
    const bad = [];
    for (const id of ['evidence', 'mission', 'history']) {
      if (o[id]?.needsScroll) bad.push(id + ' 整页需滚动(' + o[id].pageScroll + '>' + o[id].viewport + ')');
      (o[id]?.rails || []).forEach(r => { if (r.scrolls) bad.push(id + ' 容器 .' + r.cls + ' 需滚动(' + r.sh + '>' + r.ch + ')'); });
    }
    if (o.fonts?.below14) bad.push('字号小于 14px 的元素 ' + o.fonts.below14 + ' 个');
    console.log('\n===== 达标判定 =====');
    if (!bad.length) console.log('PASS：三页均一屏可见，字号全部 >= 14px');
    else { console.log('FAIL：'); bad.forEach(b => console.log('  - ' + b)); }
  } catch (e) { }
  process.exit(0);
})();
