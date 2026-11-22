"""
Foglio Confronto della verifica di un ponte, con lo stesso schema del file dell'ID100: misure QGIS (colonna D),
valori del codice (colonne F e K), formule della parte C (colonna J). Aggiunge il foglio Note con differenze e
modalita' di esecuzione.

Uso: python excel_verifica_manuale.py <xlsm ID100> <misure.json> <parametri morfologici.csv> <ID> <note.txt> <out.xlsx>
"""
import json
import sys

import openpyxl
import pandas as pd
from openpyxl.styles import Alignment, Font

modello, mis, csvp, ID, note, out = sys.argv[1:7]
ID = int(ID)
m = json.load(open(mis))
c = pd.read_csv(csvp)
c = c[c.ID.astype(int) == ID].iloc[0]
wb = openpyxl.load_workbook(modello)
for s in wb.sheetnames:
    if s != 'Confronto':
        del wb[s]
ws = wb['Confronto']
ws['A1'] = f'Parametri misurati in QGIS Ponte ID_{ID}'
nomi = ['ponte_xyg'] * 4 + ['sezione'] * 2 + ['bacino'] * 3 + ['dem_m.tif'] * 2 + ['bacino'] * 2 + \
       ['sezione_pendenza', 'percorso_piu_lungo', 'percorso_sezione_lung', 'punto_monte_quota', 'punto_valle_quota']
for r, n in enumerate(nomi, 2):
    ws.cell(r, 1, f'p{ID}_{n}')
ws['B8'] = f'geometria ({int(m["accumulo_sezione"])} celle x 25 m²)'
ws['B15'] = 'CS_1'
ws['B14'] = 'S_mean'
D = {'X': (m['X'], 2), 'Y': (m['Y'], 2), 'LON': (m['LON'], 6), 'LAT': (m['LAT'], 6), 'XS': (m['XS'], 2),
     'YS': (m['YS'], 2), 'A': (m['A'], 4), 'P': (m['P'], 3), 'AE': (m['AE'], 2), 'ZMIN': (m['ZMIN'], 2),
     'ZMAX': (m['ZMAX'], 2), 'CN': (m['CN'], 2), 'S': (m['S'], 5), 'CS': (m['CS'], 4), 'LMAX': (m['LMAX'], 2),
     'LSEZ': (m['LSEZ'], 2), 'ZUP': (m['ZUP'], 2), 'ZDN': (m['ZDN'], 2), 'DUP': (m['DUP'], 0), 'DDN': (m['DDN'], 0)}
F = {'X': c.X_UTM33N, 'Y': c.Y_UTM33N, 'LON': c.Longitude, 'LAT': c.Latitude, 'XS': '-', 'YS': '-', 'A': c.A_km2,
     'P': c.Basin_Perimeter_km, 'AE': c.AE_m, 'ZMIN': '-', 'ZMAX': '-', 'CN': c.Curve_Number_mean, 'S': c.S,
     'CS': c.Cell_Slope}
for r in range(2, 22):
    s = ws.cell(r, 3).value
    v, nd = D[s]
    ws.cell(r, 4, round(float(v), nd) if nd else int(v))
    ws.cell(r, 6, F.get(s))
K = [c.Snap_Distance_m, c.Longest_flow_length_km, c.Relief_m, c.Form_factor_FF, c.Melton_relative_relief,
     c.Hypsometric_integral, c.Elongation_ratio, c.Shape_factor, c.Compactness, c.Circularity, c.Relief_Ratio,
     c.Relative_relief, c.Reach_Length_Centered_m, c.Reach_Slope_Centered,
     'true' if str(c.Reach_Slope_Centered_is_fallback).lower() == 'true' else 'false']
for r, v in enumerate(K, 2):
    ws.cell(r, 11, v)
ws.cell(16, 10, 'tratto tracciato' if m['FB'] == 'no' else 'fallback: S')
# colonna L: differenza % tra applicazione e codice
ws.cell(1, 12, 'Differenza %').font = Font(bold=True)
for r in range(2, 16):
    ws.cell(r, 12, f'=IFERROR((J{r}-K{r})/K{r}*100,"-")').number_format = '0.0'
n = wb.create_sheet('Note')
n.column_dimensions['A'].width = 130
for i, riga in enumerate(open(note, encoding='utf-8').read().splitlines(), 1):
    n.cell(i, 1, riga).alignment = Alignment(wrap_text=True, vertical='top')
wb.save(out)
print('salvato', out)
