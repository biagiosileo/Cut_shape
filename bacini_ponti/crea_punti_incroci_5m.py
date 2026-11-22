"""
Punti di calcolo sugli incroci tra il tracciato di ciascun ponte e il reticolo a 5 m del codice, per calcolare con
il codice invariato (pysheds_bridges_5m.py) l'area drenata da ogni corso d'acqua che passa sotto il ponte.

Tracciato: KML abbinato al ponte; se manca, linea inizio-fine del database (solo se piu' corta di 2 km).
Incroci: tratti del reticolo del codice che toccano il tracciato o distano meno di TOLL_M (il tracciato KML e'
disegnato a mano). Per ogni tratto si prende il vertice del reticolo piu' vicino al tracciato (i vertici sono gli
angoli in alto a sinistra delle celle); se non c'e' nessun tratto entro TOLL_M si cerca entro TOLL_LARGA_M e il punto di calcolo e' posto 1.25 m a Est e 1.25 m a Sud del vertice,
come per i ponti: snap_to_mask aggancia la stessa cella. Vertici a meno di 1 cella l'uno dall'altro = stesso
incrocio. Porzione e limiti: quelli del ponte; soglia: nessuna (i punti sono gia' sul reticolo a 0.1 km2).

ID dei punti: ID ponte x 100 + numero dell'incrocio (es. 10703 = ponte 107, incrocio 3).

Uso: python crea_punti_incroci_5m.py <reticolo_idrografico.geojson> <controllo_coordinate.gpkg> <ponti.csv>
        <out_dir>
"""
import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point

TOLL_M = 15.0
TOLL_LARGA_M = 50.0
OFFSET_M = 1.25

ret, gpkg, ponti, out = sys.argv[1:5]
os.makedirs(out, exist_ok=True)
R = gpd.read_file(ret).to_crs(32633)
sidx = R.sindex
k = gpd.read_file(gpkg, layer='kml_abbinato').set_index('ID')
kt = gpd.read_file(gpkg, layer='kml_tracciati').to_crs(32633).drop_duplicates('nome').set_index('nome').geometry
dbl = gpd.read_file(gpkg, layer='db_attraversamento_inizio_fine').to_crs(32633).set_index('ID').geometry
P = pd.read_csv(ponti).set_index('id')
to_utm = Transformer.from_crs('EPSG:4326', 'EPSG:32633', always_xy=True)
to_geo = Transformer.from_crs('EPSG:32633', 'EPSG:4326', always_xy=True)

righe, punti, tracc = [], [], []
for i in P.index:
    x, y = to_utm.transform(P.X[i], P.Y[i])
    q = Point(x, y)
    nome = k.KML_nome.get(i)
    t, fonte = (kt.get(nome), 'KML') if isinstance(nome, str) else (None, '')
    if t is None or t.length == 0:
        t, fonte = dbl.get(i), 'database inizio-fine'
        if t is None or t.length == 0 or t.length > 2000:
            righe.append({'ID': i, 'Tracciato': 'assente', 'N_incroci': 0}); continue
    tracc.append({'ID': i, 'Tracciato': fonte, 'Lungh_m': round(t.length), 'geometry': t})
    vert = []
    for toll in (TOLL_M, TOLL_LARGA_M):  # se il tracciato non tocca il reticolo entro 15 m, si allarga a 50 m
        for geo in R.geometry.iloc[list(sidx.query(t.buffer(toll), predicate='intersects'))]:
            c = np.array(geo.coords)
            d = np.array([t.distance(Point(v)) for v in c])
            if d.min() <= toll:
                vert.append((tuple(c[d.argmin()]), float(d.min())))
        if vert:
            break
    scelti = []
    for v, d in sorted(vert, key=lambda a: a[1]):
        if all(np.hypot(v[0] - s[0][0], v[1] - s[0][1]) > 5.1 for s in scelti):
            scelti.append((v, d))
    scelti.sort(key=lambda a: Point(a[0]).distance(q))
    for n, (v, d) in enumerate(scelti, 1):
        xp, yp = v[0] + OFFSET_M, v[1] - OFFSET_M
        lon, lat = to_geo.transform(xp, yp)
        punti.append({'id': i * 100 + n, 'X': round(lon, 10), 'Y': round(lat, 10), 'porzione': P.porzione[i],
                      'xmin': P.xmin[i], 'ymax': P.ymax[i], 'xmax': P.xmax[i], 'ymin': P.ymin[i], 'soglia': pd.NA,
                      'ID_ponte': i, 'Incrocio': n, 'Dist_tracciato_m': round(d, 1),
                      'Dist_punto_ponte_m': round(Point(xp, yp).distance(q), 1), 'X_UTM33N': xp, 'Y_UTM33N': yp})
    righe.append({'ID': i, 'Tracciato': fonte, 'Lungh_m': round(t.length), 'N_incroci': len(scelti),
                  'Tolleranza_m': toll if scelti else None})

Q = pd.DataFrame(punti)
Q['soglia'] = Q['soglia'].astype('Int64')
Q[['id', 'X', 'Y', 'porzione', 'xmin', 'ymax', 'xmax', 'ymin', 'soglia']].to_csv(os.path.join(out, 'ponti.csv'), index=False)
Q.drop(columns=['X', 'Y', 'xmin', 'ymax', 'xmax', 'ymin', 'soglia']).to_csv(os.path.join(out, 'incroci_punti.csv'), index=False)
E = pd.DataFrame(righe)
E.to_csv(os.path.join(out, 'incroci_ponti.csv'), index=False)
gpd.GeoDataFrame(tracc, crs=32633).to_file(os.path.join(out, 'tracciati.gpkg'), layer='tracciati', driver='GPKG')
print(f'{len(Q)} punti su {int((E.N_incroci > 0).sum())} ponti; porzioni {Q.porzione.nunique()}')
print(E.N_incroci.value_counts().sort_index().to_dict(), E.Tracciato.value_counts().to_dict())
