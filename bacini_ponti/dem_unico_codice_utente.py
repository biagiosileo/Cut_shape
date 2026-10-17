"""
DEM unico, CN unico e CSV unico per pysheds_bridges_5m.py (lettura a porzioni).

  - dem5m_unico.tif: DEM 5 m ibrido con reticolo di riferimento inciso (BRUCIA_M) su tutta
    l'area dei bacini (unione delle porzioni + margine), GeoTIFF Int32 in centimetri con
    scala 0,01 (QGIS lo mostra in metri), EPSG:32633, nodata -999999. Stesse quote al cm
    degli .asc gia' verificati;
  - cn5m_unico.tif: Curve Number sulla stessa griglia (float32, NaN senza dato);
  - ponti.csv: id, X, Y (WGS84, sezioni finali come nei CSV delle finestre, comprese le
    correzioni) + porzione e suoi limiti in UTM (xmin, ymin, xmax, ymax).

Controllo: per ogni porzione il ritaglio del DEM unico deve coincidere con il DEM della
finestra gia' verificata (stessa costruzione di input_codice_utente.py).

Uso: python dem_unico_codice_utente.py <run5/finestre> <finestre_codice.json> <reticolo_tagliato.shp>
        <cartella_cn5> <cartella CSV finestre (input_codice2)> <out_dir>
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
from rasterio.features import rasterize
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.windows import from_bounds, Window

dem_dir, fj, ret, cn_dir, csv_dir, out = sys.argv[1:7]
BRUCIA_M = float(os.environ.get('BRUCIA_M', '5'))
NODATA = -9999.0
C5 = 5.0
os.makedirs(out, exist_ok=True)
fin = json.load(open(fj))['finestre']
xmin = min(w['bounds'][0] for w in fin)
ymin = min(w['bounds'][1] for w in fin)
xmax = max(w['bounds'][2] for w in fin)
ymax = max(w['bounds'][3] for w in fin)
# allineamento alla griglia dei DEM delle finestre (i limiti nel json non sono allineati)
with rasterio.open(os.path.join(dem_dir, f"f{fin[0]['origine']:03d}_dem_ibrido.tif")) as s:
    ox, oy = s.transform.c, s.transform.f
xmin = ox + np.floor((xmin - ox) / C5) * C5
xmax = ox + np.ceil((xmax - ox) / C5) * C5
ymin = oy - np.ceil((oy - ymin) / C5) * C5
ymax = oy - np.floor((oy - ymax) / C5) * C5
W, H = int(round((xmax - xmin) / C5)), int(round((ymax - ymin) / C5))
T = from_origin(xmin, ymax, C5, C5)
print('griglia unica', H, 'x', W, round(H * W / 1e6), 'milioni di celle', flush=True)

# 1) mosaico del DEM ibrido (non inciso) dalle finestre del calcolo finale
z = np.full((H, W), NODATA, np.float32)
dentro = np.zeros((H, W), bool)
diffmax = 0.0
for k in sorted({w['origine'] for w in fin}):
    with rasterio.open(os.path.join(dem_dir, f'f{k:03d}_dem_ibrido.tif')) as s:
        a = s.read(1)
        crs = s.crs
        fx, fy = (s.transform.c - xmin) / C5, (ymax - s.transform.f) / C5
        assert abs(fx - round(fx)) < 1e-3 and abs(fy - round(fy)) < 1e-3, 'finestra non allineata'
        c0, r0 = int(round(fx)), int(round(fy))
    # solo la parte della finestra di origine che cade nella griglia unica
    rr0, cc0 = max(r0, 0), max(c0, 0)
    rr1, cc1 = min(r0 + a.shape[0], H), min(c0 + a.shape[1], W)
    a = a[rr0 - r0:rr1 - r0, cc0 - c0:cc1 - c0]
    zz = z[rr0:rr1, cc0:cc1]
    gia = dentro[rr0:rr1, cc0:cc1] & (a != NODATA) & (zz != NODATA)
    if gia.any():
        diffmax = max(diffmax, float(np.abs(zz[gia] - a[gia]).max()))
    nuovo = (zz == NODATA) & (a != NODATA)
    zz[nuovo] = a[nuovo]
    dentro[rr0:rr1, cc0:cc1] = True
    print('finestra di origine', k, flush=True)
print('differenza massima nelle sovrapposizioni (m):', diffmax, flush=True)
del dentro

# 2) incisione del reticolo di riferimento (stessa regola delle finestre)
R = gpd.read_file(ret).to_crs(32633)
R = R.cx[xmin:xmax, ymin:ymax]
m = rasterize(((g, 1) for g in R.geometry), out_shape=(H, W), transform=T, all_touched=True, dtype='uint8')
v = (m == 1) & (z != NODATA)
z[v] -= np.float32(BRUCIA_M)
del m, v
# arrotondamento a 2 decimali come negli .asc
ok = z != NODATA
z[ok] = np.round(z[ok], 2)
del ok

# 3) controllo: ogni porzione deve coincidere con la finestra verificata
for w in fin:
    with rasterio.open(os.path.join(dem_dir, f"f{w['origine']:03d}_dem_ibrido.tif")) as s:
        win = from_bounds(*w['bounds'], transform=s.transform).round_offsets().round_lengths()
        a = s.read(1, window=win)
        Tw = s.window_transform(win)
    sel = R.cx[Tw.c:Tw.c + a.shape[1] * C5, Tw.f - a.shape[0] * C5:Tw.f]
    if len(sel):
        mm = rasterize(((g, 1) for g in sel.geometry), out_shape=a.shape, transform=Tw,
                       all_touched=True, dtype='uint8').astype(bool)
        a = np.where(mm & (a != NODATA), a - BRUCIA_M, a).astype(np.float32)
    a = np.where(a != NODATA, np.round(a, 2), a)
    c0 = int(round((Tw.c - xmin) / C5))
    r0 = int(round((ymax - Tw.f) / C5))
    b = z[r0:r0 + a.shape[0], c0:c0 + a.shape[1]]
    d = np.abs(b.astype(np.float64) - a.astype(np.float64))
    if b.shape != a.shape or d.max() > 0.006:
        raise SystemExit(f"porzione {w['k']}: il DEM unico non coincide (diff max {d.max()})")
print('controllo porzioni: tutte coincidenti', flush=True)

# quote in centimetri interi (scala 0,01) e compressione ZSTD: stessa precisione, 383 MB
ok = z != NODATA
zi = np.full(z.shape, -999999, np.int32)
zi[ok] = np.rint(z[ok].astype(np.float64) * 100).astype(np.int32)
del z, ok
with rasterio.open(os.path.join(out, 'dem5m_unico.tif'), 'w', driver='GTiff', height=H, width=W, count=1,
                   dtype='int32', crs=crs, transform=T, nodata=-999999, compress='zstd', predictor=2,
                   zstd_level=22, tiled=True, blockxsize=512, blockysize=512, BIGTIFF='YES') as d:
    d.write(zi, 1)
    d.scales = (0.01,)
    d.units = ('m',)
del zi

# 4) CN sulla stessa griglia
cn_files = sorted(glob.glob(os.path.join(cn_dir, '**', '*.tif'), recursive=True))
mm, _ = merge(cn_files, bounds=(xmin, ymin, xmax, ymax), res=C5, nodata=0)
cn = mm[0][:H, :W]
del mm
cnf = np.where(cn > 0, cn.astype(np.float32), np.float32(np.nan))
del cn
# controllo: ogni porzione deve coincidere con il CN della finestra verificata
for w in fin:
    with rasterio.open(os.path.join(csv_dir, f"finestra_{w['k']:02d}_cn5m.tif")) as s:
        a = s.read(1)
        c0 = int(round((s.transform.c - xmin) / C5))
        r0 = int(round((ymax - s.transform.f) / C5))
    b = cnf[r0:r0 + a.shape[0], c0:c0 + a.shape[1]]
    if b.shape != a.shape or not np.array_equal(a, b, equal_nan=True):
        raise SystemExit(f"porzione {w['k']}: il CN unico non coincide")
print('controllo CN: tutte le porzioni coincidenti', flush=True)
with rasterio.open(os.path.join(out, 'cn5m_unico.tif'), 'w', driver='GTiff', height=H, width=W, count=1,
                   dtype='float32', crs=crs, transform=T, nodata=np.nan, compress='deflate', predictor=3,
                   tiled=True, blockxsize=512, blockysize=512, BIGTIFF='YES') as d:
    d.write(cnf, 1)
del cnf

# 5) CSV unico: coordinate dai CSV delle finestre (gia' corrette) + porzione
righe = []
for w in fin:
    nome = f"porzione_{w['k']:02d}"
    p = pd.read_csv(os.path.join(csv_dir, f"finestra_{w['k']:02d}_ponti.csv"))
    p['porzione'] = nome
    # limiti esatti della porzione sulla griglia (stessa regola di input_codice_utente.py)
    with rasterio.open(os.path.join(dem_dir, f"f{w['origine']:03d}_dem_ibrido.tif")) as s:
        win = from_bounds(*w['bounds'], transform=s.transform).round_offsets().round_lengths()
        Tw = s.window_transform(win)
    p['xmin'], p['ymax'] = round(Tw.c, 4), round(Tw.f, 4)
    p['xmax'], p['ymin'] = round(Tw.c + win.width * C5, 4), round(Tw.f - win.height * C5, 4)
    righe.append(p)
P = pd.concat(righe).sort_values('id')
assert P.id.is_unique and len(P) == 212
P.to_csv(os.path.join(out, 'ponti.csv'), index=False)
print('fatto', flush=True)
