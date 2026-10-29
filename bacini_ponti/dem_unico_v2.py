"""
DEM unico v2 (file nuovo, il DEM unico originale non cambia):
  1) alto Agri (ponte 6): le celle senza dato dentro la zona 1 del vettoriale di ritaglio vengono riempite con
     il DEM Copernicus GLO-30 (pubblico, 30 m, quote ellissoidiche EGM2008, modello di superficie), riproiettato
     sulla griglia a 5 m (bilineare) e corretto della differenza mediana rispetto al DEM a 5 m nella fascia di
     sovrapposizione; poi il reticolo di riferimento viene inciso di BRUCIA_M nelle sole celle riempite (stessa
     regola del DEM unico);
  2) tombini: le celle toccate dalle linee "taglio tombino" (prova_tombino.gpkg, ID indicati) vengono portate
     alla quota minima lungo il taglio meno BRUCIA_M.
Stessa griglia, tipo (int32 in cm, scala 0,01), nodata e compressione del DEM unico.

Uso: python dem_unico_v2.py <dem5m_unico.tif> <aree_ritaglio_dem5m.shp> <reticolo_tagliato.shp>
        <prova_tombino.gpkg> <out.tif> <copernicus_1.tif> [<copernicus_2.tif> ...] --tombini 105 [...]
"""
import sys

import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.merge import merge
from rasterio.warp import Resampling, reproject
from rasterio.windows import Window, from_bounds

arg = sys.argv[1:]
tomb = [int(v) for v in arg[arg.index('--tombini') + 1:]] if '--tombini' in arg else []
arg = arg[:arg.index('--tombini')] if '--tombini' in arg else arg
dem_path, zone_shp, ret_shp, tomb_gpkg, out = arg[:5]
cop = arg[5:]
BRUCIA_M = 5.0
FASCIA_M = 2000.0

src = rasterio.open(dem_path)
prof = src.profile
prof.update(BIGTIFF='IF_SAFER', predictor=2, zstd_level=22)
dst = rasterio.open(out, 'w', **prof)
dst.scales, dst.offsets = src.scales, src.offsets  # quote in cm con scala 0,01, come il DEM unico
for r0 in range(0, src.height, 1024):
    w = Window(0, r0, src.width, min(1024, src.height - r0))
    dst.write(src.read(1, window=w), 1, window=w)
print('copia del DEM unico fatta', flush=True)

# --- 1) alto Agri ---
zona = gpd.read_file(zone_shp).to_crs(32633)
zona = zona[zona.id == 1].geometry.iloc[0]
w = from_bounds(*zona.bounds, transform=src.transform).round_offsets().round_lengths()
w = w.intersection(Window(0, 0, src.width, src.height))
T = src.window_transform(w)
a = src.read(1, window=w)
nd = a == src.nodata
z5 = a.astype(np.float64) * 0.01
mosaic, mt = merge([rasterio.open(f) for f in cop])
zc = np.full(a.shape, np.nan, np.float32)
reproject(mosaic[0], zc, src_transform=mt, src_crs='EPSG:4326', dst_transform=T, dst_crs=src.crs,
          resampling=Resampling.bilinear, src_nodata=None, dst_nodata=np.nan)
dentro = rasterize([(zona, 1)], out_shape=a.shape, transform=T).astype(bool)
# fascia di sovrapposizione: celle a 5 m entro FASCIA_M dalle celle senza dato della zona
from scipy import ndimage
vuoto = nd & dentro
fascia = ndimage.binary_dilation(vuoto, iterations=int(FASCIA_M / 5)) & ~nd & np.isfinite(zc)
diff = zc[fascia] - z5[fascia]
corr = float(np.median(diff))
print(f'celle da riempire: {vuoto.sum()} ({vuoto.sum() * 25 / 1e6:.0f} km2); differenza Copernicus - DEM 5 m nella fascia: '
      f'mediana {corr:.2f} m, 10-90% {np.percentile(diff, 10):.2f} / {np.percentile(diff, 90):.2f} m', flush=True)
riemp = vuoto & np.isfinite(zc)
z = z5.copy()
z[riemp] = zc[riemp] - corr
R = gpd.read_file(ret_shp).to_crs(32633)
R = R.cx[T.c:T.c + a.shape[1] * 5, T.f - a.shape[0] * 5:T.f]
inc = rasterize(((g, 1) for g in R.geometry), out_shape=a.shape, transform=T, all_touched=True).astype(bool) & riemp
z[inc] -= BRUCIA_M
b = a.copy()
b[riemp] = np.rint(z[riemp] * 100).astype(np.int32)
dst.write(b, 1, window=w)
print(f'riempite {riemp.sum()} celle, incise {inc.sum()} celle del reticolo di riferimento', flush=True)

# --- 2) tombini ---
if tomb:
    L = gpd.read_file(tomb_gpkg, layer='linee')
    L = L[(L.tipo == 'taglio tombino') & L.ID.isin(tomb)]
    for _, r in L.iterrows():
        w2 = from_bounds(*r.geometry.buffer(20).bounds, transform=src.transform).round_offsets().round_lengths()
        T2 = src.window_transform(w2)
        a2 = src.read(1, window=w2)
        m = rasterize([(r.geometry, 1)], out_shape=a2.shape, transform=T2, all_touched=True).astype(bool) & (a2 != src.nodata)
        a2[m] = a2[m].min() - int(BRUCIA_M * 100)
        dst.write(a2, 1, window=w2)
        print(f'tombino ponte {int(r.ID)}: {m.sum()} celle portate a {a2[m].min() / 100:.2f} m', flush=True)
dst.close()
print('scritto', out)
