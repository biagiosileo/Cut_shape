"""
Punto di attraversamento = intersezione tra il tracciato del ponte nel KML e
il reticolo idrografico, e area del bacino chiuso in quel punto. Confronto con
le aree ottenute dagli altri punti (input dei gruppi, punto medio DB, punto KML).

Reticolo: DEM (qui il mosaico a 30 m) condizionato con Whitebox (riempimento +
D8); celle con area contribuente >= SOGLIA_KM2; ogni cella di reticolo e'
rappresentata dal segmento che unisce il suo centro a quello della cella a
valle. L'area in un punto del segmento e' l'area della cella di monte.

Uso: python intersezione_tracciati.py <dem.tif> <controllo_coordinate.gpkg> <out_dir>
"""
import os
import sys

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import whitebox_workflows as wb
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points

SOGLIA_KM2 = 0.25
TOL = 0.15
MARGINE_M = 300.0          # finestra attorno al tracciato
MAX_DIST_TRACCIATO_M = 50  # abbinamento tracciato-punto KML per vicinanza

dem_p, gpkg, out_dir = sys.argv[1:4]
os.makedirs(out_dir, exist_ok=True)

wbe = wb.WbEnvironment()
wbe.verbose = False
filled = wbe.hydrology.fill_depressions(dem=wbe.read_raster(dem_p))
tmp_a, tmp_p = os.path.join(out_dir, '_acc.tif'), os.path.join(out_dir, '_pnt.tif')
wbe.write_raster(wbe.hydrology.d8_flow_accum(input=filled, out_type='cells'), tmp_a)
wbe.write_raster(wbe.hydrology.d8_pointer(dem=filled), tmp_p)
with rasterio.open(tmp_a) as s:
    T = s.transform
    acc = s.read(1).astype(float) * abs(T.a * T.e) / 1e6
with rasterio.open(tmp_p) as s:
    pnt = s.read(1).astype(int)
os.remove(tmp_a)
os.remove(tmp_p)
with rasterio.open(dem_p) as s:
    valid = s.read(1) != s.nodata
acc[~valid] = 0
nr, nc = acc.shape
# Codici puntatore Whitebox: 1 NE, 2 E, 4 SE, 8 S, 16 SW, 32 W, 64 NW, 128 N
OFF = {1: (-1, 1), 2: (0, 1), 4: (1, 1), 8: (1, 0), 16: (1, -1), 32: (0, -1), 64: (-1, -1), 128: (-1, 0)}
inv = ~T


def centro(r, c):
    return T * (c + 0.5, r + 0.5)


def segmenti(xmin, ymin, xmax, ymax):
    """Segmenti di reticolo (cella -> cella a valle) nella finestra."""
    c0, r0 = inv * (xmin, ymax)
    c1, r1 = inv * (xmax, ymin)
    r0, c0 = max(int(r0), 0), max(int(c0), 0)
    r1, c1 = min(int(r1) + 1, nr), min(int(c1) + 1, nc)
    out = []
    for r, c in zip(*np.nonzero(acc[r0:r1, c0:c1] >= SOGLIA_KM2)):
        r, c = r + r0, c + c0
        off = OFF.get(int(pnt[r, c]))
        if off is None:
            continue
        out.append((LineString([centro(r, c), centro(r + off[0], c + off[1])]), acc[r, c]))
    return out


def vicino(x, y):
    """Regola attuale: cella di reticolo piu' vicina al punto."""
    c0, r0 = inv * (x, y)
    r0, c0 = int(r0), int(c0)
    n = 4
    while True:
        rr, cc = np.mgrid[max(r0 - n, 0):min(r0 + n + 1, nr), max(c0 - n, 0):min(c0 + n + 1, nc)]
        X, Y = T * (cc + .5, rr + .5)
        d = np.hypot(X - x, Y - y)
        m = acc[rr, cc] >= SOGLIA_KM2
        if m.any():
            i = np.argmin(np.where(m, d, np.inf))
            return acc[rr.flat[i], cc.flat[i]]
        n *= 2


inp = gpd.read_file(gpkg, layer='input_script').set_index('ID')
kml = gpd.read_file(gpkg, layer='kml_abbinato').set_index('ID')
ini = gpd.read_file(gpkg, layer='db_inizio').set_index('ID')
fin = gpd.read_file(gpkg, layer='db_fine').set_index('ID')
trc = gpd.read_file(gpkg, layer='kml_tracciati')

righe, inters, tracce, retic = [], [], [], {}
for i in inp.index:
    o = {'ID': i, 'Gruppo': inp.Gruppo[i], 'SP': inp.SP[i], 'km': inp.km[i], 'A_db_km2': inp.A_db_km2[i]}
    # tracciato: stesso nome del punto KML, altrimenti il piu' vicino al punto KML
    nome = kml.KML_nome.get(i)
    t = trc[trc.nome == nome]
    if len(t):
        line, fonte = t.geometry.iloc[0], 'KML, stesso nome'
    else:
        d = trc.distance(kml.geometry[i])
        j = d.idxmin()
        if d[j] <= MAX_DIST_TRACCIATO_M:
            line, fonte = trc.geometry[j], f'KML, per vicinanza ({trc.nome[j]}, {d[j]:.1f} m)'
        elif i in ini.index and i in fin.index:
            line, fonte = LineString([ini.geometry[i], fin.geometry[i]]), 'segmento inizio-fine DB'
        else:
            line, fonte = None, 'nessun tracciato'
    o['Tracciato'] = fonte
    o['Lunghezza_tracciato_m'] = line.length if line is not None else np.nan
    if line is not None:
        tracce.append({'ID': i, 'fonte': fonte, 'geometry': line})
        xmin, ymin, xmax, ymax = line.bounds
        segs = segmenti(xmin - MARGINE_M, ymin - MARGINE_M, xmax + MARGINE_M, ymax + MARGINE_M)
        retic[i] = segs
        hit = []
        for s, a in segs:
            if s.intersects(line):
                p = s.intersection(line)
                p = p if p.geom_type == 'Point' else p.centroid
                hit.append((a, p))
        if hit:
            hit.sort(key=lambda h: -h[0])
            a, p = hit[0]
            o['Intersezione'] = 'sul tracciato'
            o['N_corsi_intersecati'] = len({round(h[0], 3) for h in hit})
            o['Aree_intersecate_km2'] = '; '.join(f'{h[0]:.3g}' for h in hit)
            o['Dist_tracciato_reticolo_m'] = 0.0
        elif segs:
            # nessuna intersezione: punto di reticolo piu' vicino al tracciato
            best = min(segs, key=lambda sa: sa[0].distance(line))
            a = best[1]
            p = nearest_points(best[0], line)[0]
            o['Intersezione'] = 'reticolo più vicino al tracciato'
            o['N_corsi_intersecati'] = 0
            o['Dist_tracciato_reticolo_m'] = best[0].distance(line)
        else:
            a, p = np.nan, None
            o['Intersezione'] = 'nessun reticolo entro la finestra'
        o['A_intersezione_km2'] = a
        if p is not None:
            o['int_x'], o['int_y'] = p.x, p.y
            inters.append({'ID': i, 'A_km2': a, 'tipo': o['Intersezione'],
                           'A_db_km2': o['A_db_km2'], 'geometry': p})
            o['Dist_intersezione_input_m'] = p.distance(inp.geometry[i])
            o['Dist_intersezione_KML_m'] = p.distance(kml.geometry[i]) if i in kml.index else np.nan
    o['A_input_km2'] = vicino(inp.geometry[i].x, inp.geometry[i].y)
    o['A_KML_km2'] = vicino(kml.geometry[i].x, kml.geometry[i].y) if i in kml.index else np.nan
    righe.append(o)

r = pd.DataFrame(righe)
for c in ('A_input_km2', 'A_KML_km2', 'A_intersezione_km2'):
    k = c.replace('A_', 'OK_').replace('_km2', '')
    r[k] = np.where(r.A_db_km2.notna(), (r[c] / r.A_db_km2 - 1).abs() <= TOL, None)
    r[c.replace('A_', 'Diff_pct_').replace('_km2', '')] = (r[c] / r.A_db_km2 - 1) * 100
r.to_csv(os.path.join(out_dir, 'intersezione_tracciati.csv'), index=False)

gpd.GeoDataFrame(tracce, crs=32633).to_file(gpkg, layer='tracciato_usato', driver='GPKG')
gi = gpd.GeoDataFrame(inters, crs=32633).merge(
    r[['ID', 'OK_intersezione', 'Diff_pct_intersezione', 'N_corsi_intersecati']], on='ID')
gi.to_file(gpkg, layer='intersezione_tracciato_reticolo', driver='GPKG')
segs_all = {}
for i, segs in retic.items():
    for s, a in segs:
        segs_all[s.wkb] = (s, a)
gpd.GeoDataFrame({'A_km2': [v[1] for v in segs_all.values()]},
                 geometry=[v[0] for v in segs_all.values()], crs=32633) \
    .to_file(gpkg, layer='reticolo_30m_vicino_ponti', driver='GPKG')
n = int(r.A_db_km2.notna().sum())
for c in ('OK_input', 'OK_KML', 'OK_intersezione'):
    print(f'{c:18s} {int((r[c] == True).sum())} / {n}')
print(r.Intersezione.value_counts().to_dict())
print('Tracciato:', r.Tracciato.str.split(',').str[0].value_counts().to_dict())
