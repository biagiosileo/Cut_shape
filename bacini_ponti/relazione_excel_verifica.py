"""
Excel di verifica del codice sul campione:
  Legenda              come si usa
  Grandezze primarie   codice vs ricalcolo indipendente (differenze come formule)
  Parametri derivati   grandezze primarie in blu (modificabili a mano) e indici calcolati con le
                       stesse formule del codice, confrontati con il valore del codice
  Metodo indipendente  bacino A (codice) vs bacino B (WhiteboxTools): area, IoU, sezioni, L, quote, CN

Uso: python relazione_excel_verifica.py <cartella dati> <parametri_codice.csv> <Database.xlsx> <out.xlsx>
"""
import glob
import os
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.formatting.rule import FormulaRule

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
        106: 'quasi compatibile, bacino molto piccolo', 90: 'non compatibile, errore coordinate DB',
        174: 'non compatibile, errore valore area DB', 129: 'area DB sotto soglia del reticolo',
        154: 'area di bonifica piatta', 107: 'altro corso (Bradano Vecchio)'}

AR = 'Arial'
F, FB = Font(name=AR, size=10), Font(name=AR, size=10, bold=True)
FBLU = Font(name=AR, size=10, color='0000FF')
HEAD = PatternFill('solid', fgColor='D9D9D9')
GIALLO = PatternFill('solid', fgColor='FFF2CC')
VERDE = PatternFill('solid', fgColor='E2EFDA')
ROSSO = PatternFill('solid', fgColor='F8CBAD')
thin = Side(style='thin', color='BFBFBF')
B = Border(left=thin, right=thin, top=thin, bottom=thin)
wb = Workbook()


def intest(ws, row, labels, widths=None):
    for k, t in enumerate(labels, 1):
        c = ws.cell(row, k, t)
        c.font, c.fill, c.border = FB, HEAD, B
        c.alignment = Alignment(wrap_text=True, horizontal='center', vertical='center')
    ws.row_dimensions[row].height = 45
    if widths:
        for k, w in enumerate(widths, 1):
            ws.column_dimensions[ws.cell(row, k).column_letter].width = w


# ---------------- Legenda ----------------
ws = wb.active
ws.title = 'Legenda'
testo = [
    ('Verifica del codice pysheds_bridges_5m.py su un campione di ponti', FB),
    ('', F),
    ('Grandezze primarie: valori del codice (file NEW_parametri_morfologici.csv) e valori ricalcolati con codice '
     'indipendente sullo stesso bacino; le differenze sono formule.', F),
    ('Parametri derivati: le celle in BLU sono le grandezze primarie del codice, modificabili a mano una a una; '
     'gli indici sono formule identiche a quelle del codice e si ricalcolano subito. La colonna "codice" riporta il '
     'valore scritto dal codice, la colonna "diff." la differenza (verde se entro l\'arrotondamento).', F),
    ('Metodo indipendente: confronto tra il bacino del codice (A, pysheds) e quello ricavato in modo indipendente '
     '(B, WhiteboxTools con breaching e sezione ricavata di nuovo dal tracciato KML). IoU = area comune / area unione.', F),
    ('', F),
    ('Formule del codice (A in km², L in km, R in m, P in km, AE e h_min in m):', FB),
    ('FF = A / L²   ·   Melton = (R/1000) / √A   ·   HI = (AE − h_min) / R   ·   Re = 2·√(A/π) / L', F),
    ('Shape factor = L / √A   ·   Kc = P / (2·√(π·A))   ·   Rc = 4·π·A / P²   ·   Rr = (R/1000) / L   ·   '
     'Rilievo relativo = R / (P·1000)', F),
]
for k, (t, f) in enumerate(testo, 1):
    c = ws.cell(k, 1, t)
    c.font = f
    c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.row_dimensions[k].height = 32 if len(t) > 110 else 16
ws.column_dimensions['A'].width = 140

# ---------------- Grandezze primarie ----------------
ws = wb.create_sheet('Grandezze primarie')
# (colonna codice, colonna ricalcolo, nome, formato, tolleranza = mezza unita' dell'arrotondamento del codice)
grandezze = [('A_km2', 'A_km2', 'Area A (km²)', '0.0000', 0.0005), ('S', 'S', 'Pendenza media S (-)', '0.00000', 5e-6),
             ('AE_m', 'AE_m', 'Quota media AE (m)', '0.00', 0.005), ('Relief_m', 'Relief_m', 'Rilievo R (m)', '0.00', 0.005),
             ('Longest_flow_length_km', 'L_km', 'Percorso più lungo L (km)', '0.000', 0.0005),
             ('Basin_Perimeter_km', 'P_km', 'Perimetro P (km)', '0.000', 0.0005),
             ('Curve_Number_mean', 'CN_medio', 'CN medio (-)', '0.00', 0.005),
             ('Cell_Slope', 'Cell_Slope', 'Pendenza della cella di sezione (-)', '0.00000', 5e-6),
             ('Reach_Slope_Centered', 'Reach_Slope', 'Pendenza del tratto 500 m (-)', '0.00000', 5e-6)]
lab = ['ID', 'Caso']
for _, _, n, _, _ in grandezze:
    lab += [f'{n}\ncodice', f'{n}\nricalcolo', 'diff.']
intest(ws, 1, lab, [6, 30] + [13, 13, 9] * len(grandezze))
for r, i in enumerate(ids, 2):
    ws.cell(r, 1, i).font = F
    ws.cell(r, 2, CASO.get(i, '')).font = F
    for k, (cu, cv, n, fmt, tol) in enumerate(grandezze):
        c0 = 3 + 3 * k
        a = ws.cell(r, c0, float(U.loc[i, cu]))
        b = ws.cell(r, c0 + 1, float(V.loc[i, cv]))
        L1, L2 = a.column_letter, b.column_letter
        d = ws.cell(r, c0 + 2, f'={L2}{r}-{L1}{r}')
        for c in (a, b, d):
            c.number_format, c.font, c.border = fmt, F, B
        ws.conditional_formatting.add(f'{d.column_letter}{r}', FormulaRule(
            formula=[f'ABS({d.column_letter}{r})<={tol * 1.0001}'], fill=VERDE))
        ws.conditional_formatting.add(f'{d.column_letter}{r}', FormulaRule(
            formula=[f'ABS({d.column_letter}{r})>{tol * 1.0001}'], fill=ROSSO))
ws.freeze_panes = 'C2'
nr = len(ids) + 3
ws.cell(nr, 1, 'Verde: differenza entro l\'arrotondamento con cui il codice scrive il valore (A e L a 3 decimali, quote '
               'e CN a 2, pendenze a 5). Ponte 167: ricalcolo in precisione singola (limite di memoria).').font = F

# ---------------- Parametri derivati ----------------
ws = wb.create_sheet('Parametri derivati')
inp = ['A (km²)', 'L (km)', 'R (m)', 'AE (m)', 'h_min (m)', 'P (km)']
der = [('FF', 'Form_factor_FF', '=B{r}/C{r}^2'),
       ('Melton', 'Melton_relative_relief', '=(D{r}/1000)/SQRT(B{r})'),
       ('HI', 'Hypsometric_integral', '=(E{r}-F{r})/D{r}'),
       ('Re', 'Elongation_ratio', '=2*SQRT(B{r}/PI())/C{r}'),
       ('Shape factor', 'Shape_factor', '=C{r}/SQRT(B{r})'),
       ('Kc', 'Compactness', '=G{r}/(2*SQRT(PI()*B{r}))'),
       ('Rc', 'Circularity', '=4*PI()*B{r}/G{r}^2'),
       ('Rr', 'Relief_Ratio', '=(D{r}/1000)/C{r}'),
       ('Rilievo relativo', 'Relative_relief', '=D{r}/(G{r}*1000)')]
lab = ['ID'] + inp
for n, _, _ in der:
    lab += [f'{n}\nformula', f'{n}\ncodice', 'diff.']
intest(ws, 1, lab, [6] + [11] * 6 + [11, 11, 9] * len(der))
for r, i in enumerate(ids, 2):
    ws.cell(r, 1, i).font = F
    # valori a precisione piena del ricalcolo (uguali a quelli del codice, che li scrive arrotondati)
    vals = [V.loc[i, 'A_km2'], V.loc[i, 'L_km'], V.loc[i, 'Relief_m'], V.loc[i, 'AE_m'],
            V.loc[i, 'Quota_min_m'], V.loc[i, 'P_km']]
    for k, v in enumerate(vals, 2):
        c = ws.cell(r, k, float(v))
        c.font, c.border, c.fill = FBLU, B, GIALLO
        c.number_format = '0.000000'
    for k, (n, cu, f) in enumerate(der):
        c0 = 8 + 3 * k
        a = ws.cell(r, c0, f.format(r=r))
        b = ws.cell(r, c0 + 1, float(U.loc[i, cu]))
        d = ws.cell(r, c0 + 2, f'={a.column_letter}{r}-{b.column_letter}{r}')
        for c in (a, b, d):
            c.font, c.border, c.number_format = F, B, '0.0000'
        ws.conditional_formatting.add(f'{d.column_letter}{r}',
                                      FormulaRule(formula=[f'ABS({d.column_letter}{r})<=0.0006'], fill=VERDE))
        ws.conditional_formatting.add(f'{d.column_letter}{r}',
                                      FormulaRule(formula=[f'ABS({d.column_letter}{r})>0.0006'], fill=ROSSO))
ws.freeze_panes = 'B2'
nr = len(ids) + 3
ws.cell(nr, 1, 'Celle gialle con testo blu: grandezze primarie a precisione piena (uguali a quelle del codice, che le '
               'scrive arrotondate), modificabili a mano. h_min dal ricalcolo (il codice non la scrive). '
               'Verde: |diff.| ≤ 0,0006 (il codice arrotonda gli indici a 4 decimali).').font = F

# ---------------- Metodo indipendente ----------------
ws = wb.create_sheet('Metodo indipendente')
lab = ['ID', 'Caso', 'Area DB (km²)', 'Area A codice (km²)', 'Area B indipendente (km²)', 'Diff. B/A', 'IoU',
       'Solo in A (km²)', 'Solo in B (km²)', 'Distanza sezioni A-B (m)', 'Regola sezione B', 'L A (km)', 'L B (km)',
       'AE A (m)', 'AE B (m)', 'CN A', 'CN B', 'Diff. A vs DB', 'Diff. B vs DB']
intest(ws, 1, lab, [6, 30, 11, 11, 11, 9, 8, 10, 10, 11, 34, 9, 9, 9, 9, 8, 8, 10, 10])
for r, i in enumerate(ids, 2):
    v = V.loc[i]
    adb = pd.to_numeric(db.loc[i, 'SUPERFICIE BACINO (km2)'], errors='coerce')
    row = [i, CASO.get(i, ''), None if pd.isna(adb) else float(adb), float(U.loc[i, 'A_km2']), float(v.A_B_km2),
           f'=E{r}/D{r}-1', float(v.IoU_AB), float(v.Solo_A_km2), float(v.Solo_B_km2), float(v.Dist_sezioni_AB_m),
           v.Regola_sezione_B, float(U.loc[i, 'Longest_flow_length_km']), float(v.L_B_km), float(U.loc[i, 'AE_m']),
           float(v.AE_B_m), float(U.loc[i, 'Curve_Number_mean']), float(v.CN_B),
           f'=IF(C{r}="","",D{r}/C{r}-1)', f'=IF(C{r}="","",E{r}/C{r}-1)']
    for k, val in enumerate(row, 1):
        if isinstance(val, float) and val != val:  # NaN -> cella vuota
            val = None
        c = ws.cell(r, k, val)
        c.font, c.border = F, B
        if k in (6, 7, 18, 19):
            c.number_format = '0.0%'
        elif k in (3, 4, 5, 8, 9):
            c.number_format = '0.000'
        elif k in (10, 14, 15, 16, 17):
            c.number_format = '0.0'
        elif k in (12, 13):
            c.number_format = '0.000'
    ws.conditional_formatting.add(f'G{r}', FormulaRule(formula=[f'G{r}>=0.90'], fill=VERDE))
    ws.conditional_formatting.add(f'G{r}', FormulaRule(formula=[f'G{r}<0.90'], fill=ROSSO))
ws.freeze_panes = 'C2'
wb.save(out)
print('salvato', out, len(ids), 'ponti')
