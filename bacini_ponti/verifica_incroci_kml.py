"""
Controllo su tutti i 212 ponti: il tracciato del ponte nel KML incrocia piu' corsi d'acqua del reticolo del codice?
Per ogni incrocio tracciato-reticolo si stima l'area drenata con l'accumulo sul DEM a 25 m (ricampionato con il
minimo, cosi' gli alvei incisi restano continui) e la si confronta con l'area calcolata dal codice nel punto usato.
Segnala i ponti in cui il tracciato attraversa un corso d'acqua diverso (lontano dal punto) con area molto maggiore
o molto minore di quella calcolata: possibili multi-asta non ancora segnalati.

Uso: python verifica_incroci_kml.py <dem25_min.tif> <reticolo_idrografico.geojson> <controllo_coordinate.gpkg>
        <ponti.csv> <situazioni_dubbie_212.csv> <out_dir>
"""
import os
import sys

import geopandas as gpd
import numpy as np
np.in1d = np.isin
import pandas as pd
import rasterio
from pyproj import Proj, Transformer
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
from shapely.geometry import Point
from shapely.ops import nearest_points

DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
DIST_PROPRIO_M = 200.0  # l'incrocio del corso d'acqua usato va cercato entro questa distanza dal punto
TOLL_M = 15.0         # distanza massima tracciato-reticolo per considerare un incrocio
RAGGIO_M = 30.0        # raggio in cui cercare la cella d'alveo (accumulo massimo) attorno all'incrocio

dem25, ret, gpkg, ponti, tab, out = sys.argv[1:7]
os.makedirs(out, exist_ok=True)
with rasterio.open(dem25) as s:
    z = s.read(1).astype(np.float64)
    T = s.transform
    nod = s.nodata
    sc = s.scales[0] if s.scales else 1.0
z = np.where(z == nod, -9999, z * sc).astype(np.float32)
vf = ViewFinder(affine=T, shape=z.shape, nodata=np.float32(-9999), crs=Proj('EPSG:32633', preserve_units=True))
g = Grid(viewfinder=vf)
dem = g.resolve_flats(g.fill_depressions(g.fill_pits(Raster(z, vf))), eps=1e-6, max_iter=10000)
A = np.asarray(g.accumulation(g.flowdir(dem, dirmap=DIRMAP), dirmap=DIRMAP)) * 625 / 1e6  # km2
del z, dem
print('accumulo a 25 m calcolato', A.shape, flush=True)


def area(x, y):
    c, r = ~T * (x, y)
    c, r = int(c), int(r)
    k = int(np.ceil(RAGGIO_M / 25))
    w = A[max(r - k, 0):r + k + 1, max(c - k, 0):c + k + 1]
    return float(w.max()) if w.size else np.nan


R = gpd.read_file(ret).to_crs(32633)
sidx = R.sindex
k = gpd.read_file(gpkg, layer='kml_abbinato').set_index('ID')
kt = gpd.read_file(gpkg, layer='kml_tracciati').to_crs(32633).drop_duplicates('nome').set_index('nome').geometry
P = pd.read_csv(ponti).set_index('id')
dbl = gpd.read_file(gpkg, layer='db_attraversamento_inizio_fine').to_crs(32633).set_index('ID').geometry
to_utm = Transformer.from_crs('EPSG:4326', 'EPSG:32633', always_xy=True)
D = pd.read_csv(tab).set_index('ID')

righe, linee, punti = [], [], []
for i in P.index:
    x, y = to_utm.transform(P.X[i], P.Y[i])
    q = Point(x, y)
    nome = k.KML_nome.get(i)
    t = kt.get(nome) if isinstance(nome, str) else None
    r = {'ID': i, 'A_codice_km2': D.A_calcolata_km2[i], 'A_relazione_km2': D.A_relazione_km2[i], 'Classe': D.Classe[i],
         'Caso_dubbio': D.Categoria[i], 'KML_nome': nome}
    r['Tracciato'] = 'KML'
    if t is None or t.length == 0:
        # senza tracciato KML: linea inizio-fine del database, se plausibile (meno di 2 km)
        t = dbl.get(i)
        if t is None or t.length == 0 or t.length > 2000:
            r['Esito'] = 'tracciato assente'
            righe.append(r); continue
        r['Tracciato'] = 'database inizio-fine'
    r['Lungh_tracciato_m'] = round(t.length)
    r['Dist_punto_tracciato_m'] = round(t.distance(q), 1)
    # tratti del reticolo entro TOLL_M dal tracciato (il tracciato KML e' disegnato a mano: puo' sfiorare l'alveo
    # senza toccarlo); per ogni tratto il punto piu' vicino al tracciato
    cand = R.iloc[list(sidx.query(t.buffer(TOLL_M), predicate='intersects'))]
    pts = []
    for geo in cand.geometry:
        inter = t.intersection(geo)
        if inter.is_empty:
            pts.append(nearest_points(geo, t)[0])
        else:
            pts += [inter] if inter.geom_type == 'Point' else [p for p in getattr(inter, 'geoms', []) if p.geom_type == 'Point']
    # incroci raggruppati (piu' tratti dello stesso corso d'acqua nello stesso punto)
    gruppi = []
    for p in pts:
        for gr in gruppi:
            if gr[0].distance(p) < 15:
                break
        else:
            gruppi.append([p])
    inc = [(gr[0], area(gr[0].x, gr[0].y)) for gr in gruppi]
    # incrocio del corso d'acqua usato: tra quelli entro DIST_PROPRIO_M dal punto, quello con area piu' vicina
    # all'area calcolata dal codice; tutti gli altri incroci sono altri corsi d'acqua (anche se vicini al punto,
    # per esempio l'altro ramo di una confluenza)
    a0 = D.A_calcolata_km2[i]
    vic = [v for v in inc if v[0].distance(q) <= DIST_PROPRIO_M and v[1] > 0]
    proprio = min(vic, key=lambda v: abs(np.log(v[1] / a0))) if vic and a0 > 0 else None
    altri = [v for v in inc if v is not proprio]
    r['A_incrocio_proprio_km2'] = round(proprio[1], 3) if proprio else np.nan
    # anche l'incrocio "proprio" conta se ha area molto maggiore: il punto non e' sul corso d'acqua del tracciato
    if proprio and a0 > 0 and proprio[1] / a0 >= 2 and proprio[1] >= 0.1:
        altri.append(proprio)
    r['N_incroci'] = len(inc)
    r['Aree_incroci_km2'] = '; '.join(f'{a:.3f} a {p.distance(q):.0f} m' for p, a in sorted(inc, key=lambda v: v[0].distance(q)))
    ar = sorted(a for _, a in inc if a >= 0.05)
    r['Corsi_acqua_distinti'] = int(1 + sum(1 for u, v in zip(ar, ar[1:]) if v / u >= 2)) if ar else 0
    r['N_incroci_lontani_dal_punto'] = len(altri)
    if altri:
        pm, am = max(altri, key=lambda v: v[1])
        r['A_max_altro_incrocio_km2'] = round(am, 3)
        r['Dist_altro_incrocio_m'] = round(pm.distance(q))
        rap = am / a0 if a0 > 0 else np.inf
        r['Rapporto_aree'] = round(rap, 2)
        if am >= 0.1 and (rap >= 2 or rap <= 0.5):
            r['Esito'] = ('il tracciato attraversa un corso d\'acqua piu\' grande' if rap >= 2 else
                          'il tracciato attraversa anche un corso d\'acqua piu\' piccolo')
            linee.append({'ID': i, 'Esito': r['Esito'], 'geometry': t})
            for p, a in inc:
                punti.append({'ID': i, 'A_stimata_km2': round(a, 3), 'Etichetta': f'{i}: {a:.2f} km2', 'geometry': p})
        else:
            r['Esito'] = 'altri incroci con area simile o trascurabile'
    else:
        r['Esito'] = 'un solo corso d\'acqua sul tracciato' if inc else 'il tracciato non incrocia il reticolo'
    righe.append(r)

E = pd.DataFrame(righe)
E.to_csv(os.path.join(out, 'incroci_tracciato_kml.csv'), index=False)
f = os.path.join(out, 'incroci_tracciato_kml.gpkg')
if os.path.exists(f):
    os.remove(f)
if linee:
    gpd.GeoDataFrame(linee, crs=32633).to_file(f, layer='tracciati_segnalati', driver='GPKG')
    gpd.GeoDataFrame(punti, crs=32633).to_file(f, layer='incroci', driver='GPKG')
print(E.Esito.value_counts())
s = E[E.Esito.str.startswith('il tracciato attraversa')]
pd.set_option('display.width', 250)
m = E[E.Corsi_acqua_distinti >= 2]
print('tracciati che attraversano piu\' corsi d\'acqua distinti:', len(m))
print(m[['ID', 'A_codice_km2', 'A_relazione_km2', 'Classe', 'Caso_dubbio', 'Lungh_tracciato_m', 'Aree_incroci_km2']].to_string(index=False))
print(s[['ID', 'A_codice_km2', 'A_relazione_km2', 'Classe', 'Caso_dubbio', 'Dist_punto_tracciato_m', 'N_incroci',
         'A_max_altro_incrocio_km2', 'Dist_altro_incrocio_m', 'Rapporto_aree']].to_string(index=False))
