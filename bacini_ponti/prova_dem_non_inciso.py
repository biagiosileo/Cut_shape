"""
Prova sui ponti fuori tolleranza: stesso calcolo del codice dell'utente sul DEM unico cosi' com'e'
(reticolo di riferimento inciso di BRUCIA_M) e sul DEM unico senza incisione (quote originali a 5 m).

Il DEM non inciso si ottiene dal DEM unico rialzando di BRUCIA_M le celle toccate dal reticolo di
riferimento (stessa rasterizzazione all_touched usata per l'incisione): e' l'inverso esatto del passo
di incisione di dem_unico_codice_utente.py.

Per ogni ponte e ciascun DEM: catena del codice (fill_pits, fill_depressions, resolve_flats eps=1e-6
max_iter=10000, D8, accumulo, snap_to_mask acc > 4000, catchment), in float32 per stare in memoria.
In piu', sul reticolo di ciascun DEM, la cella con area compatibile con il database (+-15%) piu'
vicina al punto del ponte entro RAGGIO_M.

Uso: python prova_dem_non_inciso.py <dem5m_unico.tif> <ponti.csv> <reticolo_tagliato.shp> <Database.xlsx>
        <out_dir> <id> [<id> ...]
"""
import os
import sys
import time

import numpy as np
np.in1d = np.isin
import geopandas as gpd
import pandas as pd
import rasterio
from pyproj import Proj, Transformer
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
from rasterio.features import rasterize
from rasterio.windows import from_bounds

DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
ACC_THRESHOLD = 4000
BRUCIA_M = float(os.environ.get('BRUCIA_M', '5'))
RAGGIO_M = 300.0
C5 = 5.0

dem_path, csv_path, ret_path, dbx, out = sys.argv[1:6]
ids = [int(i) for i in sys.argv[6:]]
os.makedirs(out, exist_ok=True)
P = pd.read_csv(csv_path).set_index('id')
db = pd.read_excel(dbx).rename(columns={'Unnamed: 0': 'ID'})
db = db[pd.to_numeric(db.ID, errors='coerce').notna()]
db['ID'] = db.ID.astype(int)
adb = pd.to_numeric(db.set_index('ID')['SUPERFICIE BACINO (km2)'], errors='coerce')
R = gpd.read_file(ret_path).to_crs(32633)
tr = Transformer.from_crs('EPSG:4326', 'EPSG:32633', always_xy=True)
crs = Proj('EPSG:32633', preserve_units=True)


def leggi(lim):
    with rasterio.open(dem_path) as src:
        w = from_bounds(*lim, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w)
        T = src.window_transform(w)
        nd = a == src.nodata
    sel = R.cx[T.c:T.c + a.shape[1] * C5, T.f - a.shape[0] * C5:T.f]
    inc = np.zeros(a.shape, bool)
    if len(sel):
        inc = rasterize(((g, 1) for g in sel.geometry), out_shape=a.shape, transform=T, all_touched=True,
                        dtype='uint8').astype(bool) & ~nd
    return a, nd, inc, T


def flusso(z, T):
    vf = ViewFinder(affine=T, shape=z.shape, nodata=np.float32(-9999), crs=crs)
    grid = Grid(viewfinder=vf)
    dem = Raster(z, vf)
    dem = grid.fill_pits(dem)
    dem = grid.fill_depressions(dem)
    dem = grid.resolve_flats(dem, eps=1e-6, max_iter=10000)
    fdir = grid.flowdir(dem, dirmap=DIRMAP)
    del dem
    acc = grid.accumulation(fdir, dirmap=DIRMAP)
    return grid, fdir, acc


def bacino(grid, fdir, acc, T, x, y, a_db):
    xs, ys = grid.snap_to_mask(acc > ACC_THRESHOLD, (x, y))
    m = np.asarray(grid.catchment(x=xs, y=ys, fdir=fdir, dirmap=DIRMAP, xytype='coordinate'))
    H, W = m.shape
    bordo = bool(m[:2].any() or m[-2:].any() or m[:, :2].any() or m[:, -2:].any())
    r = {'A_km2': round(m.sum() * C5 * C5 / 1e6, 3), 'snap_m': round(float(np.hypot(xs - x, ys - y)), 1),
         'bordo': bordo}
    # cella del reticolo con area compatibile piu' vicina al punto
    r['dist_compat_m'], r['A_compat_km2'] = None, None
    if not np.isnan(a_db):
        k = int(RAGGIO_M / C5)
        c, rr = ~T * (x, y)
        r0, c0 = int(rr), int(c)
        A = np.asarray(acc)[max(r0 - k, 0):r0 + k + 1, max(c0 - k, 0):c0 + k + 1] * C5 * C5 / 1e6
        ii, jj = np.where((A * 1e6 / (C5 * C5) > ACC_THRESHOLD) & (np.abs(A / a_db - 1) <= 0.15))
        if len(ii):
            xx = T.c + (max(c0 - k, 0) + jj + 0.5) * C5
            yy = T.f - (max(r0 - k, 0) + ii + 0.5) * C5
            d = np.hypot(xx - x, yy - y)
            j = d.argmin()
            if d[j] <= RAGGIO_M:
                r['dist_compat_m'], r['A_compat_km2'] = round(float(d[j])), round(float(A[ii[j], jj[j]]), 3)
    return r


righe = []
sel = P.loc[ids]
for porz, g in sel.groupby('porzione', sort=False):
    t0 = time.time()
    lim = tuple(g.iloc[0][['xmin', 'ymin', 'xmax', 'ymax']])
    a, nd, inc, T = leggi(lim)
    for versione in ('inciso', 'non_inciso'):
        z = (a.astype(np.float64) * 0.01).astype(np.float32)
        if versione == 'non_inciso':
            z[inc] += np.float32(BRUCIA_M)
        z[nd] = -9999
        grid, fdir, acc = flusso(z, T)
        del z
        for i, p in g.iterrows():
            x, y = tr.transform(p.X, p.Y)
            b = bacino(grid, fdir, acc, T, x, y, adb.get(i, np.nan))
            righe.append({'ID': i, 'porzione': porz, 'DEM': versione, 'A_db_km2': adb.get(i, np.nan), **b})
            print(porz, i, versione, b, flush=True)
        del grid, fdir, acc
    print(porz, 'fatto in', round(time.time() - t0), 's', flush=True)
    pd.DataFrame(righe).to_csv(os.path.join(out, 'prova_dem_non_inciso.csv'), index=False)
