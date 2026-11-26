#!/usr/bin/env bash
# Validation of the what-if prediction: monolithic SPA on the baseline testbed (config A).
set -u
cd "$(dirname "$0")/.."
mkdir -p results/raw_mono
node stand/start.js config/system.json > results/stand_mono.log 2>&1 &
SP=$!; sleep 2
for N in 10 50 90 130; do for r in 1 2; do
  node loadgen/loadgen.js config/system.json mono $N 10 60 results/raw_mono/mono_N${N}_r${r}.json
done; done
kill $SP
python3 - <<'PY'
import glob, json, re, pandas as pd
rows=[]
for f in glob.glob('results/raw_mono/*.json'):
    r=json.load(open(f)); rows.append(dict(N=r['N'], X=r['X'], R=r['R_mean']))
pd.DataFrame(rows).groupby('N').mean().reset_index().to_csv('results/measurements_mono.csv', index=False)
PY
echo MONO_DONE
