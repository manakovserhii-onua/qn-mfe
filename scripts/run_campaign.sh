#!/usr/bin/env bash
# Measurement campaign: for each configuration start the testbed, run the closed
# workload at several populations N with repetitions, then stop the testbed.
# Usage: scripts/run_campaign.sh <warmup s> <measure s> <reps>
set -u
cd "$(dirname "$0")/.."
WARM=${1:-10}; MEAS=${2:-60}; REPS=${3:-3}
LEVELS="10 30 50 70 90 110 140"
for CFG in A:config/system.json B:config/system_B_scaled.json; do
  TAG=${CFG%%:*}; FILE=${CFG#*:}
  node stand/start.js "$FILE" > results/stand_$TAG.log 2>&1 &
  SP=$!; sleep 2
  for N in $LEVELS; do for r in $(seq 1 $REPS); do
    node loadgen/loadgen.js "$FILE" mfe $N $WARM $MEAS results/raw/${TAG}_N${N}_r${r}.json
  done; done
  kill $SP; sleep 2
done
echo CAMPAIGN_DONE
