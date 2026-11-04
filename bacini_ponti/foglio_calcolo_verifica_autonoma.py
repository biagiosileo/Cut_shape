"""
Foglio di calcolo per la verifica autonoma delle variabili morfologiche (input: shape ponti_analisi, DEM unito, CN).
Fogli:
  1 Calcolo ponte 100       misure in QGIS (giallo) e variabili calcolate con le formule (verde), con il calcolo a mano
  2 Confronto ponte 100     confronto A POSTERIORI con parametri morfologici.csv (si compila solo alla fine)
  3 Modello calcolo / 4 Modello confronto   da copiare per ogni ponte
Uso: python foglio_calcolo_verifica_autonoma.py <out.xlsx>
"""
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

out = sys.argv[1]
GIALLO = PatternFill('solid', fgColor='FFF2CC')
VERDE = PatternFill('solid', fgColor='E2EFDA')
AZZURRO = PatternFill('solid', fgColor='DDEBF7')
GRIGIO = PatternFill('solid', fgColor='D9D9D9')
s = Side(style='thin', color='999999')
B = Border(top=s, bottom=s, left=s, right=s)

# sigla, descrizione, unità, passo, formula (None = misura), valore esempio, calcolo a mano (esempio), formato
CALC = [
    ('Misure in QGIS', ),
    ('X', 'X UTM 33N del ponte (utm_x)', 'm', 'B1', None, 622645.25, '', '0.00'),
    ('Y', 'Y UTM 33N del ponte (utm_y)', 'm', 'B1', None, 4469207.10, '', '0.00'),
    ('LON', 'longitudine WGS84 del ponte (wgs_x)', '°', 'B1', None, 16.444488348, '', '0.000000000'),
    ('LAT', 'latitudine WGS84 del ponte (wgs_y)', '°', 'B1', None, 40.364421474, '', '0.000000000'),
    ('XS', 'X del centro della cella di chiusura', 'm', 'A4', None, 622646.50, '', '0.00'),
    ('YS', 'Y del centro della cella di chiusura', 'm', 'A4', None, 4469205.85, '', '0.00'),
    ('A', 'area del bacino (area_km2)', 'km²', 'B2', None, 0.4986, '', '0.0000'),
    ('P', 'perimetro del bacino (perim_km)', 'km', 'B2', None, 5.17, '', '0.000'),
    ('AE', 'quota media, DEM in metri non riempito (dem_mean)', 'm', 'B3', None, 231.22, '', '0.00'),
    ('ZMIN', 'quota minima (dem_min)', 'm', 'B3', None, 120.25, '', '0.00'),
    ('ZMAX', 'quota massima (dem_max)', 'm', 'B3', None, 372.36, '', '0.00'),
    ('CN', 'Curve Number medio (cn_mean)', '-', 'B3', None, 84.0, '', '0.00'),
    ('S', 'pendenza media di bacino D8 (S_mean)', 'm/m', 'B4', None, 0.36119, '', '0.00000'),
    ('CS', 'pendenza D8 della cella di chiusura (pend_1)', 'm/m', 'B5', None, 0.0297, '', '0.0000'),
    ('LMAX', 'lunghezza massima dei percorsi dalle celle sorgenti', 'm', 'B6', None, 5575.23, '', '0.00'),
    ('LSEZ', 'lunghezza del percorso dalla sezione', 'm', 'B6', None, 3782.91, '', '0.00'),
    ('ZUP', 'quota del punto 250 m a monte', 'm', 'B7', None, 130.06, '', '0.00'),
    ('ZDN', 'quota del punto 250 m a valle', 'm', 'B7', None, 110.70, '', '0.00'),
    ('DUP', 'distanza a monte', 'm', 'B7', None, 250, '', '0'),
    ('DDN', 'distanza a valle', 'm', 'B7', None, 250, '', '0'),
    ('FB', 'tratto non tracciabile? (si/no)', '-', 'B7', None, 'no', '', None),
    ('Variabili calcolate (formule)', ),
    ('SNAP', 'distanza ponte - cella di chiusura = √((XS−X)² + (YS−Y)²)', 'm', 'C', '=SQRT(({XS}-{X})^2+({YS}-{Y})^2)',
     None, '√(1,25² + 1,25²) = √3,1250 = 1,77', '0.00'),
    ('L', 'percorso di flusso più lungo = (LMAX − LSEZ) / 1000', 'km', 'C', '=({LMAX}-{LSEZ})/1000', None,
     '(5575,23 − 3782,91) / 1000 = 1,7923', '0.0000'),
    ('REL', 'rilievo = ZMAX − ZMIN', 'm', 'C', '={ZMAX}-{ZMIN}', None, '372,36 − 120,25 = 252,11', '0.00'),
    ('FF', 'form factor = A / L²', '-', 'C', '={A}/{L}^2', None, '0,4986 / 1,7923² = 0,4986 / 3,2124 = 0,1552', '0.0000'),
    ('MEL', 'Melton = (REL/1000) / √A', '-', 'C', '=({REL}/1000)/SQRT({A})', None,
     '0,25211 / √0,4986 = 0,25211 / 0,7061 = 0,3570', '0.0000'),
    ('HI', 'integrale ipsometrico = (AE − ZMIN) / REL', '-', 'C', '=({AE}-{ZMIN})/{REL}', None,
     '(231,22 − 120,25) / 252,11 = 110,97 / 252,11 = 0,4402', '0.0000'),
    ('ER', 'rapporto di allungamento = 2·√(A/π) / L', '-', 'C', '=2*SQRT({A}/PI())/{L}', None,
     '2·√(0,4986/3,1416) / 1,7923 = 2·0,3984 / 1,7923 = 0,4445', '0.0000'),
    ('SF', 'fattore di forma = L / √A', '-', 'C', '={L}/SQRT({A})', None, '1,7923 / 0,7061 = 2,5383', '0.0000'),
    ('CO', 'compattezza = P / (2·√(π·A))', '-', 'C', '={P}/(2*SQRT(PI()*{A}))', None,
     '5,17 / (2·√1,5664) = 5,17 / (2·1,2516) = 2,0654', '0.0000'),
    ('CI', 'circolarità = 4·π·A / P²', '-', 'C', '=4*PI()*{A}/{P}^2', None, '6,2656 / 26,7289 = 0,2344', '0.0000'),
    ('RR', 'relief ratio = (REL/1000) / L', '-', 'C', '=({REL}/1000)/{L}', None, '0,25211 / 1,7923 = 0,1407', '0.0000'),
    ('RRE', 'rilievo relativo = REL / (P·1000)', '-', 'C', '={REL}/({P}*1000)', None, '252,11 / 5170 = 0,0488', '0.0000'),
    ('RL', 'lunghezza del tratto = DUP + DDN', 'm', 'C', '={DUP}+{DDN}', None, '250 + 250 = 500', '0'),
    ('RS', 'pendenza di tratto = (ZUP − ZDN) / RL  (se FB = si: S)', 'm/m', 'C',
     '=IF({FB}="si",{S},({ZUP}-{ZDN})/{RL})', None, '(130,06 − 110,70) / 500 = 19,36 / 500 = 0,0387', '0.0000'),
]
# colonna del CSV del codice -> sigla del foglio Calcolo
CONF = [('Longitude', 'LON'), ('Latitude', 'LAT'), ('X_UTM33N', 'X'), ('Y_UTM33N', 'Y'), ('Snap_Distance_m', 'SNAP'),
        ('A_km2', 'A'), ('S', 'S'), ('AE_m', 'AE'), ('Longest_flow_length_km', 'L'), ('Relief_m', 'REL'),
        ('Form_factor_FF', 'FF'), ('Curve_Number_mean', 'CN'), ('Melton_relative_relief', 'MEL'),
        ('Hypsometric_integral', 'HI'), ('Elongation_ratio', 'ER'), ('Shape_factor', 'SF'), ('Cell_Slope', 'CS'),
        ('Reach_Slope_Centered', 'RS'), ('Reach_Length_Centered_m', 'RL'), ('Reach_Slope_Centered_is_fallback', 'FB'),
        ('Basin_Perimeter_km', 'P'), ('Compactness', 'CO'), ('Circularity', 'CI'), ('Relief_Ratio', 'RR'),
        ('Relative_relief', 'RRE')]
CODICE_100 = {'Longitude': 16.444488348, 'Latitude': 40.364421474, 'X_UTM33N': 622645.25, 'Y_UTM33N': 4469207.1,
              'Snap_Distance_m': 1.8, 'A_km2': 0.498, 'S': 0.36128, 'AE_m': 231.18, 'Longest_flow_length_km': 1.792,
              'Relief_m': 252.11, 'Form_factor_FF': 0.1551, 'Curve_Number_mean': 84.0, 'Melton_relative_relief': 0.3571,
              'Hypsometric_integral': 0.44, 'Elongation_ratio': 0.4444, 'Shape_factor': 2.5389, 'Cell_Slope': 0.0297,
              'Reach_Slope_Centered': 0.03885, 'Reach_Length_Centered_m': 503.0,
              'Reach_Slope_Centered_is_fallback': 'False', 'Basin_Perimeter_km': 5.15, 'Compactness': 2.058,
              'Circularity': 0.2361, 'Relief_Ratio': 0.1407, 'Relative_relief': 0.049}


def calcolo(ws, esempio):
    ws['A1'] = 'Verifica autonoma – calcolo delle variabili morfologiche' + (' – esempio ponte 100' if esempio else ' – ponte n. ____')
    ws['A1'].font = Font(bold=True, size=13)
    ws['A2'] = ('Input: shape ponti_analisi, DEM unito, Curve Number. Celle gialle: misure in QGIS (passo del manuale). '
                'Celle verdi: formule. Colonna G: calcolo a mano. Il confronto con il codice si fa solo alla fine, '
                'nell\'altro foglio.')
    ws['A2'].font = Font(italic=True, size=9)
    ws.append([])
    ws.append(['Sigla', 'Descrizione', 'Unità', 'Passo', 'Valore', '', 'Calcolo a mano'])
    for c in ws[4]:
        c.font = Font(bold=True)
        c.fill = GRIGIO
        c.border = B
    pos, r = {}, 5
    for riga in CALC:
        if len(riga) > 1:
            pos[riga[0]] = f'$E${r}'
        r += 1
    r = 5
    for riga in CALC:
        if len(riga) == 1:
            ws.cell(r, 1, riga[0]).font = Font(bold=True)
            r += 1
            continue
        k, des, u, passo, f, v, mano, fmt = riga
        for j, val in enumerate([k, des, u, passo], start=1):
            ws.cell(r, j, val).border = B
        c = ws.cell(r, 5, f.format(**pos) if f else (v if esempio else None))
        c.fill = VERDE if f else GIALLO
        c.border = B
        if fmt:
            c.number_format = fmt
        g = ws.cell(r, 7, mano if esempio else None)
        g.border = B
        if f:
            g.fill = AZZURRO
        r += 1
    for col, w in zip('ABCDEFG', [7, 58, 6, 6, 16, 2, 52]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = 'A5'
    return pos


def confronto(ws, nome_calc, pos, esempio):
    ws['A1'] = 'Confronto A POSTERIORI con il codice (parametri morfologici.csv)' + (' – ponte 100' if esempio else '')
    ws['A1'].font = Font(bold=True, size=13)
    ws['A2'] = ('Da compilare solo dopo aver terminato il foglio di calcolo: si copia nella colonna C il valore della '
                'riga del ponte in parametri morfologici.csv.')
    ws['A2'].font = Font(italic=True, size=9)
    ws.append([])
    ws.append(['Colonna del CSV', 'Valore verifica', 'Valore codice', 'Differenza %'])
    for c in ws[4]:
        c.font = Font(bold=True)
        c.fill = GRIGIO
        c.border = B
    for i, (col, sig) in enumerate(CONF, start=5):
        ws.cell(i, 1, col)
        ws.cell(i, 2, f"='{nome_calc}'!{pos[sig]}")
        cc = ws.cell(i, 3, CODICE_100[col] if esempio else None)
        cc.fill = GIALLO
        ws.cell(i, 4, f'=IF(OR(C{i}="",ISTEXT(B{i}),ISTEXT(C{i}),C{i}=0),"",B{i}/C{i}-1)')
        ws.cell(i, 4).number_format = '+0.00%;-0.00%;0.00%'
        ws.cell(i, 2).number_format = ws.cell(i, 3).number_format = '0.0000' if col not in (
            'Longitude', 'Latitude') else '0.000000000'
        for j in range(1, 5):
            ws.cell(i, j).border = B
    for col, w in zip('ABCD', [34, 16, 16, 14]):
        ws.column_dimensions[col].width = w


wb = Workbook()
w1 = wb.active
w1.title = 'Calcolo ponte 100'
p1 = calcolo(w1, True)
confronto(wb.create_sheet('Confronto ponte 100'), 'Calcolo ponte 100', p1, True)
p3 = calcolo(wb.create_sheet('Modello calcolo'), False)
confronto(wb.create_sheet('Modello confronto'), 'Modello calcolo', p3, False)
wb.save(out)
print('ok', out)
