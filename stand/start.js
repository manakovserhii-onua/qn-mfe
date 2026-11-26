// Starts every station of the testbed as a separate Node.js process.
// Usage: node stand/start.js config/system.json
'use strict';
const { spawn } = require('child_process');
const path = require('path');
const cfgPath = path.resolve(process.argv[2] || 'config/system.json');
const cfg = require(cfgPath);
const procs = Object.keys(cfg.stations).map(n =>
  spawn(process.execPath, [path.join(__dirname, 'station.js'), n, cfgPath], { stdio: 'inherit' }));
const stop = () => { procs.forEach(p => p.kill()); process.exit(0); };
process.on('SIGINT', stop); process.on('SIGTERM', stop);
