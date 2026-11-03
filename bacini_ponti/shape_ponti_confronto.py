"""
Shapefile per mostrare le differenze tra i ponti iniziali e quelli usati nell'analisi finale (DEM v4).

Scrive in <out_dir>:
  ponti_iniziali.shp     212 punti del ponti.csv iniziale
  ponti_analisi.shp      212 punti del ponti.csv dell'analisi in corso
  spostamenti.shp        segmento dal punto iniziale al punto finale, per i ponti spostati
Attributi comuni: ID (database 1-212), modificato (si/no), spost_m, porz_ini, porz_fin, soglia, motivo.
Tutti in EPSG:32633 (UTM 33N), come DEM e bacini.

Uso: python shape_ponti_confronto.py <ponti iniziale.csv> <ponti finale.csv> <modifiche_rispetto_a_ponti_originale.csv> <out_dir>
"""
import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point

ini_csv, fin_csv, mod_csv, out = sys.argv[1:5]
os.makedirs(out, exist_ok=True)
A = pd.read_csv(ini_csv).set_index('id')
B = pd.read_csv(fin_csv).set_index('id')
assert len(A) == len(B) == 212 and (A.index == B.index).all()

# motivi della prima revisione (porzioni, tracciato KML, soglia)
M = pd.read_csv(mod_csv).set_index('id')['motivo'].to_dict()
# modifiche successive (DEM v2/v3, relazioni di ispezione, proposte di revisione)
DOPO = {
    6: 'porzione_69 (bacino intero con il DEM esteso sull alto Agri)',
    105: 'sezione sul taglio del tombino',
    107: 'sezione che riproduce la relazione di ispezione',
    108: 'sezione che riproduce la relazione di ispezione',
    109: 'sezione che riproduce la relazione di ispezione',
    111: 'sezione della proposta di revisione (relazione)',
    196: 'sezione sul piccolo affluente confermato dalla relazione',
    113: 'porzione_70 (DEM v3: costa riempita)',
    155: 'porzione_71 (DEM v3: costa riempita)',
}
for i, t in DOPO.items():
    M[i] = (M[i] + '; ' if i in M else '') + t

geo = gpd.GeoSeries.from_xy(A.X, A.Y, crs=4326).to_crs(32633)
gfi = gpd.GeoSeries.from_xy(B.X, B.Y, crs=4326).to_crs(32633)
geo.index = gfi.index = A.index
d = pd.Series(np.hypot(geo.x - gfi.x, geo.y - gfi.y), index=A.index)
cambiato = (d > 0.01) | (A.porzione != B.porzione) | B.soglia.notna()

att = pd.DataFrame({
    'ID': A.index,
    'modificato': np.where(cambiato, 'si', 'no'),
    'spost_m': d.round(1).values,
    'porz_ini': A.porzione.values,
    'porz_fin': B.porzione.values,
    'soglia': B.soglia.values,
    'motivo': [M.get(i, '' if not cambiato[i] else 'vedi colonne') for i in A.index],
})
gpd.GeoDataFrame(att, geometry=geo.values, crs=32633).to_file(os.path.join(out, 'ponti_iniziali.shp'), encoding='utf-8')
gpd.GeoDataFrame(att, geometry=gfi.values, crs=32633).to_file(os.path.join(out, 'ponti_analisi.shp'), encoding='utf-8')
s = d > 0.01
lin = [LineString([geo[i], gfi[i]]) for i in A.index[s]]
gpd.GeoDataFrame(att[s.values].reset_index(drop=True), geometry=lin, crs=32633).to_file(
    os.path.join(out, 'spostamenti.shp'), encoding='utf-8')
att.to_csv(os.path.join(out, 'confronto_ponti.csv'), index=False)
print('modificati:', int(cambiato.sum()), '- spostati:', int(s.sum()))
print(att[cambiato.values].to_string(index=False))
