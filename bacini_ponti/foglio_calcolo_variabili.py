"""
Foglio di calcolo per la verifica manuale delle variabili morfologiche (Excel con formule).
Foglio 'Esempio ponte 100' compilato con i valori misurati in QGIS durante la prova; foglio 'Modello' vuoto
da copiare per ogni ponte. Le formule delle variabili derivate sono quelle del codice pysheds_bridges_5m.py.

Uso: python foglio_calcolo_variabili.py <out.xlsx>
"""
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

out = sys.argv[1]
GIALLO = PatternFill('solid', fgColor='FFF2CC')   # celle da compilare (misure in QGIS)
VERDE = PatternFill('solid', fgColor='E2EFDA')    # celle calcolate con formula
GRIGIO = PatternFill('solid', fgColor='D9D9D9')
s = Side(style='thin', color='999999')
B = Border(top=s, bottom=s, left=s, right=s)

# (chiave, nome CSV, descrizione, unità, passo del manuale, formula Excel o None se misurata, valore QGIS es., codice es.)
RIGHE = [
    ('Misure in QGIS (celle gialle)', None, None, None, None, None, None, None),
    ('X', 'X_UTM33N', 'X UTM 33N del punto del ponte', 'm', 'B1', None, 622645.25, 622645.25),
    ('Y', 'Y_UTM33N', 'Y UTM 33N del punto del ponte', 'm', 'B1', None, 4469207.10, 4469207.1),
    ('SNAP', 'Snap_Distance_m', 'distanza ponte - cella di chiusura', 'm', 'B1', None, 1.77, 1.8),
    ('A', 'A_km2', 'area del bacino', 'km²', 'B2', None, 0.4986, 0.498),
    ('P', 'Basin_Perimeter_km', 'perimetro del bacino', 'km', 'B2', None, 5.17, 5.15),
    ('AE', 'AE_m', 'quota media del bacino (DEM non riempito)', 'm', 'B3', None, 231.22, 231.18),
    ('ZMIN', '-', 'quota minima del bacino', 'm', 'B3', None, 120.25, None),
    ('ZMAX', '-', 'quota massima del bacino', 'm', 'B3', None, 372.36, None),
    ('CN', 'Curve_Number_mean', 'Curve Number medio', '-', 'B3', None, 84.0, 84.0),
    ('S', 'S', 'pendenza media di bacino (D8, DEM riempito)', 'm/m', 'B4', None, 0.36119, 0.36128),
    ('CS', 'Cell_Slope', 'pendenza D8 nella cella di chiusura', 'm/m', 'B5', None, 0.0297, 0.0297),
    ('L', 'Longest_flow_length_km', 'percorso di flusso più lungo', 'km', 'B6', None, 1.7923, 1.792),
    ('ZUP', '-', 'quota 250 m a monte sul canale principale', 'm', 'B7', None, 130.06, None),
    ('ZDN', '-', 'quota 250 m a valle lungo il flusso', 'm', 'B7', None, 110.70, None),
    ('DUP', '-', 'distanza percorsa a monte', 'm', 'B7', None, 250, None),
    ('DDN', '-', 'distanza percorsa a valle', 'm', 'B7', None, 250, None),
    ('Variabili calcolate (celle verdi, formule del codice)', None, None, None, None, None, None, None),
    ('REL', 'Relief_m', 'rilievo = quota max − quota min', 'm', 'C', '={ZMAX}-{ZMIN}', None, 252.11),
    ('FF', 'Form_factor_FF', 'form factor = A / L²', '-', 'C', '={A}/{L}^2', None, 0.1551),
    ('MEL', 'Melton_relative_relief', 'Melton = (rilievo/1000) / √A', '-', 'C', '=({REL}/1000)/SQRT({A})', None, 0.3571),
    ('HI', 'Hypsometric_integral', 'integrale ipsometrico = (AE − min) / rilievo', '-', 'C', '=({AE}-{ZMIN})/{REL}', None, 0.44),
    ('ER', 'Elongation_ratio', 'rapporto di allungamento = 2·√(A/π) / L', '-', 'C', '=2*SQRT({A}/PI())/{L}', None, 0.4444),
    ('SF', 'Shape_factor', 'fattore di forma = L / √A', '-', 'C', '={L}/SQRT({A})', None, 2.5389),
    ('CO', 'Compactness', 'compattezza = P / (2·√(π·A))', '-', 'C', '={P}/(2*SQRT(PI()*{A}))', None, 2.058),
    ('CI', 'Circularity', 'circolarità = 4·π·A / P²', '-', 'C', '=4*PI()*{A}/{P}^2', None, 0.2361),
    ('RR', 'Relief_Ratio', 'relief ratio = (rilievo/1000) / L', '-', 'C', '=({REL}/1000)/{L}', None, 0.1407),
    ('RRE', 'Relative_relief', 'rilievo relativo = rilievo / (P·1000)', '-', 'C', '={REL}/({P}*1000)', None, 0.049),
    ('RL', 'Reach_Length_Centered_m', 'lunghezza del tratto = d monte + d valle', 'm', 'C', '={DUP}+{DDN}', None, 503.0),
    ('RS', 'Reach_Slope_Centered', 'pendenza di tratto = (z monte − z valle) / lunghezza', 'm/m', 'C',
     '=IF({RL}>0,({ZUP}-{ZDN})/{RL},{S})', None, 0.03885),
]

wb = Workbook()


def foglio(ws, esempio):
    ws['A1'] = 'Verifica manuale delle variabili morfologiche' + (' – esempio ponte 100' if esempio else ' – ponte n. ____')
    ws['A1'].font = Font(bold=True, size=13)
    ws['A2'] = ('Celle gialle: valori misurati in QGIS (passo del manuale in colonna E). Celle verdi: formule del codice. '
                'Colonna G: valore del codice (da parametri morfologici.csv). Colonna H: differenza %.')
    ws['A2'].font = Font(italic=True, size=9)
    ws.append([])
    ws.append(['Sigla', 'Colonna CSV', 'Descrizione', 'Unità', 'Passo', 'Valore verifica', 'Valore codice', 'Differenza %'])
    for c in ws[4]:
        c.font = Font(bold=True)
        c.fill = GRIGIO
        c.border = B
    pos = {}
    r = 5
    for k, csv, des, u, passo, f, vq, vc in RIGHE:
        if csv is None:
            ws.cell(r, 1, k).font = Font(bold=True)
            r += 1
            continue
        pos[k] = f'F{r}'
        r += 1
    r = 5
    for k, csv, des, u, passo, f, vq, vc in RIGHE:
        if csv is None:
            r += 1
            continue
        ws.cell(r, 1, k)
        ws.cell(r, 2, csv)
        ws.cell(r, 3, des)
        ws.cell(r, 4, u)
        ws.cell(r, 5, passo)
        cf = ws.cell(r, 6, f.format(**pos) if f else (vq if esempio else None))
        cf.fill = VERDE if f else GIALLO
        ws.cell(r, 7, vc if esempio else None)
        ws.cell(r, 8, f'=IF(OR(G{r}="",F{r}="",G{r}=0),"",F{r}/G{r}-1)')
        ws.cell(r, 8).number_format = '+0.00%;-0.00%;0.00%'
        for c in ('F', 'G'):
            ws[f'{c}{r}'].number_format = '0.0000' if u in ('-', 'm/m', 'km', 'km²') else '0.00'
        for j in range(1, 9):
            ws.cell(r, j).border = B
        r += 1
    for col, w in zip('ABCDEFGH', [7, 26, 50, 7, 7, 15, 15, 13]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = 'A5'


foglio(wb.active, True)
wb.active.title = 'Esempio ponte 100'
foglio(wb.create_sheet('Modello'), False)
wb.save(out)
print('ok', out)
