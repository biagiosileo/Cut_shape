"""
Regola: la sezione di chiusura deve stare dove il tracciato del ponte nel KML attraversa il reticolo.

Per ogni ponte si misura la distanza del punto di ponti.csv dal tracciato del ponte (KML abbinato per nome,
altrimenti il tracciato usato nel controllo delle coordinate). Entro TOLL_M il punto resta com'e'. Oltre,
il punto viene ricollocato sul tracciato, stesso DEM e stessa catena del codice (DEM unico inciso, D8, accumulo):
  - tra le celle entro TOLL_M dal tracciato con accumulo > 4000 (reticolo del codice) si prende quella con
    accumulo maggiore (il corso principale scavalcato dal ponte);
  - se il tracciato non tocca il reticolo del codice e dista meno di DIST_FOSSO_M dal punto, il tracciato e'
    considerato impreciso e il punto resta; se dista di piu', si prende la cella toccata con accumulo maggiore
    (almeno MIN_CELLE) e si assegna al ponte una soglia di aggancio pari al 90% del suo accumulo
    (colonna "soglia" di ponti.csv);
  - il punto e' il centro della cella spostato di 1,25 m verso l'angolo in alto a sinistra (snap_to_mask).
Se il punto sta sul tracciato KML di un altro ponte (nomi/progressive scambiati tra database e KML) resta.
Se il tracciato o il bacino del corso attraversato escono dalla porzione del ponte, si crea una porzione nuova dall'ingombro del bacino stimato
a 25 m (acc/fd sul DEM unico ricampionato al minimo 5x5) piu' MARGINE_M.
L'area del database non entra nella scelta.

Uso: python ricolloca_su_tracciato.py <dem5m_unico.tif> <ponti.csv> <controllo_coordinate.gpkg>
        <acc25.npy> <fd25.npy> <out_dir>
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
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from shapely.geometry import Point, box

DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
PASSO = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}
ACC_THRESHOLD = 4000
TOLL_M = 10.0
MIN_CELLE = 50
DIST_FOSSO_M = 50.0
MARGINE_M = 1500.0
OFFSET_M = 1.25
C5 = 5.0

dem_path, csv_path, gpkg, acc25, fd25, out = sys.argv[1:7]
os.makedirs(out, exist_ok=True)
P = pd.read_csv(csv_path).set_index('id')
Orig = P[['X', 'Y']].copy()
if 'soglia' not in P:
    P['soglia'] = pd.NA
k = gpd.read_file(gpkg, layer='kml_abbinato').set_index('ID').to_crs(32633)
kt = gpd.read_file(gpkg, layer='kml_tracciati').to_crs(32633).set_index('nome').geometry
tu = gpd.read_file(gpkg, layer='tracciato_usato').set_index('ID').to_crs(32633)
to_utm = Transformer.from_crs('EPSG:4326', 'EPSG:32633', always_xy=True)
to_geo = Transformer.from_crs('EPSG:32633', 'EPSG:4326', always_xy=True)
crs = Proj('EPSG:32633', preserve_units=True)
with rasterio.open(dem_path) as s:
    X0, Y0, XMAX, YMIN = s.transform.c, s.transform.f, s.bounds.right, s.bounds.bottom
A25 = np.load(acc25)
F25 = np.load(fd25)
T25 = Affine(25, 0, X0, 0, -25, Y0)


def tracciato(i):
    t = kt.get(k.loc[i, 'KML_nome'])
    return (t, 'KML per nome') if t is not None else (tu.geometry[i], tu.fonte[i])


def allinea(b):
    n = lambda v, f: f(round(v / C5, 3))
    return [float(round(v, 4)) for v in (X0 + n(max(b[0], X0) - X0, np.floor) * C5,
                                         Y0 - n(Y0 - max(b[1], YMIN), np.ceil) * C5,
                                         X0 + n(min(b[2], XMAX) - X0, np.ceil) * C5,
                                         Y0 - n(Y0 - min(b[3], Y0), np.floor) * C5)]


def porzione_da_25m(t):
    m = rasterize([(t.buffer(15), 1)], out_shape=A25.shape, transform=T25, all_touched=True).astype(bool)
    rr, cc = np.where(m)
    q = np.argmax(A25[rr, cc])
    up = np.zeros(F25.shape, bool)
    up[rr[q], cc[q]] = True
    st = [(rr[q], cc[q])]
    while st:
        a, b = st.pop()
        for d, (dr, dc) in PASSO.items():
            r2, c2 = a - dr, b - dc
            if 0 <= r2 < up.shape[0] and 0 <= c2 < up.shape[1] and not up[r2, c2] and F25[r2, c2] == d:
                up[r2, c2] = True
                st.append((r2, c2))
    r_, c_ = np.where(up)
    b = [X0 + c_.min() * 25, Y0 - (r_.max() + 1) * 25, X0 + (c_.max() + 1) * 25, Y0 - r_.min() * 25]
    tb = t.bounds
    return allinea([min(b[0], tb[0]) - MARGINE_M, min(b[1], tb[1]) - MARGINE_M,
                    max(b[2], tb[2]) + MARGINE_M, max(b[3], tb[3]) + MARGINE_M])


def flusso(lim):
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
    return np.asarray(grid.accumulation(fdir, dirmap=DIRMAP)), T


righe = []
da_fare = []
for i, p in P.iterrows():
    t, fonte = tracciato(i)
    x, y = to_utm.transform(p.X, p.Y)
    d = t.distance(Point(x, y))
    r = {'ID': i, 'Tracciato': fonte, 'Lunghezza tracciato (m)': round(t.length), 'Dist punto-tracciato (m)': round(d, 1),
         'Porzione prima': p.porzione}
    altri = [j for j in P.index if j != i and kt.get(k.loc[j, 'KML_nome']) is not None
             and kt[k.loc[j, 'KML_nome']].distance(Point(x, y)) <= TOLL_M]
    if d <= TOLL_M:
        r['Esito'] = 'sul tracciato: invariato'
    elif altri:
        r['Esito'] = (f'sul tracciato KML abbinato al ponte {altri[0]} (nomi/progressive scambiati tra database e '
                      'KML): invariato')
    else:
        da_fare.append(i)
    righe.append(r)
R = pd.DataFrame(righe).set_index('ID')

nuove = 62
gruppi = {}
for i in da_fare:
    t, _ = tracciato(i)
    p = P.loc[i]
    lim = [p.xmin, p.ymin, p.xmax, p.ymax]
    l25 = porzione_da_25m(t)
    if not box(*lim).buffer(-200).contains(t):
        gruppi.setdefault(('nuova', i), (l25, [i]))
    elif box(*lim).contains(box(*l25).buffer(-MARGINE_M + 500)):
        gruppi.setdefault(p.porzione, (lim, []))[1].append(i)
    else:  # il bacino del corso sul tracciato esce dalla porzione: porzione allargata
        gruppi.setdefault(('nuova', i), (allinea([min(lim[0], l25[0]), min(lim[1], l25[1]),
                                                   max(lim[2], l25[2]), max(lim[3], l25[3])]), [i]))
for chiave, (lim, ids) in gruppi.items():
    A, T = flusso(lim)
    for i in ids:
        t, _ = tracciato(i)
        m = rasterize([(t.buffer(TOLL_M), 1)], out_shape=A.shape, transform=T, all_touched=True).astype(bool)
        rr, cc = np.where(m & (A > ACC_THRESHOLD))
        soglia = None
        if len(rr) == 0:
            rr, cc = np.where(m & (A >= MIN_CELLE))
            if R.loc[i, 'Dist punto-tracciato (m)'] <= DIST_FOSSO_M:
                R.loc[i, 'Esito'] = (f'il tracciato non tocca il reticolo ed e\' a meno di {DIST_FOSSO_M:.0f} m dal '
                                     'punto: tracciato impreciso, invariato')
                continue
            if len(rr) == 0:
                R.loc[i, 'Esito'] = 'il tracciato non tocca nessun fosso: invariato'
                continue
        q = np.argmax(A[rr, cc])
        acc_cella = float(A[rr[q], cc[q]])
        if acc_cella <= ACC_THRESHOLD:
            soglia = int(0.9 * acc_cella)
        xc, yc = T.c + (cc[q] + 0.5) * C5, T.f - (rr[q] + 0.5) * C5
        lon, lat = to_geo.transform(xc - OFFSET_M, yc + OFFSET_M)
        P.loc[i, ['X', 'Y']] = [round(lon, 9), round(lat, 9)]
        P.loc[i, 'soglia'] = soglia if soglia is not None else pd.NA
        if isinstance(chiave, tuple):
            P.loc[i, 'porzione'] = f'porzione_{nuove}'
            P.loc[i, ['xmin', 'ymin', 'xmax', 'ymax']] = lim
            nuove += 1
        R.loc[i, 'Esito'] = 'ricollocato sul tracciato' + (f' (soglia {soglia} celle)' if soglia else '')
        R.loc[i, 'Area cella sul tracciato (km²)'] = round(acc_cella * C5 * C5 / 1e6, 4)
        R.loc[i, 'Spostamento (m)'] = round(Point(to_utm.transform(Orig.X[i], Orig.Y[i])).distance(Point(xc, yc)))
        R.loc[i, 'Porzione nuova'] = P.loc[i, 'porzione']
        print(i, R.loc[i].to_dict(), flush=True)
    del A
P.to_csv(os.path.join(out, 'ponti_tracciato_kml.csv'), index=False)
R.reset_index().to_csv(os.path.join(out, 'ricollocazione_tracciato.csv'), index=False)
print(R.Esito.value_counts())
