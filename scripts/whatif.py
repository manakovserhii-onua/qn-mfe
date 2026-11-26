"""What-if analysis with the calibrated model M3 (fjs), checked by simulation:
  W1  micro-frontend vs monolithic SPA, response time vs population N;
  W2  sensitivity of the page response time to client network delay (RTT);
  W3  scaling out the bottleneck service (variant B) - capacity and N*.
Usage: python3 scripts/whatif.py  (after scripts/analyze.py, uses results/calibration.json)"""
import copy, json, sys
import numpy as np
import pandas as pd
sys.path.insert(0, 'model')
import qnmodel as qm
import sim as qs

scale = json.load(open('results/calibration.json'))['scale']
out = {}

# W1: architectures vs N
rows = []
for arch in ('mfe', 'mono'):
    for tag, path in (('A', 'config/system.json'), ('B', 'config/system_B_scaled.json')):
        m = qm.load(path, arch, scale)
        ser = qm.solve(m, 160, 'fjs')['series']
        for N in range(5, 161, 5):
            rows.append(dict(arch=arch, cfg=tag, N=N, X=ser[N][0], R=ser[N][1]))
w1 = pd.DataFrame(rows); w1.to_csv('results/whatif_arch_N.csv', index=False)

# W2: RTT sensitivity at moderate load (N = 30)
rows = []
for rtt in (0, 10, 20, 40, 60, 80, 100, 150):
    for arch in ('mfe', 'mono'):
        m = qm.load('config/system.json', arch, scale); m['rtt'] = rtt
        R = qm.solve(m, 30, 'fjs')['R']
        rows.append(dict(arch=arch, rtt=rtt, R=R))
w2 = pd.DataFrame(rows)
# simulation check at three RTT values
cfg = json.load(open('config/system.json'))
for rtt in (20, 80, 150):
    cfg2 = copy.deepcopy(cfg); cfg2['client_rtt_ms'] = rtt
    p = f'/tmp/cfg_rtt{rtt}.json'; json.dump(cfg2, open(p, 'w'))
    for arch in ('mfe', 'mono'):
        s = np.mean([qs.simulate(p, 30, arch, T=1_200_000, warm=100_000, seed=k, demand_scale=scale)['R'] for k in (1, 2)])
        w2.loc[(w2.arch == arch) & (w2.rtt == rtt), 'R_sim'] = s
w2.to_csv('results/whatif_rtt.csv', index=False)

# W1b: simulation check of the monolith after scaling out the bottleneck (config B)
rows = []
for N in (50, 90, 110, 140):
    r = [qs.simulate('config/system_B_scaled.json', N, 'mono', T=1_200_000, warm=100_000, seed=k, demand_scale=scale) for k in (1, 2)]
    rows.append(dict(N=N, X=np.mean([x['X'] for x in r]), R=np.mean([x['R'] for x in r])))
pd.DataFrame(rows).to_csv('results/whatif_monoB_sim.csv', index=False)

# W3: bounds
for tag, path in (('A', 'config/system.json'), ('B', 'config/system_B_scaled.json')):
    for arch in ('mfe', 'mono'):
        m = qm.load(path, arch, scale)
        D = qm.station_demands(m); S = m['servers']
        Dmax = max(D[k] / S[k] for k in D)
        R1 = qm.solve(m, 1, 'fjs')['R']
        out[f'{tag}_{arch}'] = dict(Xmax=1000 / Dmax, bottleneck=max(D, key=lambda k: D[k] / S[k]),
                                    R1=R1, Nstar=(R1 + m['Z']) / Dmax)
json.dump(out, open('results/whatif_bounds.json', 'w'), indent=1)
print(json.dumps(out, indent=1)); print(w2.round(1))
