"""
Ponti con il bacino troncato dal bordo della porzione: allarga la porzione finche' il
bacino non tocca piu' il bordo.

Per ogni ponte si ripete la catena di pysheds_bridges_5m.py (fill_pits, fill_depressions,
resolve_flats eps=1e-6 max_iter=10000, D8, accumulo, snap_to_mask acc > 4000, catchment) sulla
porzione corrente, in float32 per stare in memoria anche sulle porzioni grandi. Se il bacino
arriva alle due celle di bordo, i lati toccati si spostano in fuori di max(2 km, lato attuale)
e il calcolo si ripete. La porzione finale e' quella in cui il bacino e' chiuso, con un
margine di MARGINE_M sul suo ingombro (allineata alla griglia del DEM unico).

Il punto del ponte (X, Y di ponti.csv) non cambia: cambia solo la porzione di DEM letta.

Uso: python correzione_porzioni.py <dem5m_unico.tif> <ponti.csv> <out_dir> <id> [<id> ...]
     opzione --iniziale ID:xmin,ymin,xmax,ymax  porzione di partenza (al posto di quella del CSV)
"""
import json
import os
import sys
import time

import numpy as np
np.in1d = np.isin
import pandas as pd
import rasterio
from pyproj import Proj, Transformer
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
from rasterio.windows import from_bounds

DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
ACC_THRESHOLD = 4000
C5 = 5.0
MARGINE_M = 1000.0
MAX_ITER = 8

arg = sys.argv[1:]
iniziali = {}
while '--iniziale' in arg:
    k = arg.index('--iniziale')
    i, b = arg[k + 1].split(':')
    iniziali[int(i)] = [float(v) for v in b.split(',')]
    del arg[k:k + 2]
dem_path, csv_path, out = arg[:3]
ids = [int(i) for i in arg[3:]]
os.makedirs(out, exist_ok=True)
P = pd.read_csv(csv_path).set_index('id')
tr = Transformer.from_crs('EPSG:4326', 'EPSG:32633', always_xy=True)
crs = Proj('EPSG:32633', preserve_units=True)
with rasterio.open(dem_path) as s:
    X0, Y0 = s.transform.c, s.transform.f
    XMAX, YMIN = X0 + s.width * C5, Y0 - s.height * C5


def allinea(b):
    """Limiti sulla griglia del DEM unico, dentro la sua estensione."""
    def n(v, f):  # numero di celle, senza errori di arrotondamento sui limiti gia' allineati
        return f(round(v / C5, 3))
    xmin = X0 + n(max(b[0], X0) - X0, np.floor) * C5
    xmax = X0 + n(min(b[2], XMAX) - X0, np.ceil) * C5
    ymax = Y0 - n(Y0 - min(b[3], Y0), np.floor) * C5
    ymin = Y0 - n(Y0 - max(b[1], YMIN), np.ceil) * C5
    return [float(round(v, 4)) for v in (xmin, ymin, xmax, ymax)]


def bacino(lim, x, y):
    with rasterio.open(dem_path) as src:
        w = from_bounds(*lim, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w)
        T = src.window_transform(w)
        nd = a == src.nodata
        a = (a.astype(np.float64) * src.scales[0]).astype(np.float32)
    a[nd] = -9999
    del nd
    vf = ViewFinder(affine=T, shape=a.shape, nodata=np.float32(-9999), crs=crs)
    grid = Grid(viewfinder=vf)
    dem = Raster(a, vf)
    del a
    dem = grid.fill_pits(dem)
    dem = grid.fill_depressions(dem)
    dem = grid.resolve_flats(dem, eps=1e-6, max_iter=10000)
    fdir = grid.flowdir(dem, dirmap=DIRMAP)
    del dem
    acc = grid.accumulation(fdir, dirmap=DIRMAP)
    xs, ys = grid.snap_to_mask(acc > ACC_THRESHOLD, (x, y))
    del acc
    m = np.asarray(grid.catchment(x=xs, y=ys, fdir=fdir, dirmap=DIRMAP, xytype='coordinate'))
    del fdir
    r, c = np.where(m)
    # ingombro del bacino (coordinate dei bordi delle celle) e lati della porzione toccati
    ing = [T.c + c.min() * C5, T.f - (r.max() + 1) * C5, T.c + (c.max() + 1) * C5, T.f - r.min() * C5]
    H, W = m.shape
    tocca = {'ovest': c.min() <= 1, 'sud': r.max() >= H - 2, 'est': c.max() >= W - 2, 'nord': r.min() <= 1}
    return {'A_km2': round(m.sum() * C5 * C5 / 1e6, 3), 'snap_m': round(float(np.hypot(xs - x, ys - y)), 1),
            'ingombro': [round(v, 4) for v in ing], 'tocca': [k for k, v in tocca.items() if v],
            'celle_porzione': H * W}


righe = []
for i in ids:
    p = P.loc[i]
    x, y = tr.transform(p.X, p.Y)
    lim = allinea(iniziali.get(i, [p.xmin, p.ymin, p.xmax, p.ymax]))
    storia = []
    for it in range(MAX_ITER):
        t0 = time.time()
        b = bacino(lim, x, y)
        storia.append({'iterazione': it, 'porzione': lim, **b, 's': round(time.time() - t0)})
        print(i, it, [float(v) for v in lim], b['A_km2'], 'km2, tocca:', b['tocca'] or '-', f"({b['celle_porzione'] / 1e6:.0f} M celle)",
              flush=True)
        bordo_dem = [lim[0] <= X0, lim[1] <= YMIN, lim[2] >= XMAX, lim[3] >= Y0]
        if not b['tocca']:
            break
        dx, dy = max(2000, lim[2] - lim[0]), max(2000, lim[3] - lim[1])
        nuovo = list(lim)
        if 'ovest' in b['tocca']:
            nuovo[0] -= dx
        if 'est' in b['tocca']:
            nuovo[2] += dx
        if 'sud' in b['tocca']:
            nuovo[1] -= dy
        if 'nord' in b['tocca']:
            nuovo[3] += dy
        nuovo = allinea(nuovo)
        if nuovo == lim:  # gia' al bordo del DEM unico
            print(i, 'bacino troncato dal bordo del DEM unico', bordo_dem, flush=True)
            break
        lim = nuovo
    f = storia[-1]
    finale = allinea([f['ingombro'][0] - MARGINE_M, f['ingombro'][1] - MARGINE_M,
                      f['ingombro'][2] + MARGINE_M, f['ingombro'][3] + MARGINE_M]) if not f['tocca'] else f['porzione']
    righe.append({'ID': i, 'porzione_prima': p.porzione, 'A_prima_km2': storia[0]['A_km2'],
                  'A_finale_km2': f['A_km2'], 'iterazioni': len(storia), 'chiuso': not f['tocca'],
                  'xmin': finale[0], 'ymin': finale[1], 'xmax': finale[2], 'ymax': finale[3]})
    json.dump(storia, open(os.path.join(out, f'id{i:03d}_iterazioni.json'), 'w'), indent=1)
    pd.DataFrame(righe).to_csv(os.path.join(out, 'porzioni_corrette.csv'), index=False)
print(pd.DataFrame(righe).to_string())
