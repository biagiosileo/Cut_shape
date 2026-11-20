"""
Immagini (JPEG) degli attraversamenti multi-asta e dei canali di bonifica.

Per ogni ponte, sulla porzione di DEM del codice (stesso condizionamento: quote al cm, fill_pits,
fill_depressions, resolve_flats eps=1e-6 max_iter=10000, D8, accumulo):
  - sezione usata dal codice (ponti.csv, aggancio come nel codice) e suo bacino;
  - alternativa A: cella con accumulo massimo entro 10 m dal tracciato del ponte nel KML (asta principale
    sotto il ponte) e suo bacino, se diversa dalla sezione usata;
  - alternativa B: punto medio inizio-fine del database agganciato al reticolo (acc > soglia) e suo bacino,
    se diverso;
  - reticolo principale (acc > 4000 celle = 0.1 km2) e secondario (acc > 400 celle = 0.01 km2), tracciato e punto
    del KML, punti inizio e fine del database.
Pannello sinistro: bacini interi; pannello destro: ingrandimento di 600 x 600 m sul ponte.
Scrive anche una tabella CSV con le aree.

Uso: python mappe_multiasta.py <dem5m_unico.tif> <ponti.csv> <controllo_coordinate.gpkg> <3_parametri.csv>
        <Database.xlsx> <note_relazioni.csv> <out_dir> ID [ID ...]
"""
import os
import sys

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
if not hasattr(np, 'in1d'):
    np.in1d = np.isin
import pandas as pd
import rasterio
from matplotlib.colors import LightSource
from pyproj import Proj, Transformer
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
from rasterio.features import rasterize, shapes
from rasterio.windows import from_bounds
from shapely.geometry import Point, shape

dem_path, pcsv, gpkg, par_csv, dbx, ncsv, out = sys.argv[1:8]
IDS = [int(i) for i in sys.argv[8:]]
os.makedirs(out, exist_ok=True)
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
P = pd.read_csv(pcsv)
P['id'] = P.id.astype(int)
P = P.set_index('id')
R = pd.read_csv(par_csv)
R['ID'] = R.ID.astype(int)
R = R.set_index('ID')
db = pd.read_excel(dbx).rename(columns={'Unnamed: 0': 'ID'})
db = db[pd.to_numeric(db.ID, errors='coerce').notna()]
db['ID'] = db.ID.astype(int)
db = db.set_index('ID')
N = pd.read_csv(ncsv).set_index('ID')
ini = gpd.read_file(gpkg, layer='db_inizio').set_index('ID').to_crs(32633)
fin = gpd.read_file(gpkg, layer='db_fine').set_index('ID').to_crs(32633)
kab = gpd.read_file(gpkg, layer='kml_abbinato').set_index('ID').to_crs(32633)
ktr = gpd.read_file(gpkg, layer='kml_tracciati').to_crs(32633)
tr = Transformer.from_crs(4326, 32633, always_xy=True)
crs = Proj('EPSG:32633', preserve_units=True)


def area_db(i):
    a = pd.to_numeric(db.loc[i, 'SUPERFICIE BACINO (km2)'], errors='coerce')
    if i in N.index and pd.notna(N.loc[i, 'Area_DB_corretta']):
        a = float(N.loc[i, 'Area_DB_corretta'])
    return a


def condiziona(porz):
    p = P[P.porzione == porz].iloc[0]
    with rasterio.open(dem_path) as src:
        w = from_bounds(p.xmin, p.ymin, p.xmax, p.ymax, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w)
        T = src.window_transform(w)
        z = a.astype(np.float64) * src.scales[0]
        z[a == src.nodata] = -9999.0
    v = z != -9999
    z[v] = np.round(z[v], 2)
    vf = ViewFinder(affine=T, shape=z.shape, nodata=np.float64(-9999.0), crs=crs)
    g = Grid(viewfinder=vf)
    dem = Raster(z, vf)
    inf = g.resolve_flats(g.fill_depressions(g.fill_pits(dem)), eps=1e-6, max_iter=10000)
    fd = g.flowdir(inf, dirmap=DIRMAP)
    accR = g.accumulation(fd, dirmap=DIRMAP)
    return g, fd, accR, z, T


def bacino(g, fd, T, r, c):
    m = np.asarray(g.catchment(x=int(c), y=int(r), fdir=fd, dirmap=DIRMAP, xytype='index')).astype(bool)
    geoms = [shape(s) for s, v in shapes(m.astype(np.uint8), mask=m, transform=T) if v == 1]
    return m, gpd.GeoSeries(geoms, crs=32633).union_all() if geoms else None


righe = []
cache = {}
for i in IDS:
    porz = P.loc[i, 'porzione']
    if porz not in cache:
        print('condizionamento', porz, flush=True)
        cache.clear()
        cache[porz] = condiziona(porz)
    g, fd, accR, z, T = cache[porz]
    acc = np.asarray(accR)
    soglia = int(P.loc[i, 'soglia']) if pd.notna(P.loc[i, 'soglia']) else 4000
    # sezione usata dal codice
    x, y = tr.transform(P.loc[i, 'X'], P.loc[i, 'Y'])
    xs, ys = g.snap_to_mask(accR > soglia, (x, y))
    c0, r0 = g.nearest_cell(xs, ys)
    m0, b0 = bacino(g, fd, T, r0, c0)
    A0 = m0.sum() * 25 / 1e6
    # alternativa A: accumulo massimo entro 10 m dal tracciato KML
    kp = kab.loc[i, 'geometry']
    trc = ktr.loc[ktr.distance(kp).idxmin(), 'geometry']
    mk = rasterize([(trc.buffer(10), 1)], out_shape=acc.shape, transform=T, all_touched=True).astype(bool)
    accm = np.where(mk, acc, -1)
    rA, cA = np.unravel_index(np.argmax(accm), acc.shape)
    altA = None
    if (rA, cA) != (r0, c0) and acc[rA, cA] > 0:
        mA, bA = bacino(g, fd, T, rA, cA)
        if abs(mA.sum() - m0.sum()) > 0.02 * m0.sum() and mA.sum() >= 200:  # ignora celle isolate (< 0.005 km2)
            altA = (rA, cA, mA.sum() * 25 / 1e6, bA)
    # alternativa B: punto medio del database agganciato al reticolo
    pm = Point((ini.loc[i].geometry.x + fin.loc[i].geometry.x) / 2, (ini.loc[i].geometry.y + fin.loc[i].geometry.y) / 2)
    altB = None
    try:
        xb, yb = g.snap_to_mask(accR > soglia, (pm.x, pm.y))
        cB, rB = g.nearest_cell(xb, yb)
        if (rB, cB) != (r0, c0):
            mB, bB = bacino(g, fd, T, rB, cB)
            if abs(mB.sum() - m0.sum()) > 0.02 * m0.sum() and mB.sum() >= 200:
                altB = (rB, cB, mB.sum() * 25 / 1e6, bB, pm.distance(Point(T * (cB + 0.5, rB + 0.5))))
    except Exception:
        pass
    adb = area_db(i)
    nome = str(db.loc[i, 'Nome opera']).strip()
    nome = '' if nome in ('-', 'nan') else nome
    sp, km = db.loc[i, 'NUOVA NUMERAZIONE'], db.loc[i, 'Progressiva km']
    nota = str(N.loc[i, 'Correzione']) if i in N.index else ''
    righe.append({'ID': i, 'strada': sp, 'km': km, 'nome': nome, 'A_db_km2': adb, 'A_codice_km2': round(A0, 3),
                  'A_alt_A_tracciato_km2': round(altA[2], 3) if altA else None,
                  'A_alt_B_punto_database_km2': round(altB[2], 3) if altB else None,
                  'dist_punto_db_sezione_m': round(pm.distance(Point(xs, ys))),
                  'acc_sezione_celle': int(acc[r0, c0]), 'nota': nota})
    print(righe[-1], flush=True)

    # ---- figura
    sez = Point(T * (c0 + 0.5, r0 + 0.5))
    tutti = [b for b in [b0, altA[3] if altA else None, altB[3] if altB else None] if b is not None]
    bx = gpd.GeoSeries(tutti + [trc], crs=32633).total_bounds
    pad = max(bx[2] - bx[0], bx[3] - bx[1]) * 0.08 + 100
    ls = LightSource(azdeg=315, altdeg=45)
    zz = np.where(z == -9999, np.nan, z)
    fig, ax = plt.subplots(1, 3, figsize=(21, 8.0), dpi=100)
    for k, (x0, y0, x1, y1) in enumerate([(bx[0] - pad, bx[1] - pad, bx[2] + pad, bx[3] + pad),
                                           (sez.x - 300, sez.y - 300, sez.x + 300, sez.y + 300),
                                           (sez.x - 75, sez.y - 75, sez.x + 75, sez.y + 75)]):
        a = ax[k]
        c_a, r_a = ~T * (x0, y1)
        c_b, r_b = ~T * (x1, y0)
        r_a, c_a = max(int(r_a), 0), max(int(c_a), 0)
        r_b, c_b = min(int(r_b) + 1, z.shape[0]), min(int(c_b) + 1, z.shape[1])
        sub = zz[r_a:r_b, c_a:c_b]
        ext = (T.c + c_a * 5, T.c + c_b * 5, T.f - r_b * 5, T.f - r_a * 5)
        hs = ls.hillshade(np.nan_to_num(sub, nan=np.nanmin(sub)), vert_exag=2, dx=5, dy=5)
        a.imshow(hs, cmap='gray', extent=ext, alpha=0.9)
        sa = acc[r_a:r_b, c_a:c_b]
        a.imshow(np.ma.masked_where(sa <= 400, np.ones_like(sa)), cmap='Blues', vmin=0, vmax=1.3, extent=ext, alpha=0.5)
        a.imshow(np.ma.masked_where(sa <= 4000, np.ones_like(sa)), cmap='winter', vmin=0, vmax=1, extent=ext, alpha=0.9)
        gpd.GeoSeries([b0], crs=32633).plot(ax=a, facecolor=(0.1, 0.7, 0.2, 0.25), edgecolor='green', linewidth=1.8)
        if altA:
            gpd.GeoSeries([altA[3]], crs=32633).boundary.plot(ax=a, color='darkorange', linewidth=1.6)
        if altB:
            gpd.GeoSeries([altB[3]], crs=32633).boundary.plot(ax=a, color='purple', linewidth=1.4, linestyle='--')
        ms = [6, 7, 10][k]
        a.plot(sez.x, sez.y, 's', mfc='none', mec='black', mew=2, ms=ms + 2, zorder=8)
        if altA:
            pa = T * (altA[1] + 0.5, altA[0] + 0.5)
            a.plot(*pa, 'D', mfc='none', mec='darkorange', mew=2, ms=ms + 1, zorder=8)
        if altB:
            pb = T * (altB[1] + 0.5, altB[0] + 0.5)
            a.plot(*pb, 'o', mfc='none', mec='purple', mew=2, ms=ms + 1, zorder=8)
        a.plot([ini.loc[i].geometry.x, fin.loc[i].geometry.x], [ini.loc[i].geometry.y, fin.loc[i].geometry.y], 'v', color='magenta', mec='k', ms=ms, zorder=9)
        gpd.GeoSeries([trc], crs=32633).plot(ax=a, color='red', linewidth=[2, 4, 6][k], zorder=10)
        a.plot(*kp.xy, 'o', color='yellow', mec='k', ms=ms - 1, zorder=11)
        a.set_xlim(x0, x1)
        a.set_ylim(y0, y1)
        a.set_aspect('equal')
        a.ticklabel_format(useOffset=False, style='plain')
        a.tick_params(labelsize=7)
        a.set_title(['bacini interi', 'ingrandimento 600 x 600 m', 'ingrandimento 150 x 150 m sul ponte'][k], fontsize=10)
    leg = [plt.Line2D([], [], color='green', lw=2, label=f'bacino del codice, sezione: quadrato nero; A = {A0:.3f} km2'),
           plt.Line2D([], [], color='red', lw=2.5, label='tracciato del ponte (KML); cerchio giallo: punto KML'),
           plt.Line2D([], [], color='magenta', marker='v', lw=0, label='inizio e fine del ponte (database)'),
           plt.Line2D([], [], color='teal', lw=4, label='reticolo principale (> 0.1 km2)'),
           plt.Line2D([], [], color='lightsteelblue', lw=4, label='reticolo secondario (> 0.01 km2)')]
    if altA:
        leg.append(plt.Line2D([], [], color='darkorange', lw=1.6, marker='D', label=f'alternativa A, asta principale sul tracciato: A = {altA[2]:.3f} km2'))
    if altB:
        leg.append(plt.Line2D([], [], color='purple', lw=1.4, ls='--', marker='o', label=f'alternativa B, punto del database sul reticolo: A = {altB[2]:.3f} km2'))
    fig.legend(handles=leg, loc='lower center', ncol=3, fontsize=9, frameon=False)
    adb_t = f'{adb:.3f}' if pd.notna(adb) else 'assente'
    fig.suptitle(f'Ponte {i} - {sp} km {km}' + (f' - {nome}' if nome else '') +
                 f'\narea database {adb_t} km2, area codice {A0:.3f} km2' + (f'\n{nota}' if nota else ''), fontsize=11)
    fig.subplots_adjust(bottom=0.15, top=0.86, wspace=0.14, left=0.04, right=0.99)
    fig.savefig(os.path.join(out, f'ponte_{i:03d}.jpg'), dpi=100, pil_kwargs={'quality': 90})
    plt.close(fig)
pd.DataFrame(righe).to_csv(os.path.join(out, 'aree_alternative.csv'), index=False)
print('fatto')
