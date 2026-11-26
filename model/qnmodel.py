"""Analytical closed queueing-network models of a micro-frontend page load.

Three models are compared (ablation):
  M1  'seq'  - classic exact MVA, the page is treated as a sequence of all its requests;
  M2  'fj'   - MVA + fork-join: page time = sequential part + E[max of branch times];
  M3  'fjs'  - M2 + correction for sibling sub-requests of the same page that meet
               in a shared station (simultaneous arrivals at the fork, and
               time-overlap of siblings later in the branches).
Multi-server stations use Seidmann's approximation (queueing part d/c,
delay part d(c-1)/c). Branch time distribution: constant client delay plus a sum
of exponential residence times (hypoexponential), E[max] computed numerically.
"""
import json
import numpy as np
from scipy.signal import fftconvolve


def load(cfg_path, arch='mfe', demand_scale=None):
    cfg = json.load(open(cfg_path))
    A = cfg['architectures'][arch]
    st = {k: v['servers'] for k, v in cfg['stations'].items()}
    sc = demand_scale or {}

    def visits(reqs):
        out = []
        for r in reqs:
            for s, d in r['chain']:
                out.append((s, d * sc.get(s, 1.0)))
        return out
    seq = visits(A['sequential'])
    seq_http = len(A['sequential'])
    br = [visits(b['requests']) for b in A.get('parallel', [])]
    br_http = [len(b['requests']) for b in A.get('parallel', [])]
    return dict(cfg=cfg, servers=st, Z=cfg['think_time_ms'], rtt=cfg['client_rtt_ms'],
                seq=seq, seq_http=seq_http, br=br, br_http=br_http)


def station_demands(m):
    D = {k: 0.0 for k in m['servers']}
    for s, d in m['seq'] + [v for b in m['br'] for v in b]:
        D[s] += d
    return D


def _hypo_max_mean(branches, dt=0.2):
    """E[max_b (c_b + sum_i Exp(mean_i))] for independent branches."""
    if not branches:
        return 0.0, []
    horizon = max(c + 12 * sum(ms) + 10 for c, ms in branches)
    t = np.arange(0, horizon, dt)
    cdfs = []
    for c, ms in branches:
        pdf = None
        for mu in ms:
            if mu <= 1e-9:
                continue
            p = np.exp(-t / mu) / mu * dt
            pdf = p if pdf is None else fftconvolve(pdf, p)[:len(t)]
        if pdf is None:
            pdf = np.zeros(len(t)); pdf[0] = 1.0
        cdf = np.clip(np.cumsum(pdf), 0, 1)
        shift = int(round(c / dt))
        cdf = np.concatenate([np.zeros(shift), cdf])[:len(t)]
        cdfs.append(cdf)
    F = np.prod(cdfs, axis=0)
    return float(np.sum(1 - F) * dt), [float(np.sum(1 - f) * dt) for f in cdfs]


def _first_visit_sibling_wait(m_arr, c, d):
    """Mean wait of one of m_arr simultaneous sibling arrivals at an idle c-server station."""
    return (d / c) * np.mean([max(0, j - c + 1) for j in range(m_arr)])


def solve(m, N, model='fjs'):
    """Returns dict with X (pages/ms), R (ms), U, residences for population 1..N (last)."""
    S = m['servers']; Z = m['Z']; rtt = m['rtt']
    stations = list(S)
    allv = m['seq'] + [v for b in m['br'] for v in b]
    D = station_demands(m)
    # stations that receive the first request of more than one branch simultaneously
    first = {}
    for b in m['br']:
        if b:
            first.setdefault(b[0][0], []).append(b[0][1])
    Qq = {k: 0.0 for k in stations}       # queueing-part population (Seidmann)
    hist = []
    for n in range(1, N + 1):
        def resid(s, d, extra=0.0):
            c = S[s]
            return d + (d / c) * (Qq[s] + extra)
        if model == 'seq':
            r = [resid(s, d) for s, d in allv]
            R = sum(r) + rtt * (m['seq_http'] + sum(m['br_http']))
            X = n / (Z + R)
            newQ = {k: 0.0 for k in stations}
            for (s, d), rv in zip(allv, r):
                newQ[s] += X * (rv - d * (S[s] - 1) / S[s])
            Qq = newQ
            hist.append(dict(n=n, X=X, R=R))
            continue
        r_seq = [resid(s, d) for s, d in m['seq']]
        T_seq = sum(r_seq) + rtt * m['seq_http']
        # previous-iteration per-branch residence at each station (for time overlap)
        prev = hist[-1]['br_res'] if hist else None
        prevF = hist[-1]['Efork'] if hist else None
        r_br = []
        for bi, b in enumerate(m['br']):
            rb = []
            for vi, (s, d) in enumerate(b):
                extra_w = 0.0; extra_q = 0.0
                if model == 'fjs':
                    if vi == 0 and len(first.get(s, [])) > 1:
                        extra_w = _first_visit_sibling_wait(len(first[s]), S[s], d)
                    elif prev is not None and prevF:
                        # expected number of siblings found at s (time-overlap estimate)
                        sib = sum(prev[bj].get(s, 0.0) for bj in range(len(m['br'])) if bj != bi)
                        extra_q = sib / prevF
                rb.append(resid(s, d, extra_q) + extra_w)
            r_br.append(rb)
        branches = [(rtt * h, rb) for h, rb in zip(m['br_http'], r_br)]
        Emax, Eb = _hypo_max_mean(branches)
        R = T_seq + Emax
        X = n / (Z + R)
        newQ = {k: 0.0 for k in stations}
        for (s, d), rv in zip(m['seq'], r_seq):
            newQ[s] += X * (rv - d * (S[s] - 1) / S[s])
        br_res = []
        for b, rb in zip(m['br'], r_br):
            acc = {}
            for (s, d), rv in zip(b, rb):
                newQ[s] += X * (rv - d * (S[s] - 1) / S[s])
                acc[s] = acc.get(s, 0.0) + rv
            br_res.append(acc)
        Qq = newQ
        hist.append(dict(n=n, X=X, R=R, T_seq=T_seq, Efork=Emax, Eb=Eb, br_res=br_res))
    last = hist[-1]
    U = {k: last['X'] * D[k] / S[k] for k in stations}
    return dict(N=N, X=last['X'] * 1000, R=last['R'], U=U,
                branch_means=last.get('Eb'), fork=last.get('Efork'), seq=last.get('T_seq'),
                series={h['n']: (h['X'] * 1000, h['R']) for h in hist})


def bounds(m):
    D = station_demands(m); S = m['servers']
    Dmax = max(D[k] / S[k] for k in D)
    return dict(Xmax=1000 / Dmax, bottleneck=max(D, key=lambda k: D[k] / S[k]))


if __name__ == '__main__':
    import sys
    m = load(sys.argv[1] if len(sys.argv) > 1 else 'config/system.json')
    print(station_demands(m), bounds(m))
    for N in (1, 10, 40, 80, 120, 150):
        print(N, {k: round(solve(m, N, k)['R'], 1) for k in ('seq', 'fj', 'fjs')},
              {k: round(solve(m, N, k)['X'], 2) for k in ('seq', 'fj', 'fjs')})
