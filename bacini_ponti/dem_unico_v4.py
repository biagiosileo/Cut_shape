"""
DEM unico v4 (file nuovo): DEM unico v3 con il buco senza dato di circa 2 km2 (X 612654-614944, Y 4459268-4460143)
riempito con i valori della tavola DTM a 5 m dtm5m_bacino_06_parte5di7.tif (stessa griglia, cella per cella,
nessun ricampionamento). Scrive anche la patch corrispondente (patch_buco_Agri.tif) per esegui.py.

Uso: python dem_unico_v4.py <dem v3.tif> <tavola.tif> <out.tif> <patch.tif>
"""
import sys

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds

v3, tav, out, patch = sys.argv[1:5]
B = (612000, 4458700, 615600, 4460700)  # rettangolo che contiene il buco con un margine
src = rasterio.open(v3)
prof = src.profile
prof.update(BIGTIFF='IF_SAFER', predictor=2, zstd_level=22)
with rasterio.open(out, 'w', **prof) as dst:
    dst.scales, dst.offsets = src.scales, src.offsets
    for r0 in range(0, src.height, 1024):
        w = Window(0, r0, src.width, min(1024, src.height - r0))
        dst.write(src.read(1, window=w), 1, window=w)
    w = from_bounds(*B, transform=src.transform).round_offsets().round_lengths()
    a = src.read(1, window=w)
    with rasterio.open(tav) as t:
        z = t.read(1, window=from_bounds(*B, transform=t.transform).round_offsets().round_lengths())
        ok = (a == src.nodata) & (z != t.nodata) & (z > -9000)
    a[ok] = np.rint(z[ok] * 100).astype(np.int32)
    dst.write(a, 1, window=w)
    print(f'celle riempite: {ok.sum()} ({ok.sum() * 25 / 1e6:.3f} km2)')
pp = prof.copy()
pp.update(width=a.shape[1], height=a.shape[0], transform=src.window_transform(w), tiled=False)
pp.pop('blockxsize', None); pp.pop('blockysize', None)
with rasterio.open(patch, 'w', **pp) as p:
    p.scales, p.offsets = src.scales, src.offsets
    p.write(a, 1)
print('scritto', out, patch)
