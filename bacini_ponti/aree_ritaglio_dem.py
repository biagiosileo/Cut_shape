"""
Vettoriale per ritagliare un DEM a 5 m piu' esteso: zone in cui i bacini escono dal DEM unico
(o usano il DEM a 30 m), con margine.

  1 alto Agri (ponte 6): stima dell'ingombro del bacino del database (figura della scheda: circa
    E 557,5-630 km, N 4.443,4-4.483,4 km) a ovest di E 582 km, dove il DEM unico non ha dati,
    piu' 5 km di margine;
  2 ponte 164: parte del bacino fuori dalle tavole a 5 m (oggi a 30 m), piu' 2 km;
  3 ponte 113: parte del bacino fuori dalle tavole a 5 m (oggi a 30 m), piu' 1 km.
Layer di riferimento: copertura attuale del DEM unico (dati validi).

Uso: python aree_ritaglio_dem.py <dem5m_unico.tif> <copertura_dem5.gpkg> <cartella porzioni> <out_dir>
"""
import glob
import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
from rasterio.features import shapes

dem, cop5, cart, out = sys.argv[1:5]
os.makedirs(out, exist_ok=True)
cov5 = gpd.read_file(cop5).geometry[0]
bac = pd.concat([gpd.read_file(f) for f in glob.glob(os.path.join(cart, '*_bacini_afferenti.geojson'))])
bac['ID'] = bac.ID.astype(int)

righe = [{'id': 1, 'ponti': '6', 'motivo': 'alto Agri fuori dal DEM unico (bacino del database oltre E 582 km)',
          'geometry': shapely.box(557500, 4443400, 582000, 4483400).buffer(5000, join_style='mitre')}]
for k, (i, m) in enumerate([(164, 2000), (113, 1000)], start=2):
    fuori = bac[bac.ID == i].geometry.iloc[0].difference(cov5)
    righe.append({'id': k, 'ponti': str(i), 'motivo': 'parte del bacino fuori dalle tavole a 5 m (oggi DEM a 30 m)',
                  'geometry': shapely.box(*fuori.bounds).buffer(m, join_style='mitre')})
g = gpd.GeoDataFrame(righe, crs=32633)
g['area_km2'] = (g.area / 1e6).round(1)
g.to_file(os.path.join(out, 'aree_ritaglio_dem5m.shp'))
g.to_crs(4326).to_file(os.path.join(out, 'aree_ritaglio_dem5m.kml'), driver='KML')

with rasterio.open(dem) as d:
    f = 20
    a = d.read(1, out_shape=(d.height // f, d.width // f))
    t = d.transform * d.transform.scale(d.width / (d.width // f), d.height / (d.height // f))
    m = a != d.nodata
cop = shapely.unary_union([shapely.geometry.shape(s) for s, v in shapes(m.astype('uint8'), mask=m, transform=t)])
gpd.GeoDataFrame({'nome': ['copertura DEM unico attuale']}, geometry=[cop], crs=32633).to_file(
    os.path.join(out, 'copertura_dem_unico_attuale.shp'))
print(g.drop(columns='geometry').to_string())
print([round(v) for v in g.total_bounds])
