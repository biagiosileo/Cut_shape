"""DEM d'Italia a 1 km in EPSG:3035 (ETRS89-LAEA) da Copernicus GLO-90.

Uso:
    python make_dem_italia.py <cartella_tile_cop90> <limits_IT_regions.geojson> \
        <ne_10m_admin_0_countries.geojson> <cartella_output>

Dati:
- tile Copernicus DEM GLO-90: https://copernicus-dem-90m.s3.amazonaws.com/
- confini regionali ISTAT (generalizzati, openpolis/geojson-italy):
  https://raw.githubusercontent.com/openpolis/geojson-italy/master/geojson/limits_IT_regions.geojson
- Natural Earth 10m admin 0 (solo per San Marino, Vaticano e Stati confinanti):
  https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson

Passi:
1. mosaico dei tile Copernicus GLO-90 (3", EGM2008) in EPSG:4326; i tile mancanti
   (solo mare) e il mare nei tile valgono 0;
2. ricampionamento con media su griglia 1000 m allineata alla griglia di riferimento
   EEA (origine multipla di 1000 m), sia della quota sia della frazione di terra (z != 0);
   quota della cella = media delle sole celle di terra (sum(z)/n_terra);
3. maschera: cella tenuta se (frazione di terra nel DEM >= 0.5 oppure frazione di
   territorio ISTAT >= 0.5) e il centro cade in Italia
   (regioni ISTAT + San Marino + Vaticano) oppure entro 1,5 km dalla costa italiana
   ma fuori da altri Stati (per non perdere celle costiere per la generalizzazione
   dei confini; la linea di costa effettiva la dà il DEM);
   le isole che non hanno celle con terra >= 0.5 tengono la loro cella più terrestre
   se superano 0,05 km2; i buchi interni (lagune a quota 0) sono riempiti.
"""
import glob
import os
import sys

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import reproject
from scipy import ndimage

RES = 1000.0
NODATA = -9999.0
DST_CRS = "EPSG:3035"
COAST_BUFFER = 1500.0

tiles_dir, istat_path, ne_path, out_dir = sys.argv[1:5]
os.makedirs(out_dir, exist_ok=True)

# --- confini -----------------------------------------------------------------
world = gpd.read_file(ne_path).to_crs(DST_CRS)
regions = gpd.read_file(istat_path).to_crs(DST_CRS)
smr_vat = world[world.ADM0_A3.isin(["SMR", "VAT"])].union_all()
italy = regions.union_all().union(smr_vat)
coast_zone = italy.buffer(COAST_BUFFER)
others = world[~world.ADM0_A3.isin(["ITA", "SMR", "VAT"])]
others = others[others.intersects(coast_zone.buffer(50000))].union_all()

xmin, ymin, xmax, ymax = coast_zone.bounds
xmin, ymin = np.floor(xmin / RES) * RES, np.floor(ymin / RES) * RES
xmax, ymax = np.ceil(xmax / RES) * RES, np.ceil(ymax / RES) * RES
width, height = int((xmax - xmin) / RES), int((ymax - ymin) / RES)
dst_transform = from_origin(xmin, ymax, RES, RES)
print(f"griglia {width} x {height} celle, bounds {xmin, ymin, xmax, ymax}")

# --- mosaico (una sola lettura dei tile) --------------------------------------
files = sorted(glob.glob(os.path.join(tiles_dir, "*.tif")))
print(f"{len(files)} tile")
srcs = [rasterio.open(f) for f in files]
mosaic, src_transform = merge(srcs, nodata=0.0)  # zone senza tile = mare = 0
src_crs = srcs[0].crs
for s in srcs:
    s.close()
z = mosaic[0]
del mosaic
land = (z != 0).astype("float32")
print(f"mosaico {z.shape}")

# --- ricampionamento a 1 km ---------------------------------------------------
def to_grid(arr):
    out = np.zeros((height, width), "float32")
    reproject(arr, out, src_transform=src_transform, src_crs=src_crs,
              dst_transform=dst_transform, dst_crs=DST_CRS,
              resampling=Resampling.average, num_threads=4)
    return out

z_mean = to_grid(z)
del z
land_frac = to_grid(land)
del land

# quota: celle a maggioranza terra -> media delle sole celle di terra;
# celle a maggioranza acqua (lagune, laghi costieri) -> media areale (acqua = 0)
with np.errstate(invalid="ignore", divide="ignore"):
    elev = np.where(land_frac >= 0.5, z_mean / land_frac, z_mean)

# --- maschera ----------------------------------------------------------------
shape = (height, width)
in_italy = rasterize([(italy, 1)], out_shape=shape, transform=dst_transform, dtype="uint8")
in_coast = rasterize([(coast_zone, 1)], out_shape=shape, transform=dst_transform, dtype="uint8")
in_other = rasterize([(others, 1)], out_shape=shape, transform=dst_transform, dtype="uint8")
in_area = (in_italy == 1) | ((in_coast == 1) & (in_other == 0))

# frazione di cella coperta dal territorio ISTAT (rasterizzato a 100 m)
SUB = 10
fine = rasterize([(italy, 1)], out_shape=(height * SUB, width * SUB),
                 transform=from_origin(xmin, ymax, RES / SUB, RES / SUB), dtype="uint8")
istat_frac = fine.reshape(height, SUB, width, SUB).mean(axis=(1, 3))
del fine

# cella tenuta se è per almeno metà terra nel DEM, oppure per almeno metà territorio
# italiano secondo ISTAT (lagune separate dal mare da cordoni < 1 km, es. Varano)
keep = in_area & ((land_frac >= 0.5) | (istat_frac >= 0.5))

# isole minori: una terra emersa (componente connessa con land_frac > 0) che con la
# soglia 0.5 non avrebbe nessuna cella conserva almeno la sua cella "più terrestre",
# se la sua superficie totale è >= MIN_ISLAND km2 (filtra i disturbi sul mare).
MIN_ISLAND = 0.05
lab, n = ndimage.label((land_frac > 0) & in_area, structure=np.ones((3, 3)))
idx = np.arange(1, n + 1)
has_keep = ndimage.maximum(keep, lab, idx) > 0
area = ndimage.sum(land_frac, lab, idx)
best = ndimage.maximum_position(land_frac, lab, idx)
added = 0
for i in np.where(~has_keep & (area >= MIN_ISLAND))[0]:
    keep[best[i]] = True
    added += 1
print(f"isole minori recuperate: {added}")

# lagune/laghi costieri a quota 0 nel DEM (es. Lesina, Varano): i buchi interamente
# racchiusi da celle tenute e dentro il confine ISTAT vengono riempiti con la quota
# media della cella (acqua = 0). Prima una chiusura morfologica (3x3) chiude i varchi
# di 1-2 celle che a 1 km collegano le lagune al mare.
closed = ndimage.binary_closing(keep, structure=np.ones((3, 3)))
holes = ndimage.binary_fill_holes(closed) & ~keep & (in_italy == 1)
keep |= holes
print(f"celle di laguna/lago riempite: {int(holes.sum())}")
dem = np.where(keep, np.round(elev, 1), NODATA).astype("float32")

profile = dict(driver="GTiff", width=width, height=height, count=1, dtype="float32",
               crs=DST_CRS, transform=dst_transform, nodata=NODATA, compress="deflate",
               predictor=3, tiled=True, blockxsize=256, blockysize=256)
out_tif = os.path.join(out_dir, "dem_italia_1km_3035.tif")
with rasterio.open(out_tif, "w", **profile) as dst:
    dst.write(dem, 1)
    dst.set_band_description(1, "Quota media (m s.l.m., EGM2008)")
    dst.update_tags(
        SOURCE="Copernicus DEM GLO-90 (DSM), ricampionato a 1 km con media",
        MASK=("Regioni ISTAT (openpolis/geojson-italy) + San Marino e Vaticano (Natural Earth); "
              "linea di costa da Copernicus (frazione di terra >= 0.5)"),
        ATTRIBUTION=("produced using Copernicus WorldDEM-90 (c) DLR e.V. 2010-2014 and "
                     "(c) Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS "
                     "by the European Union and ESA; all rights reserved"),
    )
    dst.build_overviews([2, 4, 8], Resampling.average)
    dst.update_tags(ns="rio_overview", resampling="average")

v = dem[dem != NODATA]
print(f"scritto {out_tif}")
print(f"celle valide {v.size} (= {v.size} km2), min {v.min():.1f} m, max {v.max():.1f} m, media {v.mean():.1f} m")
