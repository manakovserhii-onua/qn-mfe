"""Aggregates the measurement campaign, calibrates the models and compares
testbed <-> analytical models (M1 seq, M2 fj, M3 fjs) <-> simulation.
Usage: python3 scripts/analyze.py   (from the repository root)"""
import glob, json, os, re, sys
import numpy as np
import pandas as pd
sys.path.insert(0, 'model')
import qnmodel as qm
import sim as qs

CFG = {'A': 'config/system.json', 'B': 'config/system_B_scaled.json'}
os.makedirs('results', exist_ok=True)

# ---------- 1. measurements -------------------------------------------------
rows = []
for f in sorted(glob.glob('results/raw/*.json')):
    tag, N, rep = re.match(r'.*/([AB])_N(\d+)_r(\d+)\.json', f).groups()
    r = json.load(open(f))
    row = dict(cfg=tag, N=int(N), rep=int(rep), X=r['X'], R=r['R_mean'], R95=r['R_p95'],
               seq=r['seq_mean'], fork=r['fork_mean'])
    for k, s in r['stations'].items():
        row['U_' + k] = s['U']; row['D_' + k] = s['D_ms']
    rows.append(row)
raw = pd.DataFrame(rows)
raw.to_csv('results/measurements_raw.csv', index=False)
meas = raw.groupby(['cfg', 'N']).agg(['mean', 'std']).drop(columns='rep')
stations = [c[2:] for c in raw.columns if c.startswith('U_')]

# ---------- 2. calibration (utilisation law at the lowest load of variant A) ----
base = qm.station_demands(qm.load(CFG['A']))
lowA = raw[(raw.cfg == 'A') & (raw.N == raw[raw.cfg == 'A'].N.min())]
Dcal = {k: lowA['D_' + k].mean() for k in stations}
scale = {k: Dcal[k] / base[k] for k in stations}
json.dump(dict(D_config=base, D_calibrated=Dcal, scale=scale), open('results/calibration.json', 'w'), indent=1)

# ---------- 3. predictions ---------------------------------------------------
pred = []
for tag, path in CFG.items():
    Ns = sorted(raw[raw.cfg == tag].N.unique())
    m = qm.load(path, demand_scale=scale)
    for model in ('seq', 'fj', 'fjs'):
        ser = qm.solve(m, max(Ns), model)['series']
        for N in Ns:
            pred.append(dict(cfg=tag, N=N, model=model, X=ser[N][0], R=ser[N][1]))
    for N in Ns:
        sims = [qs.simulate(path, N, T=1_200_000, warm=100_000, seed=s, demand_scale=scale) for s in (1, 2, 3)]
        pred.append(dict(cfg=tag, N=N, model='sim', X=np.mean([s['X'] for s in sims]),
                         R=np.mean([s['R'] for s in sims]), R_sd=np.std([s['R'] for s in sims])))
pred = pd.DataFrame(pred)
pred.to_csv('results/predictions.csv', index=False)

# ---------- 4. errors ---------------------------------------------------------
cmp_rows = []
for (tag, N), g in pred.groupby(['cfg', 'N']):
    mX, mR = meas.loc[(tag, N), ('X', 'mean')], meas.loc[(tag, N), ('R', 'mean')]
    for _, p in g.iterrows():
        cmp_rows.append(dict(cfg=tag, N=N, model=p.model, X_meas=mX, R_meas=mR, X_pred=p.X, R_pred=p.R,
                             eX=abs(p.X - mX) / mX * 100, eR=abs(p.R - mR) / mR * 100))
cmp = pd.DataFrame(cmp_rows)
cmp.to_csv('results/comparison.csv', index=False)
mape = cmp.groupby(['cfg', 'model'])[['eX', 'eR']].mean().round(2)
mape.to_csv('results/mape.csv')
print('calibration scale:', {k: round(v, 3) for k, v in scale.items()})
print(meas.xs('mean', axis=1, level=1)[['X', 'R', 'R95']].round(1))
print(cmp.pivot_table(index=['cfg', 'N'], columns='model', values='R_pred').round(1))
print('MAPE, %:\n', mape)
