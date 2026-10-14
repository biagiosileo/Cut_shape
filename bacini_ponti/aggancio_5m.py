"""
Passo 2 dell'analisi a 5 m: area del bacino per ogni ponte, per piu' soglie del
reticolo e per piu' punti di aggancio, usando le toppe salvate da
dem5_finestre.py.

Punti di aggancio (cella di reticolo piu' vicina con area >= soglia):
  input   = coordinate dei file Bacino_NN_ponti.csv (punto medio inizio-fine DB)
  inizio  = coordinata iniziale DB (coincide col punto KML in 202 casi)
  fine    = coordinata finale DB
  kml     = punto di localizzazione KML
Intersezione: il tracciato KML del ponte interseca il reticolo (segmenti dal
centro di ogni cella di reticolo al centro della cella a valle); se interseca
piu' corsi si prende quello con area maggiore; se non lo interseca si prende il
punto di reticolo piu' vicino al tracciato (distanza registrata).

Uso: python aggancio_5m.py <cartella_toppe> <controllo_coordinate.gpkg> <out.csv>
"""
import glob
import os
import sys

import numpy as np
import pandas as pd
import geopandas as gpd
from affine import Affine
from shapely.geometry import LineString
from shapely.ops import nearest_points

SOGLIE_KM2 = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
OFF = {1: (-1, 1), 2: (0, 1), 4: (1, 1), 8: (1, 0), 16: (1, -1), 32: (0, -1), 64: (-1, -1), 128: (-1, 0)}
MARGINE_TRACCIATO_M = 100.0

tdir, gpkg, out = sys.argv[1:4]
geo = {}
for lay, nome in (('input_script', 'input'), ('db_inizio', 'inizio'), ('db_fine', 'fine'), ('kml_abbinato', 'kml')):
    geo[nome] = gpd.read_file(gpkg, layer=lay).set_index('ID').geometry
trc = gpd.read_file(gpkg, layer='tracciato_usato').set_index('ID')
adb = gpd.read_file(gpkg, layer='input_script').set_index('ID').A_db_km2

righe = []
for f in sorted(glob.glob(os.path.join(tdir, 'id*.npz'))):
    i = int(os.path.basename(f)[2:5])
    z = np.load(f)
    acc, ptr, f5 = z['acc_km2'], z['ptr'], z['fonte5']
    T = Affine(*z['transform'])
    inv = ~T
    H, W = acc.shape
    R, C = np.mgrid[0:H, 0:W]
    X, Y = T * (C + 0.5, R + 0.5)
    for s in SOGLIE_KM2:
        rete = acc >= s
        o = {'ID': i, 'Soglia_km2': s, 'A_db_km2': adb.get(i)}
        for nome, g in geo.items():
            if i not in g.index:
                continue
            p = g[i]
            d = np.where(rete, np.hypot(X - p.x, Y - p.y), np.inf)
            k = np.argmin(d)
            cp, rp = inv * (p.x, p.y)
            if np.isfinite(d.flat[k]) and 0 <= cp < W and 0 <= rp < H:
                o[f'A_{nome}'] = float(acc.flat[k])
                o[f'Dist_{nome}_m'] = float(d.flat[k])
                o[f'Fonte5_{nome}'] = bool(f5.flat[k])
                o[f'Cella_{nome}'] = f'{k // W},{k % W}'
            else:
                o[f'A_{nome}'] = np.nan
                o[f'Dist_{nome}_m'] = np.nan
        if i in trc.index:
            line = trc.geometry[i]
            xmin, ymin, xmax, ymax = line.bounds
            m = rete & (X >= xmin - MARGINE_TRACCIATO_M) & (X <= xmax + MARGINE_TRACCIATO_M) & \
                (Y >= ymin - MARGINE_TRACCIATO_M) & (Y <= ymax + MARGINE_TRACCIATO_M)
            hit, segs = [], []
            for r, c in zip(*np.nonzero(m)):
                off = OFF.get(int(ptr[r, c]))
                if off is None:
                    continue
                r2, c2 = r + off[0], c + off[1]
                if not (0 <= r2 < H and 0 <= c2 < W):
                    continue
                sg = LineString([(X[r, c], Y[r, c]), (X[r2, c2], Y[r2, c2])])
                segs.append((sg, acc[r, c], r, c))
                if sg.intersects(line):
                    hit.append((acc[r, c], r, c))
            if hit:
                a, rh, ch = max(hit)
                o['A_intersezione'] = float(a)
                o['Cella_intersezione'] = f'{rh},{ch}'
                hit = [h[0] for h in hit]
                o['Tipo_intersezione'] = 'sul tracciato'
                o['N_corsi_intersecati'] = len({round(float(h), 4) for h in hit})
                o['Dist_tracciato_m'] = 0.0
            elif segs:
                sg, a, rh, ch = min(segs, key=lambda t: t[0].distance(line))
                o['A_intersezione'] = float(a)
                o['Cella_intersezione'] = f'{rh},{ch}'
                o['Tipo_intersezione'] = 'reticolo più vicino al tracciato'
                o['N_corsi_intersecati'] = 0
                o['Dist_tracciato_m'] = float(sg.distance(line))
            else:
                o['A_intersezione'] = o.get('A_input', np.nan)
                o['Cella_intersezione'] = o.get('Cella_input')
                o['Tipo_intersezione'] = 'nessun reticolo vicino al tracciato (uso input)'
                o['N_corsi_intersecati'] = 0
        righe.append(o)
pd.DataFrame(righe).to_csv(out, index=False)
print('salvato', out, len(righe))
