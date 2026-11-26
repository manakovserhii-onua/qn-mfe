// Generic service station of the testbed.
// A station has `servers` service slots (a FIFO semaphore). Each visit samples a
// service time from the configured distribution, holds one slot for that time,
// releases it and then forwards the rest of the call chain to the next station
// asynchronously (non-blocking I/O, as in Node.js services): the slot is NOT held
// while downstream stations work. This maps each hop to a separate queueing visit.
//
// Request:  GET /work?chain=gateway:5,profile:6,db:4   (head must be this station)
// Stats:    GET /stats      Reset: GET /reset
'use strict';
const http = require('http');
const { URL } = require('url');

const name = process.argv[2];
const cfg = require(require('path').resolve(process.argv[3]));
const st = cfg.stations[name];
if (!st) { console.error('unknown station', name); process.exit(1); }
const SERVERS = st.servers;
const DIST = cfg.service_distribution || 'exp';
const PAYLOAD = JSON.stringify({ station: name, data: 'x'.repeat(512) });

const agent = new http.Agent({ keepAlive: true, maxSockets: Infinity });
const now = () => Number(process.hrtime.bigint()) / 1e6; // ms

// ---- FIFO semaphore -------------------------------------------------------
let free = SERVERS;
const waitQ = [];
function acquire() {
  if (free > 0) { free--; return Promise.resolve(); }
  return new Promise(res => waitQ.push(res));
}
function release() {
  const next = waitQ.shift();
  if (next) next(); else free++;
}

// ---- statistics -----------------------------------------------------------
let S;
function reset() {
  S = { t0: now(), busy_ms: 0, completions: 0, resid_ms: 0, wait_ms: 0,
        n: 0, n_area: 0, n_t: now() };
}
reset();
function nChange(d) { const t = now(); S.n_area += S.n * (t - S.n_t); S.n_t = t; S.n += d; }

function sample(mean) {
  if (DIST === 'det') return mean;
  return -mean * Math.log(1 - Math.random()); // exponential
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

function callNext(chain) {
  const [head] = chain[0].split(':');
  const port = cfg.stations[head].port;
  return new Promise((resolve, reject) => {
    const req = http.get({ host: '127.0.0.1', port, agent,
      path: '/work?chain=' + encodeURIComponent(chain.join(',')) }, res => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => resolve(body));
    });
    req.on('error', reject);
  });
}

async function handleWork(chain, res) {
  const [head, meanStr] = chain[0].split(':');
  if (head !== name) { res.writeHead(400); return res.end('wrong station'); }
  const tArr = now();
  nChange(+1);
  await acquire();
  const tStart = now();
  await sleep(sample(Number(meanStr)));
  const tEnd = now();
  release();
  nChange(-1);
  S.busy_ms += tEnd - tStart; S.wait_ms += tStart - tArr; S.resid_ms += tEnd - tArr; S.completions++;
  let body = PAYLOAD;
  if (chain.length > 1) body = await callNext(chain.slice(1));
  res.writeHead(200, { 'content-type': 'application/json' });
  res.end(body);
}

http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x');
  if (u.pathname === '/work') {
    const chain = (u.searchParams.get('chain') || '').split(',').filter(Boolean);
    handleWork(chain, res).catch(e => { res.writeHead(500); res.end(String(e)); });
  } else if (u.pathname === '/stats') {
    nChange(0);
    const T = now() - S.t0;
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ station: name, servers: SERVERS, T_ms: T, busy_ms: S.busy_ms,
      completions: S.completions, resid_ms: S.resid_ms, wait_ms: S.wait_ms, n_area: S.n_area }));
  } else if (u.pathname === '/reset') {
    reset(); res.end('ok');
  } else { res.writeHead(404); res.end(); }
}).listen(st.port, '127.0.0.1', () => console.log(`${name} on ${st.port} (c=${SERVERS})`));
