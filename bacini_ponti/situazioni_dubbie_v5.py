"""
Situazioni dubbie, versione 5 (snella): stessi contenuti della versione 4, organizzati per la lettura.
  Database_situazioni_dubbie.xlsx  fogli "Situazioni dubbie" (36 ponti, 11 colonne, non compatibili per primi),
                                   "Database completo" (212 ponti, colonne originali + classe, categoria, nota;
                                   righe segnalate colorate), "Legenda"
  situazioni_dubbie.gpkg           ponti, tracciato_kml, aste_sotto_il_ponte, bacini_segnalati, reticolo (con stili)
Il progetto QGIS si costruisce con progetto_qgis_v5.py.

Uso: python situazioni_dubbie_v5.py <Database.xlsx originale> <cartella v4> <cartella uscita>
"""
import os
import sqlite3
import sys
from copy import copy

import geopandas as gpd
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

dbx, v4, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
T = pd.read_csv(os.path.join(v4, 'situazioni_dubbie_212.csv')).set_index('ID', drop=False)
g4 = os.path.join(v4, 'situazioni_dubbie.gpkg')

CAT = ['canali di bonifica', 'multi-asta', 'area relazione non riproducibile', 'quasi compatibile',
       'sezione lontana dal ponte', 'coordinate database errate', 'anagrafica KML incongruente']
COL = {'canali di bonifica': 'C9D6F0', 'multi-asta': 'D9C3E9', 'area relazione non riproducibile': 'F4B6B6',
       'quasi compatibile': 'FBD5A8', 'sezione lontana dal ponte': 'FFF2A8', 'coordinate database errate': 'BFE6E6',
       'anagrafica KML incongruente': 'D9D9D9'}
HEX = {'canali di bonifica': '#2c7bb6', 'multi-asta': '#8e44ad', 'area relazione non riproducibile': '#d7191c',
       'quasi compatibile': '#f39c33', 'sezione lontana dal ponte': '#e6c700', 'coordinate database errate': '#1b9e9e',
       'anagrafica KML incongruente': '#7f7f7f'}
SIGN = {'canali di bonifica': 'pianura con canali: il canale non e\' rappresentato nel DEM e il bacino calcolato '
                              'puo\' essere incompleto',
        'multi-asta': 'sotto il ponte passano piu\' aste; la sezione e\' sull\'asta indicata dalla relazione',
        'area relazione non riproducibile': 'nessuna sezione vicino al ponte riproduce l\'area della relazione',
        'quasi compatibile': 'differenza entro il 25%, oppure entro 0.1 km2 e il 50%',
        'sezione lontana dal ponte': 'sezione di calcolo a piu\' di 50 m dal ponte del database',
        'coordinate database errate': 'un estremo del ponte nel database e\' lontano dal ponte; sezione corretta',
        'anagrafica KML incongruente': 'nel KML il nome del ponte e\' associato a un\'altra progressiva; sezione corretta'}
AZ = {'canali di bonifica': 'verificare l\'estensione del bacino lungo il canale',
      'multi-asta': 'confermare quale asta attraversa il ponte',
      'area relazione non riproducibile': 'verificare l\'area o la sezione di chiusura della relazione',
      'quasi compatibile': 'nessuna',
      'sezione lontana dal ponte': 'verificare la posizione del ponte',
      'coordinate database errate': 'correggere le coordinate nel database',
      'anagrafica KML incongruente': 'correggere l\'abbinamento nel KML'}
NOTA = {
    13: 'calcolo 4.09 km2 lungo un canale in pianura; la relazione (18.06 km2) descrive un bacino collinare',
    154: 'come il 13 (relazione 18.6 km2, calcolo 4.09 km2); sul tracciato anche un fosso da 0.51 km2',
    15: 'canale artificiale di scolo in pianura costiera; area della relazione assente; 4.00 km2 confermati dalla verifica manuale',
    107: 'sotto il ponte passa anche un canale da 7.16 km2; sezione e relazione sul ramo piccolo (0.72 km2)',
    108: 'sotto il ponte passa anche un canale da 9.18 km2; sezione e relazione sul ramo accanto (0.27 km2)',
    109: 'sotto il ponte passa anche un canale da 6.64 km2; sezione sul fosso laterale (0.26 km2, relazione 0.31)',
    111: 'sezione sul torrente a 81 m (15.79 km2, relazione 14.5); nel punto del database c\'e\' un fosso da 0.14 km2',
    196: 'sotto il ponte passa l\'asta principale da 87.0 km2; sezione e relazione sull\'affluente (0.83 km2)',
    19: 'sotto il ponte 0.131 km2; un bacino di 0.63 km2 si chiude a circa 925 m dal ponte',
    58: 'sotto il ponte 58.1 km2; nessuna sezione entro 1 km riproduce 2.63 km2',
    72: 'sotto il ponte 95.0 km2 contro 116.1 (-18%); nessuna asta alternativa vicino al ponte',
    117: 'sotto il ponte 0.081 km2; un bacino di 0.38 km2 si chiude a circa 460 m dal ponte',
    118: 'sotto il ponte 0.751 km2; un bacino di 0.45 km2 si chiude a circa 900 m dal ponte',
    164: 'il ponte scavalca un corso d\'acqua da 215.6 km2; la relazione indica 0.75 km2',
    174: 'sotto il ponte 22.3 km2; nessuna sezione entro 2 km riproduce 6.83 km2',
    14: 'sezione a 204 m dal ponte del database; area della relazione assente',
    82: 'viadotto di 1.2 km; sezione a 110 m dall\'asse del database',
    98: 'sezione a 165 m dal ponte del database',
    155: 'sezione a 127 m dal ponte del database (zona con buco del DEM riempito)',
    73: 'coordinata finale del database a 1.0 km dal ponte; sezione a 7 m dal tracciato KML',
    83: 'coordinata iniziale del database a 1.6 km dal ponte; sezione a 8 m dal tracciato KML',
    90: 'coordinata finale del database a 20 km dal ponte; sezione a 12 m dal tracciato KML',
    143: 'coordinata finale del database a 3.0 km dal ponte; sezione a 8 m dal tracciato KML',
    77: 'nel KML il tracciato abbinato e\' quello del 204 (a 1.3 km); sezione e area corrette (9.42 km2, relazione 8.92)',
    204: 'nel KML il tracciato abbinato e\' quello del 77 (a 1.3 km); sezione e area corrette (12.82 km2, relazione 12.1)',
}
S = T[T.Segnalato == 'si'].copy()
assert len(S) == 36 and set(NOTA) | set(S.index[S.Categoria == 'quasi compatibile']) == set(S.index)
for i in S.index[S.Categoria == 'quasi compatibile']:
    NOTA[i] = f'differenza di area {T.Diff_perc[i]:+.1f}% ({T.Diff_km2[i]:+.3f} km2)'
T['Nota'] = [NOTA.get(i, '') for i in T.index]
T['Azione'] = [AZ[c] if c in AZ else '' for c in T.Categoria]
S = T[T.Segnalato == 'si'].copy()
S['o1'] = (S.Classe != 'non compatibile').astype(int)
S['o2'] = S.Categoria.map(CAT.index)
S = S.reset_index(drop=True).sort_values(['o1', 'o2', 'ID'])

# ---------------------------------------------------------------- Excel
wb = load_workbook(dbx)
leg_orig = wb['Legenda'] if 'Legenda' in wb.sheetnames else None
righe_leg_orig = [[c.value for c in r] for r in leg_orig.iter_rows()] if leg_orig else []
for n in wb.sheetnames[1:]:
    del wb[n]
ws = wb.worksheets[0]
ws.title = 'Database completo'
hdr = next(r for r in range(1, 6) if any(str(c.value).strip() == 'SUPERFICIE BACINO (km2)' for c in ws[r] if c.value))
c0 = ws.max_column + 1
href = ws.cell(hdr, ws.max_column)
for k, (t, w) in enumerate([('Classe di compatibilita\'', 18), ('Categoria situazione dubbia', 26), ('Nota', 70)]):
    c = ws.cell(hdr, c0 + k, t)
    c.font = copy(href.font); c.border = copy(href.border)
    c.alignment = Alignment(wrap_text=True, vertical='center'); c.fill = PatternFill('solid', fgColor='BFBFBF')
    ws.column_dimensions[get_column_letter(c0 + k)].width = w
n = 0
for r in range(hdr + 1, ws.max_row + 1):
    try:
        i = int(ws.cell(r, 1).value)
    except (TypeError, ValueError):
        continue
    n += 1
    cat = T.Categoria[i]
    for k, v in enumerate([T.Classe[i], cat if cat != 'nessuna' else '', T.Nota[i]]):
        c = ws.cell(r, c0 + k, v); c.alignment = Alignment(wrap_text=k == 2, vertical='top')
        if cat != 'nessuna':
            c.fill = PatternFill('solid', fgColor=COL[cat])
    if cat != 'nessuna':
        ws.cell(r, 1).fill = PatternFill('solid', fgColor=COL[cat])
assert n == 212

w1 = wb.create_sheet('Situazioni dubbie', 0)
cols = [('ID', 'ID', 6), ('SP', 'SP', 7), ('km', 'km', 8), ('Nome_opera', 'Nome opera', 24),
        ('A_relazione_km2', 'A relazione (km2)', 11), ('A_calcolata_km2', 'A codice (km2)', 11),
        ('Diff_perc', 'Differenza (%)', 10), ('Classe', 'Classe', 16), ('Categoria', 'Categoria', 24),
        ('Nota', 'Nota', 70), ('Azione', 'Azione proposta', 34)]
for k, (_, t, w) in enumerate(cols, 1):
    x = w1.cell(1, k, t); x.font = Font(bold=True); x.fill = PatternFill('solid', fgColor='BFBFBF')
    x.alignment = Alignment(wrap_text=True, vertical='center'); w1.column_dimensions[get_column_letter(k)].width = w
r = 2
prima = None
for _, s in S.iterrows():
    gruppo = 'NON COMPATIBILI' if s.Classe == 'non compatibile' else s.Categoria.upper()
    if gruppo != prima:
        x = w1.cell(r, 1, gruppo); x.font = Font(bold=True); r += 1; prima = gruppo
    for k, (c, _, _) in enumerate(cols, 1):
        v = s[c]
        v = None if isinstance(v, float) and pd.isna(v) else (v.item() if hasattr(v, 'item') else v)
        x = w1.cell(r, k, v); x.alignment = Alignment(wrap_text=True, vertical='top')
        x.fill = PatternFill('solid', fgColor=COL[s.Categoria])
    r += 1
w1.freeze_panes = 'A2'
w1.page_setup.orientation = 'landscape'
w1.sheet_properties.pageSetUpPr.fitToPage = True
w1.page_setup.fitToWidth, w1.page_setup.fitToHeight = 1, 0
w1.print_title_rows = '1:1'

w3 = wb.create_sheet('Legenda', 2)
leg = [('Categoria', 'Colore', 'Significato', 'Azione proposta', 'Ponti', 'ID')]
nome = {'C9D6F0': 'azzurro', 'D9C3E9': 'viola', 'F4B6B6': 'rosso', 'FBD5A8': 'arancio', 'FFF2A8': 'giallo',
        'BFE6E6': 'verde acqua', 'D9D9D9': 'grigio'}
for c in CAT:
    ids = sorted(T.index[T.Categoria == c])
    leg.append((c, nome[COL[c]], SIGN[c], AZ[c], len(ids), ', '.join(map(str, ids))))
leg.append(('nessuna', '-', 'nessuna situazione dubbia', '-', int((T.Segnalato == 'no').sum()), 'tutti gli altri'))
for rr, row in enumerate(leg, 1):
    for k, v in enumerate(row, 1):
        x = w3.cell(rr, k, v); x.alignment = Alignment(wrap_text=True, vertical='top')
        if rr == 1:
            x.font = Font(bold=True)
        elif row[0] in COL:
            x.fill = PatternFill('solid', fgColor=COL[row[0]])
for k, wd in enumerate([28, 11, 55, 38, 7, 45], 1):
    w3.column_dimensions[get_column_letter(k)].width = wd
nc = sorted(T.index[T.Classe == 'non compatibile'])
note = ['Note',
        f'Non compatibili ({len(nc)}): {", ".join(map(str, nc))}. Sono tutti tra le situazioni dubbie (13 e 154 canali di '
        'bonifica, gli altri area della relazione non riproducibile).',
        'Classi: compatibile se la differenza con l\'area della relazione e\' entro il 15%; quasi compatibile entro il 25%, '
        'oppure entro 0.1 km2 e il 50%; altrimenti non compatibile. Per 21 e 190 si usa l\'area della relazione corretta '
        'per il refuso (13.33 e 2.167 km2).',
        'Le aste che passano sotto ogni ponte, con la loro area, sono nella mappa QGIS (layer "Aste sotto il ponte").']
base = len(leg) + 2
for k, t in enumerate(note):
    x = w3.cell(base + k, 1, t)
    if k == 0:
        x.font = Font(bold=True)
if righe_leg_orig:
    base += len(note) + 1
    w3.cell(base, 1, 'Legenda del database originale (colonne dei parametri calcolati)').font = Font(bold=True)
    for k, row in enumerate(righe_leg_orig, 1):
        for j, v in enumerate(row, 1):
            if v is not None:
                w3.cell(base + k, j, v).alignment = Alignment(wrap_text=True, vertical='top')
f_x = os.path.join(out, 'Database_situazioni_dubbie.xlsx')
wb.save(f_x)

# ---------------------------------------------------------------- GeoPackage
f_g = os.path.join(out, 'situazioni_dubbie.gpkg')
if os.path.exists(f_g):
    os.remove(f_g)
P = pd.concat([gpd.read_file(g4, layer='ponti_segnalati'), gpd.read_file(g4, layer='ponti_non_segnalati')])
P = P[['ID', 'SP', 'km', 'Nome_opera', 'A_relazione_km2', 'A_calcolata_km2', 'Diff_perc', 'Classe', 'Categoria',
       'geometry']].copy()
P['Nota'] = P.ID.map(T.Nota); P['Azione'] = P.ID.map(T.Azione)
P['Etichetta'] = P.ID.astype(int).astype(str)
P = P.sort_values('ID')
gpd.GeoDataFrame(P, crs=32633).to_file(f_g, layer='ponti', driver='GPKG')
gpd.read_file(g4, layer='ponte_kml')[['ID', 'SP', 'km', 'Nome_opera', 'KML_nome', 'geometry']].to_file(
    f_g, layer='tracciato_kml', driver='GPKG')
gpd.read_file(g4, layer='aste_sotto_il_ponte').to_file(f_g, layer='aste_sotto_il_ponte', driver='GPKG')
gpd.read_file(g4, layer='bacini_codice').to_file(f_g, layer='bacini_segnalati', driver='GPKG')
gpd.read_file(g4, layer='reticolo_codice')[['id_ramo', 'geometry']].to_file(f_g, layer='reticolo', driver='GPKG')


def sym_point(name, color, size, shape='circle'):
    return (f'<symbol type="marker" name="{name}" alpha="1" clip_to_extent="1" force_rhr="0">'
            f'<layer class="SimpleMarker" enabled="1" pass="0" locked="0"><Option type="Map">'
            f'<Option name="name" value="{shape}" type="QString"/><Option name="color" value="{color}" type="QString"/>'
            f'<Option name="outline_color" value="#000000" type="QString"/>'
            f'<Option name="outline_width" value="0.3" type="QString"/>'
            f'<Option name="size" value="{size}" type="QString"/></Option></layer></symbol>')


def sym_line(name, color, width):
    return (f'<symbol type="line" name="{name}" alpha="1" clip_to_extent="1" force_rhr="0">'
            f'<layer class="SimpleLine" enabled="1" pass="0" locked="0"><Option type="Map">'
            f'<Option name="line_color" value="{color}" type="QString"/>'
            f'<Option name="line_width" value="{width}" type="QString"/></Option></layer></symbol>')


def rgba(c, a=255):
    return ','.join(str(int(c[k:k + 2], 16)) for k in (1, 3, 5)) + f',{a}'


def sym_fill(name, color):
    return (f'<symbol type="fill" name="{name}" alpha="1" clip_to_extent="1" force_rhr="0">'
            f'<layer class="SimpleFill" enabled="1" pass="0" locked="0"><Option type="Map">'
            f'<Option name="color" value="{rgba(color, 35)}" type="QString"/><Option name="style" value="solid" type="QString"/>'
            f'<Option name="outline_color" value="{rgba(color)}" type="QString"/>'
            f'<Option name="outline_width" value="0.7" type="QString"/></Option></layer></symbol>')


def labels(field, size=8, color='#000000', scala_max=None, placement=2):
    vis = f'scaleVisibility="1" scaleMin="1" scaleMax="{scala_max}"' if scala_max else 'scaleVisibility="0"'
    return (f'<labeling type="simple"><settings calloutType="simple"><text-style fieldName="{field}" isExpression="0" '
            f'fontSize="{size}" fontSizeUnit="Point" textColor="{rgba(color)}" textOpacity="1" fontWeight="75" fontFamily="Arial">'
            f'<text-buffer bufferDraw="1" bufferSize="0.8" bufferSizeUnits="MM" bufferColor="255,255,255,255" bufferOpacity="1"/>'
            f'</text-style><placement placement="{placement}" dist="1"/><rendering {vis}/></settings></labeling>')


def qml(renderer, lab=''):
    return (f'<!DOCTYPE qgis PUBLIC \'http://mrcc.com/qgis.dtd\' \'SYSTEM\'><qgis version="3.28" '
            f'styleCategories="Symbology|Labeling">{renderer}{lab}</qgis>')


def categorized(field, cats):
    s = ''.join(sym(str(k)) for k, (_, _, sym) in enumerate(cats))
    c = ''.join(f'<category render="true" symbol="{k}" value="{v}" label="{l}"/>' for k, (v, l, _) in enumerate(cats))
    return (f'<renderer-v2 type="categorizedSymbol" attr="{field}" enableorderby="0" forceraster="0" symbollevels="0">'
            f'<categories>{c}</categories><symbols>{s}</symbols></renderer-v2>')


def single(sym):
    return f'<renderer-v2 type="singleSymbol" enableorderby="0" forceraster="0" symbollevels="0"><symbols>{sym}</symbols></renderer-v2>'


cats_p = [(c, f'{c} ({int((T.Categoria == c).sum())})', lambda n, c=c: sym_point(n, HEX[c], 3.6)) for c in CAT]
cats_p.append(('nessuna', f'nessuna situazione dubbia ({int((T.Categoria == "nessuna").sum())})',
               lambda n: sym_point(n, '#bdbdbd', 1.8)))
stili = {
    'ponti': qml(categorized('Categoria', cats_p), labels('Etichetta', 9)),
    'tracciato_kml': qml(single(sym_line('0', '#e31a1c', 1.2))),
    'aste_sotto_il_ponte': qml(categorized('Asta', [
        ('usata', 'asta usata dal codice', lambda n: sym_point(n, '#00a65a', 2.6, 'diamond')),
        ('altra', 'altra asta sotto il ponte', lambda n: sym_point(n, '#ff7f00', 2.6, 'diamond'))]),
        labels('Etichetta', 8, '#003c8f', 25000, 0)),
    'bacini_segnalati': qml(categorized('Categoria', [(c, c, lambda n, c=c: sym_fill(n, HEX[c])) for c in CAT]),
                            labels('Etichetta', 8, '#333333', 150000, 0)),
    'reticolo': qml(single(sym_line('0', '#6fa8ff', 0.4))),
}
con = sqlite3.connect(f_g)
con.execute('''CREATE TABLE IF NOT EXISTS layer_styles (id INTEGER PRIMARY KEY AUTOINCREMENT, f_table_catalog TEXT(256),
    f_table_schema TEXT(256), f_table_name TEXT(256), f_geometry_column TEXT(256), styleName TEXT(30), styleQML TEXT,
    styleSLD TEXT, useAsDefault BOOLEAN, description TEXT, owner TEXT(30), ui TEXT(30),
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP)''')
for lay, q in stili.items():
    con.execute('INSERT INTO layer_styles (f_table_catalog,f_table_schema,f_table_name,f_geometry_column,styleName,'
                'styleQML,styleSLD,useAsDefault,description,owner,update_time) VALUES (?,?,?,?,?,?,?,?,?,?,'
                "strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
                ('', '', lay, 'geom', lay, q, '', 1, 'stile predefinito', ''))
con.commit(); con.close()
print(f_x); print(f_g)
print(S[['ID', 'Classe', 'Categoria']].to_string(index=False))
