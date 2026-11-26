"""Discrete-event simulation (SimPy) of the same closed network with exact
fork-join semantics of the page load: N users, exponential think time,
FIFO multi-server stations, exponential service, constant client delay per HTTP request."""
import json, sys
import numpy as np
import simpy


def simulate(cfg_path, N, arch='mfe', T=3000_000.0, warm=200_000.0, seed=1, demand_scale=None):
    cfg = json.load(open(cfg_path))
    A = cfg['architectures'][arch]
    sc = demand_scale or {}
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    res = {k: simpy.Resource(env, capacity=v['servers']) for k, v in cfg['stations'].items()}
    busy = {k: 0.0 for k in res}
    Z, rtt = cfg['think_time_ms'], cfg['client_rtt_ms']
    rec = []

    def visit(s, d):
        with res[s].request() as rq:
            yield rq
            t = rng.exponential(d * sc.get(s, 1.0))
            if env.now >= warm:
                busy[s] += t
            yield env.timeout(t)

    def request(r):
        yield env.timeout(rtt / 2)
        for s, d in r['chain']:
            yield from visit(s, d)
        yield env.timeout(rtt / 2)

    def branch(b):
        for r in b['requests']:
            yield from request(r)

    def user():
        yield env.timeout(rng.uniform(0, Z))
        while True:
            yield env.timeout(rng.exponential(Z))
            t0 = env.now
            for r in A['sequential']:
                yield from request(r)
            procs = [env.process(branch(b)) for b in A.get('parallel', [])]
            if procs:
                yield simpy.AllOf(env, procs)
            if t0 >= warm:
                rec.append(env.now - t0)

    for _ in range(N):
        env.process(user())
    env.run(until=warm + T)
    X = len(rec) / T * 1000
    U = {k: busy[k] / (cfg['stations'][k]['servers'] * T) for k in res}
    return dict(N=N, X=X, R=float(np.mean(rec)), R_p95=float(np.percentile(rec, 95)), U=U, pages=len(rec))


if __name__ == '__main__':
    for N in map(int, sys.argv[2:]):
        r = simulate(sys.argv[1], N, T=600_000)
        print(N, round(r['X'], 2), round(r['R'], 1), {k: round(v, 2) for k, v in r['U'].items()})
