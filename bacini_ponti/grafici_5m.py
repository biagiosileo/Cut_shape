"""
Schede di dettaglio (1 km x 1 km) dei ponti non compatibili o senza area DB,
sul reticolo a 5 m: punti DB inizio/fine, input, KML, tracciato, sezione di
chiusura scelta e contorno del bacino.

Uso: python grafici_5m.py <cartella_toppe> <soglia_km2> <controllo_coordinate.gpkg>
                          <risultati_5m.gpkg> <Risultati_5m_ibrido.xlsx> <out_dir>
"""
import glob
import os
import sys

import numpy as np
import pandas as pd
import geopandas as gpd
from affine import Affine
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

tdir, soglia, gpkg, rgpkg, xlsx, out = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
os.makedirs(out, exist_ok=True)
H = 500.0
L = {n: gpd.read_file(gpkg, layer=n).set_index('ID').geometry
     for n in ('db_inizio', 'db_fine', 'input_script', 'kml_abbinato')}
trc = gpd.read_file(gpkg, layer='tracciato_usato').set_index('ID').geometry
bac = gpd.read_file(rgpkg, layer='bacini').set_index('ID').geometry
sez = gpd.read_file(rgpkg, layer='sezioni_chiusura').set_index('ID').geometry
t = pd.read_excel(xlsx).set_index('ID')
ids = [i for i in t.index if t.loc[i, 'Compatibile (±15%)'] is not True and t.loc[i, 'Compatibile (±15%)'] != True]
for p in range(0, len(ids), 12):
    blocco = ids[p:p + 12]
    fig, axs = plt.subplots(3, 4, figsize=(16, 14.5), dpi=110)
    for ax, i in zip(axs.flat, blocco):
        z = np.load(os.path.join(tdir, f'id{i:03d}.npz'))
        a = z['acc_km2']
        T = Affine(*z['transform'])
        x0, y0 = T * (0, 0)
        x1, y1 = T * (a.shape[1], a.shape[0])
        ax.imshow(np.where(a >= soglia, np.log10(a), np.nan), extent=(x0, x1, y1, y0), cmap='Blues',
                  vmin=np.log10(soglia) - 0.5, vmax=3.5, interpolation='nearest')
        cx, cy = L['input_script'][i].x, L['input_script'][i].y
        if i in bac.index:
            gpd.GeoSeries([bac[i].boundary]).plot(ax=ax, color='#7b3294', lw=1.2, zorder=2)
        if i in trc.index:
            xs, ys = trc[i].xy
            ax.plot(xs, ys, color='#6b6b6b', lw=2.5, zorder=3)
        if i in L['db_inizio'].index and i in L['db_fine'].index:
            a_, b_ = L['db_inizio'][i], L['db_fine'][i]
            ax.plot([a_.x, b_.x], [a_.y, b_.y], color='#c00000', lw=1, ls='--', zorder=3)
            ax.scatter(a_.x, a_.y, marker='^', s=45, c='#c00000', zorder=4)
            ax.scatter(b_.x, b_.y, marker='s', s=35, c='#c00000', zorder=4)
        ax.scatter(cx, cy, s=50, c='#111111', ec='white', zorder=5)
        if i in L['kml_abbinato'].index:
            k = L['kml_abbinato'][i]
            ax.scatter(k.x, k.y, marker='*', s=130, c='#f2c200', ec='#333', lw=.6, zorder=6)
        if i in sez.index:
            ax.scatter(sez[i].x, sez[i].y, marker='X', s=90, c='#1a9850', ec='white', lw=.6, zorder=7)
        ax.set_xlim(cx - H, cx + H)
        ax.set_ylim(cy - H, cy + H)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlabel('')
        ax.set_ylabel('')
        r = t.loc[i]
        adb = '—' if pd.isna(r['Area database (km²)']) else f"{r['Area database (km²)']:g}"
        ax.set_title(f"ID {i} · {r['Strada']} km {r['Progressiva']}\nDB {adb} km² · calcolata "
                     f"{r['Area calcolata 5 m (km²)']:.3g} km²\n{str(r['Esito']).replace('Non compatibile: ', '')}",
                     fontsize=7.5, loc='left')
    for ax in list(axs.flat)[len(blocco):]:
        ax.axis('off')
    fig.legend(handles=[
        plt.Line2D([], [], marker='^', ls='', c='#c00000', label='DB inizio'),
        plt.Line2D([], [], marker='s', ls='', c='#c00000', label='DB fine'),
        plt.Line2D([], [], marker='o', ls='', c='#111111', label='input (punto medio DB)'),
        plt.Line2D([], [], marker='*', ls='', c='#f2c200', mec='#333', ms=12, label='punto KML'),
        plt.Line2D([], [], c='#6b6b6b', lw=2, label='tracciato KML'),
        plt.Line2D([], [], marker='X', ls='', c='#1a9850', ms=10, label='sezione di chiusura'),
        plt.Line2D([], [], c='#7b3294', lw=1.2, label='confine del bacino'),
        plt.Rectangle((0, 0), 1, 1, fc='#6aaed6', label=f'reticolo 5 m ≥ {soglia:g} km²'),
    ], loc='lower center', ncol=8, fontsize=8.5, frameon=False)
    fig.suptitle('DEM 5 m (ibrido): ponti non compatibili o senza area DB, dettaglio 1 km × 1 km',
                 fontsize=11, x=0.01, ha='left')
    plt.tight_layout(rect=(0, 0.03, 1, 0.97), h_pad=2.5)
    plt.savefig(os.path.join(out, f'schede_5m_{p // 12 + 1:02d}.png'))
    plt.close()
print(len(ids), 'schede')
