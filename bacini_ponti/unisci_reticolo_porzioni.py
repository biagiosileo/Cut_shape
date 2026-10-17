"""
Riunisce il reticolo estratto da pysheds_bridges_5m.py porzione per porzione
(porzioni/porzione_NN_reticolo_idrografico.geojson) in un GeoPackage per QGIS.

Layer:
  reticolo_unito        tutti i rami dissolti: i tratti identici nelle porzioni che si
                        sovrappongono compaiono una volta sola; rami spezzati alle confluenze
  reticolo_per_porzione i rami cosi' come escono da ogni porzione (campo porzione)
  porzioni              rettangoli delle porzioni (campo porzione, ponti)
  sezioni_ponti         punti di chiusura dei ponti dal CSV (campo id = ID del database)
Le geometrie sono semplificate con tolleranza 1 cm: si tolgono solo i vertici allineati
(una linea D8 ha un vertice per cella), la forma non cambia.

Uso: python unisci_reticolo_porzioni.py <cartella porzioni> <ponti.csv> <out.gpkg>
"""
import glob
import json
import os
import sys

import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import box, shape

cart, csv, out = sys.argv[1:4]
righe = []
for f in sorted(glob.glob(os.path.join(cart, 'porzione_*_reticolo_idrografico.geojson'))):
    nome = os.path.basename(f).replace('_reticolo_idrografico.geojson', '')
    gj = json.load(open(f))
    geoms = [shape(ft['geometry']) for ft in gj['features']]
    righe.append(gpd.GeoDataFrame({'porzione': [nome] * len(geoms)}, geometry=geoms, crs=32633))
    print(nome, len(geoms), 'rami', flush=True)
R = pd.concat(righe, ignore_index=True)
R['geometry'] = shapely.simplify(R.geometry.values, 0.01)
R = R[~R.geometry.is_empty & (R.geometry.length > 0)]
R['lung_m'] = R.geometry.length.round(1)
R.to_file(out, layer='reticolo_per_porzione', driver='GPKG')

U = shapely.line_merge(shapely.unary_union(R.geometry.values))
U = gpd.GeoDataFrame(geometry=[U], crs=32633).explode(index_parts=False).reset_index(drop=True)
U['geometry'] = shapely.simplify(U.geometry.values, 0.01)
U['lung_m'] = U.geometry.length.round(1)
U.to_file(out, layer='reticolo_unito', driver='GPKG')

P = pd.read_csv(csv)
por = P.groupby('porzione').agg(xmin=('xmin', 'first'), ymin=('ymin', 'first'), xmax=('xmax', 'first'),
                                ymax=('ymax', 'first'), ponti=('id', lambda s: ' '.join(map(str, sorted(s)))))
gpd.GeoDataFrame(por.reset_index()[['porzione', 'ponti']],
                 geometry=[box(r.xmin, r.ymin, r.xmax, r.ymax) for r in por.itertuples()],
                 crs=32633).to_file(out, layer='porzioni', driver='GPKG')
gpd.GeoDataFrame(P[['id', 'porzione']], geometry=gpd.points_from_xy(P.X, P.Y), crs=4326).to_crs(32633).to_file(
    out, layer='sezioni_ponti', driver='GPKG')
print('reticolo_per_porzione', len(R), 'rami,', round(R.length.sum() / 1000), 'km')
print('reticolo_unito', len(U), 'tratti,', round(U.length.sum() / 1000), 'km')
