"""Bottleneck demand actually realized in each run (utilization law, D = U*c/X) and
method M3 recomputed with the demands measured in the same runs (near-saturation check).
Usage: python3 scripts/realized_demand.py   (from the repository root)"""
import json, sys
import pandas as pd
sys.path.insert(0, 'model')
import qnmodel as qm

CFG = {'A': 'config/system.json', 'B': 'config/system_B_scaled.json'}
raw = pd.read_csv('results/measurements_raw.csv')
cal = json.load(open('results/calibration.json'))
st = [c[2:] for c in raw.columns if c.startswith('D_')]

print('Per run, bottleneck "electives" (configuration A):')
for _, r in raw[(raw.cfg == 'A') & (raw.N >= 90)].iterrows():
    print(f"  N={r.N:3d} rep={r.rep}  X={r.X:6.2f}  U={r.U_electives:.4f}  D={r.D_electives:5.2f} ms"
          f"  (calibrated {cal['D_calibrated']['electives']:.2f})  limit 1/D={1000 / r.D_electives:5.2f} pages/s")

rows = []
for tag, path in CFG.items():
    Dc = qm.station_demands(qm.load(path))
    for N in (90, 110, 140):
        g = raw[(raw.cfg == tag) & (raw.N == N)]
        scale = {k: g['D_' + k].mean() / Dc[k] for k in st}
        X, R = qm.solve(qm.load(path, demand_scale=scale), N, 'fjs')['series'][N]
        rows.append(dict(cfg=tag, N=N, X_meas=g.X.mean(), R_meas=g.R.mean(), X_M3=X, R_M3=R,
                         eR=(R - g.R.mean()) / g.R.mean() * 100))
out = pd.DataFrame(rows)
out.to_csv('results/realized_demand_M3.csv', index=False)
print('\nMethod M3 with demands measured in the same runs:')
print(out.round(2).to_string(index=False))
