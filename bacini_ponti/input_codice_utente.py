"""
Prepara gli input per pysheds_bridges.py (codice dell'utente) finestra per finestra.

Per ogni finestra del calcolo finale (finestre.json):
  - DEM 5 m ibrido con reticolo di riferimento inciso di BRUCIA_M (.asc, EPSG:32633, nodata -9999)
    + .prj; e' lo stesso DEM usato per i 168/207;
  - Curve Number sulla stessa griglia (.tif float32, NaN fuori copertura e dove CN = 0),
    cosi' np.nanmean del codice esclude le celle senza CN;
  - CSV dei ponti della finestra (id, X = longitudine, Y = latitudine, WGS84) con le
    coordinate delle sezioni di chiusura finali (layer sezioni_chiusura).

Uso: python input_codice_utente.py <run5/finestre (dem_ibrido non inciso)> <finestre.json o finestre_codice.json>
        <reticolo_tagliato.shp> <cartella_cn5> <risultati_5m.gpkg> <out_dir>
Variabili: SOLO_FINESTRA=k,k,...  BRUCIA_M (default 5)  SOLO_CSV=1 (riscrive solo i CSV)

Nel CSV ogni sezione e' spostata di 1,25 m in x e in y verso l'angolo in alto a sinistra
della sua cella: snap_to_mask di pysheds misura la distanza dagli angoli in alto a sinistra
delle celle, e un punto al centro esatto sarebbe equidistante da 4 celle.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.merge import merge
from rasterio.windows import from_bounds

dem_dir, fj, ret, cn_dir, rgpkg, out = sys.argv[1:7]
BRUCIA_M = float(os.environ.get('BRUCIA_M', '5'))
solo = os.environ.get('SOLO_FINESTRA')
solo = {int(v) for v in solo.split(',')} if solo else None
SOLO_CSV = os.environ.get('SOLO_CSV') == '1'
NODATA = -9999.0
C5 = 5.0
OFFSET_M = 1.25

fin = json.load(open(fj))['finestre']
R = gpd.read_file(ret).to_crs(32633)
sez = gpd.read_file(rgpkg, layer='sezioni_chiusura').set_index('ID')
sez84 = gpd.GeoSeries(gpd.points_from_xy(sez.geometry.x - OFFSET_M, sez.geometry.y + OFFSET_M),
                      index=sez.index, crs=32633).to_crs(4326)
cn_files = sorted(glob.glob(os.path.join(cn_dir, '**', '*.tif'), recursive=True))
cn_idx = [(f, rasterio.open(f).bounds) for f in cn_files]
os.makedirs(out, exist_ok=True)
righe = []
for w in fin:
    k = w['k']
    if solo is not None and k not in solo:
        continue
    nome = f'finestra_{k:02d}'
    ids = sorted(int(i) for i in w['ponti'])
    if SOLO_CSV:
        p = sez84.loc[ids]
        pd.DataFrame({'id': ids, 'X': p.x.round(9).values, 'Y': p.y.round(9).values}).to_csv(
            os.path.join(out, f'{nome}_ponti.csv'), index=False)
        continue
    # finestre ritagliate (finestre_codice_utente.py): si legge dal DEM della finestra di origine
    o = w.get('origine', k)
    with rasterio.open(os.path.join(dem_dir, f'f{o:03d}_dem_ibrido.tif')) as s:
        if 'origine' in w:
            win = from_bounds(*w['bounds'], transform=s.transform).round_offsets().round_lengths()
            z = s.read(1, window=win)
            T = s.window_transform(win)
        else:
            z = s.read(1)
            T = s.transform
        crs = s.crs
    H, W = z.shape
    xmin, ymax = T.c, T.f
    xmax, ymin = xmin + W * C5, ymax - H * C5
    sel = R.cx[xmin:xmax, ymin:ymax]
    if len(sel):
        m = rasterize(((g, 1) for g in sel.geometry), out_shape=z.shape, transform=T,
                      all_touched=True, dtype='uint8').astype(bool)
        z = np.where(m & (z != NODATA), z - BRUCIA_M, z).astype(np.float32)
    prof = dict(driver='AAIGrid', height=H, width=W, count=1, dtype='float32', crs=crs,
                transform=T, nodata=NODATA)
    with rasterio.open(os.path.join(out, f'{nome}_dem5m.asc'), 'w', DECIMAL_PRECISION=2, **prof) as d:
        d.write(z, 1)
    del z
    with open(os.path.join(out, f'{nome}_dem5m.prj'), 'w') as f:
        f.write(crs.to_wkt())
    aux = os.path.join(out, f'{nome}_dem5m.asc.aux.xml')
    if os.path.exists(aux):
        os.remove(aux)

    cn = np.zeros((H, W), np.uint8)
    selc = [f for f, b in cn_idx if b.left < xmax and b.right > xmin and b.bottom < ymax and b.top > ymin]
    if selc:
        mm, _ = merge(selc, bounds=(xmin, ymin, xmax, ymax), res=C5, nodata=0)
        cn[:] = mm[0][:H, :W]
    cnf = np.where(cn > 0, cn.astype(np.float32), np.float32(np.nan))
    with rasterio.open(os.path.join(out, f'{nome}_cn5m.tif'), 'w', driver='GTiff', height=H, width=W, count=1,
                       dtype='float32', crs=crs, transform=T, nodata=np.nan, compress='deflate',
                       tiled=True, BIGTIFF='IF_SAFER') as d:
        d.write(cnf, 1)
    del cn, cnf

    p = sez84.loc[ids]
    df = pd.DataFrame({'id': ids, 'X': p.x.round(9).values, 'Y': p.y.round(9).values})
    df.to_csv(os.path.join(out, f'{nome}_ponti.csv'), index=False)
    righe.append({'Finestra': nome, 'Righe': H, 'Colonne': W, 'Celle (milioni)': round(H * W / 1e6, 1),
                  'Finestra di origine': o, 'N. ponti': len(ids), 'ID ponti': ' '.join(map(str, ids))})
    print(nome, H, W, len(ids), flush=True)

if solo is None and not SOLO_CSV:
    pd.DataFrame(righe).to_csv(os.path.join(out, 'elenco_finestre.csv'), index=False)
