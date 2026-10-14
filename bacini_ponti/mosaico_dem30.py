"""Unisce i ritagli dem30_bacino_NN.tif (stessa griglia a 30 m) in un unico
mosaico, cosi' che un bacino che esce dal ritaglio del proprio gruppo possa
proseguire nei ritagli adiacenti. I file di ingresso sono solo letti.

Uso: python mosaico_dem30.py <cartella_con_i_tif> <mosaico_out.tif>
"""
import glob
import os
import sys

import numpy as np
import rasterio
from rasterio.transform import Affine

src_dir, out_path = sys.argv[1], sys.argv[2]
files = sorted(glob.glob(os.path.join(src_dir, '**', 'dem30_bacino_*.tif'), recursive=True))
if not files:
    sys.exit(f"Nessun dem30_bacino_*.tif in {src_dir}")

srcs = [rasterio.open(f) for f in files]
t0 = srcs[0].transform
rx, ry = t0.a, t0.e
offs = []
for s in srcs:
    dc = (s.transform.c - t0.c) / rx
    dr = (s.transform.f - t0.f) / ry
    if abs(dc - round(dc)) > 1e-3 or abs(dr - round(dr)) > 1e-3 or s.crs != srcs[0].crs:
        sys.exit(f"{s.name}: griglia non allineata")
    offs.append((int(round(dr)), int(round(dc))))
r0 = min(o[0] for o in offs); c0 = min(o[1] for o in offs)
r1 = max(o[0] + s.height for o, s in zip(offs, srcs))
c1 = max(o[1] + s.width for o, s in zip(offs, srcs))
nodata = -9999.0
mos = np.full((r1 - r0, c1 - c0), nodata, dtype=np.float32)
for (dr, dc), s in zip(offs, srcs):
    a = s.read(1)
    v = a != s.nodata
    sub = mos[dr - r0:dr - r0 + s.height, dc - c0:dc - c0 + s.width]
    sub[v] = a[v]
transform = Affine(rx, 0, t0.c + c0 * rx, 0, ry, t0.f + r0 * ry)
prof = dict(driver='GTiff', height=mos.shape[0], width=mos.shape[1], count=1,
            dtype='float32', crs=srcs[0].crs, transform=transform, nodata=nodata,
            compress='deflate', tiled=True)
if os.path.abspath(out_path).startswith(os.path.abspath(src_dir) + os.sep):
    sys.exit("Il mosaico non va scritto dentro la cartella dei dati di ingresso")
with rasterio.open(out_path, 'w', **prof) as dst:
    dst.write(mos, 1)
v = mos != nodata
print(f"Mosaico {mos.shape}, area valida {v.sum() * abs(rx * ry) / 1e6:.0f} km2 -> {out_path}")
