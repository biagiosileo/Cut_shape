"""
ponti.csv per rilanciare il codice (invariato) con la posizione INIZIALE dei punti, solo per i ponti spostati.
Porzioni e limiti: quelli finali (piu' ampi), cosi' il confronto misura solo l'effetto dello spostamento.
Soglia di aggancio: vuota (nella prima analisi non c'era la soglia ridotta per i fossi).

Uso: python crea_ponti_iniziali.py <ponti_iniziali.shp> <ponti.csv finale> <ponti.csv di uscita>
"""
import sys

import geopandas as gpd
import pandas as pd

shp, finale, out = sys.argv[1:4]
g = gpd.read_file(shp).to_crs(4326).set_index('ID')
P = pd.read_csv(finale).set_index('id')
mossi = g.index[g.spost_m > 0]
Q = P.loc[mossi].copy()
Q['X'] = [round(g.geometry[i].x, 10) for i in mossi]
Q['Y'] = [round(g.geometry[i].y, 10) for i in mossi]
Q['soglia'] = pd.array([pd.NA] * len(Q), dtype='Int64')
g32 = g.to_crs(32633)
for i in mossi:
    x, y = g32.geometry[i].x, g32.geometry[i].y
    r = Q.loc[i]
    if not (r.xmin < x < r.xmax and r.ymin < y < r.ymax):
        print(f'ATTENZIONE ponte {i}: punto iniziale fuori dalla porzione {r.porzione}')
Q.reset_index().to_csv(out, index=False)
print(f'{len(Q)} ponti con posizione iniziale:', list(mossi))
