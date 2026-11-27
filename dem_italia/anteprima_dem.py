"""Controlli e anteprima (rilievo ombreggiato) del DEM d'Italia a 1 km.

Uso: python anteprima_dem.py dem_italia_1km_3035.tif anteprima_dem_italia.png
"""
import sys

import matplotlib
import numpy as np
import rasterio
from matplotlib.colors import LightSource
from pyproj import Transformer

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

src, out = sys.argv[1:3]
with rasterio.open(src) as r:
    a = r.read(1, masked=True)
    T, ext = r.transform, r.bounds
    print(r.crs, r.res, f"{r.width} x {r.height}", "nodata", r.nodata)

v = a.compressed()
print(f"celle valide {v.size} km2, min {v.min():.1f}, max {v.max():.1f}, media {v.mean():.1f} m")

# isole minori: celle valide in un intorno 7x7 km
to3035 = Transformer.from_crs(4326, 3035, always_xy=True)
isole = {"Pantelleria": (11.95, 36.78), "Lampedusa": (12.58, 35.51), "Linosa": (12.87, 35.865),
         "Lampione": (12.32, 35.55), "Ustica": (13.18, 38.71), "Tremiti": (15.49, 42.115),
         "Ventotene": (13.43, 40.80), "Ponza": (12.96, 40.90), "Palmarola": (12.86, 40.94),
         "Gorgona": (9.90, 43.43), "Capraia": (9.83, 43.05), "Giglio": (10.90, 42.36),
         "Alicudi": (14.35, 38.54), "Marettimo": (12.06, 37.97)}
for nome, (lon, lat) in isole.items():
    c, rw = ~T * to3035.transform(lon, lat)
    c, rw = int(c), int(rw)
    print(f"  {nome:12s} celle: {a[max(rw - 3, 0):rw + 4, max(c - 3, 0):c + 4].count()}")

z = a.filled(np.nan)
ls = LightSource(azdeg=315, altdeg=45)
rgb = ls.shade(np.nan_to_num(z, nan=0), cmap=plt.cm.terrain, vmin=-200, vmax=3500,
               blend_mode="soft", vert_exag=0.05, dx=1000, dy=1000)
rgb[np.isnan(z)] = 1
fig, ax = plt.subplots(figsize=(8, 10))
ax.imshow(rgb, extent=(ext.left, ext.right, ext.bottom, ext.top))
sm = plt.cm.ScalarMappable(cmap=plt.cm.terrain, norm=plt.Normalize(-200, 3500))
fig.colorbar(sm, ax=ax, shrink=0.5, label="Quota (m s.l.m.)")
ax.set_title("DEM d'Italia 1 km – EPSG:3035 (ETRS89-LAEA)")
ax.ticklabel_format(style="plain")
ax.tick_params(labelsize=7)
ax.text(0.01, 0.01, "Copernicus DEM GLO-90 (© DLR e.V., © Airbus DS; UE/ESA) – confini ISTAT",
        transform=ax.transAxes, fontsize=6)
fig.savefig(out, dpi=150, bbox_inches="tight")
print("anteprima:", out)
