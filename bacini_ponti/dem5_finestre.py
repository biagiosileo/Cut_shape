"""
Passo 1 dell'analisi a 5 m: idrologia su finestre di DEM ibrido.

DEM ibrido: DTM a 5 m dei 13 gruppi dove disponibile; fuori dalla copertura a
5 m, DEM a 30 m ricampionato (bilineare) sulla stessa griglia a 5 m, solo per
completare i bacini che escono dal 5 m. Ogni cella porta il flag della fonte.

Per ogni ponte la finestra e' l'ingombro del suo bacino a 30 m (gia' calcolato)
piu' MARGINE_M. Le finestre sono condivise: un ponte la cui finestra sta dentro
una gia' elaborata usa quella.

Per ogni finestra: Whitebox riempimento delle depressioni + puntatore D8 +
accumulo. Si salvano:
  - puntatore D8 della finestra (GeoTIFF, codici Whitebox) e flag fonte;
  - per ogni ponte una "toppa" di +-TOPPA_M attorno al ponte con accumulo (km2),
    puntatore e flag fonte, per le analisi di aggancio.

Uso: python dem5_finestre.py <cartella_dem5> <dem30_mosaico.tif> <contenimento.csv>
                             <controllo_coordinate.gpkg> <cartella_out>
"""
import glob
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
import whitebox_workflows as wb

MARGINE_M = 1000.0
TOPPA_M = 750.0
CELLA = 5.0
NODATA = -9999.0

dem5_dir, dem30_p, cont_csv, gpkg, out = sys.argv[1:6]
os.makedirs(os.path.join(out, 'finestre'), exist_ok=True)
os.makedirs(os.path.join(out, 'toppe'), exist_ok=True)
files5 = sorted(glob.glob(os.path.join(dem5_dir, '**', '*.tif'), recursive=True))
idx5 = []
for f in files5:
    with rasterio.open(f) as s:
        idx5.append((f, s.bounds))
x_or, y_or = rasterio.open(files5[0]).transform.c, rasterio.open(files5[0]).transform.f


def allinea(v, orig, giu):
    k = (v - orig) / CELLA
    return orig + (np.floor(k) if giu else np.ceil(k)) * CELLA


def dem_ibrido(xmin, ymin, xmax, ymax):
    xmin, xmax = allinea(xmin, x_or, True), allinea(xmax, x_or, False)
    ymin, ymax = allinea(ymin, y_or, True), allinea(ymax, y_or, False)
    W, H = int(round((xmax - xmin) / CELLA)), int(round((ymax - ymin) / CELLA))
    T = from_origin(xmin, ymax, CELLA, CELLA)
    z = np.full((H, W), NODATA, np.float32)
    sel = [f for f, b in idx5 if b.left < xmax and b.right > xmin and b.bottom < ymax and b.top > ymin]
    if sel:
        m, _ = merge(sel, bounds=(xmin, ymin, xmax, ymax), res=CELLA, nodata=NODATA)
        z[:] = m[0][:H, :W]
    fonte5 = z != NODATA
    if not fonte5.all():
        z30 = np.full((H, W), NODATA, np.float32)
        with rasterio.open(dem30_p) as s:
            reproject(rasterio.band(s, 1), z30, dst_transform=T, dst_crs=s.crs,
                      resampling=Resampling.bilinear, src_nodata=s.nodata, dst_nodata=NODATA)
        z = np.where(fonte5, z, z30)
    return z, fonte5, T


def scrivi(path, arr, T, nodata, dtype):
    with rasterio.open(path, 'w', driver='GTiff', height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype=dtype, crs='EPSG:32633', transform=T, nodata=nodata,
                       compress='deflate', tiled=True, BIGTIFF='IF_SAFER') as d:
        d.write(arr.astype(dtype), 1)


cont = pd.read_csv(cont_csv)
cont['ID'] = cont.ID.astype(int)
pts = {}
for lay in ('input_script', 'db_inizio', 'db_fine', 'kml_abbinato'):
    g = gpd.read_file(gpkg, layer=lay).set_index('ID')
    pts[lay] = g.geometry
tr = gpd.read_file(gpkg, layer='tracciato_usato').set_index('ID').geometry


def bounds_ponte(i):
    r = cont.set_index('ID').loc[i]
    xs = [r.xmin, r.xmax]
    ys = [r.ymin, r.ymax]
    for lay in pts.values():
        if i in lay.index:
            xs.append(lay[i].x)
            ys.append(lay[i].y)
    if i in tr.index:
        b = tr[i].bounds
        xs += [b[0], b[2]]
        ys += [b[1], b[3]]
    return (min(xs) - MARGINE_M, min(ys) - MARGINE_M, max(xs) + MARGINE_M, max(ys) + MARGINE_M)


B = {int(i): bounds_ponte(i) for i in cont.ID}
ordine = sorted(B, key=lambda i: -(B[i][2] - B[i][0]) * (B[i][3] - B[i][1]))
if os.environ.get('SOLO_ID'):
    ordine = [int(v) for v in os.environ['SOLO_ID'].split(',')]
    B = {i: B[i] for i in ordine}
finestre, assegna = [], {}
for i in ordine:
    b = B[i]
    for k, fb in enumerate(finestre):
        if b[0] >= fb[0] and b[1] >= fb[1] and b[2] <= fb[2] and b[3] <= fb[3]:
            assegna[i] = k
            break
    else:
        finestre.append(b)
        assegna[i] = len(finestre) - 1
print(f"{len(B)} ponti, {len(finestre)} finestre", flush=True)

wbe = wb.WbEnvironment()
wbe.verbose = False
meta = {'finestre': [], 'ponti': {}}
for k, fb in enumerate(finestre):
    t0 = time.time()
    fdir = os.path.join(out, 'finestre')
    p_ptr = os.path.join(fdir, f'f{k:03d}_puntatore.tif')
    p_fon = os.path.join(fdir, f'f{k:03d}_fonte5m.tif')
    p_dem = os.path.join(fdir, f'f{k:03d}_dem_ibrido.tif')
    ids = [i for i, kk in assegna.items() if kk == k]
    z, fonte5, T = dem_ibrido(*fb)
    scrivi(p_dem, z, T, NODATA, 'float32')
    scrivi(p_fon, fonte5, T, 255, 'uint8')
    del z
    dem = wbe.read_raster(p_dem)
    filled = wbe.hydrology.fill_depressions(dem=dem)
    ptr = wbe.hydrology.d8_pointer(dem=filled)
    accr = wbe.hydrology.d8_flow_accum(input=ptr, out_type='cells', input_is_pointer=True)
    wbe.write_raster(ptr, p_ptr, options={'compress': True, 'geotiff': {'compression': 'deflate', 'bigtiff': True}})
    p_acc = os.path.join(fdir, '_acc.tif')
    wbe.write_raster(accr, p_acc)
    del dem, filled, ptr, accr
    with rasterio.open(p_acc) as s:
        acc = s.read(1)
    with rasterio.open(p_ptr) as s:
        ptr_a = s.read(1)
    os.remove(p_acc)
    inv = ~T
    for i in ids:
        cx, cy = pts['input_script'][i].x, pts['input_script'][i].y
        c0, r0 = inv * (cx - TOPPA_M, cy + TOPPA_M)
        c1, r1 = inv * (cx + TOPPA_M, cy - TOPPA_M)
        r0, c0, r1, c1 = max(int(r0), 0), max(int(c0), 0), min(int(r1) + 1, acc.shape[0]), min(int(c1) + 1, acc.shape[1])
        Tp = T * T.translation(c0, r0)
        np.savez_compressed(os.path.join(out, 'toppe', f'id{i:03d}.npz'),
                            acc_km2=(acc[r0:r1, c0:c1] * CELLA * CELLA / 1e6).astype(np.float32),
                            ptr=ptr_a[r0:r1, c0:c1].astype(np.uint8),
                            fonte5=fonte5[r0:r1, c0:c1], transform=np.array(Tp)[:6],
                            finestra=k, offset=np.array([r0, c0]))
        meta['ponti'][int(i)] = k
    meta['finestre'].append({'k': k, 'bounds': fb, 'shape': list(fonte5.shape), 'ponti': ids,
                             'frazione_5m': float(fonte5.mean()), 'secondi': round(time.time() - t0)})
    print(f"finestra {k}: {fonte5.shape} celle, {len(ids)} ponti, 5m {fonte5.mean():.2f}, "
          f"{time.time() - t0:.0f}s", flush=True)
    del acc, ptr_a, fonte5
    with open(os.path.join(out, 'finestre.json'), 'w') as f:
        json.dump(meta, f)
print("fatto", flush=True)
