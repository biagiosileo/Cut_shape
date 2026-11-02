"""
DEM unico v3 (file nuovo): DEM unico v2 piu'
  1) riempimento delle celle senza dato nelle zone indicate (rettangoli UTM): prima con le tavole DTM a 5 m
     fornite (stessa griglia, valore della cella), poi con il DEM Copernicus GLO-30 riportato a 5 m (bilineare)
     e corretto della differenza mediana con il DEM a 5 m nella fascia di sovrapposizione; il mare (Copernicus
     <= 0,5 m) resta senza dato; nelle celle riempite si incide il reticolo di riferimento di BRUCIA_M;
  2) tombino del ponte 198: le celle del taglio individuate dal breaching (tagli.gpkg) prendono la quota del
     DEM inciso dal breaching (br.tif).
Stessa griglia, tipo (int32 in cm, scala 0,01), nodata e compressione del DEM unico.

Uso: python dem_unico_v3.py <dem v2.tif> <cartella tavole 5 m> <reticolo_tagliato.shp> <tagli.gpkg> <br.tif>
        <out.tif> --zone xmin,ymin,xmax,ymax [...] --copernicus f1.tif [f2.tif ...]
"""
import glob
import os
import sys

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.merge import merge
from rasterio.warp import Resampling, reproject
from rasterio.windows import Window, from_bounds
from scipy import ndimage

arg = sys.argv[1:]
zi, ci = arg.index('--zone'), arg.index('--copernicus')
zone = [[float(v) for v in z.split(',')] for z in arg[zi + 1:ci]]
cop = arg[ci + 1:]
dem_path, tav_dir, ret_shp, tagli, br_tif, out = arg[:6]
BRUCIA_M = 5.0
FASCIA_M = 2000.0

src = rasterio.open(dem_path)
prof = src.profile
prof.update(BIGTIFF='IF_SAFER', predictor=2, zstd_level=22)
dst = rasterio.open(out, 'w', **prof)
dst.scales, dst.offsets = src.scales, src.offsets
for r0 in range(0, src.height, 1024):
    w = Window(0, r0, src.width, min(1024, src.height - r0))
    dst.write(src.read(1, window=w), 1, window=w)
print('copia del DEM v2 fatta', flush=True)
tavole = sorted(glob.glob(os.path.join(tav_dir, '*.tif')))
mosaic, mt = merge([rasterio.open(f) for f in cop])
R = gpd.read_file(ret_shp).to_crs(32633)

for b in zone:
    w = from_bounds(*b, transform=src.transform).round_offsets().round_lengths().intersection(
        Window(0, 0, src.width, src.height))
    T = src.window_transform(w)
    a = dst.read(1, window=w)
    nd = a == src.nodata
    z = np.where(nd, np.nan, a * 0.01)
    da_tav = np.zeros(a.shape, bool)
    for f in tavole:
        with rasterio.open(f) as t:
            tb = t.bounds
            if tb.right < b[0] or tb.left > b[2] or tb.top < b[1] or tb.bottom > b[3]:
                continue
            zt = np.full(a.shape, np.nan, np.float32)
            reproject(rasterio.band(t, 1), zt, dst_transform=T, dst_crs=src.crs, resampling=Resampling.nearest,
                      dst_nodata=np.nan, src_nodata=t.nodata)
        ok = np.isnan(z) & np.isfinite(zt) & (zt > -9000)
        z[ok] = zt[ok]
        da_tav |= ok
    zc = np.full(a.shape, np.nan, np.float32)
    reproject(mosaic[0], zc, src_transform=mt, src_crs='EPSG:4326', dst_transform=T, dst_crs=src.crs,
              resampling=Resampling.bilinear, dst_nodata=np.nan)
    vuoto = np.isnan(z) & np.isfinite(zc) & (zc > 0.5)
    fascia = ndimage.binary_dilation(vuoto, iterations=int(FASCIA_M / 5)) & np.isfinite(z) & np.isfinite(zc)
    corr = float(np.median(zc[fascia] - z[fascia])) if fascia.any() else 0.0
    z[vuoto] = zc[vuoto] - corr
    riemp = da_tav | vuoto
    sel = R.cx[T.c:T.c + a.shape[1] * 5, T.f - a.shape[0] * 5:T.f]
    if len(sel):
        inc = rasterize(((g, 1) for g in sel.geometry), out_shape=a.shape, transform=T, all_touched=True).astype(bool) & riemp
        z[inc] -= BRUCIA_M
    else:
        inc = np.zeros(a.shape, bool)
    a[riemp] = np.rint(z[riemp] * 100).astype(np.int32)
    dst.write(a, 1, window=w)
    print(f'zona {b}: dalle tavole 5 m {da_tav.sum() * 25 / 1e6:.1f} km2, dal Copernicus {vuoto.sum() * 25 / 1e6:.1f} km2 '
          f'(correzione {corr:.2f} m), reticolo inciso {inc.sum()} celle', flush=True)

with rasterio.open(br_tif) as br:
    w = from_bounds(*br.bounds, transform=src.transform).round_offsets().round_lengths()
    B = br.read(1)
    m = rasterize([(g, 1) for g in gpd.read_file(tagli).geometry], out_shape=B.shape, transform=br.transform).astype(bool)
    a = dst.read(1, window=w)
    a[m] = np.rint(B[m] * 100).astype(np.int32)
    dst.write(a, 1, window=w)
    print(f'tombino 198: {m.sum()} celle', flush=True)
dst.close()
print('scritto', out)
