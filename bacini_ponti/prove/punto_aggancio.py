# Prova: area del bacino (DEM 30 m, Whitebox riempimento + D8) agganciando il
# ponte a punti diversi: punto medio DB (input attuale), punto KML, e massimo
# accumulo lungo il segmento inizio-fine dell'attraversamento.
# Uso: python punto_aggancio.py <dem30.tif> <controllo_coordinate.gpkg> <Database.xlsx> <out.csv>
import sys, os
import numpy as np, pandas as pd, geopandas as gpd, rasterio, whitebox_workflows as wb
dem_p, gpkg, dbx, out = sys.argv[1:5]
wbe = wb.WbEnvironment(); wbe.verbose = False
tmp = out + '.acc.tif'
wbe.write_raster(wbe.hydrology.d8_flow_accum(input=wbe.hydrology.fill_depressions(dem=wbe.read_raster(dem_p)), out_type='cells'), tmp)
with rasterio.open(tmp) as s:
    acc = s.read(1).astype(float) * abs(s.transform.a * s.transform.e) / 1e6; T = s.transform
os.remove(tmp)
with rasterio.open(dem_p) as s:
    acc[s.read(1) == s.nodata] = 0
SOGLIA = 0.25
inv = ~T
def vicino(x, y):
    c0, r0 = inv * (x, y); r0, c0 = int(r0), int(c0); n = 4
    while True:
        rr, cc = np.mgrid[max(r0-n,0):r0+n+1, max(c0-n,0):c0+n+1]
        X, Y = T * (cc + .5, rr + .5); d = np.hypot(X - x, Y - y); m = acc[rr, cc] >= SOGLIA
        if m.any(): i = np.argmin(np.where(m, d, np.inf)); return acc[rr.flat[i], cc.flat[i]], d.flat[i]
        n *= 2
def segmento(x0, y0, x1, y1, buf=1):
    L = np.hypot(x1-x0, y1-y0); n = max(int(L / 10), 1)
    best = (0, np.nan)
    for t in np.linspace(0, 1, n + 1):
        x, y = x0 + t*(x1-x0), y0 + t*(y1-y0); c, r = inv * (x, y); r, c = int(r), int(c)
        w = acc[r-buf:r+buf+1, c-buf:c+buf+1]
        if w.max() > best[0]: best = (w.max(), t)
    return best[0]
ini = gpd.read_file(gpkg, layer='db_inizio').set_index('ID'); fin = gpd.read_file(gpkg, layer='db_fine').set_index('ID')
inp = gpd.read_file(gpkg, layer='input_script').set_index('ID'); kml = gpd.read_file(gpkg, layer='kml_abbinato').set_index('ID')
db = pd.read_excel(dbx).rename(columns={'Unnamed: 0': 'ID'}).set_index('ID')
adb = pd.to_numeric(db['SUPERFICIE BACINO (km2)'], errors='coerce')
rows = []
for i in inp.index:
    o = {'ID': i, 'A_db': adb.get(i)}
    o['A_medio'], _ = vicino(inp.geometry[i].x, inp.geometry[i].y)
    o['A_kml'], o['d_kml'] = vicino(kml.geometry[i].x, kml.geometry[i].y) if i in kml.index else (np.nan, np.nan)
    if i in ini.index and i in fin.index:
        a, b = ini.geometry[i], fin.geometry[i]
        o['A_segmento'] = segmento(a.x, a.y, b.x, b.y); o['L_seg'] = a.distance(b)
    rows.append(o)
r = pd.DataFrame(rows); r.to_csv(out, index=False)
ok = lambda c: ((r[c]/r.A_db - 1).abs() <= .15) & r.A_db.notna()
for c in ('A_medio', 'A_kml', 'A_segmento'): print(c, ok(c).sum(), '/', r.A_db.notna().sum())
s = r.L_seg <= 300
print('segmento solo se lungo <=300 m, altrimenti punto medio:', (np.where(s, ok('A_segmento'), ok('A_medio'))).sum())
