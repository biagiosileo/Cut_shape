"""
Sezione sul tracciato del ponte nel KML: per i ponti indicati si cerca, tra le celle del reticolo (acc > 4000)
toccate dal tracciato del KML, quella con l'area piu' vicina all'area del database, e si ricalcola il bacino
a 5 m con la stessa catena del codice dell'utente sul DEM unico.

1) stima a 25 m (accumulo e direzioni gia' calcolati sul DEM unico ricampionato al minimo 5x5): cella del
   tracciato con area piu' vicina al database e ingombro del suo bacino -> porzione di calcolo (+ MARGINE_M);
2) calcolo a 5 m sulla porzione: fill_pits, fill_depressions, resolve_flats eps=1e-6 max_iter=10000, D8,
   accumulo; cella del reticolo toccata dal tracciato con area piu' vicina al database; punto = centro della
   cella spostato di 1,25 m verso l'angolo in alto a sinistra; snap_to_mask e catchment da quel punto.

Uso: python verifica_tracciati_kml.py <dem5m_unico.tif> <acc25.npy> <fd25.npy> <controllo_coordinate.gpkg>
        <Database.xlsx> <out_dir> <id> [<id> ...]
"""
import os
import sys

import numpy as np
np.in1d = np.isin
import geopandas as gpd
import pandas as pd
import rasterio
from affine import Affine
from pyproj import Proj, Transformer
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
from rasterio.features import rasterize, shapes
from rasterio.windows import from_bounds
from shapely.geometry import shape
from shapely.ops import unary_union

DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
PASSO = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}
ACC_THRESHOLD = 4000
MARGINE_M = 1500.0
OFFSET_M = 1.25

dem_path, acc25, fd25, gpkg, dbx, out = sys.argv[1:7]
ids = [int(i) for i in sys.argv[7:]]
os.makedirs(out, exist_ok=True)
with rasterio.open(dem_path) as s:
    X0, Y0, XMAX, YMIN = s.transform.c, s.transform.f, s.bounds.right, s.bounds.bottom
T25 = Affine(25, 0, X0, 0, -25, Y0)
A25 = np.load(acc25) * 625 / 1e6
F25 = np.load(fd25)
k = gpd.read_file(gpkg, layer='kml_abbinato').set_index('ID').to_crs(32633)
kt = gpd.read_file(gpkg, layer='kml_tracciati').to_crs(32633).set_index('nome').geometry
db = pd.read_excel(dbx).rename(columns={'Unnamed: 0': 'ID'})
db = db[pd.to_numeric(db.ID, errors='coerce').notna()]
db['ID'] = db.ID.astype(int)
adb = pd.to_numeric(db.set_index('ID')['SUPERFICIE BACINO (km2)'], errors='coerce')
to_geo = Transformer.from_crs('EPSG:32633', 'EPSG:4326', always_xy=True)
crs = Proj('EPSG:32633', preserve_units=True)


def celle_tracciato(g, T, shape_):
    return rasterize([(g, 1)], out_shape=shape_, transform=T, all_touched=True).astype(bool)


def bacino25(r, c):
    up = np.zeros(F25.shape, bool)
    up[r, c] = True
    st = [(r, c)]
    while st:
        a, b = st.pop()
        for d, (dr, dc) in PASSO.items():
            rr, cc = a - dr, b - dc
            if 0 <= rr < up.shape[0] and 0 <= cc < up.shape[1] and not up[rr, cc] and F25[rr, cc] == d:
                up[rr, cc] = True
                st.append((rr, cc))
    rr, cc = np.where(up)
    return [X0 + cc.min() * 25, Y0 - (rr.max() + 1) * 25, X0 + (cc.max() + 1) * 25, Y0 - rr.min() * 25]


def allinea(b):
    n = lambda v, f: f(round(v / 5.0, 3))
    return [X0 + n(max(b[0], X0) - X0, np.floor) * 5, Y0 - n(Y0 - max(b[1], YMIN), np.ceil) * 5,
            X0 + n(min(b[2], XMAX) - X0, np.ceil) * 5, Y0 - n(Y0 - min(b[3], Y0), np.floor) * 5]


righe, poli, punti = [], [], []
for i in ids:
    tr = kt.get(k.loc[i, 'KML_nome'])
    g = tr.buffer(5) if tr is not None else k.geometry[i].buffer(30)
    # 1) stima a 25 m
    m = celle_tracciato(g.buffer(10), T25, A25.shape)
    rr, cc = np.where(m & (A25 >= 0.1))
    q = np.argmin(np.abs(np.log(A25[rr, cc] / adb[i])))
    ing = bacino25(rr[q], cc[q])
    lim = allinea([min(ing[0], g.bounds[0]) - MARGINE_M, min(ing[1], g.bounds[1]) - MARGINE_M,
                   max(ing[2], g.bounds[2]) + MARGINE_M, max(ing[3], g.bounds[3]) + MARGINE_M])
    # 2) calcolo a 5 m
    with rasterio.open(dem_path) as src:
        w = from_bounds(*lim, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w)
        T = src.window_transform(w)
        z = (a.astype(np.float64) * src.scales[0]).astype(np.float32)
        z[a == src.nodata] = -9999
    del a
    vf = ViewFinder(affine=T, shape=z.shape, nodata=np.float32(-9999), crs=crs)
    grid = Grid(viewfinder=vf)
    dem = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(Raster(z, vf))), eps=1e-6, max_iter=10000)
    del z
    fdir = grid.flowdir(dem, dirmap=DIRMAP)
    del dem
    acc = grid.accumulation(fdir, dirmap=DIRMAP)
    A = np.asarray(acc)
    mt = celle_tracciato(g, T, A.shape) & (A > ACC_THRESHOLD)
    rr, cc = np.where(mt)
    aree = A[rr, cc] * 25 / 1e6
    q = np.argmin(np.abs(np.log(aree / adb[i])))
    xc, yc = T.c + (cc[q] + 0.5) * 5, T.f - (rr[q] + 0.5) * 5
    xn, yn = xc - OFFSET_M, yc + OFFSET_M
    xs, ys = grid.snap_to_mask(acc > ACC_THRESHOLD, (xn, yn))
    mb = np.asarray(grid.catchment(x=xs, y=ys, fdir=fdir, dirmap=DIRMAP, xytype='coordinate'))
    an = mb.sum() * 25 / 1e6
    bordo = bool(mb[:2].any() or mb[-2:].any() or mb[:, :2].any() or mb[:, -2:].any())
    r_, c_ = np.where(mb)
    sub = mb[r_.min():r_.max() + 1, c_.min():c_.max() + 1].astype('uint8')
    poli.append({'ID': i, 'A_km2': round(an, 3), 'geometry': unary_union(
        [shape(s) for s, v in shapes(sub, mask=sub.astype(bool), transform=T * T.translation(c_.min(), r_.min()))])})
    lon, lat = to_geo.transform(xn, yn)
    sez_csv = None
    righe.append({'ID': i, 'A_db_km2': adb[i], 'A_max_tracciato_km2': round(float(aree.max()), 3),
                  'A_sezione_tracciato_km2': round(an, 3), 'Diff_vs_DB': round(an / adb[i] - 1, 3),
                  'Compatibile': abs(an / adb[i] - 1) <= 0.15, 'Bacino_sul_bordo': bordo,
                  'X_nuovo': round(lon, 9), 'Y_nuovo': round(lat, 9), 'xmin': lim[0], 'ymin': lim[1], 'xmax': lim[2],
                  'ymax': lim[3], 'celle_porzione_M': round(A.size / 1e6, 1)})
    punti.append({'ID': i, 'A_km2': round(an, 3), 'geometry': gpd.points_from_xy([xn], [yn])[0]})
    print(righe[-1], flush=True)
    del grid, fdir, acc, A, mb
pd.DataFrame(righe).to_csv(os.path.join(out, 'sezioni_su_tracciato_kml.csv'), index=False)
gp = os.path.join(out, 'sezioni_su_tracciato_kml.gpkg')
gpd.GeoDataFrame(punti, crs=32633).to_file(gp, layer='sezione_su_tracciato', driver='GPKG')
gpd.GeoDataFrame(poli, crs=32633).to_file(gp, layer='bacino_sezione_su_tracciato', driver='GPKG')
