"""
Revisione dei ponti fuori tolleranza (cartella separata, i risultati precedenti non cambiano).

Stesso DEM e stessa catena del codice dell'utente (DEM unico inciso, fill_pits, fill_depressions,
resolve_flats eps=1e-6 max_iter=10000, D8, accumulo), sulle porzioni corrette. Tre gruppi:

  sposta  ponti con una sezione di area compatibile (+-15% dal database) entro RAGGIO_SPOSTA_M: si
          propone la sezione compatibile piu' vicina al tracciato del ponte (a parita', al punto
          attuale); si indica se e' sullo stesso corso (a monte / a valle) o su un altro corso;
  soglia  ponti con area del database sotto la soglia del reticolo (0,1 km2): stesso calcolo con una
          soglia ridotta solo per il ponte, meta' dell'area del database (minimo SOGLIA_MIN celle);
  db      ponti senza sezione compatibile vicina: area massima entro RAGGIO_SPOSTA_M e sezione
          compatibile piu' vicina entro RAGGIO_DB_M, per capire se le coordinate indicano un altro
          ponte o se il valore di area non e' coerente.

Il punto proposto e' il centro della cella spostato di 1,25 m verso l'angolo in alto a sinistra,
come i punti di ponti.csv (convenzione di snap_to_mask); per ogni punto proposto si verifica che il
bacino ricalcolato da quel punto abbia l'area attesa.

Uso: python revisione_non_compatibili.py <dem5m_unico.tif> <ponti.csv> <Database.xlsx>
        <controllo_coordinate.gpkg> <out_dir>
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
from rasterio.features import shapes
from rasterio.windows import from_bounds
from shapely.geometry import LineString, Point, shape
from shapely.ops import unary_union

DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
PASSO = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}
ACC_THRESHOLD = 4000
SOGLIA_MIN = 50
RAGGIO_SPOSTA_M = 300.0
RAGGIO_DB_M = 2000.0
TOL = 0.15
C5 = 5.0
OFFSET_M = 1.25
GRUPPI = {
    'sposta': [44, 72, 85, 102, 104, 105, 106, 107, 108, 109, 111, 124, 143, 177, 196, 200],
    'soglia': [64, 116, 129, 151, 168, 202],
    'db': [13, 19, 21, 58, 83, 90, 103, 113, 117, 118, 155, 174, 190, 198],
}

dem_path, csv_path, dbx, gpkg, out = sys.argv[1:6]
os.makedirs(out, exist_ok=True)
P = pd.read_csv(csv_path).set_index('id')
db = pd.read_excel(dbx).rename(columns={'Unnamed: 0': 'ID'})
db = db[pd.to_numeric(db.ID, errors='coerce').notna()]
db['ID'] = db.ID.astype(int)
db = db.set_index('ID')
adb = pd.to_numeric(db['SUPERFICIE BACINO (km2)'], errors='coerce')
trac = gpd.read_file(gpkg, layer='tracciato_usato').to_crs(32633).set_index('ID').geometry
to_utm = Transformer.from_crs('EPSG:4326', 'EPSG:32633', always_xy=True)
to_geo = Transformer.from_crs('EPSG:32633', 'EPSG:4326', always_xy=True)
crs = Proj('EPSG:32633', preserve_units=True)
gruppo_di = {i: g for g, ids in GRUPPI.items() for i in ids}


def flusso(lim):
    with rasterio.open(dem_path) as src:
        w = from_bounds(*lim, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w)
        T = src.window_transform(w)
        nd = a == src.nodata
        z = (a.astype(np.float64) * src.scales[0]).astype(np.float32)
    del a
    z[nd] = -9999
    vf = ViewFinder(affine=T, shape=z.shape, nodata=np.float32(-9999), crs=crs)
    grid = Grid(viewfinder=vf)
    dem = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(Raster(z, vf))), eps=1e-6, max_iter=10000)
    del z
    fdir = grid.flowdir(dem, dirmap=DIRMAP)
    del dem
    return grid, fdir, grid.accumulation(fdir, dirmap=DIRMAP), T


def cella(T, x, y):
    c, r = ~T * (x, y)
    return int(r), int(c)


def poligono(m, T):
    r, c = np.where(m)
    r0, r1, c0, c1 = r.min(), r.max() + 1, c.min(), c.max() + 1
    Tm = T * T.translation(c0, r0)
    sub = m[r0:r1, c0:c1].astype('uint8')
    return unary_union([shape(g) for g, v in shapes(sub, mask=sub.astype(bool), transform=Tm)])


def bacino(grid, fdir, acc, x, y, soglia):
    xs, ys = grid.snap_to_mask(acc > soglia, (x, y))
    m = np.asarray(grid.catchment(x=xs, y=ys, fdir=fdir, dirmap=DIRMAP, xytype='coordinate'))
    return m, (xs, ys)


def a_valle(F, r, c, r2, c2, nmax=400):
    """True se la cella (r2, c2) si raggiunge da (r, c) seguendo la direzione di flusso."""
    for _ in range(nmax):
        if (r, c) == (r2, c2):
            return True
        d = int(F[r, c])
        if d not in PASSO:
            return False
        r, c = r + PASSO[d][0], c + PASSO[d][1]
        if not (0 <= r < F.shape[0] and 0 <= c < F.shape[1]):
            return False
    return False


def candidati(A, T, x, y, a_db, soglia, raggio):
    """Celle di reticolo con area compatibile entro il raggio: (dist punto, area, riga, col, xc, yc)."""
    k = int(raggio / C5) + 1
    r0, c0 = cella(T, x, y)
    ra, ca = max(r0 - k, 0), max(c0 - k, 0)
    W = A[ra:r0 + k + 1, ca:c0 + k + 1]
    ii, jj = np.where((W > soglia) & (np.abs(W * C5 * C5 / 1e6 / a_db - 1) <= TOL))
    xc = T.c + (ca + jj + 0.5) * C5
    yc = T.f - (ra + ii + 0.5) * C5
    d = np.hypot(xc - x, yc - y)
    s = d <= raggio
    return [(float(d[q]), float(W[ii[q], jj[q]] * C5 * C5 / 1e6), ra + ii[q], ca + jj[q], float(xc[q]), float(yc[q]))
            for q in np.where(s)[0]]


righe, punti_att, punti_nuovi, linee, bac_att, bac_nuovi = [], [], [], [], [], []
ids = [i for g in GRUPPI.values() for i in g]
for porz, g in P.loc[ids].groupby('porzione'):
    t0 = time.time()
    grid, fdir, acc, T = flusso(tuple(g.iloc[0][['xmin', 'ymin', 'xmax', 'ymax']]))
    A, F = np.asarray(acc), np.asarray(fdir)
    for i, p in g.iterrows():
        gr, a_db = gruppo_di[i], float(adb[i])
        nome = str(db.loc[i, 'Nome opera']).strip()
        x, y = to_utm.transform(p.X, p.Y)
        soglia = max(SOGLIA_MIN, int(round(0.5 * a_db / (C5 * C5 / 1e6)))) if gr == 'soglia' else ACC_THRESHOLD
        m0, (xs0, ys0) = bacino(grid, fdir, acc, x, y, ACC_THRESHOLD)
        a0 = m0.sum() * C5 * C5 / 1e6
        tr = trac.get(i)
        riga = {'ID': i, 'Nome opera': nome if nome not in ('-', 'nan') else '', 'Gruppo': gr,
                'SP': db.loc[i, 'NUOVA NUMERAZIONE'], 'km': db.loc[i, 'Progressiva km'], 'A_db_km2': a_db,
                'A_attuale_km2': round(a0, 3), 'Soglia_celle': soglia}
        punti_att.append({'ID': i, 'gruppo': gr, 'A_db_km2': a_db, 'A_km2': round(a0, 3), 'geometry': Point(x, y)})
        bac_att.append({'ID': i, 'gruppo': gr, 'A_km2': round(a0, 3), 'geometry': poligono(m0, T)})
        del m0
        if gr == 'db':
            k = int(RAGGIO_SPOSTA_M / C5)
            r0, c0 = cella(T, x, y)
            W = A[max(r0 - k, 0):r0 + k + 1, max(c0 - k, 0):c0 + k + 1]
            riga['A_max_300m_km2'] = round(float(W.max()) * C5 * C5 / 1e6, 3)
            cand = candidati(A, T, x, y, a_db, ACC_THRESHOLD, RAGGIO_DB_M)
            if cand:
                d, a, rr, cc, xc, yc = min(cand)
                riga.update({'Dist_compat_2km_m': round(d), 'A_compat_km2': round(a, 3)})
                linee.append({'ID': i, 'gruppo': gr, 'dist_m': round(d), 'geometry': LineString([(x, y), (xc, yc)])})
            righe.append(riga)
            print(porz, i, gr, riga, flush=True)
            continue
        if gr == 'soglia':
            m1, (xs1, ys1) = bacino(grid, fdir, acc, x, y, soglia)
            riga['A_soglia_ridotta_km2'] = round(m1.sum() * C5 * C5 / 1e6, 4)
            riga['Snap_soglia_ridotta_m'] = round(float(np.hypot(xs1 - x, ys1 - y)), 1)
            del m1
        cand = candidati(A, T, x, y, a_db, soglia, RAGGIO_SPOSTA_M)
        if not cand:
            riga['Esito'] = 'nessuna sezione compatibile entro 300 m'
            righe.append(riga)
            print(porz, i, gr, riga, flush=True)
            continue
        # sezione proposta: la piu' vicina al tracciato del ponte, a parita' la piu' vicina al punto
        chiave = (lambda q: (round(tr.distance(Point(q[4], q[5])) / 5), q[0])) if tr is not None else (lambda q: q[0])
        d, a, rr, cc, xc, yc = min(cand, key=chiave)
        xn, yn = xc - OFFSET_M, yc + OFFSET_M
        m2, (xs2, ys2) = bacino(grid, fdir, acc, xn, yn, soglia)
        a2 = m2.sum() * C5 * C5 / 1e6
        rs, cs = cella(T, xs0, ys0)
        corso = ('stesso corso, a valle' if a_valle(F, rs, cs, rr, cc) else
                 'stesso corso, a monte' if a_valle(F, rr, cc, rs, cs) else 'altro corso')
        lon, lat = to_geo.transform(xn, yn)
        riga.update({'Dist_spostamento_m': round(d), 'Dist_dal_tracciato_m': round(tr.distance(Point(xc, yc))) if tr is not None else None,
                     'Corso': corso, 'A_proposta_km2': round(a2, 4), 'X_nuovo': round(lon, 9), 'Y_nuovo': round(lat, 9),
                     'Verifica': 'ok' if abs(a2 / a_db - 1) <= TOL else 'controllare'})
        punti_nuovi.append({'ID': i, 'gruppo': gr, 'A_db_km2': a_db, 'A_km2': round(a2, 4), 'dist_m': round(d),
                            'corso': corso, 'soglia': soglia, 'conferma': '', 'note': '', 'geometry': Point(xn, yn)})
        linee.append({'ID': i, 'gruppo': gr, 'dist_m': round(d), 'geometry': LineString([(x, y), (xn, yn)])})
        bac_nuovi.append({'ID': i, 'gruppo': gr, 'A_km2': round(a2, 4), 'geometry': poligono(m2, T)})
        del m2
        righe.append(riga)
        print(porz, i, gr, riga, flush=True)
    del grid, fdir, acc, A, F
    print(porz, 'fatto in', round(time.time() - t0), 's', flush=True)

pd.DataFrame(righe).sort_values(['Gruppo', 'ID']).to_csv(os.path.join(out, 'revisione.csv'), index=False)
gp = os.path.join(out, 'revisione_non_compatibili.gpkg')
for nome, L in [('punto_attuale', punti_att), ('punto_proposto', punti_nuovi), ('spostamento', linee),
                ('bacino_attuale', bac_att), ('bacino_proposto', bac_nuovi)]:
    gpd.GeoDataFrame(L, crs=32633).sort_values('ID').to_file(gp, layer=nome, driver='GPKG')
tt = trac[trac.index.isin(ids)].reset_index()
tt['gruppo'] = tt.ID.map(gruppo_di)
gpd.GeoDataFrame(tt, crs=32633).to_file(gp, layer='tracciato_ponte', driver='GPKG')
print('fatto')
