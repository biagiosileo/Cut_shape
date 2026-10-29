"""
Crea dem5m_unico_v2.tif dal tuo dem5m_unico.tif applicando le patch di questa cartella
(alto Agri riempito con Copernicus GLO-30 per il ponte 6, tombino del ponte 105).
Il dem5m_unico.tif originale NON viene modificato.

Uso (dalla cartella con dem5m_unico.tif):
    python applica_patch_dem.py dem5m_unico.tif dem5m_unico_v2.tif patch_alto_Agri.tif patch_tombino_105.tif
"""
import sys

import rasterio
from rasterio.windows import Window, from_bounds

src_path, out_path, *patch = sys.argv[1:]
with rasterio.open(src_path) as src:
    prof = src.profile
    prof.update(BIGTIFF='IF_SAFER', predictor=2, zstd_level=22)
    with rasterio.open(out_path, 'w', **prof) as dst:
        dst.scales, dst.offsets = src.scales, src.offsets
        for r0 in range(0, src.height, 1024):
            w = Window(0, r0, src.width, min(1024, src.height - r0))
            dst.write(src.read(1, window=w), 1, window=w)
        for p in patch:
            with rasterio.open(p) as pt:
                assert pt.res == src.res and pt.crs == src.crs, 'patch non allineata'
                w = from_bounds(*pt.bounds, transform=src.transform).round_offsets().round_lengths()
                dst.write(pt.read(1), 1, window=w)
                print('applicata', p)
print('scritto', out_path)
