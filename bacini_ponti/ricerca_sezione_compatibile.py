"""
Per i ponti non compatibili (|A_calc/A_DB - 1| > 15%) cerca sul reticolo (accumulo >= 0,1 km2)
entro la toppa di +-750 m attorno al ponte le celle con area compatibile con il database
(+-15%), e misura quanto sono lontane dal ponte (tracciato KML + punti inizio/fine del DB).

Per ogni ponte:
  - cella compatibile piu' vicina al ponte e sua distanza;
  - se sta sullo stesso corso d'acqua della sezione attuale (a monte o a valle) o su un altro;
  - cella compatibile piu' vicina sullo stesso corso;
  - area del corso attuale lungo il tracciato (min-max entro 50 m dal ponte).
Esito (area DB >= 0,1 km2; sotto la soglia del reticolo il ponte e' classificato a parte):
  distanza <= 50 m           spostamento piccolo: problema di posizionamento della sezione
  50 < distanza <= 200 m     spostamento possibile, da verificare sulla cartografia
  > 200 m o nessuna cella    l'area del DB non si trova vicino al ponte: probabile errore DB

Uso: python ricerca_sezione_compatibile.py <toppe> <risultati_5m.gpkg> <controllo_coordinate.gpkg>
        <Risultati_5m_ibrido.xlsx> <out_dir> <Ponti_non_compatibili.xlsx>
"""
import os
import sys

import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from affine import Affine
from shapely.geometry import LineString, Point

toppe, rgpkg, cgpkg, xlsx, out, xnc = sys.argv[1:7]
os.makedirs(out, exist_ok=True)
TOLL = 0.15
SOGLIA_KM2 = 0.1
OFF = {1: (-1, 1), 2: (0, 1), 4: (1, 1), 8: (1, 0), 16: (1, -1), 32: (0, -1), 64: (-1, -1), 128: (-1, 0)}

sez = gpd.read_file(rgpkg, layer='sezioni_chiusura').set_index('ID')
tr = gpd.read_file(cgpkg, layer='tracciato_usato').set_index('ID').geometry
ini = gpd.read_file(cgpkg, layer='db_inizio').set_index('ID').geometry
fin = gpd.read_file(cgpkg, layer='db_fine').set_index('ID').geometry
X = pd.read_excel(xlsx, sheet_name='Ponti').set_index('ID')
NC = pd.read_excel(xnc).set_index('ID')
nc = sez.index[sez.A_db.notna() & ((sez.A_5m / sez.A_db - 1).abs() > TOLL)]


def a_valle(r, c, ptr, n=100000):
    """celle a valle di (r, c) fino all'uscita dalla toppa"""
    out_ = []
    for _ in range(n):
        v = int(ptr[r, c])
        if v not in OFF:
            break
        dr, dc = OFF[v]
        r, c = r + dr, c + dc
        if not (0 <= r < ptr.shape[0] and 0 <= c < ptr.shape[1]):
            break
        out_.append((r, c))
    return out_


righe, punti, linee = [], [], []
for i in nc:
    d = np.load(os.path.join(toppe, f'id{i:03d}.npz'), allow_pickle=True)
    acc, ptr = d['acc_km2'], d['ptr']
    T = Affine(*d['transform'][:6])
    a_db, a_calc = float(sez.A_db[i]), float(sez.A_5m[i])
    geoms = [g for g in (tr.get(i), ini.get(i), fin.get(i)) if g is not None and not g.is_empty]
    ponte = shapely.unary_union(geoms)
    # sezione attuale nella toppa
    s = sez.geometry[i]
    c0, r0 = (int(np.floor(v)) for v in ~T * (s.x, s.y))
    dentro = 0 <= r0 < acc.shape[0] and 0 <= c0 < acc.shape[1]
    valle0 = set(a_valle(r0, c0, ptr)) if dentro else set()
    # asta principale a monte: si risale sempre il vicino affluente con area maggiore
    monte0 = set()
    if dentro:
        r, c = r0, c0
        while True:
            best_n = None
            for v, (dr, dc) in OFF.items():
                rn_, cn_ = r - dr, c - dc
                if 0 <= rn_ < ptr.shape[0] and 0 <= cn_ < ptr.shape[1] and int(ptr[rn_, cn_]) == v:
                    if best_n is None or acc[rn_, cn_] > acc[best_n]:
                        best_n = (rn_, cn_)
            if best_n is None or acc[best_n] < SOGLIA_KM2:
                break
            r, c = best_n
            monte0.add((r, c))
    # celle compatibili
    # area DB sotto la soglia del reticolo: si cercano anche celle fuori dal reticolo
    sotto = a_db * (1 + TOLL) < SOGLIA_KM2
    soglia = 0.0 if sotto else SOGLIA_KM2
    rr, cc = np.nonzero((acc >= soglia) & (np.abs(acc / a_db - 1) <= TOLL))
    xs, ys = T * (cc + 0.5, rr + 0.5)
    dist = shapely.distance(shapely.points(xs, ys), ponte) if len(rr) else np.array([])
    ordine = np.argsort(dist)

    def relazione(k):
        r, c = rr[k], cc[k]
        if not dentro:
            return 'non determinabile'
        if (r, c) in valle0:
            return 'stesso corso, a valle'
        if (r, c) in monte0:
            return 'stesso corso, a monte'
        if (r0, c0) in set(a_valle(r, c, ptr)):
            return 'affluente a monte della sezione'
        return 'altro corso'

    best = stesso = None
    for k in ordine[:4000]:
        rel = relazione(k)
        if best is None:
            best = (k, rel)
        if rel.startswith('stesso'):
            stesso = (k, rel)
            break
    # area del corso attuale vicino al ponte (celle del reticolo entro 50 m dal ponte)
    rn, cn = np.nonzero(acc >= SOGLIA_KM2)
    xn, yn = T * (cn + 0.5, rn + 0.5)
    vicino = shapely.distance(shapely.points(xn, yn), ponte) <= 50 if len(rn) else np.array([], bool)
    a_vic = acc[rn[vicino], cn[vicino]] if vicino.any() else np.array([])

    rec = {'ID': i, 'Area database (km²)': a_db, 'Area calcolata (km²)': round(a_calc, 3),
           'Differenza %': a_calc / a_db - 1,
           'Area massima del reticolo entro 50 m dal ponte (km²)': round(float(a_vic.max()), 3) if a_vic.size else None}
    if best is not None:
        k, rel = best
        rec.update({'Sezione compatibile più vicina: distanza dal ponte (m)': round(float(dist[k]), 1),
                    'Sezione compatibile più vicina: area (km²)': round(float(acc[rr[k], cc[k]]), 3),
                    'Sezione compatibile più vicina: corso': rel})
        punti.append({'ID': i, 'tipo': 'compatibile più vicina', 'area_km2': round(float(acc[rr[k], cc[k]]), 3),
                      'dist_m': round(float(dist[k]), 1), 'corso': rel, 'geometry': Point(xs[k], ys[k])})
        linee.append({'ID': i, 'dist_m': round(float(dist[k]), 1),
                      'geometry': LineString([(s.x, s.y), (xs[k], ys[k])])})
    if stesso is not None:
        k, rel = stesso
        rec.update({'Sullo stesso corso: distanza dal ponte (m)': round(float(dist[k]), 1),
                    'Sullo stesso corso: area (km²)': round(float(acc[rr[k], cc[k]]), 3),
                    'Sullo stesso corso: posizione': rel})
        if best is None or k != best[0]:
            punti.append({'ID': i, 'tipo': 'compatibile sullo stesso corso', 'area_km2': round(float(acc[rr[k], cc[k]]), 3),
                          'dist_m': round(float(dist[k]), 1), 'corso': rel, 'geometry': Point(xs[k], ys[k])})
    dmin = rec.get('Sezione compatibile più vicina: distanza dal ponte (m)')
    if sotto:
        esito = ('Area DB sotto la soglia del reticolo (0,1 km²): corso troppo piccolo per il reticolo a 5 m; '
                 'il calcolo si aggancia al corso minimo rappresentato')
    elif dmin is None:
        esito = "Nessuna sezione compatibile entro ~750 m: probabile errore nel database (area o coordinate del ponte)"
    elif dmin <= 50:
        esito = 'Spostamento piccolo (≤50 m): probabile problema di posizionamento della sezione'
    elif dmin <= 200:
        esito = 'Spostamento possibile (50-200 m): da verificare sulla cartografia'
    else:
        esito = "Sezione compatibile solo lontano dal ponte (>200 m): probabile errore nel database (area o coordinate del ponte)"
    corso = rec.get('Sezione compatibile più vicina: corso')
    if not sotto and dmin is not None and dmin <= 200 and corso in ('altro corso', 'affluente a monte della sezione'):
        esito += f' - su {"un affluente" if corso.startswith("affluente") else "un altro corso"}: verificare quale corso attraversa il ponte'
    rec['Esito della ricerca'] = esito
    rec['Probabile origine errore (analisi precedente)'] = NC['Probabile origine errore'].get(i)
    rec['Nome opera'] = X['Nome opera'].get(i)
    righe.append(rec)

T_ = pd.DataFrame(righe).sort_values('ID')
cols = ['ID', 'Nome opera', 'Area database (km²)', 'Area calcolata (km²)', 'Differenza %', 'Esito della ricerca',
        'Sezione compatibile più vicina: distanza dal ponte (m)', 'Sezione compatibile più vicina: area (km²)',
        'Sezione compatibile più vicina: corso', 'Sullo stesso corso: distanza dal ponte (m)',
        'Sullo stesso corso: area (km²)', 'Sullo stesso corso: posizione',
        'Area massima del reticolo entro 50 m dal ponte (km²)', 'Probabile origine errore (analisi precedente)']
T_ = T_[[c for c in cols if c in T_.columns]]
xo = os.path.join(out, 'Ricerca_sezione_compatibile.xlsx')
with pd.ExcelWriter(xo, engine='openpyxl') as w:
    T_.to_excel(w, sheet_name='Non compatibili', index=False)
    ws = w.sheets['Non compatibili']
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 60)
    j = list(T_.columns).index('Differenza %') + 1
    for row in ws.iter_rows(min_row=2, min_col=j, max_col=j):
        row[0].number_format = '0.0%'
    ws.freeze_panes = 'B2'
    ws.auto_filter.ref = ws.dimensions
    R = T_['Esito della ricerca'].str.split(' - ').str[0].value_counts().rename_axis('Esito').reset_index(name='N. ponti')
    R.to_excel(w, sheet_name='Riepilogo', index=False)
    w.sheets['Riepilogo'].column_dimensions['A'].width = 90
go = os.path.join(out, 'ricerca_sezione_compatibile.gpkg')
gpd.GeoDataFrame(punti, crs=32633).to_file(go, layer='sezioni_compatibili', driver='GPKG')
gpd.GeoDataFrame(linee, crs=32633).to_file(go, layer='spostamento', driver='GPKG')
sez.loc[nc].reset_index()[['ID', 'A_db', 'A_5m', 'geometry']].to_file(go, layer='sezioni_attuali', driver='GPKG')
gpd.GeoDataFrame({'ID': list(tr.index)}, geometry=list(tr.values), crs=32633).loc[lambda g: g.ID.isin(nc)].to_file(
    go, layer='tracciati_ponti', driver='GPKG')
print(T_[['ID', 'Area database (km²)', 'Area calcolata (km²)', 'Sezione compatibile più vicina: distanza dal ponte (m)',
          'Sezione compatibile più vicina: corso', 'Sullo stesso corso: distanza dal ponte (m)']].to_string())
print(R.to_string())
