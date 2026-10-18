"""
Figure della relazione di verifica (PNG) dai dati di relazione_dati_campione.py.

Uso: python relazione_figure.py <cartella dati> <controllo_coordinate.gpkg> <out_dir>
"""
import glob
import os
import sys

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Patch

dati, cgpkg, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Liberation Serif', 'Times New Roman', 'DejaVu Serif'], 'font.size': 9, 'axes.titlesize': 10})
COL_A, COL_B = '#1f6fd1', '#e07b12'
INK, MUTED = '#222222', '#666666'
TR = gpd.read_file(cgpkg, layer='tracciato_usato').set_index('ID').geometry
INI = gpd.read_file(cgpkg, layer='db_inizio').set_index('ID').geometry
FIN = gpd.read_file(cgpkg, layer='db_fine').set_index('ID').geometry
V = pd.concat([pd.read_csv(f) for f in glob.glob(os.path.join(dati, 'valori_*.csv'))]).drop_duplicates('ID').set_index('ID')


def estensione(T, shape):
    a, b, c, d, e, f = T
    return (c, c + a * shape[1], f + e * shape[0], f)


def scala(ax, L):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    lung = [10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000][
        np.searchsorted([10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000], (x1 - x0) / 5)]
    xs, ys = x0 + (x1 - x0) * 0.05, y0 + (y1 - y0) * 0.05
    ax.plot([xs, xs + lung], [ys, ys], color=INK, lw=3, solid_capstyle='butt')
    ax.text(xs + lung / 2, ys + (y1 - y0) * 0.02, f'{lung:g} m' if lung < 1000 else f'{lung / 1000:g} km',
            ha='center', va='bottom', fontsize=8, color=INK,
            bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=1))


def km2(v):
    return f'{v:,.0f}'.replace(',', '.') if v >= 1000 else (f'{v:.3g}'.replace('.', ','))


def pulisci(ax):
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color('#999999')


def fig_posizione(i, d, ax):
    T = d['z_T']
    ext = estensione(T, d['z_hs'].shape)
    ax.imshow(d['z_hs'], cmap='gray', extent=ext, vmin=0, vmax=1.1)
    ra = np.ma.masked_where(~d['z_reteA'], d['z_reteA'])
    rb = np.ma.masked_where(~d['z_reteB'], d['z_reteB'])
    ax.imshow(ra, cmap=ListedColormap([COL_A]), extent=ext, alpha=0.85, interpolation='nearest')
    ax.contour(np.flipud(d['z_reteB'].astype(float)), levels=[0.5], colors=[COL_B], linewidths=0.9,
               linestyles='--', extent=(ext[0], ext[1], ext[2], ext[3]))
    if i in TR.index:
        g = TR[i]
        ax.plot(*g.xy, color='black', lw=1.6)
    for geo, mk, lab in ((INI.get(i), 'o', 'inizio DB'), (FIN.get(i), 's', 'fine DB')):
        if geo is not None and not geo.is_empty and ext[0] <= geo.x <= ext[1] and ext[2] <= geo.y <= ext[3]:
            ax.plot(geo.x, geo.y, mk, ms=6, mfc='white', mec='black', mew=1)
    a, b = d['secA'], d['secB']
    ax.plot(*a, 'o', ms=9, mfc='none', mec=COL_A, mew=2.2)
    if ext[0] <= b[0] <= ext[1] and ext[2] <= b[1] <= ext[3]:
        ax.plot(*b, '^', ms=8, mfc='none', mec=COL_B, mew=2)
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    pulisci(ax)
    scala(ax, None)
    ax.set_title(f'Ponte {i}: posizione e intersezione con il reticolo')


LEG_POS = [Line2D([], [], color='black', lw=1.6, label='tracciato KML del ponte'),
           Line2D([], [], marker='o', ls='', mfc='white', mec='black', label='inizio DB'),
           Line2D([], [], marker='s', ls='', mfc='white', mec='black', label='fine DB'),
           Patch(color=COL_A, label='reticolo A (codice, acc > 4000)'),
           Line2D([], [], color=COL_B, ls='--', label='reticolo B (indipendente)'),
           Line2D([], [], marker='o', ls='', mfc='none', mec=COL_A, mew=2, ms=8, label='sezione A'),
           Line2D([], [], marker='^', ls='', mfc='none', mec=COL_B, mew=2, ms=8, label='sezione B')]


def fig_bacino(i, d, ax, titolo=True):
    T = d['b_T']
    ext = estensione(T, d['b_hs'].shape)
    ax.imshow(d['b_hs'], cmap='gray', extent=ext, vmin=0, vmax=1.1)
    A = d['b_A']
    ax.imshow(np.ma.masked_where(~A, A), cmap=ListedColormap([COL_A]), extent=ext, alpha=0.35, interpolation='nearest')
    rete = d['b_reteA']
    ax.imshow(np.ma.masked_where(~rete, rete), cmap=ListedColormap([COL_A]), extent=ext, alpha=0.9,
              interpolation='nearest')
    ax.contour(np.flipud(d['b_B'].astype(float)), levels=[0.5], colors=[COL_B], linewidths=1.4, linestyles='--',
               extent=ext)
    p = d['path']
    if len(p):
        ax.plot(p[:, 0], p[:, 1], color='#c0392b', lw=1.6)
    ax.plot(*d['secA'], 'o', ms=8, mfc='none', mec=COL_A, mew=2)
    ax.plot(*d['secB'], '^', ms=7, mfc='none', mec=COL_B, mew=2)
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    pulisci(ax)
    scala(ax, None)
    if titolo:
        v = V.loc[i]
        ax.set_title(f'Ponte {i}: bacino A {km2(v.A_km2)} km² - bacino B {km2(v.A_B_km2)} km² (IoU {v.IoU_AB:.0%})')


LEG_BAC = [Patch(facecolor=COL_A, alpha=0.35, label='bacino A (codice)'),
           Line2D([], [], color=COL_B, ls='--', lw=1.4, label='bacino B (indipendente)'),
           Patch(color=COL_A, label='reticolo A'),
           Line2D([], [], color='#c0392b', lw=1.6, label='percorso di flusso più lungo L'),
           Line2D([], [], marker='o', ls='', mfc='none', mec=COL_A, mew=2, ms=8, label='sezione A'),
           Line2D([], [], marker='^', ls='', mfc='none', mec=COL_B, mew=2, ms=8, label='sezione B')]


def fig_cn(i, d, ax):
    T = d['b_T']
    ext = estensione(T, d['b_hs'].shape)
    ax.imshow(d['b_hs'], cmap='gray', extent=ext, vmin=0, vmax=1.1)
    cn = np.ma.masked_where(~d['b_A'] | ~np.isfinite(d['b_cn']), d['b_cn'])
    im = ax.imshow(cn, cmap='YlGnBu', extent=ext, vmin=40, vmax=95, interpolation='nearest')
    ax.contour(np.flipud(d['b_A'].astype(float)), levels=[0.5], colors=[INK], linewidths=0.8, extent=ext)
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    pulisci(ax)
    scala(ax, None)
    cb = plt.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label('Curve Number')
    v = V.loc[i]
    ax.set_title(f'Ponte {i}: CN nel bacino - medio {v.CN_medio:.1f}')


def fig_ipso(i, d, ax):
    q, zq = d['hyps_q'], d['hyps_z']
    v = V.loc[i]
    hr = (zq - v.Quota_min_m) / v.Relief_m
    ax.plot(q, hr, color=COL_A, lw=2)
    ax.fill_between(q, 0, hr, color=COL_A, alpha=0.12)
    hi = (v.AE_m - v.Quota_min_m) / v.Relief_m
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel('area relativa a/A (quota superiore a h)')
    ax.set_ylabel('quota relativa (h - h_min)/R')
    ax.grid(color='#e5e5e5', lw=0.6)
    ax.text(0.55, 0.85, f'HI = (AE - h_min)/R = {hi:.3f}', fontsize=9, color=INK)
    ax.set_title(f'Ponte {i}: curva ipsometrica')


npz = sorted(glob.glob(os.path.join(dati, 'id*.npz')))
for f in npz:
    i = int(os.path.basename(f)[2:5])
    d = np.load(f)
    # posizione
    fig, ax = plt.subplots(figsize=(6.3, 5.6))
    fig_posizione(i, d, ax)
    ax.legend(handles=LEG_POS, loc='upper left', fontsize=7, framealpha=0.9, ncol=2)
    fig.tight_layout()
    fig.savefig(os.path.join(out, f'id{i:03d}_posizione.png'), dpi=200)
    plt.close(fig)
    # bacino
    fig, ax = plt.subplots(figsize=(6.3, 5.6))
    fig_bacino(i, d, ax)
    ax.legend(handles=LEG_BAC, loc='upper left', fontsize=7, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(os.path.join(out, f'id{i:03d}_bacino.png'), dpi=200)
    plt.close(fig)
    # CN e ipsometria
    fig, ax = plt.subplots(figsize=(6.3, 5.0))
    fig_cn(i, d, ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out, f'id{i:03d}_cn.png'), dpi=200)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(5.0, 3.6))
    fig_ipso(i, d, ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out, f'id{i:03d}_ipsometria.png'), dpi=200)
    plt.close(fig)
    # scheda di allegato: posizione + bacino affiancati
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.6))
    fig_posizione(i, d, axs[0])
    fig_bacino(i, d, axs[1])
    axs[0].set_title('Posizione e intersezione', fontsize=9)
    v = V.loc[i]
    axs[1].set_title(f'Bacino A {km2(v.A_km2)} km² / B {km2(v.A_B_km2)} km² (IoU {v.IoU_AB:.0%})', fontsize=9)
    fig.legend(handles=LEG_POS[:5] + LEG_BAC[:2] + LEG_BAC[3:], loc='lower center', ncol=5, fontsize=7, frameon=False)
    fig.suptitle(f'Ponte {i}', fontsize=11)
    fig.tight_layout(rect=(0, 0.1, 1, 0.96))
    fig.savefig(os.path.join(out, f'id{i:03d}_scheda.png'), dpi=170)
    plt.close(fig)
    print('figure', i)

# ---- sintesi A vs B ----
fig, ax = plt.subplots(figsize=(5.6, 4.6))
x, y = V.A_km2, V.A_B_km2
lo, hi = min(x.min(), y.min()) * 0.6, max(x.max(), y.max()) * 1.6
ax.plot([lo, hi], [lo, hi], color=MUTED, lw=1)
ax.fill_between([lo, hi], [lo * 0.85, hi * 0.85], [lo * 1.15, hi * 1.15], color='#dddddd', alpha=0.5, lw=0)
ok = V.IoU_AB >= 0.90
ax.scatter(x[ok], y[ok], s=36, color=COL_A, label='bacini concordanti (IoU ≥ 90%)', zorder=3, edgecolor='white')
ax.scatter(x[~ok], y[~ok], s=40, marker='D', color=COL_B, label='bacini diversi (IoU < 90%)', zorder=3,
           edgecolor='white')
for k, (a, b) in zip(V.index, zip(x, y)):
    ax.annotate(str(k), (a, b), xytext=(4, -9), textcoords='offset points', fontsize=7, color=INK)
ax.set_xscale('log')
ax.set_yscale('log')
ax.set_xlim(lo, hi)
ax.set_ylim(lo, hi)
ax.set_xlabel('Area A, codice pysheds (km²)')
ax.set_ylabel('Area B, metodo indipendente (km²)')
ax.grid(color='#eeeeee', which='both', lw=0.5)
ax.text(lo * 1.3, hi * 0.45, 'fascia ±15%', fontsize=7, color=MUTED)
ax.legend(fontsize=7, loc='lower right')
ax.set_title('Area del bacino: codice (A) e metodo indipendente (B)')
fig.tight_layout()
fig.savefig(os.path.join(out, 'sintesi_aree_A_B.png'), dpi=200)
plt.close(fig)

# ---- schema del flusso di lavoro ----
fig, ax = plt.subplots(figsize=(9.5, 5.2))
ax.set_xlim(0, 100)
ax.set_ylim(0, 60)
ax.axis('off')


def box(x, y, w, h, t, c='#f2f2f2', ec='#888888', fs=8):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.4,rounding_size=1.2', fc=c, ec=ec, lw=1))
    ax.text(x + w / 2, y + h / 2, t, ha='center', va='center', fontsize=fs, color=INK, wrap=True)


def freccia(x0, y0, x1, y1):
    ax.annotate('', (x1, y1), (x0, y0), arrowprops=dict(arrowstyle='->', color='#555555', lw=1))


box(14, 52, 72, 6, 'DATI: DEM 5 m (reticolo inciso) · CN · database (inizio/fine) · tracciati KML', '#e8e8e8')
box(2, 40, 44, 8, 'A - CODICE (pysheds)\nfill_pits + fill_depressions + resolve_flats\nD8 · accumulo · reticolo acc > 4000 celle',
    '#dce8f8', COL_A)
box(54, 40, 44, 8, 'B - METODO INDIPENDENTE\ndepressioni scavate (breaching a costo minimo)\nD8 · accumulo · reticolo acc > 4000 celle',
    '#fbe7d3', COL_B)
box(2, 28, 44, 8, '1. Sezione: punto del CSV (intersezione\ntracciato-reticolo) agganciato con snap_to_mask', '#dce8f8', COL_A)
box(54, 28, 44, 8, '1. Sezione ricavata di nuovo: cella del reticolo B\nattraversata dal tracciato KML (accumulo max)', '#fbe7d3', COL_B)
box(2, 16, 44, 8, '2. Bacino A: catchment pysheds\nA = n. celle × 25 m²', '#dce8f8', COL_A)
box(54, 16, 44, 8, '2. Bacino B: celle che drenano alla sezione B\nA = n. celle × 25 m²', '#fbe7d3', COL_B)
box(2, 2, 44, 10, '3-6. Parametri del codice: CN, L, P, quote,\npendenze, indici di forma\n+ RICALCOLO INDIPENDENTE sul bacino A', '#dce8f8', COL_A)
box(54, 2, 44, 10, 'Confronto A-B: area, sovrapposizione (IoU),\nposizione della sezione, L, quote, CN', '#fbe7d3', COL_B)
freccia(30, 51.6, 24, 48.6)
freccia(70, 51.6, 76, 48.6)
for xa in (24, 76):
    freccia(xa, 40, xa, 36.6)
    freccia(xa, 28, xa, 24.6)
    freccia(xa, 16, xa, 12.6)
freccia(46.6, 20, 53.4, 20)
fig.tight_layout()
fig.savefig(os.path.join(out, 'schema_flusso.png'), dpi=200)
plt.close(fig)
print('fatto')
