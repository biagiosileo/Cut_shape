"""
Prodotti grafici del controllo coordinate, per QGIS e come immagini:
  - reticolo a 30 m (celle con area contribuente >= 0,25 km2, valore = area in
    km2) in GeoTIFF;
  - strato 'esito_aree' nel GeoPackage: punto di input con area adottata,
    differenza col database ed esito;
  - mappa d'insieme (PNG) e schede di dettaglio (PNG, 1 km x 1 km) per i ponti
    segnalati dal controllo coordinate o non compatibili.

Uso: python grafici_coordinate.py <dem30.tif> <cartella_coordinate> <Decisioni_per_ponte.xlsx>
"""
import os
import sys

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import whitebox_workflows as wb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SOGLIA_KM2 = 0.25
FINESTRA_M = 1000.0
dem_p, cdir, dec_xlsx = sys.argv[1:4]
gpkg = os.path.join(cdir, 'controllo_coordinate.gpkg')

# ---------------- Reticolo 30 m ----------------
wbe = wb.WbEnvironment()
wbe.verbose = False
tmp = os.path.join(cdir, '_acc.tif')
wbe.write_raster(wbe.hydrology.d8_flow_accum(
    input=wbe.hydrology.fill_depressions(dem=wbe.read_raster(dem_p)), out_type='cells'), tmp)
with rasterio.open(tmp) as s:
    prof = s.profile
    T = s.transform
    acc = s.read(1).astype(np.float32) * abs(T.a * T.e) / 1e6
os.remove(tmp)
with rasterio.open(dem_p) as s:
    acc[s.read(1) == s.nodata] = 0
ret = np.where(acc >= SOGLIA_KM2, acc, -1).astype(np.float32)
prof.update(dtype='float32', nodata=-1, compress='deflate', count=1)
with rasterio.open(os.path.join(cdir, 'reticolo_30m_soglia_0.25km2.tif'), 'w', **prof) as d:
    d.write(ret, 1)

# ---------------- Strato esiti ----------------
inp = gpd.read_file(gpkg, layer='input_script')
dec = pd.read_excel(dec_xlsx)[['ID', 'Area adottata (km²)', 'Fonte area adottata', 'Differenza %',
                               'Compatibile (±15%)', 'Esito', 'Azione']]
dec.columns = ['ID', 'A_adottata_km2', 'Fonte_area', 'Differenza_pct', 'Compatibile', 'Esito', 'Azione']
dec['Differenza_pct'] = dec.Differenza_pct * 100
es = inp.merge(dec, on='ID', how='left')
es.to_file(gpkg, layer='esito_aree', driver='GPKG')

ini = gpd.read_file(gpkg, layer='db_inizio').set_index('ID')
fin = gpd.read_file(gpkg, layer='db_fine').set_index('ID')
kml = gpd.read_file(gpkg, layer='kml_abbinato').set_index('ID')
trc = gpd.read_file(gpkg, layer='tracciato_usato').set_index('ID')
itx = gpd.read_file(gpkg, layer='intersezione_tracciato_reticolo').set_index('ID')
es = es.set_index('ID')

# ---------------- Mappa d'insieme ----------------
col = {True: '#2a6fdb', False: '#e8710a'}
fig, ax = plt.subplots(figsize=(8, 9.5), dpi=150)
step = 4
small = np.where(ret[::step, ::step] > 0, np.log10(ret[::step, ::step]), np.nan)
ext = (T.c, T.c + T.a * ret.shape[1], T.f + T.e * ret.shape[0], T.f)
ax.imshow(small, extent=ext, cmap='Blues', vmin=-1, vmax=3.5, alpha=.6, interpolation='nearest')
for k, g in es.groupby(es.Compatibile.fillna(False).astype(bool)):
    ax.scatter(g.geometry.x, g.geometry.y, s=18, c=col[k], ec='white', lw=.7, zorder=3,
               label='compatibile ±15%' if k else 'non compatibile o area DB mancante')
seg = es[es.N_segnalazioni > 0]
ax.scatter(seg.geometry.x, seg.geometry.y, s=70, facecolors='none', edgecolors='#c00000', lw=1.2, zorder=4,
           label=f'segnalazione sulle coordinate ({len(seg)})')
ax.set_aspect('equal')
ax.set_xlim(ext[0], ext[1])
ax.set_ylim(ext[2], ext[3])
ax.ticklabel_format(style='plain')
ax.tick_params(labelsize=7, colors='#555')
ax.set_title('Esito aree e segnalazioni sulle coordinate (sfondo: reticolo 30 m ≥ 0,25 km²)',
             fontsize=9.5, loc='left')
ax.legend(loc='lower right', fontsize=7.5, framealpha=.95)
plt.tight_layout()
plt.savefig(os.path.join(cdir, 'mappa_insieme_coordinate.png'))
plt.close()

# ---------------- Schede di dettaglio ----------------
ids = sorted(set(es.index[es.N_segnalazioni > 0]) | set(es.index[es.Compatibile == False]))
inv = ~T
per_pag = 12
for p in range(0, len(ids), per_pag):
    blocco = ids[p:p + per_pag]
    fig, axs = plt.subplots(3, 4, figsize=(16, 12.5), dpi=110)
    for ax, i in zip(axs.flat, blocco):
        cx, cy = es.geometry[i].x, es.geometry[i].y
        h = FINESTRA_M / 2
        c0, r0 = inv * (cx - h, cy + h)
        c1, r1 = inv * (cx + h, cy - h)
        r0, r1, c0, c1 = int(r0), int(r1) + 1, int(c0), int(c1) + 1
        w = ret[r0:r1, c0:c1]
        x0, y0 = T * (c0, r0)
        x1, y1 = T * (c1, r1)
        ax.imshow(np.where(w > 0, np.log10(np.maximum(w, 1e-3)), np.nan), extent=(x0, x1, y1, y0),
                  cmap='Blues', vmin=-1, vmax=3.5, interpolation='nearest')
        if i in trc.index:
            xs, ys = trc.geometry[i].xy
            ax.plot(xs, ys, color='#6b6b6b', lw=2.5, zorder=2)
        if i in itx.index:
            ax.scatter(itx.geometry[i].x, itx.geometry[i].y, marker='X', s=90, c='#1a9850', ec='white',
                       lw=.6, zorder=7)
        if i in ini.index and i in fin.index:
            ax.plot([ini.geometry[i].x, fin.geometry[i].x], [ini.geometry[i].y, fin.geometry[i].y],
                    color='#c00000', lw=1, ls='--', zorder=3)
            ax.scatter(ini.geometry[i].x, ini.geometry[i].y, marker='^', s=45, c='#c00000', zorder=4)
            ax.scatter(fin.geometry[i].x, fin.geometry[i].y, marker='s', s=35, c='#c00000', zorder=4)
        ax.scatter(cx, cy, s=55, c='#111111', ec='white', zorder=5)
        if i in kml.index:
            ax.scatter(kml.geometry[i].x, kml.geometry[i].y, marker='*', s=140, c='#f2c200', ec='#333', lw=.6, zorder=6)
        ax.set_xlim(cx - h, cx + h)
        ax.set_ylim(cy - h, cy + h)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlabel('')
        ax.set_ylabel('')
        r = es.loc[i]
        adb = '—' if pd.isna(r.A_db_km2) else f'{r.A_db_km2:g}'
        ad = '—' if pd.isna(r.A_adottata_km2) else f'{r.A_adottata_km2:.3g}'
        ax.set_title(f'ID {i} · {r.SP} km {r.km}\nDB {adb} km² · calcolata {ad} km² · {r.Esito}',
                     fontsize=8, loc='left')
    for ax in list(axs.flat)[len(blocco):]:
        ax.axis('off')
    fig.legend(handles=[
        plt.Line2D([], [], marker='^', ls='', c='#c00000', label='DB inizio'),
        plt.Line2D([], [], marker='s', ls='', c='#c00000', label='DB fine'),
        plt.Line2D([], [], marker='o', ls='', c='#111111', label='input script (= punto medio DB)'),
        plt.Line2D([], [], marker='*', ls='', c='#f2c200', mec='#333', ms=12, label='punto KML'),
        plt.Line2D([], [], c='#6b6b6b', lw=2, label='tracciato KML'),
        plt.Line2D([], [], marker='X', ls='', c='#1a9850', ms=10, label='intersezione tracciato-reticolo'),
        plt.Rectangle((0, 0), 1, 1, fc='#6aaed6', label='reticolo 30 m (più scuro = area maggiore)'),
    ], loc='lower center', ncol=7, fontsize=9, frameon=False)
    fig.suptitle('Dettaglio 1 km × 1 km dei ponti con segnalazioni o non compatibili', fontsize=11, x=0.01, ha='left')
    plt.tight_layout(rect=(0, 0.03, 1, 0.97))
    plt.savefig(os.path.join(cdir, f'schede_dettaglio_{p // per_pag + 1:02d}.png'))
    plt.close()
print(f"Schede: {len(ids)} ponti in {int(np.ceil(len(ids) / per_pag))} pagine")
