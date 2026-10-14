"""
Confronto con il reticolo idrografico di riferimento (shapefile con nome,
livello, codice SIBAPO).

Per ogni ponte (ID del database):
  1. corso di riferimento attraversato dal tracciato KML (intersezione; se
     manca, il tratto piu' vicino entro 50 m): nome, livello, codice;
  2. distanza tra la sezione di chiusura calcolata a 5 m e quel corso, e
     corso di riferimento piu' vicino alla sezione: la sezione e' sullo
     stesso corso attraversato dal ponte?
  3. lunghezza del reticolo di riferimento a monte del punto di
     attraversamento (grafo dei tratti; si risale solo verso quote non
     inferiori a quella dell'attraversamento - 1 m, quote dal DEM a 30 m) e
     area stimata = lunghezza / densita' di drenaggio, con la densita'
     ricavata sui ponti compatibili (mediana). Stima indipendente dal
     database e dal DEM a 5 m (dipende solo dalla completezza del reticolo).

Uso: python confronto_reticolo_riferimento.py <reticolo.shp> <dem30.tif> <controllo_coordinate.gpkg>
        <risultati_5m.gpkg> <Risultati_5m_ibrido.xlsx (con origine errore)> <out_dir>
"""
import os
import sys
from collections import defaultdict, deque

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from shapely.geometry import Point, LineString, MultiLineString
from shapely.ops import substring

TOL = 0.15
shp, dem30, cgpkg, rgpkg, xlsx, out = sys.argv[1:7]
os.makedirs(out, exist_ok=True)

R = gpd.read_file(shp).to_crs(32633)
R = R.explode(index_parts=False).reset_index(drop=True)
R = R[R.geometry.length > 0].reset_index(drop=True)
R['L'] = R.length
with rasterio.open(dem30) as s:
    def quota(xy):
        v = np.array([x[0] for x in s.sample(xy)], dtype=float)
        v[v == s.nodata] = np.nan
        return v
    a = [g.coords[0] for g in R.geometry]
    b = [g.coords[-1] for g in R.geometry]
    R['z_a'] = quota(a)
    R['z_b'] = quota(b)

# grafo: nodi = estremi arrotondati a 0,5 m
def chiave(p):
    return (round(p[0] * 2) / 2, round(p[1] * 2) / 2)


adj = defaultdict(list)
na, nb = [], []
for k, g in enumerate(R.geometry):
    u, v = chiave(g.coords[0]), chiave(g.coords[-1])
    na.append(u)
    nb.append(v)
    adj[u].append(k)
    adj[v].append(k)
R['na'] = na
R['nb'] = nb
sidx = R.sindex

trc = gpd.read_file(cgpkg, layer='tracciato_usato').set_index('ID').geometry
inp = gpd.read_file(cgpkg, layer='input_script').set_index('ID').geometry
sez = gpd.read_file(rgpkg, layer='sezioni_chiusura').set_index('ID').geometry
P = pd.read_excel(xlsx, sheet_name='Ponti').set_index('ID')
adb = P['Area database (km²)']
a5 = P['Area calcolata 5 m (km²)']
ok = P['Compatibile (±15%)'] == True  # noqa: E712


def lunghezza_monte(k, p, z0):
    """Lunghezza del reticolo a monte del punto p sul tratto k."""
    g = R.geometry[k]
    s0 = g.project(p)
    za, zb = R.z_a[k], R.z_b[k]
    # estremo di monte del tratto = quello piu' alto
    if np.nan_to_num(za, nan=-1e9) >= np.nan_to_num(zb, nan=-1e9):
        tot, start = s0, R.na[k]
    else:
        tot, start = g.length - s0, R.nb[k]
    visti_e, visti_n = {k}, {start}
    q = deque([start])
    while q:
        n = q.popleft()
        for e in adj[n]:
            if e in visti_e:
                continue
            zmin = np.nanmin([R.z_a[e], R.z_b[e]]) if not (np.isnan(R.z_a[e]) and np.isnan(R.z_b[e])) else np.nan
            if np.isfinite(zmin) and np.isfinite(z0) and zmin < z0 - 1.0:
                continue
            visti_e.add(e)
            tot += R.L[e]
            for m in (R.na[e], R.nb[e]):
                if m not in visti_n:
                    visti_n.add(m)
                    q.append(m)
    return tot / 1000, len(visti_e)


righe = []
with rasterio.open(dem30) as s:
    for i in P.index:
        o = {'ID': i}
        line = trc[i] if i in trc.index else None
        cand = []
        if line is not None:
            for k in sidx.query(line, predicate='intersects'):
                ip = R.geometry[k].intersection(line)
                ip = ip if ip.geom_type == 'Point' else ip.centroid
                cand.append((k, ip, 0.0))
        tipo = 'intersezione col tracciato'
        if not cand:
            ref = line if line is not None else inp[i]
            near = [k for k in sidx.query(ref.buffer(50)) if R.geometry[k].distance(ref) <= 50]
            if near:
                k = min(near, key=lambda k: R.geometry[k].distance(ref))
                d = R.geometry[k].distance(ref)
                ip = R.geometry[k].interpolate(R.geometry[k].project(ref.centroid))
                cand.append((k, ip, d))
                tipo = 'tratto più vicino entro 50 m'
        if not cand:
            o['Rif_tipo'] = 'nessun corso di riferimento entro 50 m'
            righe.append(o)
            continue
        # se piu' corsi, quello di livello gerarchico piu' basso (corso principale)
        cand.sort(key=lambda c: (pd.to_numeric(R.livello[c[0]], errors='coerce') or 99, -R.L[c[0]]))
        k, ip, d = cand[0]
        o['Rif_tipo'] = tipo
        o['Rif_distanza_m'] = d
        o['Rif_n_corsi_attraversati'] = len({R.sibapo[c[0]] for c in cand})
        o['Rif_nome'] = R.nome[k]
        o['Rif_toponimo'] = R.toponimo[k]
        o['Rif_livello'] = R.livello[k]
        o['Rif_sibapo'] = R.sibapo[k]
        o['Rif_altri_corsi'] = '; '.join(sorted({str(R.nome[c[0]]) for c in cand[1:]}))
        z0 = float([v[0] for v in s.sample([(ip.x, ip.y)])][0])
        Lm, ne = lunghezza_monte(k, ip, z0)
        o['Rif_L_monte_km'] = Lm
        o['Rif_n_tratti_monte'] = ne
        o['rif_x'], o['rif_y'] = ip.x, ip.y
        if i in sez.index:
            ps = sez[i]
            o['Dist_sezione_corso_rif_m'] = R.geometry[k].distance(ps)
            kk = list(sidx.query(ps.buffer(200)))
            if kk:
                k2 = min(kk, key=lambda e: R.geometry[e].distance(ps))
                o['Corso_rif_vicino_sezione'] = R.nome[k2]
                o['Dist_sezione_rif_vicino_m'] = R.geometry[k2].distance(ps)
                o['Sezione_su_stesso_corso'] = (R.sibapo[k2] == R.sibapo[k]) and \
                    (R.geometry[k].distance(ps) <= 50)
        righe.append(o)

D = pd.DataFrame(righe).set_index('ID')
D['A_db'] = adb
D['A_calc'] = a5
D['Compatibile'] = ok
cal = D[ok & D.Rif_L_monte_km.notna() & (D.A_calc > 0.5) & (D.Rif_tipo == 'intersezione col tracciato')]
dens = (cal.Rif_L_monte_km / cal.A_calc)
k_med = float(dens.median())
q25, q75 = dens.quantile([.25, .75])
D['A_da_reticolo_km2'] = D.Rif_L_monte_km / k_med
D['A_reticolo_min_km2'] = D.Rif_L_monte_km / q75
D['A_reticolo_max_km2'] = D.Rif_L_monte_km / q25
D['DB_in_intervallo_reticolo'] = (D.A_db >= D.A_reticolo_min_km2) & (D.A_db <= D.A_reticolo_max_km2)
D['Calc_in_intervallo_reticolo'] = (D.A_calc >= D.A_reticolo_min_km2) & (D.A_calc <= D.A_reticolo_max_km2)


def giudizio(r):
    if pd.isna(r.A_db) or r.Compatibile:
        return ''
    if pd.isna(r.Rif_L_monte_km):
        return 'nessun corso di riferimento vicino al ponte'
    s = []
    if r.Sezione_su_stesso_corso is False or r.Sezione_su_stesso_corso == False:  # noqa: E712
        s.append('sezione calcolata NON sul corso di riferimento attraversato dal ponte')
    if r.DB_in_intervallo_reticolo and not r.Calc_in_intervallo_reticolo:
        s.append('il reticolo di riferimento sostiene il DATABASE')
    elif r.Calc_in_intervallo_reticolo and not r.DB_in_intervallo_reticolo:
        s.append('il reticolo di riferimento sostiene il CALCOLO')
    elif r.Calc_in_intervallo_reticolo and r.DB_in_intervallo_reticolo:
        s.append('reticolo compatibile con entrambi')
    else:
        s.append('reticolo incompatibile con entrambi')
    return '; '.join(s)


D['Giudizio_reticolo'] = [giudizio(r) for _, r in D.iterrows()]
D.to_csv(os.path.join(out, 'confronto_reticolo_riferimento.csv'))
print(f'densità di drenaggio del reticolo di riferimento: mediana {k_med:.2f} km/km² '
      f'(IQR {q25:.2f}-{q75:.2f}) su {len(cal)} ponti compatibili')
c = D[ok]
print('compatibili: calcolata entro intervallo reticolo', int(c.Calc_in_intervallo_reticolo.sum()), '/', len(c),
      '; sezione sullo stesso corso', int((c.Sezione_su_stesso_corso == True).sum()))  # noqa: E712
nc = D[~ok & D.A_db.notna()]
print(nc.Giudizio_reticolo.value_counts().to_string())
