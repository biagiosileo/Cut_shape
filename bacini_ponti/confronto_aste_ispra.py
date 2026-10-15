"""
Controllo con le aste fluviali ISPRA (Reticolo Idrografico 1:250.000).

Il file AsteFluviali.shp ha un .prj che dichiara UTM 33N, ma le coordinate (e i
metadati .qmd) sono in EPSG:3857 (WGS 84 / Pseudo-Mercator): si assegna 3857 e
si riproietta in EPSG:32633. Si salva la versione corretta ritagliata sull'area.

Per ogni ponte (ID del database): asta ISPRA piu' vicina entro DIST_MAX_M
(tolleranza ampia per la scala 1:250.000), nome, ordine, bacino; confronto con
il nome del corso del reticolo regionale; area tipica per ordine (dai ponti
compatibili) come ulteriore controllo di plausibilita' dell'area DB.

Uso: python confronto_aste_ispra.py <AsteFluviali.shp> <controllo_coordinate.gpkg>
        <confronto_reticolo_riferimento.csv> <Risultati_5m_ibrido.xlsx> <out_dir>
"""
import os
import re
import sys
import warnings

import numpy as np
import pandas as pd
import geopandas as gpd

warnings.filterwarnings('ignore')
DIST_MAX_M = 300.0
TOL = 0.15
shp, cgpkg, rifcsv, xlsx, out = sys.argv[1:6]
os.makedirs(out, exist_ok=True)

A = gpd.read_file(shp).set_crs(3857, allow_override=True).to_crs(32633)
inp = gpd.read_file(cgpkg, layer='input_script').set_index('ID')
zona = inp.total_bounds
A = A.cx[zona[0] - 60000:zona[2] + 60000, zona[1] - 60000:zona[3] + 60000].copy()
A.to_file(os.path.join(out, 'aste_fluviali_ISPRA_EPSG32633.gpkg'), layer='aste_fluviali', driver='GPKG')

trc = gpd.read_file(cgpkg, layer='tracciato_usato').set_index('ID').geometry
R = pd.read_csv(rifcsv).set_index('ID')
P = pd.read_excel(xlsx, sheet_name='Ponti').set_index('ID')
adb = P['Area database (km²)']
a5 = P['Area calcolata 5 m (km²)']
ok = P['Compatibile (±15%)'] == True  # noqa: E712
si = A.sindex


def norm(s):
    s = str(s).upper()
    s = re.sub(r'\b(FIUME|TORRENTE|T\.|F\.|FOSSO|F\.SSO|FIUMARA|CANALE|VALLONE|GRAVINA|RIO|LAMA)\b', ' ', s)
    return re.sub(r'[^A-Z]', '', s)


righe = []
for i in P.index:
    g = trc[i] if i in trc.index else inp.geometry[i]
    near = [k for k in si.query(g.buffer(DIST_MAX_M)) if A.geometry.iloc[k].distance(g) <= DIST_MAX_M]
    o = {'ID': i}
    if near:
        k = min(near, key=lambda k: A.geometry.iloc[k].distance(g))
        r = A.iloc[k]
        o.update({'ISPRA_dist_m': A.geometry.iloc[k].distance(g), 'ISPRA_nome': r.nome, 'ISPRA_tipo': r.tipo,
                  'ISPRA_ordine': r.ordine, 'ISPRA_bacino': r.bacino_pri, 'ISPRA_id_fiume': r.id_fiume,
                  'ISPRA_n_aste_entro_300m': len({A.id_fiume.iloc[j] for j in near})})
    righe.append(o)
D = pd.DataFrame(righe).set_index('ID')
D['Rif_regionale_nome'] = R.Rif_nome
nr, ni = D.Rif_regionale_nome.map(norm), D.ISPRA_nome.map(norm)
D['Nomi_concordi'] = [None if (pd.isna(x) or pd.isna(y)) else bool(a and b and (a in b or b in a))
                      for x, y, a, b in zip(D.ISPRA_nome, D.Rif_regionale_nome, ni, nr)]
D['A_db'] = adb
D['A_calc'] = a5
D['Compatibile'] = ok
# area tipica per ordine ISPRA, dai ponti compatibili
cmp_ = D[ok & D.ISPRA_ordine.notna()]
tip = cmp_.groupby('ISPRA_ordine').A_calc.agg(['count', 'median', lambda s: s.quantile(.1), lambda s: s.quantile(.9)])
tip.columns = ['N_ponti_compatibili', 'Area_mediana', 'Area_P10', 'Area_P90']
D = D.join(tip[['Area_P10', 'Area_P90']], on='ISPRA_ordine')
D['DB_entro_P10_P90_ordine'] = (D.A_db >= D.Area_P10 * 0.5) & (D.A_db <= D.Area_P90 * 2)
D['Calc_entro_P10_P90_ordine'] = (D.A_calc >= D.Area_P10 * 0.5) & (D.A_calc <= D.Area_P90 * 2)
D.to_csv(os.path.join(out, 'confronto_aste_ISPRA.csv'))
pd.set_option('display.width', 250)
print('aste ISPRA nell\'area:', len(A))
print('ponti con asta ISPRA entro 300 m:', int(D.ISPRA_ordine.notna().sum()), '/ 212; con nome:',
      int(D.ISPRA_nome.notna().sum()), '; nomi concordi col reticolo regionale:',
      int((D.Nomi_concordi == True).sum()), 'su', int(D.Nomi_concordi.notna().sum()))  # noqa: E712
print(tip.round(2).to_string())
nc = D[~ok & D.A_db.notna()]
print(nc[['ISPRA_dist_m', 'ISPRA_nome', 'ISPRA_ordine', 'Rif_regionale_nome', 'A_db', 'A_calc',
          'DB_entro_P10_P90_ordine', 'Calc_entro_P10_P90_ordine']].round(1).to_string())
