"""Black-and-white figures for the paper (journal: grayscale, TIFF 300 dpi, <= 17 cm).
Usage: python3 scripts/figures.py uk|en"""
import json, subprocess, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

L = sys.argv[1] if len(sys.argv) > 1 else 'uk'
T = {
 'uk': dict(N='Кількість користувачів N', R='Час відгуку сторінки R, мс', X='Пропускна здатність X, сторінок/с',
            meas='Стенд (вимірювання)', seq='M1: класичний MVA', fj='M2: MVA з fork-join',
            fjs='M3: запропонований метод', sim='Імітаційна модель (SimPy)', sim_s='імітаційна модель',
            A='а) базова конфігурація', B='б) масштабоване вузьке місце', U='Завантаження U',
            mfe='Мікрофронтенди', mono='Монолітний клієнт', rtt='Мережна затримка клієнта τ, мс',
            w1='а) X(N) після масштабування вузького місця', w2='б) R(τ) за N = 30', mon_meas='стенд',
            ms='мс', think='Користувачі\n(обдумування Z,\nзатримка τ)', fork='розгалуження', join='злиття',
            st=dict(edge='Edge', gateway='Шлюз', profile='Профіль', schedule='Розклад', grades='Успішність',
                    electives='Вибіркові', db='СКБД')),
 'en': dict(N='Number of users N', R='Page response time R, ms', X='Throughput X, pages/s',
            meas='Testbed (measured)', seq='M1: classic MVA', fj='M2: MVA with fork-join',
            fjs='M3: proposed method', sim='Simulation model (SimPy)', sim_s='simulation model',
            A='a) baseline configuration', B='b) scaled-out bottleneck', U='Utilization U',
            mfe='Micro-frontends', mono='Monolithic client', rtt='Client network delay τ, ms',
            w1='a) X(N) after scaling out the bottleneck', w2='b) R(τ) at N = 30', mon_meas='testbed',
            ms='ms', think='Users\n(think time Z,\ndelay τ)', fork='fork', join='join',
            st=dict(edge='Edge', gateway='Gateway', profile='Profile', schedule='Schedule', grades='Grades',
                    electives='Electives', db='DBMS')),
}[L]
plt.rcParams.update({'font.family': 'Liberation Serif', 'font.size': 9, 'axes.linewidth': 0.6,
                     'lines.linewidth': 1.0, 'legend.fontsize': 7.5, 'legend.frameon': False})
STY = {'seq': dict(ls=':', color='0.35'), 'fj': dict(ls='--', color='0.2'),
       'fjs': dict(ls='-', color='0.0'), 'sim': dict(ls='none', marker='x', color='0.3', ms=5)}
CM = 1 / 2.54


def sub(ax, text):
    """Subfigure label (а), (б) placed under the axes, below the x-axis title."""
    ax.annotate(text, xy=(0.5, 0), xycoords='axes fraction', xytext=(0, -32), textcoords='offset points',
                ha='center', va='top', fontsize=9)


def save(fig, name):
    p = f'results/fig/{L}_{name}'
    fig.savefig(p + '.png', dpi=300, bbox_inches='tight')
    Image.open(p + '.png').convert('L').save(p + '.tif', dpi=(300, 300), compression='tiff_lzw')
    plt.close(fig)


subprocess.run(['mkdir', '-p', 'results/fig'])
raw = pd.read_csv('results/measurements_raw.csv')
pred = pd.read_csv('results/predictions.csv')
meas = raw.groupby(['cfg', 'N']).agg(X=('X', 'mean'), Xs=('X', 'std'), R=('R', 'mean'), Rs=('R', 'std')).reset_index()

# Fig. 2 - response time vs N
fig, axs = plt.subplots(1, 2, figsize=(17 * CM, 6.2 * CM), sharey=True)
for ax, tag in zip(axs, 'AB'):
    mm = meas[meas.cfg == tag]
    for mod in ('seq', 'fj', 'fjs', 'sim'):
        p = pred[(pred.cfg == tag) & (pred.model == mod)]
        ax.plot(p.N, p.R, label=T[mod], **STY[mod])
    ax.errorbar(mm.N, mm.R, yerr=mm.Rs, fmt='o', mfc='white', mec='black', ecolor='black', ms=4,
                capsize=2, label=T['meas'], zorder=5)
    sub(ax, T[tag]); ax.set_xlabel(T['N']); ax.grid(alpha=0.3, lw=0.4)
axs[0].set_ylabel(T['R']); axs[0].legend(loc='upper left')
save(fig, 'fig2_R_vs_N')

# Fig. 3 - throughput vs N and bottleneck utilization
fig, axs = plt.subplots(1, 2, figsize=(17 * CM, 6.2 * CM)); fig.subplots_adjust(wspace=0.32)
for tag, mk in (('A', 'o'), ('B', 's')):
    mm = meas[meas.cfg == tag]; p = pred[(pred.cfg == tag) & (pred.model == 'fjs')]
    axs[0].plot(p.N, p.X, color='black', ls='-' if tag == 'A' else '--', label=f"M3 ({tag})")
    axs[0].errorbar(mm.N, mm.X, yerr=mm.Xs, fmt=mk, mfc='white', mec='black', ecolor='black', ms=4,
                    capsize=2, label=f"{T['mon_meas']} ({tag})")
axs[0].set_xlabel(T['N']); axs[0].set_ylabel(T['X']); axs[0].legend(loc='lower right'); axs[0].grid(alpha=0.3, lw=0.4)
sub(axs[0], T['A'][:3] + ('пропускна здатність' if L == 'uk' else 'throughput'))
ua = raw[raw.cfg == 'A'].groupby('N').mean(numeric_only=True)
grays = ['0.0', '0.25', '0.45', '0.6', '0.75', '0.3', '0.5']
mks = ['o', 's', '^', 'v', 'D', 'x', '+']
for i, st in enumerate(['electives', 'edge', 'grades', 'db', 'schedule', 'gateway', 'profile']):
    axs[1].plot(ua.index, ua['U_' + st], marker=mks[i], color=grays[i], ms=3.5, mfc='white', label=T['st'][st])
axs[1].set_xlabel(T['N']); axs[1].set_ylabel(T['U']); axs[1].set_ylim(0, 1.32); axs[1].set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0]); axs[1].legend(ncol=4, loc='upper center', fontsize=6.5, columnspacing=0.8, handlelength=1.6)
axs[1].grid(alpha=0.3, lw=0.4)
sub(axs[1], 'б) завантаження станцій (конфігурація A)' if L == 'uk' else 'b) station utilization (config. A)')
save(fig, 'fig3_X_U')

# Fig. 4 - what-if
try:
    w1 = pd.read_csv('results/whatif_arch_N.csv'); w2 = pd.read_csv('results/whatif_rtt.csv')
    fig, axs = plt.subplots(1, 2, figsize=(17 * CM, 6.2 * CM)); fig.subplots_adjust(wspace=0.32)
    for arch, ls in (('mfe', '-'), ('mono', '--')):
        p = w1[(w1.arch == arch) & (w1.cfg == 'B') & (w1.N <= 145)]
        axs[0].plot(p.N, p.X, color='black', ls=ls, label=f"{T[arch]}, M3")
    mm = meas[meas.cfg == 'B']
    axs[0].plot(mm.N, mm.X, 'o', mfc='white', mec='black', ms=4, label=f"{T['mfe']}, {T['mon_meas']}")
    sb = pd.read_csv('results/whatif_monoB_sim.csv')
    axs[0].plot(sb.N, sb.X, 's', color='0.3', mfc='none', ms=5, label=f"{T['mono']}, {T['sim_s']}")
    axs[0].set_xlabel(T['N']); axs[0].set_ylabel(T['X']); axs[0].legend(loc='upper left'); sub(axs[0], T['w1'])
    axs[0].grid(alpha=0.3, lw=0.4); axs[0].set_xlim(0, 145)
    for arch, ls, mk in (('mfe', '-', 'o'), ('mono', '--', 's')):
        p = w2[w2.arch == arch]
        axs[1].plot(p.rtt, p.R, color='black', ls=ls, label=T[arch])
        q = p.dropna(subset=['R_sim'])
        axs[1].plot(q.rtt, q.R_sim, mk, color='0.3', mfc='none', ms=5, label=f"{T[arch]}, {T['sim_s']}")
    axs[1].set_xlabel(T['rtt']); axs[1].set_ylabel(T['R']); axs[1].legend(); sub(axs[1], T['w2'])
    axs[1].grid(alpha=0.3, lw=0.4)
    save(fig, 'fig4_whatif')
except FileNotFoundError:
    pass

# Fig. 1 - page-load task graph mapped to stations (Graphviz)
cfg = json.load(open('config/system.json'))
A = cfg['architectures']['mfe']
dot = ['digraph G {', 'rankdir=LR; bgcolor=white; nodesep=0.12; ranksep=0.22;',
       'node [shape=box, style="rounded", fontname="Liberation Serif", fontsize=10, height=0.3, color=black];',
       'edge [arrowsize=0.6, color=black];',
       f'U [label="{T["think"]}", shape=box, style="dashed"];']
prev = 'U'; i = 0
def lab(r):
    names = '→'.join(T['st'][st] for st, _ in r['chain'])
    ds = '+'.join(str(d) for _, d in r['chain'])
    return f"{r['name']}\\n{names}\\n{ds} {T['ms']}"
for r in A['sequential']:
    i += 1; n = f'n{i}'
    dot.append(f'{n} [label="{lab(r)}"];'); dot.append(f'{prev} -> {n};'); prev = n
dot.append(f'F [label="{T["fork"]}", shape=circle, fontsize=9, margin=0.02];')
dot.append(f'{prev} -> F;')
dot.append(f'J [label="{T["join"]}", shape=circle, fontsize=9, margin=0.02];')
for b in A['parallel']:
    p = 'F'
    for r in b['requests']:
        i += 1; n = f'n{i}'
        dot.append(f'{n} [label="{lab(r)}"];'); dot.append(f'{p} -> {n};'); p = n
    dot.append(f'{p} -> J;')
dot.append('J -> U [constraint=false, style=dashed];')
dot.append('}')
open('results/fig/page_graph.dot', 'w').write('\n'.join(dot))
subprocess.run(['dot', '-Tpng', '-Gdpi=300', 'results/fig/page_graph.dot', '-o', f'results/fig/{L}_fig1_page_graph.png'])
Image.open(f'results/fig/{L}_fig1_page_graph.png').convert('L').save(f'results/fig/{L}_fig1_page_graph.tif', dpi=(300, 300), compression='tiff_lzw')
print('figures done')
