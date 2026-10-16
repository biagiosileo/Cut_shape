"""
Allinea le sezioni di chiusura del CSV alla griglia di flusso di pysheds.

Il codice dell'utente condiziona il DEM con pysheds (fill_pits, fill_depressions,
resolve_flats), non con Whitebox: in pochi punti l'alveo principale passa nella cella
accanto e la sezione finale cade su un affluente. Per i ponti indicati si cerca, entro
RAGGIO_M dalla sezione finale, la cella del reticolo pysheds (acc > 4000) con area piu'
vicina a quella di riferimento (a parita', la piu' vicina) e la si scrive nel CSV.

Uso: python correggi_sezioni_pysheds.py <cartella input> <finestra_NN> <risultati_5m.gpkg> <ID> [ID ...]
Il CSV originale viene salvato come finestra_NN_ponti_prima_della_correzione.csv;
le modifiche vanno in correzioni_sezioni.csv (cartella input).
"""
import os
import shutil
import sys

import numpy as np
np.in1d = np.isin
import pandas as pd
import geopandas as gpd
from pyproj import Transformer
from pysheds.grid import Grid

D, nome, rgpkg = sys.argv[1:4]
ids = [int(v) for v in sys.argv[4:]]
RAGGIO_M = 25.0
SOGLIA = 4000
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)

p = os.path.join(D, f'{nome}_dem5m.asc')
grid = Grid.from_ascii(p)
dem = grid.read_ascii(p)
dem = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem)), eps=1e-6, max_iter=10000)
fdir = grid.flowdir(dem, dirmap=DIRMAP)
del dem
acc = np.asarray(grid.accumulation(fdir, dirmap=DIRMAP))
T = grid.affine
cs = T.a
sez = gpd.read_file(rgpkg, layer='sezioni_chiusura').set_index('ID')
a4326 = Transformer.from_crs(32633, 4326, always_xy=True)
csv = os.path.join(D, f'{nome}_ponti.csv')
df = pd.read_csv(csv)
righe = []
for i in ids:
    s = sez.loc[i]
    x0, y0 = s.geometry.x, s.geometry.y  # centro della cella della sezione finale
    a_rif = s.A_5m
    c0, r0 = (int(v) for v in ~T * (x0, y0))
    k = int(RAGGIO_M // cs)
    best = None
    for r in range(r0 - k, r0 + k + 1):
        for c in range(c0 - k, c0 + k + 1):
            if not (0 <= r < acc.shape[0] and 0 <= c < acc.shape[1]) or acc[r, c] <= SOGLIA:
                continue
            x, y = T * (c + .5, r + .5)
            d = float(np.hypot(x - x0, y - y0))
            if d > RAGGIO_M:
                continue
            a = acc[r, c] * cs * cs / 1e6
            key = (round(abs(a / a_rif - 1), 3), d)
            if best is None or key < best[0]:
                best = (key, x, y, a, d)
    a_prima = acc[r0, c0] * cs * cs / 1e6
    if best is None:
        print(i, 'nessuna cella del reticolo entro', RAGGIO_M, 'm')
        continue
    _, x, y, a, d = best
    lon, lat = a4326.transform(x - 1.25, y + 1.25)  # verso l'angolo in alto a sinistra (vedi input_codice_utente.py)
    df.loc[df.id == i, ['X', 'Y']] = [round(lon, 9), round(lat, 9)]
    righe.append({'ID': i, 'Finestra': nome, 'Area riferimento (km²)': round(a_rif, 3),
                  'Area pysheds alla sezione finale (km²)': round(a_prima, 3),
                  'Area pysheds alla sezione corretta (km²)': round(a, 3),
                  'Spostamento (m)': round(d, 1), 'X nuova (UTM)': x, 'Y nuova (UTM)': y})
    print(righe[-1])
bak = csv.replace('.csv', '_prima_della_correzione.csv')
if not os.path.exists(bak):
    shutil.copy(csv, bak)
df.to_csv(csv, index=False)
log = os.path.join(D, 'correzioni_sezioni.csv')
old = pd.read_csv(log) if os.path.exists(log) else pd.DataFrame()
if len(old):
    old = old[~old.ID.isin([r['ID'] for r in righe])]
pd.concat([old, pd.DataFrame(righe)]).sort_values('ID').to_csv(log, index=False)
