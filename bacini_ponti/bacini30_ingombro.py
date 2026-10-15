"""
Ingombro dei bacini sul DEM a 30 m, usato per dimensionare le finestre del
calcolo a 5 m (dem5_finestre.py). Per ogni ponte: aggancio alla cella di
reticolo (area >= 0,25 km2) piu' vicina al punto di input, bacino D8 su DEM
riempito (Whitebox), area e rettangolo di ingombro.

Uso: python bacini30_ingombro.py <dem30_mosaico.tif> <controllo_coordinate.gpkg> <out.csv>
"""
import os
import sys

import numpy as np
np.in1d = np.isin
import pandas as pd
import geopandas as gpd
import whitebox_workflows as wb
from pysheds.grid import Grid

SOGLIA_KM2 = 0.25
dem_p, gpkg, out = sys.argv[1:4]
tmp = out + '.fill.tif'
wbe = wb.WbEnvironment()
wbe.verbose = False
wbe.write_raster(wbe.hydrology.fill_depressions(dem=wbe.read_raster(dem_p)), tmp)
g = Grid.from_raster(tmp)
z = g.read_raster(tmp)
fd = g.flowdir(z)
T = g.affine
cell = abs(T.a * T.e) / 1e6
acc = np.asarray(g.accumulation(fd), float) * cell
pts = gpd.read_file(gpkg, layer='input_script').set_index('ID').geometry
inv = ~T
nr, nc = acc.shape
righe = []
for i, p in pts.items():
    c0, r0 = inv * (p.x, p.y)
    r0, c0 = int(r0), int(c0)
    n = 4
    while True:
        R, C = np.mgrid[max(r0 - n, 0):min(r0 + n + 1, nr), max(c0 - n, 0):min(c0 + n + 1, nc)]
        X, Y = T * (C + .5, R + .5)
        d = np.hypot(X - p.x, Y - p.y)
        m = acc[R, C] >= SOGLIA_KM2
        if m.any() or n > 4000:
            break
        n *= 2
    k = np.argmin(np.where(m, d, np.inf))
    b = np.asarray(g.catchment(x=C.flat[k], y=R.flat[k], fdir=fd, xytype='index'), bool)
    rr, cc = np.nonzero(b)
    righe.append(dict(ID=int(i), A30=b.sum() * cell,
                      xmin=T.c + cc.min() * T.a, xmax=T.c + (cc.max() + 1) * T.a,
                      ymin=T.f + (rr.max() + 1) * T.e, ymax=T.f + rr.min() * T.e))
pd.DataFrame(righe).sort_values('ID').to_csv(out, index=False)
os.remove(tmp)
print('salvato', out, len(righe))
