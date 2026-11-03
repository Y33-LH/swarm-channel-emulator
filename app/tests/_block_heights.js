// 列出页面上每个 .panel.rail-block 的实际高度（G5 压缩的数据依据）
// 用法:SWARM_CDP=9344 node _block_heights.js <url>
// 零依赖（node 内置 http/crypto），CDP 客户端与 ui_shot.js 同款。
const http = require('http'), crypto = require('crypto');
const port = Number(process.env.SWARM_CDP || 9333);
const url = process.argv[2] || 'http://127.0.0.1:18878/index.html';

function jget(p) { return new Promise((res, rej) => { http.get({ host: '127.0.0.1', port, path: p }, r => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(JSON.parse(d))); }).on('error', rej); }); }
function wsConnect(u) { return new Promise((resolve, reject) => { const x = new URL(u); const key = crypto.randomBytes(16).toString('base64'); const req = http.request({ host: x.hostname, port: x.port, path: x.pathname + x.search, headers: { Connection: 'Upgrade', Upgrade: 'websocket', 'Sec-WebSocket-Key': key, 'Sec-WebSocket-Version': 13 } }); req.on('upgrade', (r, s) => resolve(s)); req.on('error', reject); req.end(); }); }
function wsFrame(data) { const p = Buffer.from(data); const mask = crypto.randomBytes(4); let h; if (p.length < 126) h = Buffer.from([0x81, 0x80 | p.length]); else { h = Buffer.alloc(4); h[0] = 0x81; h[1] = 0x80 | 126; h.writeUInt16BE(p.length, 2); } const m = Buffer.from(p); for (let i = 0; i < m.length; i++) m[i] ^= mask[i % 4]; return Buffer.concat([h, mask, m]); }
class CDP {
  constructor(s) { this.sock = s; this.id = 0; this.buf = Buffer.alloc(0); this.waiters = new Map(); s.on('data', d => { this.buf = Buffer.concat([this.buf, d]); this.drain(); }); }
  drain() { while (this.buf.length >= 2) { let len = this.buf[1] & 0x7f, off = 2; if (len === 126) { if (this.buf.length < 4) return; len = this.buf.readUInt16BE(2); off = 4; } else if (len === 127) { if (this.buf.length < 10) return; len = Number(this.buf.readBigUInt64BE(2)); off = 10; } if (this.buf.length < off + len) return; const payload = this.buf.slice(off, off + len); this.buf = this.buf.slice(off + len); try { const m = JSON.parse(payload.toString()); if (m.id && this.waiters.has(m.id)) { this.waiters.get(m.id)(m); this.waiters.delete(m.id); } } catch (e) { } } }
  send(method, params = {}) { return new Promise(r => { const id = ++this.id; this.waiters.set(id, r); this.sock.write(wsFrame(JSON.stringify({ id, method, params }))); }); }
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
const EXPR = `(() => {
  const out = [];
  document.querySelectorAll('.param-rail > .panel, .param-rail > details, .param-rail > .rail-tabs, .p2-left > .panel, .p2-right > .panel').forEach(b => {
    const h3 = b.querySelector('h3');
    const tab = b.classList.contains('rail-tabs');
    out.push({ t: tab ? '[tabs] ' + [...b.querySelectorAll('.rail-tab')].map(x => x.textContent).join('|') : (h3 ? h3.textContent.trim() : b.className).slice(0, 22), h: Math.round(b.getBoundingClientRect().height), open: b.tagName === 'DETAILS' ? b.open : undefined });
  });
  return JSON.stringify(out);
})()`;

(async () => {
  let targets; for (let i = 0; i < 20; i++) { try { targets = await jget('/json/list'); break; } catch (e) { await sleep(500); } }
  const page = targets.find(t => t.type === 'page');
  const cdp = new CDP(await wsConnect(page.webSocketDebuggerUrl));
  await cdp.send('Page.enable');
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
  await cdp.send('Page.navigate', { url });
  await sleep(4000);
  await cdp.send('Runtime.evaluate', { expression: "document.getElementById('guide')?.close()" });
  await sleep(600);
  /* 若命令行给了页码参数（1/2/3），先切到该页再量，否则隐藏页量为 0 */
  const pageNo = Number(process.argv[3] || 1);
  if (pageNo > 1) {
    await cdp.send('Runtime.evaluate', { expression: `document.querySelectorAll('.tab')[${pageNo - 1}]?.click()` });
    await sleep(1500);
  }
  await sleep(800);
  const r = await cdp.send('Runtime.evaluate', { expression: EXPR, returnByValue: true });
  const rows = JSON.parse(r.result.result.value || '[]');
  let sum = 0;
  console.log('块高（含折叠条）：');
  for (const x of rows) { console.log(`  ${String(x.h).padStart(5)}px  ${x.open === undefined ? '' : (x.open ? '[开] ' : '[折叠] ')}${x.t}`); sum += x.h; }
  console.log(`  合计约 ${sum}px（另加栏内 gap 14px×块数）`);
  process.exit(0);
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
