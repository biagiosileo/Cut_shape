"""
Prepara i dati (JSON) per la relazione Word: tabelle e numeri del campione.

Uso: python relazione_prepara.py <cartella dati> <parametri_codice.csv> <Database.xlsx> <out.json>
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

dati, pcsv, dbx, out = sys.argv[1:5]
V = pd.concat([pd.read_csv(f) for f in glob.glob(os.path.join(dati, 'valori_*.csv'))]).drop_duplicates('ID').set_index('ID')
U = pd.read_csv(pcsv)
U['ID'] = U.ID.astype(int)
U = U.set_index('ID')
db = pd.read_excel(dbx).rename(columns={'Unnamed: 0': 'ID'})
db = db[pd.to_numeric(db.ID, errors='coerce').notna()]
db['ID'] = db.ID.astype(int)
db = db.set_index('ID')
ORD = [2, 1, 24, 167, 72, 106, 90, 174, 129, 154, 107]
ids = [i for i in ORD if i in V.index]
CASO = {2: 'compatibile, bacino piccolo', 1: 'compatibile, bacino medio', 24: 'compatibile, bacino grande',
        167: 'compatibile, bacino molto grande (Bradano)', 72: 'quasi compatibile, sezione spostabile < 50 m',
        106: 'quasi compatibile, bacino molto piccolo', 90: 'non compatibile, errore nelle coordinate DB',
        174: 'non compatibile, errore nel valore di area DB', 129: 'area DB sotto la soglia del reticolo',
        154: 'area di bonifica piatta (Via Idrovora)', 107: 'altro corso (Bradano Vecchio)'}


def nome(i):
    n = str(db.loc[i, 'Nome opera']).strip()
    if n in ('-', 'nan', ''):
        n = f"{str(db.loc[i, 'NUOVA NUMERAZIONE']).strip()} km {str(db.loc[i, 'Progressiva km']).strip()}"
    return n


def classe(a, adb):
    if pd.isna(adb):
        return 'senza area DB'
    d = abs(a / adb - 1)
    return 'compatibile' if d <= .15 else ('quasi compatibile' if d <= .25 else 'non compatibile')


def f(x, nd=3):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return '-'
    s = f'{x:,.{nd}f}'
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


def pct(x, nd=1):
    return '-' if x is None or (isinstance(x, float) and np.isnan(x)) else f(100 * x, nd) + '%'


R = {'ids': ids, 'campione': [], 'posizione': [], 'area': [], 'cn': [], 'lunghezze': [], 'quote': [], 'scheda': {}}
for i in ids:
    v, u = V.loc[i], U.loc[i]
    adb = pd.to_numeric(db.loc[i, 'SUPERFICIE BACINO (km2)'], errors='coerce')
    R['campione'].append([str(i), nome(i), CASO[i], f(adb, 3) if not pd.isna(adb) else '-', f(u.A_km2, 3),
                          classe(u.A_km2, adb)])
    R['posizione'].append([str(i), f(u.Snap_Distance_m, 1), v.Regola_sezione_B, f(v.Dist_sezioni_AB_m, 1)])
    R['area'].append([str(i), f(u.A_km2, 3), f(v.A_km2, 4), f(v.A_poligono_km2, 4), f(v.A_B_km2, 3),
                      pct(v.A_B_km2 / u.A_km2 - 1), pct(v.IoU_AB, 1), f(adb, 3) if not pd.isna(adb) else '-'])
    R['cn'].append([str(i), f(u.Curve_Number_mean, 2), f(v.CN_medio, 2), pct(v.Quota_area_con_CN, 0), f(v.CN_B, 2)])
    R['lunghezze'].append([str(i), f(u.Longest_flow_length_km, 3), f(v.L_km, 3), f(v.L_B_km, 3),
                           f(u.Basin_Perimeter_km, 3), f(v.P_km, 3), f(v.P_B_km, 3)])
    R['quote'].append([str(i), f(u.AE_m, 2), f(v.AE_m, 2), f(u.Relief_m, 2), f(v.Relief_m, 2), f(u.S, 5), f(v.S, 5),
                       f(u.Reach_Slope_Centered, 5), f(v.Reach_Slope, 5)])
    R['scheda'][str(i)] = {'nome': nome(i), 'caso': CASO[i], 'A_db': f(adb, 3) if not pd.isna(adb) else '-',
                           'A': f(u.A_km2, 3), 'A_B': f(v.A_B_km2, 3), 'IoU': pct(v.IoU_AB, 1),
                           'dist': f(v.Dist_sezioni_AB_m, 1), 'regola': v.Regola_sezione_B,
                           'L': f(u.Longest_flow_length_km, 3), 'L_B': f(v.L_B_km, 3), 'CN': f(u.Curve_Number_mean, 2),
                           'classe': classe(u.A_km2, adb)}

# massime differenze codice - ricalcolo (verifica dei parametri)
coppie = [('Area A (km²)', 'A_km2', 'A_km2', 0.0005), ('Pendenza media S', 'S', 'S', 5e-6),
          ('Quota media AE (m)', 'AE_m', 'AE_m', 0.005), ('Rilievo R (m)', 'Relief_m', 'Relief_m', 0.005),
          ('Percorso più lungo L (km)', 'Longest_flow_length_km', 'L_km', 0.0005),
          ('Perimetro P (km)', 'Basin_Perimeter_km', 'P_km', 0.0005), ('CN medio', 'Curve_Number_mean', 'CN_medio', 0.005),
          ('Pendenza cella di sezione', 'Cell_Slope', 'Cell_Slope', 5e-6),
          ('Pendenza tratto 500 m', 'Reach_Slope_Centered', 'Reach_Slope', 5e-6)]
R['verifica'] = []
for n, cu, cv, tol in coppie:
    d = (V.loc[ids, cv] - U.loc[ids, cu]).abs()
    fuori = [str(i) for i in ids if d[i] > tol * 1.0001]
    R['verifica'].append([n, f'{d.max():.2g}', f'{tol:g}', 'verificato' if not fuori else 'differenze: ' + ', '.join(fuori)])
# derivati
# grandezze primarie a precisione piena dal ricalcolo (coincidono con il codice, che pero' le scrive arrotondate)
A, L, Rl, AE, P = V.A_km2, V.L_km, V.Relief_m, V.AE_m, V.P_km
hmin = V.Quota_min_m
der = [('Fattore di forma FF', 'A / L²', A / L ** 2, 'Form_factor_FF'),
       ('Rilievo relativo di Melton', '(R/1000) / √A', (Rl / 1000) / np.sqrt(A), 'Melton_relative_relief'),
       ('Integrale ipsometrico HI', '(AE − h_min) / R', (AE - hmin) / Rl, 'Hypsometric_integral'),
       ('Rapporto di allungamento Re', '2·√(A/π) / L', 2 * np.sqrt(A / np.pi) / L, 'Elongation_ratio'),
       ('Fattore di forma L/√A', 'L / √A', L / np.sqrt(A), 'Shape_factor'),
       ('Compattezza Kc', 'P / (2·√(π·A))', P / (2 * np.sqrt(np.pi * A)), 'Compactness'),
       ('Circolarità Rc', '4·π·A / P²', 4 * np.pi * A / P ** 2, 'Circularity'),
       ('Rapporto di rilievo Rr', '(R/1000) / L', (Rl / 1000) / L, 'Relief_Ratio'),
       ('Rilievo relativo', 'R / (P·1000)', Rl / (P * 1000), 'Relative_relief')]
R['derivati'] = []
for n, form, val, cu in der:
    d = (val.loc[ids] - U.loc[ids, cu]).abs()
    R['derivati'].append([n, form, f'{d.max():.1g}', 'verificato' if d.max() <= 0.00051 else 'controllare'])
# esempio SCS-CN sul ponte 1
i0 = 1 if 1 in ids else ids[0]
cn = float(U.loc[i0, 'Curve_Number_mean'])
S_ = 25400 / cn - 254
Ia = 0.2 * S_
Pm = 80.0
Q = (Pm - Ia) ** 2 / (Pm - Ia + S_) if Pm > Ia else 0
R['scs'] = {'id': i0, 'CN': f(cn, 2), 'S': f(S_, 1), 'Ia': f(Ia, 1), 'P': f(Pm, 0), 'Q': f(Q, 1),
            'C': pct(Q / Pm, 0), 'A': f(float(U.loc[i0, 'A_km2']), 2), 'V': f(Q / 1000 * float(U.loc[i0, 'A_km2']) * 1e6, 0)}
# sintesi metodo B
ok = V.loc[ids]
SOGLIA_IOU = 0.90
R['sintesi'] = {'n': len(ids), 'n_ok': int((ok.IoU_AB >= SOGLIA_IOU).sum()), 'id_ok': [str(i) for i in ids if V.IoU_AB[i] >= SOGLIA_IOU],
                'id_ko': [str(i) for i in ids if V.IoU_AB[i] < SOGLIA_IOU],
                'max_diff_ok': pct(float((ok.A_B_km2 / U.loc[ids].A_km2 - 1)[ok.IoU_AB >= SOGLIA_IOU].abs().max()), 1)}
v1 = V.loc[i0]
R['es'] = {'id': i0, 'nome': nome(i0), 'A': f(U.loc[i0, 'A_km2'], 3), 'celle': f'{int(v1.A_celle):,}'.replace(',', '.'),
           'A_B': f(v1.A_B_km2, 3), 'IoU': pct(v1.IoU_AB, 1), 'L': f(U.loc[i0, 'Longest_flow_length_km'], 3),
           'AE': f(U.loc[i0, 'AE_m'], 1), 'R': f(U.loc[i0, 'Relief_m'], 1), 'HI': f(U.loc[i0, 'Hypsometric_integral'], 3),
           'hmin': f(v1.Quota_min_m, 2), 'CN': f(U.loc[i0, 'Curve_Number_mean'], 2), 'cop': pct(v1.Quota_area_con_CN, 0),
           'S': f(U.loc[i0, 'S'], 4), 'reach': f(U.loc[i0, 'Reach_Slope_Centered'], 4), 'P': f(U.loc[i0, 'Basin_Perimeter_km'], 2),
           'adb': f(pd.to_numeric(db.loc[i0, 'SUPERFICIE BACINO (km2)'], errors='coerce'), 2)}
json.dump(R, open(out, 'w'), ensure_ascii=False, indent=1)
print('ok', len(ids), 'ponti')
