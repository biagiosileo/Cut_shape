"""
Aste dei fossi piccoli (soglia ridotta) da vedere in QGIS: per ogni ponte con colonna "soglia", il percorso
del flusso dal punto proposto verso monte (ramo con accumulo maggiore, finche' l'accumulo supera 50 celle) e
verso valle fino al reticolo del codice (acc > 4000), piu' il reticolo locale con la soglia ridotta.

Uso: python aste_soglia_ridotta.py <dem5m_unico.tif> <ponti_prova_completo.csv> <out.gpkg>
"""
import sys

import numpy as np
np.in1d = np.isin
import geopandas as gpd
import pandas as pd
import rasterio
from pyproj import Proj, Transformer
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
from rasterio.windows import from_bounds
from shapely.geometry import LineString, shape

DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
PASSO = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}
ACC_THRESHOLD = 4000
MIN_MONTE = 50
FINESTRA_M = 1500.0

dem_path, csv_prova, out = sys.argv[1:4]
P = pd.read_csv(csv_prova).set_index('id')
P = P[P.soglia.notna()]
tr = Transformer.from_crs('EPSG:4326', 'EPSG:32633', always_xy=True)
crs = Proj('EPSG:32633', preserve_units=True)
aste, reti = [], []
for i, p in P.iterrows():
    x, y = tr.transform(p.X, p.Y)
    lim = (x - FINESTRA_M, y - FINESTRA_M, x + FINESTRA_M, y + FINESTRA_M)
    with rasterio.open(dem_path) as src:
        w = from_bounds(*lim, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w)
        T = src.window_transform(w)
        z = (a.astype(np.float64) * src.scales[0]).astype(np.float32)
        z[a == src.nodata] = -9999
    vf = ViewFinder(affine=T, shape=z.shape, nodata=np.float32(-9999), crs=crs)
    grid = Grid(viewfinder=vf)
    dem = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(Raster(z, vf))), eps=1e-6, max_iter=10000)
    fdir = grid.flowdir(dem, dirmap=DIRMAP)
    acc = grid.accumulation(fdir, dirmap=DIRMAP)
    F, A = np.asarray(fdir), np.asarray(acc)
    soglia = int(p.soglia)
    xs, ys = grid.snap_to_mask(acc > soglia, (x, y))
    c, r = ~T * (xs, ys)
    r, c = int(r), int(c)
    monte = [(r, c)]
    while True:
        rr, cc = monte[-1]
        ent = [(rr - dr, cc - dc) for d, (dr, dc) in PASSO.items()
               if 0 <= rr - dr < F.shape[0] and 0 <= cc - dc < F.shape[1] and F[rr - dr, cc - dc] == d]
        ent = [e for e in ent if A[e] >= MIN_MONTE]
        if not ent:
            break
        monte.append(max(ent, key=lambda e: A[e]))
    valle = [(r, c)]
    while A[valle[-1]] <= ACC_THRESHOLD and len(valle) < 2000:
        d = int(F[valle[-1]])
        if d not in PASSO:
            break
        valle.append((valle[-1][0] + PASSO[d][0], valle[-1][1] + PASSO[d][1]))
    xy = lambda cel: [(T.c + (cc + 0.5) * 5, T.f - (rr + 0.5) * 5) for rr, cc in cel]
    aste.append({'ID': i, 'tratto': 'a monte del punto proposto', 'soglia': soglia, 'geometry': LineString(xy(monte[::-1]))})
    aste.append({'ID': i, 'tratto': 'a valle fino al reticolo del codice', 'soglia': soglia, 'geometry': LineString(xy(valle))})
    rn = grid.extract_river_network(fdir, acc > soglia, dirmap=DIRMAP)
    reti += [{'ID': i, 'soglia': soglia, 'geometry': shape(f['geometry'])} for f in rn['features']]
    print(i, 'monte', len(monte), 'celle, valle', len(valle), 'celle', flush=True)
gpd.GeoDataFrame(aste, crs=32633).to_file(out, layer='asta_fosso', driver='GPKG')
gpd.GeoDataFrame(reti, crs=32633).to_file(out, layer='reticolo_soglia_ridotta', driver='GPKG')
