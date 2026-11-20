"""
Prova: file dei ponti con il punto al centro della cella di chiusura (aderente al reticolo del codice).

Il ponti.csv usato finora ha ogni punto a 1.25 m (est e nord) dall'angolo in alto a sinistra della cella del DEM.
Qui il punto viene messo al centro della cella su cui il codice ha chiuso il bacino: la cella che contiene il
punto (210 ponti) oppure, per 114 e 170, la cella adiacente agganciata dal codice (verifica_aggancio_acc.py).
Tutte le altre colonne (porzione, limiti, soglia) restano uguali. Il file originale viene solo letto.

Uso: python crea_ponti_centri.py <ponti.csv originale> <ponti.csv nuovo>
"""
import sys

import numpy as np
import pandas as pd
from pyproj import Transformer

X0, Y0, DX = 557074.00012207, 4541648.3480835, 5.0      # origine e cella del DEM unico v4
# cella agganciata dal codice diversa da quella che contiene il punto: (colonne, righe) di spostamento
AGGANCIO = {114: (-1, -1), 170: (1, 0)}

src, out = sys.argv[1:3]
P = pd.read_csv(src)
a = Transformer.from_crs(4326, 32633, always_xy=True)
b = Transformer.from_crs(32633, 4326, always_xy=True)
x, y = a.transform(P.X.values, P.Y.values)
col = np.floor((x - X0) / DX).astype(int)
row = np.floor((Y0 - y) / DX).astype(int)
for i, (dc, dr) in AGGANCIO.items():
    k = np.where(P.id.values == i)[0][0]
    col[k] += dc; row[k] += dr
xc = X0 + (col + 0.5) * DX
yc = Y0 - (row + 0.5) * DX
lon, lat = b.transform(xc, yc)
Q = P.copy()
if 'soglia' in Q:
    Q['soglia'] = Q['soglia'].astype('Int64')  # stessa scrittura dell'originale (2612, non 2612.0)
Q['X'] = np.round(lon, 10); Q['Y'] = np.round(lat, 10)
Q.to_csv(out, index=False)
# controllo: il punto nuovo e' al centro della cella (2.5 m dai bordi) e sposta il vecchio di 1.77 m
x2, y2 = a.transform(Q.X.values, Q.Y.values)
ox = (x2 - X0) / DX % 1 * DX; oy = (Y0 - y2) / DX % 1 * DX
d = np.hypot(x2 - x, y2 - y)
print(f'offset nella cella: x {ox.min():.3f}-{ox.max():.3f} m, y {oy.min():.3f}-{oy.max():.3f} m')
print('spostamento dal punto originale (m):', pd.Series(d.round(2)).value_counts().to_dict())
