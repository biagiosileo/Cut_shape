"""
Database e vettoriali delle situazioni dubbie (non compatibili, quasi compatibili, multi-asta, pianura e canali,
area della relazione non riproducibile, sezione lontana dal ponte, coordinate del database errate), con l'ID 1-212.
Versione 3: nuova categoria "coordinate database errate" (73, 83, 90, 143; 83 e 90 escono da "sezione lontana",
perche' la distanza era misurata dalla linea inizio-fine sbagliata); un solo GeoPackage piu' leggibile con
reticolo e bacini del codice; progetto QGIS costruito a parte da progetto_qgis_v3.py.
Versione 2: i ponti 114 e 170 non sono piu' segnalati per l'aggancio al reticolo (verificato con l'accumulo
del codice: l'aggancio va sull'asta giusta, a una cella di distanza; vedi verifica_aggancio_acc.py).

Prodotti, tutti in una cartella nuova (gli input sono solo letti):
  Database_situazioni_dubbie.xlsx  copia del database con colonne aggiunte in fondo, foglio "Situazioni dubbie"
                                   con i soli ponti segnalati e foglio "Legenda situazioni"
  ponti_situazioni_dubbie.gpkg     layer ponti_tutti (212) e ponti_segnalati, con stile per categoria
  spostamento_ponti.gpkg           sezione di calcolo, punto e tracciato del KML, inizio e fine del database,
                                   linee sezione-KML e sezione-database con la distanza in metri

Uso: python situazioni_dubbie_v3.py <Database.xlsx> <controllo_coordinate.gpkg> <reticolo_idrografico.geojson>
        <bacini_afferenti.geojson> <cartella_uscita>
(reticolo e bacini: uscite del codice pysheds_bridges_5m.py nel ricalcolo dei 212 ponti)
"""
import os
import sqlite3
import sys
from copy import copy

import geopandas as gpd
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from shapely.geometry import LineString
from shapely.ops import nearest_points

dbx, gpkg_cc, f_ret, f_bac, out = sys.argv[1:6]
os.makedirs(out, exist_ok=True)

# ---------------------------------------------------------------- dati del database (solo lettura)
D = pd.read_excel(dbx, sheet_name=0)
D = D.rename(columns={'Unnamed: 0': 'ID'})
D['ID'] = D['ID'].astype(int)
D = D.set_index('ID', drop=False)
assert sorted(D.index) == list(range(1, 213))

A_rel = pd.to_numeric(D['SUPERFICIE BACINO (km2)'], errors='coerce')
A_rel_cls = A_rel.copy()
A_rel_cls[21], A_rel_cls[190] = 13.33, 2.167          # refusi corretti, come nella legenda del database
A_cod = D['Area bacino calcolata (km2)'].astype(float)
dA = A_cod - A_rel_cls
dP = 100 * dA / A_rel_cls


def classe(i):
    if np.isnan(A_rel_cls[i]):
        return 'senza area relazione'
    p, a = abs(dP[i]), abs(dA[i])
    if p <= 15:
        return 'compatibile'
    if p <= 25 or (a <= 0.1 and p <= 50):
        return 'quasi compatibile'
    return 'non compatibile'


CL = pd.Series({i: classe(i) for i in D.index})
# controllo con la legenda del database
assert sorted(CL[CL == 'quasi compatibile'].index) == [44, 72, 85, 102, 103, 104, 106, 109, 116, 124, 129, 151, 200]
assert sorted(CL[CL == 'non compatibile'].index) == [13, 19, 58, 117, 118, 154, 164, 174]
assert sorted(CL[CL == 'senza area relazione'].index) == [14, 15, 81, 152, 153]

# ---------------------------------------------------------------- geometrie
ll = D['Sezione di calcolo [Lat., Long.]'].str.replace('°', '').str.split(',', expand=True).astype(float)
SEZ = gpd.GeoDataFrame({'ID': D.index}, geometry=gpd.points_from_xy(ll[1], ll[0]), crs=4326).to_crs(32633)
SEZ = SEZ.set_index('ID', drop=False)
KP = gpd.read_file(gpkg_cc, layer='kml_abbinato').set_index('ID', drop=False)
DI = gpd.read_file(gpkg_cc, layer='db_inizio').set_index('ID', drop=False)
DF = gpd.read_file(gpkg_cc, layer='db_fine').set_index('ID', drop=False)
DS = gpd.read_file(gpkg_cc, layer='db_attraversamento_inizio_fine').set_index('ID', drop=False)
KT_all = gpd.read_file(gpkg_cc, layer='kml_tracciati')

# tracciato KML del ponte: la linea del KML piu' vicina al punto KML abbinato
sidx = KT_all.sindex
kt_rows = []
for i in D.index:
    j = sidx.nearest(KP.geometry[i], return_all=False)[1][0]
    kt_rows.append({'ID': i, 'KML_nome': KT_all.nome.iloc[j], 'Lungh_tracciato_m': round(KT_all.geometry.iloc[j].length, 1),
                    'Dist_punto_tracciato_m': round(KT_all.geometry.iloc[j].distance(KP.geometry[i]), 1),
                    'geometry': KT_all.geometry.iloc[j]})
KT = gpd.GeoDataFrame(kt_rows, crs=32633).set_index('ID', drop=False)

dist_kml = SEZ.distance(KP).round(1)
dist_seg = SEZ.distance(DS).round(1)
mid = DS.geometry.interpolate(0.5, normalized=True)
dist_mid = SEZ.distance(mid).round(1)
dist_trc = SEZ.distance(KT).round(1)
snap = D['Distanza di aggancio al reticolo (m)'].astype(float)

# ---------------------------------------------------------------- situazioni dubbie (definizione concordata)
MULTI = {
    107: ('sotto il ponte passa il canale con bacino di 7.16 km2; la sezione e l\'area della relazione (0.72 km2) '
          'sono sul ramo piccolo della confluenza, a 32 m', 7.16,
          'verificare quale asta attraversa il ponte; se il canale principale, area di riferimento 7.16 km2'),
    108: ('sotto il ponte passa il canale con bacino di 9.18 km2; la sezione e l\'area della relazione (0.27 km2) '
          'sono sul ramo accanto, a 38 m', 9.178,
          'verificare quale asta attraversa il ponte; se il canale principale, area di riferimento 9.18 km2'),
    109: ('sotto il ponte passa il canale con bacino di 6.64 km2; la sezione (0.26 km2, relazione 0.31) e\' sul '
          'fosso laterale a 18 m', 6.637,
          'verificare quale asta attraversa il ponte; se il canale principale, area di riferimento 6.64 km2'),
    111: ('area calcolata 15.79 km2 (relazione 14.5) con sezione sul torrente a 81 m; nel punto del database '
          'c\'e\' un fosso minore con bacino di 0.14 km2', 0.142,
          'confermare che il ponte attraversa il torrente principale'),
    196: ('sotto il ponte passa l\'asta principale con bacino di 87.0 km2; la sezione e l\'area della relazione '
          '(0.83 km2) sono sull\'affluente, a 130 m', 87.0,
          'verificare quale asta attraversa il ponte; se l\'asta principale, area di riferimento 87.0 km2'),
}
PIANURA = {
    13: ('relazione 18.06 km2 con bacino collinare (quota media 182 m, pendenza 16.8%); il calcolo trova 4.09 km2 in '
         'pianura lungo un canale rettilineo: il bacino calcolato potrebbe essere incompleto', None,
         'da approfondire: estensione del bacino a monte e collegamento con il canale'),
    154: ('database 18.6 km2, stessa relazione del 13 (18.06 km2, bacino collinare); il calcolo trova 4.09 km2 in pianura; sul tracciato del '
          'ponte c\'e\' anche un fosso con bacino di 0.51 km2', 0.509,
          'da approfondire insieme al 13'),
}
NONRIPR = {
    164: ('il ponte scavalca un corso d\'acqua con bacino di 215.6 km2; la relazione indica 0.75 km2', None,
          'verificare il dato della relazione (probabile riferimento a un fosso minore o refuso)'),
    117: ('area calcolata 0.081 km2 contro 0.38 della relazione; un bacino di 0.38 km2 si chiude a circa 460 m dal '
          'ponte', None, 'verificare la sezione di chiusura usata nella relazione'),
    118: ('area calcolata 0.751 km2 contro 0.45 della relazione; un bacino di 0.45 km2 si chiude a circa 900 m dal '
          'ponte', None, 'verificare la sezione di chiusura usata nella relazione'),
    19: ('area calcolata 0.131 km2 contro 0.63 della relazione; un bacino di 0.63 km2 si chiude a circa 925 m dal '
         'ponte', None, 'verificare la sezione di chiusura usata nella relazione'),
    72: ('area calcolata 95.0 km2 contro 116.1 della relazione (-18%); nessuna asta alternativa vicino al ponte', None,
         'verificare la sezione di chiusura usata nella relazione'),
    58: ('area calcolata 58.1 km2 contro 2.63 della relazione; nessuna sezione entro 1 km dal ponte riproduce la '
         'relazione', None, 'verificare il dato della relazione'),
    174: ('area calcolata 22.3 km2 contro 6.83 della relazione; nessuna sezione entro 2 km dal ponte riproduce la '
          'relazione', None, 'verificare il dato della relazione'),
}
SEZ_LONTANA = {
    14: 'sezione a 204 m dal ponte del database (area della relazione assente)',
    82: 'sezione a 110 m dal ponte del database',
    83: 'sezione a 53 m dal ponte del database',
    90: 'sezione a 195 m dal ponte del database',
    98: 'sezione a 165 m dal ponte del database',
    155: 'sezione a 127 m dal ponte del database (buco del DEM riempito, porzione nuova)',
}
AGGANCIO = {}  # versione 2: 114 e 170 verificati, aggancio corretto (nessuna segnalazione)
# versione 3: un estremo del ponte nel database e' lontano dal tracciato del ponte nel KML (refuso nelle coordinate)
COORD_ERRATE = {73: 'fine', 83: 'inizio', 90: 'fine', 143: 'fine'}
d_ini_kt = DI.distance(KT).round(0)
d_fin_kt = DF.distance(KT).round(0)
lung_db = DS.length.round(0)
for i, e in COORD_ERRATE.items():
    assert (d_fin_kt[i] if e == 'fine' else d_ini_kt[i]) > 900 and (d_ini_kt[i] if e == 'fine' else d_fin_kt[i]) < 10
# per questi ponti lo spostamento della sezione si misura dal tracciato KML, non dalla linea inizio-fine sbagliata
dist_rif = dist_seg.copy()
for i in COORD_ERRATE:
    dist_rif[i] = dist_trc[i]

rows = []
for i in D.index:
    sit, mot, alt, azi = [], [], None, []
    cat = None
    for nome, dd in (('multi-asta', MULTI), ('pianura e canali', PIANURA), ('area relazione non riproducibile', NONRIPR)):
        if i in dd:
            sit.append(nome); mot.append(dd[i][0]); alt = dd[i][1]; azi.append(dd[i][2]); cat = cat or nome
    if CL[i] in ('non compatibile', 'quasi compatibile'):
        sit.append(CL[i])
        if CL[i] == 'quasi compatibile' and i not in MULTI and i not in NONRIPR:
            mot.append(f'differenza di area {dP[i]:+.1f}% ({dA[i]:+.3f} km2)')
            azi.append('differenza contenuta: nessuna azione, eventuale verifica di dettaglio')
        cat = cat or CL[i]
    if dist_seg[i] > 50 and i not in COORD_ERRATE:
        sit.append('sezione lontana dal ponte (> 50 m)')
        if i in SEZ_LONTANA and i not in MULTI and i not in PIANURA:
            mot.append(SEZ_LONTANA[i])
            azi.append('verificare la posizione del ponte e la sezione di calcolo')
        cat = cat or 'sezione lontana dal ponte'
    if i in AGGANCIO:
        sit.append('aggancio anomalo'); mot.append(AGGANCIO[i])
        azi.append('nessun effetto sull\'area (differenza ' + f'{dP[i]:+.1f}%' + '): solo segnalazione')
        cat = cat or 'aggancio anomalo'
    if i in COORD_ERRATE:
        e = COORD_ERRATE[i]
        de = d_fin_kt[i] if e == 'fine' else d_ini_kt[i]
        sit.append('coordinate database errate')
        mot.append(f'coordinata {"finale" if e == "fine" else "iniziale"} del database a {de:.0f} m dal tracciato del '
                   f'ponte nel KML (linea inizio-fine lunga {lung_db[i]:.0f} m); la sezione di calcolo e\' a '
                   f'{dist_trc[i]:.0f} m dal tracciato KML: il bacino e\' calcolato nel punto giusto')
        azi.append(f'correggere la coordinata {"finale" if e == "fine" else "iniziale"} nel database')
        cat = cat or 'coordinate database errate'
    rows.append({'ID': i, 'Classe': CL[i], 'Categoria': cat or 'nessuna', 'Segnalato': 'si' if sit else 'no',
                 'Situazioni': '; '.join(sit), 'Motivazione': '; '.join(mot), 'Area_asta_alternativa_km2': alt,
                 'Azione_proposta': '; '.join(dict.fromkeys(azi))})
S = pd.DataFrame(rows).set_index('ID', drop=False)

# controlli sulle liste concordate
assert sorted(S.index[dist_seg > 50]) == [14, 82, 83, 90, 98, 111, 155, 196], sorted(S.index[dist_seg > 50])
for i in list(MULTI) + list(PIANURA) + list(NONRIPR) + list(AGGANCIO):
    assert S.Segnalato[i] == 'si'

T = pd.DataFrame({
    'ID': D.index,
    'SP': D['NUOVA NUMERAZIONE'], 'km': D['Progressiva km'], 'Nome_opera': D['Nome opera'],
    'A_relazione_km2': A_rel_cls, 'A_calcolata_km2': A_cod, 'Diff_km2': dA.round(3), 'Diff_perc': dP.round(1),
    'Classe': S.Classe, 'Categoria': S.Categoria, 'Segnalato': S.Segnalato, 'Situazioni': S.Situazioni,
    'Motivazione': S.Motivazione, 'Area_asta_alternativa_km2': S.Area_asta_alternativa_km2,
    'Azione_proposta': S.Azione_proposta,
    'Dist_sezione_ponte_DB_m': dist_seg, 'Dist_sezione_centro_DB_m': dist_mid,
    'Dist_sezione_punto_KML_m': dist_kml, 'Dist_sezione_tracciato_KML_m': dist_trc,
    'Aggancio_reticolo_m': snap, 'Dist_sezione_riferimento_m': dist_rif,
}).set_index('ID', drop=False)
T['A_relazione_km2'] = T['A_relazione_km2'].round(3)

# ---------------------------------------------------------------- Excel: copia del database con colonne aggiunte
COL = {'non compatibile': 'F4B6B6', 'quasi compatibile': 'FBD5A8', 'multi-asta': 'D9C3E9',
       'pianura e canali': 'C9D6F0', 'area relazione non riproducibile': 'F4B6B6',
       'sezione lontana dal ponte': 'FFF2A8', 'coordinate database errate': 'BFE6E6'}
wb = load_workbook(dbx)
ws = wb.worksheets[0]
nuove = ['Classe', 'Categoria', 'Segnalato', 'Situazioni', 'Motivazione', 'Area_asta_alternativa_km2',
         'Azione_proposta', 'Diff_km2', 'Diff_perc', 'Dist_sezione_ponte_DB_m', 'Dist_sezione_centro_DB_m',
         'Dist_sezione_punto_KML_m', 'Dist_sezione_tracciato_KML_m', 'Dist_sezione_riferimento_m']
titoli = ['Classe di compatibilita\'', 'Categoria situazione dubbia', 'Segnalato', 'Situazioni dubbie',
          'Motivazione', 'Area asta alternativa (km2)', 'Azione proposta', 'Differenza area calcolata - relazione (km2)',
          'Differenza area (%)', 'Distanza sezione di calcolo - ponte del database (m)',
          'Distanza sezione di calcolo - centro del ponte del database (m)',
          'Distanza sezione di calcolo - punto del ponte nel KML (m)',
          'Distanza sezione di calcolo - tracciato del ponte nel KML (m)',
          'Distanza sezione di calcolo - ponte (m): dal database, dal KML se le coordinate del database sono errate']
# riga di intestazione e colonna ID nel foglio
hdr_row = None
for r in range(1, 6):
    if any(str(c.value).strip() == 'SUPERFICIE BACINO (km2)' for c in ws[r] if c.value is not None):
        hdr_row = r; break
assert hdr_row
c0 = ws.max_column + 1
href = ws.cell(hdr_row, ws.max_column)
for k, t in enumerate(titoli):
    c = ws.cell(hdr_row, c0 + k, t)
    c.font = copy(href.font); c.alignment = Alignment(wrap_text=True, vertical='center')
    c.fill = PatternFill('solid', fgColor='BFBFBF'); c.border = copy(href.border)
    ws.column_dimensions[get_column_letter(c0 + k)].width = 45 if t in ('Motivazione', 'Azione proposta',
                                                                       'Situazioni dubbie') else 16
n_ok = 0
for r in range(hdr_row + 1, ws.max_row + 1):
    v = ws.cell(r, 1).value
    try:
        i = int(v)
    except (TypeError, ValueError):
        continue
    n_ok += 1
    for k, col in enumerate(nuove):
        val = T.at[i, col]
        if isinstance(val, float) and np.isnan(val):
            val = None
        c = ws.cell(r, c0 + k, val.item() if hasattr(val, 'item') else val)
        c.alignment = Alignment(wrap_text=col in ('Motivazione', 'Azione_proposta', 'Situazioni'), vertical='top')
        if T.at[i, 'Segnalato'] == 'si':
            c.fill = PatternFill('solid', fgColor=COL[T.at[i, 'Categoria']])
    if T.at[i, 'Segnalato'] == 'si':
        ws.cell(r, 1).fill = PatternFill('solid', fgColor=COL[T.at[i, 'Categoria']])
assert n_ok == 212, n_ok

# foglio con i soli segnalati
w2 = wb.create_sheet('Situazioni dubbie', 1)
cols2 = ['ID', 'SP', 'km', 'Nome_opera', 'A_relazione_km2', 'A_calcolata_km2', 'Diff_perc', 'Classe', 'Categoria',
         'Situazioni', 'Motivazione', 'Area_asta_alternativa_km2', 'Azione_proposta', 'Dist_sezione_riferimento_m',
         'Dist_sezione_tracciato_KML_m']
ordine = ['multi-asta', 'pianura e canali', 'area relazione non riproducibile', 'non compatibile',
          'quasi compatibile', 'sezione lontana dal ponte', 'coordinate database errate']
Sg = T[T.Segnalato == 'si'].copy()
Sg['o'] = Sg.Categoria.map(ordine.index)
Sg = Sg.reset_index(drop=True).sort_values(['o', 'ID'])
for k, c in enumerate(cols2, 1):
    x = w2.cell(1, k, c.replace('_', ' ')); x.font = Font(bold=True); x.fill = PatternFill('solid', fgColor='BFBFBF')
    x.alignment = Alignment(wrap_text=True, vertical='center')
    w2.column_dimensions[get_column_letter(k)].width = {'Motivazione': 60, 'Azione_proposta': 45, 'Situazioni': 32,
                                                        'Nome_opera': 22, 'Categoria': 22, 'Classe': 16}.get(c, 11)
for r, (_, s) in enumerate(Sg.iterrows(), 2):
    for k, c in enumerate(cols2, 1):
        val = s[c]
        if isinstance(val, float) and np.isnan(val):
            val = None
        x = w2.cell(r, k, val.item() if hasattr(val, 'item') else val)
        x.alignment = Alignment(wrap_text=True, vertical='top')
        x.fill = PatternFill('solid', fgColor=COL[s.Categoria])
w2.freeze_panes = 'B2'

# legenda
w3 = wb.create_sheet('Legenda situazioni', 2)
leg = [('Categoria', 'Colore', 'Criterio', 'N. ponti', 'ID')]
crit = {'multi-asta': 'sotto il ponte passano piu\' aste: la sezione di calcolo e/o l\'area della relazione sono su '
                      'un\'asta diversa da quella principale',
        'pianura e canali': 'zona di pianura con canali: il bacino calcolato potrebbe essere incompleto',
        'area relazione non riproducibile': 'nessuna sezione vicino al ponte riproduce l\'area della relazione',
        'non compatibile': 'differenza di area oltre le soglie (vedi Legenda)',
        'quasi compatibile': '|differenza %| <= 25%, oppure |differenza| <= 0.1 km2 e |differenza %| <= 50%',
        'sezione lontana dal ponte': 'sezione di calcolo a piu\' di 50 m dal segmento inizio-fine del ponte nel database',
        'coordinate database errate': 'un estremo del ponte nel database e\' a centinaia di metri o chilometri dal '
                                      'tracciato del ponte nel KML (refuso nelle coordinate)'}
nome_col = {'F4B6B6': 'rosso', 'FBD5A8': 'arancio', 'D9C3E9': 'viola', 'C9D6F0': 'azzurro', 'FFF2A8': 'giallo',
            'BFE6E6': 'verde acqua'}
for c in ordine:
    ids = sorted(T.index[T.Categoria == c])
    leg.append((c, nome_col[COL[c]], crit[c], len(ids), ', '.join(map(str, ids))))
leg.append(('nessuna', 'nessuno', 'nessuna situazione dubbia', int((T.Segnalato == 'no').sum()), 'tutti gli altri'))
for r, row in enumerate(leg, 1):
    for k, v in enumerate(row, 1):
        x = w3.cell(r, k, v); x.alignment = Alignment(wrap_text=True, vertical='top')
        if r == 1:
            x.font = Font(bold=True)
        elif row[0] in COL:
            x.fill = PatternFill('solid', fgColor=COL[row[0]])
for k, wd in enumerate([30, 10, 70, 9, 60], 1):
    w3.column_dimensions[get_column_letter(k)].width = wd
note = ['Note',
        'La categoria e\' la situazione principale; la colonna Situazioni elenca tutte quelle che riguardano il ponte.',
        'Classe di compatibilita\': stesse soglie del foglio Legenda; per i ponti 21 e 190 si usa l\'area della '
        'relazione corretta per il refuso (13.33 e 2.167 km2).',
        'Distanze calcolate in UTM 33N (EPSG:32633) dalla Sezione di calcolo del database.',
        'Distanza di aggancio al reticolo: 1.8 m per 210 ponti. Il punto cade gia\' su una cella del reticolo e la sezione '
        'di chiusura e\' quella cella (spostamento nullo); 1.8 m e\' la distanza dall\'angolo della cella, come misura pysheds. '
        'Ponti 114 (8.8 m) e 170 (4.0 m): il punto cade nella cella accanto al corso d\'acqua e l\'aggancio va sulla cella '
        'adiacente della stessa asta (verificato con l\'accumulo del codice): nessuna segnalazione. '
        'Lo spostamento reale e\' la distanza della sezione dal ponte del database.',
        'Le distanze dal punto KML oltre qualche centinaio di metri (77, 78, 82, 90, 204) dipendono dalla posizione '
        'del punto nel KML: la sezione e\' coerente con il tracciato del ponte.',
        'Coordinate database errate (73, 83, 90, 143): per questi ponti la distanza della sezione dal ponte e\' misurata '
        'dal tracciato del ponte nel KML (colonna Distanza sezione - riferimento).',
        'Il codice di calcolo (pysheds_bridges_5m.py) e\' lo stesso per tutti i ponti: per ogni ponte cambia solo la '
        'sezione di chiusura, scelta con la stessa regola (incrocio tra tracciato del ponte nel KML e reticolo). '
        'Vedi nota_sul_metodo.txt.']
for k, t in enumerate(note):
    x = w3.cell(len(leg) + 2 + k, 1, t)
    if k == 0:
        x.font = Font(bold=True)
f_x = os.path.join(out, 'Database_situazioni_dubbie.xlsx')
wb.save(f_x)

# ---------------------------------------------------------------- vettoriali: un solo GeoPackage, layer con nomi chiari
# Il punto di ogni ponte e' la sezione di calcolo usata dal codice (colonna "Sezione di calcolo" del database).
f_g = os.path.join(out, 'situazioni_dubbie.gpkg')
if os.path.exists(f_g):
    os.remove(f_g)
attr = T.drop(columns=['Motivazione', 'Azione_proposta']).copy()
attr['Motivazione'] = T.Motivazione; attr['Azione_proposta'] = T.Azione_proposta
P = gpd.GeoDataFrame(attr.reset_index(drop=True), geometry=SEZ.geometry.reindex(T.index).values, crs=32633)
segn = P.Segnalato == 'si'
P[segn].to_file(f_g, layer='ponti_segnalati', driver='GPKG')
P[~segn].to_file(f_g, layer='ponti_non_segnalati', driver='GPKG')
ids = list(T.index)
ids_s = sorted(T.index[T.Segnalato == 'si'])
base = T[['ID', 'SP', 'km', 'Nome_opera', 'Categoria']].reset_index(drop=True)


def gdf(geoms, extra=None, rows=None):
    b = base if rows is None else base.set_index('ID').loc[rows].reset_index()
    g = gpd.GeoDataFrame(b.copy(), geometry=list(geoms), crs=32633)
    for k, v in (extra or {}).items():
        g[k] = list(v)
    return g


# ponte nel KML (tracciato) e ponte nel database (linea inizio-fine, con le coordinate errate segnate)
gdf(KT.geometry.reindex(ids), {'KML_nome': KT.KML_nome.reindex(ids), 'Lungh_m': KT.Lungh_tracciato_m.reindex(ids)}
    ).to_file(f_g, layer='ponte_kml', driver='GPKG')
coord = ['errate' if i in COORD_ERRATE else 'corrette' for i in ids]
nota = [f'{i}: coordinata {COORD_ERRATE[i]} errata' if i in COORD_ERRATE else '' for i in ids]
gdf(DS.geometry.reindex(ids), {'Lungh_m': DS.geometry.reindex(ids).length.round(1), 'Coordinate': coord, 'Nota': nota}
    ).to_file(f_g, layer='ponte_database', driver='GPKG')
# spostamento: dalla sezione di calcolo al punto piu' vicino del ponte (database; KML se coordinate errate),
# solo dove supera 10 m (sotto i 10 m la sezione e' sul ponte, a meno di due celle del DEM)
sp = [i for i in ids if dist_rif[i] >= 10]
geo = []
for i in sp:
    rif = KT.geometry[i] if i in COORD_ERRATE else DS.geometry[i]
    geo.append(LineString([SEZ.geometry[i], nearest_points(rif, SEZ.geometry[i])[0]]))
gdf(geo, {'Dist_m': dist_rif.reindex(sp), 'Riferimento': ['KML' if i in COORD_ERRATE else 'database' for i in sp],
          'Etichetta': [f'{dist_rif[i]:.0f} m' for i in sp]}, rows=sp).to_file(f_g, layer='spostamento_sezione', driver='GPKG')

# reticolo e bacini del codice (ricalcolo dei 212 ponti, identico al database) attorno ai ponti segnalati
B = gpd.read_file(f_bac).to_crs(32633)
B['ID'] = B['ID'].astype(int)
B = B[B.ID.isin(ids_s)].merge(T[['ID', 'Categoria', 'A_relazione_km2']].reset_index(drop=True), on='ID')
B['A_km2'] = (B.geometry.area / 1e6).round(3)
B['Etichetta'] = [f'{i} ({a:g} km2)' for i, a in zip(B.ID, B.A_km2)]
B.sort_values('A_km2', ascending=False).to_file(f_g, layer='bacini_codice', driver='GPKG')
R = gpd.read_file(f_ret).to_crs(32633)
pts = SEZ.loc[ids_s]
zona = pts.buffer(1000).union_all().union(B.buffer(200).union_all())
R = R.iloc[R.sindex.query(zona, predicate='intersects')].copy()
vic = R.sindex.query(pts.buffer(100).union_all(), predicate='intersects')
R['Vicino_ponte'] = 'no'
R.iloc[vic, R.columns.get_loc('Vicino_ponte')] = 'si'
R.to_file(f_g, layer='reticolo_codice', driver='GPKG')

# ---------------------------------------------------------------- stili QGIS salvati nel GeoPackage (si caricano da soli)
HEX = {'non compatibile': '#d7191c', 'quasi compatibile': '#f39c33', 'multi-asta': '#8e44ad',
       'pianura e canali': '#2c7bb6', 'area relazione non riproducibile': '#a50f15',
       'sezione lontana dal ponte': '#e6c700', 'coordinate database errate': '#1b9e9e', 'nessuna': '#bdbdbd'}


def sym_point(name, color, size=3.0, shape='circle', outline='#000000'):
    return (f'<symbol type="marker" name="{name}" alpha="1" clip_to_extent="1" force_rhr="0">'
            f'<layer class="SimpleMarker" enabled="1" pass="0" locked="0"><Option type="Map">'
            f'<Option name="name" value="{shape}" type="QString"/>'
            f'<Option name="color" value="{color}" type="QString"/>'
            f'<Option name="outline_color" value="{outline}" type="QString"/>'
            f'<Option name="outline_width" value="0.3" type="QString"/>'
            f'<Option name="size" value="{size}" type="QString"/></Option></layer></symbol>')


def sym_line(name, color, width=0.6, dash=False):
    return (f'<symbol type="line" name="{name}" alpha="1" clip_to_extent="1" force_rhr="0">'
            f'<layer class="SimpleLine" enabled="1" pass="0" locked="0"><Option type="Map">'
            f'<Option name="line_color" value="{color}" type="QString"/>'
            f'<Option name="line_width" value="{width}" type="QString"/>'
            f'<Option name="line_style" value="{"dash" if dash else "solid"}" type="QString"/>'
            f'<Option name="capstyle" value="round" type="QString"/>'
            f'</Option></layer></symbol>')


def rgba(color, a=255):
    return ','.join(str(int(color[k:k + 2], 16)) for k in (1, 3, 5)) + f',{a}'


def sym_fill(name, color, width=0.7):
    return (f'<symbol type="fill" name="{name}" alpha="1" clip_to_extent="1" force_rhr="0">'
            f'<layer class="SimpleFill" enabled="1" pass="0" locked="0"><Option type="Map">'
            f'<Option name="color" value="{rgba(color, 35)}" type="QString"/>'
            f'<Option name="style" value="solid" type="QString"/>'
            f'<Option name="outline_color" value="{rgba(color)}" type="QString"/>'
            f'<Option name="outline_width" value="{width}" type="QString"/>'
            f'</Option></layer></symbol>')


def labels(field, size=8, color='#000000', scala_max=None, placement=2):
    color = ','.join(str(int(color[k:k + 2], 16)) for k in (1, 3, 5)) + ',255'
    vis = f'scaleVisibility="1" scaleMin="1" scaleMax="{scala_max}"' if scala_max else 'scaleVisibility="0"'
    return (f'<labeling type="simple"><settings calloutType="simple"><text-style fieldName="{field}" '
            f'isExpression="0" fontSize="{size}" fontSizeUnit="Point" textColor="{color}" textOpacity="1" fontWeight="75" fontFamily="Arial">'
            f'<text-buffer bufferDraw="1" bufferSize="0.8" bufferSizeUnits="MM" bufferColor="255,255,255,255" bufferOpacity="1"/></text-style>'
            f'<placement placement="{placement}" dist="1"/><rendering {vis}/>'
            f'</settings></labeling>')


def qml(renderer, lab=''):
    return (f'<!DOCTYPE qgis PUBLIC \'http://mrcc.com/qgis.dtd\' \'SYSTEM\'><qgis version="3.28" '
            f'styleCategories="Symbology|Labeling">{renderer}{lab}</qgis>')


def categorized(field, cats):
    """cats: (valore, etichetta in legenda, simbolo)"""
    s, c = '', ''
    for k, (val, lab, sym) in enumerate(cats):
        s += sym(str(k))
        c += f'<category render="true" symbol="{k}" value="{val}" label="{lab}"/>'
    return (f'<renderer-v2 type="categorizedSymbol" attr="{field}" enableorderby="0" forceraster="0" '
            f'symbollevels="0"><categories>{c}</categories><symbols>{s}</symbols></renderer-v2>')


def single(sym):
    return f'<renderer-v2 type="singleSymbol" enableorderby="0" forceraster="0" symbollevels="0"><symbols>{sym}</symbols></renderer-v2>'


def salva_stili(f, stili):
    con = sqlite3.connect(f)
    con.execute('''CREATE TABLE IF NOT EXISTS layer_styles (id INTEGER PRIMARY KEY AUTOINCREMENT,
        f_table_catalog TEXT(256), f_table_schema TEXT(256), f_table_name TEXT(256), f_geometry_column TEXT(256),
        styleName TEXT(30), styleQML TEXT, styleSLD TEXT, useAsDefault BOOLEAN, description TEXT, owner TEXT(30),
        ui TEXT(30), update_time DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    for lay, q in stili.items():
        con.execute('INSERT INTO layer_styles (f_table_catalog,f_table_schema,f_table_name,f_geometry_column,'
                    'styleName,styleQML,styleSLD,useAsDefault,description,owner,update_time) VALUES (?,?,?,?,?,?,?,?,?,?,'
                    "strftime('%Y-%m-%dT%H:%M:%SZ','now'))",
                    ('', '', lay, 'geom', lay, q, '', 1, 'stile predefinito', ''))
    con.commit(); con.close()


cat_s = [c for c in ordine if (T.Categoria == c).any()]
salva_stili(f_g, {
    'ponti_segnalati': qml(categorized('Categoria', [(c, c, lambda n, c=c: sym_point(n, HEX[c], 3.6)) for c in cat_s]),
                           labels('ID', 9)),
    'ponti_non_segnalati': qml(single(sym_point('0', '#9e9e9e', 2.0)), labels('ID', 7, '#555555', 25000)),
    'ponte_kml': qml(single(sym_line('0', '#e31a1c', 1.4))),
    'ponte_database': qml(categorized('Coordinate', [
        ('corrette', 'ponte nel database (inizio-fine)', lambda n: sym_line(n, '#ff00ff', 0.8)),
        ('errate', 'ponte nel database con coordinate errate', lambda n: sym_line(n, '#1b9e9e', 0.6, True))]),
        labels('Nota', 8, '#1b9e9e', None, 2)),
    'spostamento_sezione': qml(single(sym_line('0', '#000000', 0.5, True)), labels('Etichetta', 8, '#000000', 25000)),
    'reticolo_codice': qml(categorized('Vicino_ponte', [
        ('si', 'asta entro 100 m da un ponte segnalato', lambda n: sym_line(n, '#0050ff', 1.0)),
        ('no', 'altre aste del reticolo', lambda n: sym_line(n, '#6fa8ff', 0.35))])),
    'bacini_codice': qml(categorized('Categoria', [(c, c, lambda n, c=c: sym_fill(n, HEX[c])) for c in cat_s]),
                         labels('Etichetta', 8, '#333333', 150000, 0)),
})

T.to_csv(os.path.join(out, 'situazioni_dubbie_212.csv'), index=False)
print('categorie:'); print(T.Categoria.value_counts().to_string())
print('segnalati', (T.Segnalato == 'si').sum(), '; bacini', len(B), '; tratti di reticolo', len(R),
      f'({R.length.sum() / 1000:.0f} km); spostamenti >= 10 m', len(sp))
print(f_x); print(f_g)
