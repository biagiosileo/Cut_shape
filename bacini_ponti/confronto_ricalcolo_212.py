"""
Confronto tra i parametri ricalcolati dal codice originale (porzioni/<porzione>_parametri.csv) e i parametri
calcolati gia' presenti nel database (colonne BE-BZ), ponte per ponte (ID 1-212).

Uso: python confronto_ricalcolo_212.py <Database.xlsx> <cartella porzioni> <csv di uscita>
Le unita' del database (% per pendenze) sono riportate a quelle del codice prima del confronto; una differenza
e' segnalata solo se supera l'arrotondamento del valore scritto nel database.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

dbx, pdir, out = sys.argv[1:4]
D = pd.read_excel(dbx, sheet_name=0).rename(columns={'Unnamed: 0': 'ID'})
D['ID'] = D['ID'].astype(int)
D = D.set_index('ID')

R = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(pdir, '*_parametri.csv')))])
R['ID'] = R['ID'].astype(int)
R = R.drop_duplicates('ID').set_index('ID')

# colonna del codice -> (colonna del database, fattore per portare il database alle unita' del codice)
M = {
    'A_km2': ('Area bacino calcolata (km2)', 1),
    'S': ('Pendenza media bacino calcolata %', 0.01),
    'AE_m': ('Quota media bacino (m s.l.m.)', 1),
    'Relief_m': ('Rilievo bacino (m)', 1),
    'Longest_flow_length_km': ("Lunghezza percorso di flusso piu' lungo (km)", 1),
    'Basin_Perimeter_km': ('Perimetro bacino (km)', 1),
    'Curve_Number_mean': ('Curve Number medio', 1),
    'Form_factor_FF': ('Form factor', 1),
    'Melton_relative_relief': ('Indice di Melton', 1),
    'Hypsometric_integral': ('Integrale ipsometrico', 1),
    'Elongation_ratio': ('Rapporto di allungamento', 1),
    'Shape_factor': ('Fattore di forma', 1),
    'Compactness': ('Compattezza', 1),
    'Circularity': ("Circolarita'", 1),
    'Relief_Ratio': ('Relief ratio', 1),
    'Relative_relief': ('Rilievo relativo', 1),
    'Cell_Slope': ('Pendenza cella della sezione %', 0.01),
    'Reach_Slope_Centered': ('Pendenza di tratto centrata sul ponte %', 0.01),
    'Reach_Length_Centered_m': ('Lunghezza tratto per la pendenza (m)', 1),
    'Snap_Distance_m': ('Distanza di aggancio al reticolo (m)', 1),
}


def decimali(v):
    s = repr(float(v))
    return 0 if 'e' in s or '.' not in s else len(s.split('.')[1].rstrip('0'))


rows = []
for i in R.index:
    for c, (cd, f) in M.items():
        a = R.at[i, c]
        b = pd.to_numeric(D.at[i, cd], errors='coerce')
        if pd.isna(a) and pd.isna(b):
            continue
        b2 = b * f
        # tolleranza: mezza unita' dell'ultima cifra del valore piu' arrotondato tra i due
        nd = min(decimali(a) if not pd.isna(a) else 9, decimali(b) + (2 if f == 0.01 else 0))
        tol = 0.5 * 10 ** (-nd) + 1e-12
        diff = abs(a - b2) if not (pd.isna(a) or pd.isna(b)) else np.inf
        rows.append({'ID': i, 'parametro': c, 'ricalcolo': a, 'database': b2, 'diff': diff, 'uguale': diff <= tol})
T = pd.DataFrame(rows)
T.to_csv(out, index=False)
print(f'ponti ricalcolati: {R.index.nunique()} di 212; confronti: {len(T)}; diversi: {(~T.uguale).sum()}')
if (~T.uguale).any():
    print(T[~T.uguale].to_string(index=False))
mancanti = sorted(set(range(1, 213)) - set(R.index))
print('ponti non ancora ricalcolati:', len(mancanti))
