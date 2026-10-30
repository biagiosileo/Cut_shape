"""
Prova "breaching" sui ponti non compatibili: invece di riempire le depressioni (fill, come pysheds), il DEM
viene inciso lungo il percorso di costo minimo (WhiteboxTools breach_depressions_least_cost), che taglia i
rilevati (strade, ferrovie, argini) che nel DEM fanno da diga. Serve a capire se l'area mancante e' bloccata
da un rilevato a monte del ponte.

Per ogni ponte, sulla sua porzione del DEM unico: breaching, D8, accumulo; area alla cella con accumulo
maggiore entro TOLL_M dal tracciato del ponte nel KML e al punto attuale (cella piu' vicina con accumulo > 4000
entro TOLL_M), confrontate con l'area del codice e del database.

Uso: python prova_breaching.py <dem5m_unico.tif> <ponti.csv> <parametri.csv> <controllo_coordinate.gpkg>
        <Database.xlsx> <out_dir> <id> [<id> ...]
"""
import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import whitebox_workflows as wb
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.windows import from_bounds

TOLL_M = 10.0
SOGLIA = 4000

dem_path, pcsv, par, gp, dbx, out = sys.argv[1:7]
ids = [int(i) for i in sys.argv[7:]]
os.makedirs(out, exist_ok=True)
P = pd.read_csv(pcsv).set_index('id')
U = pd.read_csv(par)
U['ID'] = U.ID.astype(int)
U = U.set_index('ID')
k = gpd.read_file(gp, layer='kml_abbinato').set_index('ID').to_crs(32633)
kt = gpd.read_file(gp, layer='kml_tracciati').to_crs(32633).set_index('nome').geometry
tu = gpd.read_file(gp, layer='tracciato_usato').set_index('ID').to_crs(32633).geometry
db = pd.read_excel(dbx).rename(columns={'Unnamed: 0': 'ID'})
db = db[pd.to_numeric(db.ID, errors='coerce').notna()]
db['ID'] = db.ID.astype(int)
adb = pd.to_numeric(db.set_index('ID')['SUPERFICIE BACINO (km2)'], errors='coerce')
tr = Transformer.from_crs(4326, 32633, always_xy=True)
wbe = wb.WbEnvironment()
wbe.verbose = False
righe = []
for porz, g in P.loc[ids].groupby('porzione'):
    p = g.iloc[0]
    with rasterio.open(dem_path) as src:
        w = from_bounds(p.xmin, p.ymin, p.xmax, p.ymax, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w)
        T = src.window_transform(w)
        z = (a.astype(np.float64) * src.scales[0]).astype(np.float32)
        z[a == src.nodata] = -9999
        prof = src.profile
    prof.update(dtype='float32', nodata=-9999, width=z.shape[1], height=z.shape[0], transform=T, compress='deflate')
    prof.pop('scales', None)
    f = os.path.join(out, f'_{porz}.tif')
    with rasterio.open(f, 'w', **prof) as d:
        d.write(z, 1)
    br = wbe.hydrology.breach_depressions_least_cost(dem=wbe.read_raster(f), fill_deps=True)
    acc = wbe.hydrology.d8_flow_accum(input=wbe.hydrology.d8_pointer(dem=br), out_type='cells', input_is_pointer=True)
    wbe.write_raster(acc, f.replace('.tif', '_acc.tif'))
    with rasterio.open(f.replace('.tif', '_acc.tif')) as s:
        A = s.read(1)
    for i, q in g.iterrows():
        t = kt.get(k.loc[i, 'KML_nome'])
        t = t if t is not None else tu[i]
        m = rasterize([(t.buffer(TOLL_M), 1)], out_shape=A.shape, transform=T, all_touched=True).astype(bool)
        a_tr = float(A[m].max()) * 25 / 1e6
        x, y = tr.transform(q.X, q.Y)
        mp = rasterize([(gpd.points_from_xy([x], [y])[0].buffer(TOLL_M), 1)], out_shape=A.shape, transform=T,
                       all_touched=True).astype(bool) & (A > SOGLIA)
        a_pt = float(A[mp].max()) * 25 / 1e6 if mp.any() else np.nan
        righe.append({'ID': i, 'Area DB': adb.get(i), 'Area codice (fill)': U.A_km2[i],
                      'Breaching: punto attuale': round(a_pt, 3), 'Breaching: tracciato KML': round(a_tr, 3)})
        print(righe[-1], flush=True)
    for e in ('', '_acc'):
        os.remove(f.replace('.tif', f'{e}.tif'))
R = pd.DataFrame(righe).sort_values('ID')
R.to_csv(os.path.join(out, 'prova_breaching.csv'), index=False)
print(R.to_string(index=False))
