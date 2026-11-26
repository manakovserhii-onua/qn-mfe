// Closed-workload load generator that reproduces a browser page load of a
// micro-frontend application: sequential part (shell, profile API), then a
// fork of K parallel branches (remoteEntry -> chunk -> API) and a join.
// Each HTTP request from the "browser" adds a fixed client network delay (RTT).
//
// Usage: node loadgen/loadgen.js <config> <arch> <N users> <warmup s> <measure s> <out.json>
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');

const [cfgPath, arch, Nstr, warmS, measS, out] = process.argv.slice(2);
const cfg = require(path.resolve(cfgPath));
const A = cfg.architectures[arch];
const N = Number(Nstr), WARM = Number(warmS) * 1000, MEAS = Number(measS) * 1000;
const Z = cfg.think_time_ms, RTT = cfg.client_rtt_ms;

const agent = new http.Agent({ keepAlive: true, maxSockets: Infinity });
const now = () => Number(process.hrtime.bigint()) / 1e6;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const expo = m => -m * Math.log(1 - Math.random());

function get(port, p) {
  return new Promise((resolve, reject) => {
    http.get({ host: '127.0.0.1', port, path: p, agent }, res => {
      let b = ''; res.on('data', c => b += c); res.on('end', () => resolve(b));
    }).on('error', reject);
  });
}
const chainStr = ch => ch.map(([s, d]) => `${s}:${d}`).join(',');
async function request(r) {               // one browser HTTP request
  await sleep(RTT / 2);
  await get(cfg.stations[r.chain[0][0]].port, '/work?chain=' + encodeURIComponent(chainStr(r.chain)));
  await sleep(RTT / 2);
}
async function branch(b) { const t = now(); for (const r of b.requests) await request(r); return now() - t; }

async function page() {
  const t0 = now();
  for (const r of A.sequential) await request(r);
  const tf = now();
  const bt = await Promise.all((A.parallel || []).map(branch));
  const t1 = now();
  return { t0, t1, R: t1 - t0, seq: tf - t0, fork: t1 - tf, branches: bt };
}

let measuring = false, stopAll = false, tMeasStart = 0;
const recs = [];
async function user() {
  await sleep(Math.random() * Z);                      // desynchronise start
  while (!stopAll) {
    await sleep(expo(Z));
    if (stopAll) break;
    const p = await page();
    if (measuring && p.t1 >= tMeasStart) recs.push(p);
  }
}

async function stationStats(cmd) {
  const res = {};
  for (const [n, s] of Object.entries(cfg.stations)) res[n] = await get(s.port, '/' + cmd);
  return res;
}
const mean = a => a.reduce((x, y) => x + y, 0) / (a.length || 1);
const pct = (a, q) => { const s = [...a].sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.floor(q * s.length))]; };

(async () => {
  const users = Array.from({ length: N }, user);
  await sleep(WARM);
  await stationStats('reset');
  tMeasStart = now(); measuring = true;
  await sleep(MEAS);
  measuring = false;
  const T = (now() - tMeasStart) / 1000;
  const raw = await stationStats('stats');
  stopAll = true;
  await Promise.race([Promise.all(users), sleep(5000)]);
  const pages = recs.length, X = pages / T;
  const R = recs.map(r => r.R);
  const stations = {};
  for (const [n, js] of Object.entries(raw)) {
    const s = JSON.parse(js), Ts = s.T_ms / 1000;
    stations[n] = { servers: s.servers, U: s.busy_ms / (s.servers * s.T_ms), X: s.completions / Ts,
      D_ms: pages ? s.busy_ms / (X * Ts) : null,           // demand per page (utilisation law)
      resid_per_page_ms: pages ? s.resid_ms / (X * Ts) : null,
      Q: s.n_area / s.T_ms, completions: s.completions };
  }
  const result = { arch, N, Z_ms: Z, rtt_ms: RTT, T_s: T, pages, X, R_mean: mean(R),
    R_p50: pct(R, 0.5), R_p95: pct(R, 0.95), seq_mean: mean(recs.map(r => r.seq)),
    fork_mean: mean(recs.map(r => r.fork)),
    branch_means: (A.parallel || []).map((b, i) => mean(recs.map(r => r.branches[i]))), stations };
  fs.writeFileSync(out, JSON.stringify(result, null, 1));
  console.log(`N=${N} X=${X.toFixed(2)}/s R=${result.R_mean.toFixed(1)}ms p95=${result.R_p95.toFixed(0)} ` +
    Object.entries(stations).map(([n, s]) => `${n}:U=${s.U.toFixed(2)}`).join(' '));
  process.exit(0);
})();
