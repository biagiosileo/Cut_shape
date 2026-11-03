"""
Database finale con le variabili morfologiche calcolate dal codice (copia nuova: il database originale non cambia).

Le colonne nuove (solo i parametri calcolati dal codice python, nessun confronto) sono aggiunte in fondo al
foglio, dopo l'ultima colonna del database, così le formule e i formati esistenti (AL-AN, colori delle classi
CdA, ecc.) restano invariati. SUPERFICIE BACINO e 'pendenza media tratto %' del database restano come sono.
Colori delle righe nelle colonne nuove: quasi compatibili celeste, non compatibili giallo, senza area DB grigio
(stesse classi e soglie dell'Excel di confronto aree; aree DB corrette per i refusi dei ponti 21 e 190).
Secondo foglio 'Legenda': significato dei colori e ponti di ciascuna classe.

Uso: python database_variabili_morfologiche.py <Database.xlsx> <parametri_morfologici.csv> <note.csv> <out.xlsx>
"""
import sys
from copy import copy

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

dbx, pcsv, ncsv, out = sys.argv[1:5]
P = pd.read_csv(pcsv)
P['ID'] = P.ID.astype(int)
assert P.ID.tolist() == list(range(1, 213)), 'ID non 1-212 in ordine'
P = P.set_index('ID')
N = pd.read_csv(ncsv).set_index('ID')

CELESTE = PatternFill('solid', fgColor='BDD7EE')
GIALLO = PatternFill('solid', fgColor='FFF2CC')
GRIGIO = PatternFill('solid', fgColor='D9D9D9')
sottile = Side(style='thin', color='999999')
bordo = Border(top=sottile, bottom=sottile, left=sottile, right=sottile)

wb = load_workbook(dbx)
ws = wb.worksheets[0]
# colonne del database: riga 1 = intestazioni; ID nella colonna A
COL = {ws.cell(1, c).value: c for c in range(1, ws.max_column + 1) if ws.cell(1, c).value}
c_area, c_pend = COL['SUPERFICIE BACINO (km2)'], COL['pendenza media tratto %']
ultima = max(COL.values())
riga_id = {ws.cell(r, 1).value: r for r in range(2, ws.max_row + 1) if isinstance(ws.cell(r, 1).value, (int, float))}
assert sorted(riga_id) == list(range(1, 213)), 'ID del database non 1-212'

# (intestazione, funzione che dà il valore dalla riga dei parametri, formato numerico)
pc = lambda c: (lambda p: round(100 * p[c], 2))
NUOVE = [
    ('Area bacino calcolata (km2)', lambda p: p.A_km2, '0.000'),
    ('Pendenza media bacino calcolata %', pc('S'), '0.00'),
    ('Quota media bacino (m s.l.m.)', lambda p: p.AE_m, '0.0'),
    ('Rilievo bacino (m)', lambda p: p.Relief_m, '0.0'),
    ('Lunghezza percorso di flusso piu\' lungo (km)', lambda p: p.Longest_flow_length_km, '0.000'),
    ('Perimetro bacino (km)', lambda p: p.Basin_Perimeter_km, '0.000'),
    ('Curve Number medio', lambda p: p.Curve_Number_mean, '0.00'),
    ('Form factor', lambda p: p.Form_factor_FF, '0.0000'),
    ('Indice di Melton', lambda p: p.Melton_relative_relief, '0.0000'),
    ('Integrale ipsometrico', lambda p: p.Hypsometric_integral, '0.0000'),
    ('Rapporto di allungamento', lambda p: p.Elongation_ratio, '0.0000'),
    ('Fattore di forma', lambda p: p.Shape_factor, '0.0000'),
    ('Compattezza', lambda p: p.Compactness, '0.0000'),
    ('Circolarita\'', lambda p: p.Circularity, '0.0000'),
    ('Relief ratio', lambda p: p.Relief_Ratio, '0.0000'),
    ('Rilievo relativo', lambda p: p.Relative_relief, '0.0000'),
    ('Pendenza cella della sezione %', pc('Cell_Slope'), '0.00'),
    ('Pendenza di tratto centrata sul ponte %', pc('Reach_Slope_Centered'), '0.00'),
    ('Lunghezza tratto per la pendenza (m)', lambda p: p.Reach_Length_Centered_m, '0.0'),
    ('Pendenza di tratto = pendenza di bacino (tratto troppo corto)',
     lambda p: 'si' if str(p.Reach_Slope_Centered_is_fallback) == 'True' else 'no', None),
    ('Sezione di calcolo [Lat., Long.]', lambda p: f'{p.Latitude:.6f}°, {p.Longitude:.6f}°', None),
    ('Distanza di aggancio al reticolo (m)', lambda p: p.Snap_Distance_m, '0.0'),
]
gia = [h for h, _, _ in NUOVE if h in COL]
assert not gia, f'colonne gia\' presenti nel database: {gia}'

intest = ws.cell(1, ultima)
for j, (h, f, fmt) in enumerate(NUOVE, start=ultima + 1):
    c = ws.cell(1, j, h)
    c.font, c.fill, c.alignment, c.border = copy(intest.font), copy(intest.fill), copy(intest.alignment), copy(intest.border)
    c.alignment = Alignment(wrap_text=True, horizontal='center', vertical='center')
    ws.column_dimensions[get_column_letter(j)].width = 16
ws.column_dimensions[get_column_letter(ultima + len(NUOVE) - 1)].width = 26
CLASSI = {}
for i, r in riga_id.items():
    p = P.loc[i]
    a_db = pd.to_numeric(ws.cell(r, c_area).value, errors='coerce')
    if i in N.index and pd.notna(N.loc[i, 'Area_DB_corretta']):
        a_db = float(N.loc[i, 'Area_DB_corretta'])
    if pd.isna(a_db) or a_db == 0:
        classe, fill = 'senza area DB', GRIGIO
    else:
        dA, dP = p.A_km2 - a_db, p.A_km2 / a_db - 1
        if abs(dP) <= 0.15:
            classe, fill = 'compatibile', None
        elif abs(dP) <= 0.25 or (abs(dA) <= 0.1 and abs(dP) <= 0.5):
            classe, fill = 'quasi compatibile', CELESTE
        else:
            classe, fill = 'non compatibile', GIALLO
    CLASSI.setdefault(classe, []).append(i)
    for j, (h, f, fmt) in enumerate(NUOVE, start=ultima + 1):
        v = f(p)
        if isinstance(v, float) and pd.isna(v):
            v = None
        c = ws.cell(r, j, v)
        if fmt:
            c.number_format = fmt
        c.border = bordo
        if fill is not None:
            c.fill = fill

# ---- foglio Legenda ----
lg = wb.create_sheet('Legenda')
lg['A1'] = f'Colori delle colonne {get_column_letter(ultima + 1)}-{get_column_letter(ultima + len(NUOVE))} (parametri calcolati dal codice python)'
lg['A1'].font = Font(bold=True, size=12)
lg.append([])
lg.append(['Colore', 'Classe', 'Criterio (area calcolata rispetto a SUPERFICIE BACINO)', 'N. ponti', 'ID'])
for c in lg[3]:
    c.font = Font(bold=True)
    c.border = bordo
voci = [(None, 'compatibile', '|differenza %| <= 15%'),
        (CELESTE, 'quasi compatibile', '|differenza %| <= 25%, oppure |differenza| <= 0,1 km2 e |differenza %| <= 50%'),
        (GIALLO, 'non compatibile', 'oltre le soglie precedenti'),
        (GRIGIO, 'senza area DB', 'SUPERFICIE BACINO assente nel database')]
for fill, cl, crit in voci:
    ids = CLASSI.get(cl, [])
    lg.append(['bianco' if fill is None else {'BDD7EE': 'celeste', 'FFF2CC': 'giallo', 'D9D9D9': 'grigio'}[fill.fgColor.rgb[-6:]],
               cl, crit, len(ids), 'tutti gli altri' if cl == 'compatibile' else ', '.join(map(str, ids))])
    for c in lg[lg.max_row]:
        c.border = bordo
        c.alignment = Alignment(wrap_text=True, vertical='top')
        if fill is not None:
            c.fill = fill
lg.append([])
lg.append(['Note: per i ponti 21 e 190 la classe usa l\'area del database corretta per il refuso (13,33 e 2,167 km2); '
           'la colonna SUPERFICIE BACINO non e\' modificata.'])
lg.append(['Pendenze in % (il codice le calcola in m/m). La colonna "pendenza media tratto %" del database '
           'corrisponde alla pendenza media di bacino, non a quella di tratto.'])
for col, w in zip('ABCDE', [10, 18, 60, 9, 70]):
    lg.column_dimensions[col].width = w
wb.save(out)
print('classi:', {k: len(v) for k, v in CLASSI.items()})
print(f'colonne aggiunte: {get_column_letter(ultima + 1)}-{get_column_letter(ultima + len(NUOVE))} ({len(NUOVE)})')
