"""
Cartella condivisa, versione 2, organizzata per fasi del lavoro:
  0_modifiche_codice      codice usato e elenco delle modifiche (lettura tif, un solo lancio su tutte le porzioni)
  1_prima_analisi         punti nella posizione iniziale, aree e classi della prima analisi
  2_spostamento_punti     ponti modificati, posizione iniziale e finale, motivo, effetto su area e classe;
                          verifica con i punti al centro della cella
  3_confronto_aree        reticolo, bacini, punti finali e classi di compatibilita' (dalla versione 1)
  4_casi_dubbi            casi dubbi su tutto il campione (dalla versione 1)
  5_verifica_manuale_ID100 file della verifica manuale del ponte 100 e manuale aggiornato
Tutti gli ingressi sono solo letti.

Uso: python cartella_condivisa_v2.py <PONTI> <cartella manuale generico> <uscita>
  <PONTI> contiene: cartella_condivisa (v1), ricalcolo_212, ricalcolo_iniziali, ricalcolo_centri,
  drive_ponti_iniziali/ponti_iniziali.shp, consegna_situazioni_dubbie_v3, upload_verifica
"""
import os
import shutil
import sqlite3
import sys

import geopandas as gpd
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from shapely.geometry import LineString

BASE, MAN, out = sys.argv[1:4]
V1 = os.path.join(BASE, 'cartella_condivisa')
os.makedirs(out, exist_ok=True)


def p(*a):
    return os.path.join(BASE, *a)


def cartella(n):
    d = os.path.join(out, n)
    os.makedirs(d, exist_ok=True)
    return d


def nuovo(f):
    if os.path.exists(f):
        os.remove(f)
    return f


def classe(a, r):
    """Regola delle classi usata in tutto il lavoro."""
    if pd.isna(r) or r == 0:
        return 'senza area relazione'
    d = abs(a - r)
    if d / r <= .15:
        return 'compatibile'
    if d / r <= .25 or (d <= .1 and d / r <= .5):
        return 'quasi compatibile'
    return 'non compatibile'


# ---------- stili (come nella versione 1) ----------
CLS = {'compatibile': '#1a9641', 'quasi compatibile': '#f39c33', 'non compatibile': '#d7191c',
       'senza area relazione': '#9e9e9e'}
MOT = {'sezione sul tracciato KML': '#2c7bb6', 'sezione sul tracciato KML (fosso piccolo, soglia ridotta)': '#00a6a6',
       'sezione secondo la relazione di ispezione (multi-asta)': '#8e44ad', 'sezione sul taglio del tombino': '#e6c700',
       'solo porzione di calcolo allargata': '#9e9e9e'}


def rgba(c, a=255):
    return ','.join(str(int(c[k:k + 2], 16)) for k in (1, 3, 5)) + f',{a}'


def opt(**kw):
    return ''.join(f'<Option name="{k}" value="{v}" type="QString"/>' for k, v in kw.items())


def sym_point(n, c, size=3.0, shape='circle'):
    return (f'<symbol type="marker" name="{n}" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleMarker" '
            f'enabled="1" pass="0" locked="0"><Option type="Map">'
            f'{opt(name=shape, color=rgba(c), outline_color="0,0,0,255", outline_width="0.3", size=size)}'
            f'</Option></layer></symbol>')


def sym_line(n, c, w=0.6, dash=False):
    return (f'<symbol type="line" name="{n}" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleLine" '
            f'enabled="1" pass="0" locked="0"><Option type="Map">'
            f'{opt(line_color=rgba(c), line_width=w, line_style="dash" if dash else "solid", capstyle="round")}'
            f'</Option></layer></symbol>')


def sym_fill(n, c, w=0.6, a=30, dash=False):
    return (f'<symbol type="fill" name="{n}" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" '
            f'enabled="1" pass="0" locked="0"><Option type="Map">'
            f'{opt(color=rgba(c, a), style="solid", outline_color=rgba(c), outline_width=w, outline_style="dash" if dash else "solid")}'
            f'</Option></layer></symbol>')


def sym_line_spostata(n, c, w, dx, dy):
    """Linea disegnata traslata (generatore di geometria): i dati restano invariati."""
    inner = (f'<symbol type="line" name="@{n}@0" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleLine" '
             f'enabled="1" pass="0" locked="0"><Option type="Map">'
             f'{opt(line_color=rgba(c), line_width=w, line_style="solid", capstyle="round")}</Option></layer></symbol>')
    return (f'<symbol type="line" name="{n}" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="GeometryGenerator" '
            f'enabled="1" pass="0" locked="0"><Option type="Map">'
            f'{opt(SymbolType="Line", geometryModifier=f"translate($geometry, {dx}, {dy})", units="MapUnit")}'
            f'</Option>{inner}</layer></symbol>')


def labels(field, size=8, color='#000000', scala_max=None, placement=2):
    vis = f'scaleVisibility="1" scaleMin="1" scaleMax="{scala_max}"' if scala_max else 'scaleVisibility="0"'
    return (f'<labeling type="simple"><settings calloutType="simple"><text-style fieldName="{field}" isExpression="0" '
            f'fontSize="{size}" fontSizeUnit="Point" textColor="{rgba(color)}" textOpacity="1" fontWeight="75" '
            f'fontFamily="Arial"><text-buffer bufferDraw="1" bufferSize="0.8" bufferSizeUnits="MM" '
            f'bufferColor="255,255,255,255" bufferOpacity="1"/></text-style><placement placement="{placement}" dist="1"/>'
            f'<rendering {vis}/></settings></labeling>')


def single(sym):
    return f'<renderer-v2 type="singleSymbol" enableorderby="0" forceraster="0" symbollevels="0"><symbols>{sym}</symbols></renderer-v2>'


def categorized(field, cats):
    s = ''.join(sym(str(k)) for k, (_, _, sym) in enumerate(cats))
    c = ''.join(f'<category render="true" symbol="{k}" value="{v}" label="{l}"/>' for k, (v, l, _) in enumerate(cats))
    return (f'<renderer-v2 type="categorizedSymbol" attr="{field}" enableorderby="0" forceraster="0" symbollevels="0">'
            f'<categories>{c}</categories><symbols>{s}</symbols></renderer-v2>')


def salva_stili(f, stili):
    con = sqlite3.connect(f)
    con.execute('''CREATE TABLE IF NOT EXISTS layer_styles (id INTEGER PRIMARY KEY AUTOINCREMENT,
        f_table_catalog TEXT(256), f_table_schema TEXT(256), f_table_name TEXT(256), f_geometry_column TEXT(256),
        styleName TEXT(30), styleQML TEXT, styleSLD TEXT, useAsDefault BOOLEAN, description TEXT, owner TEXT(30),
        ui TEXT(30), update_time DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    for lay, (ren, lab) in stili.items():
        con.execute('UPDATE layer_styles SET useAsDefault=0 WHERE f_table_name=?', (lay,))
        q = (f"<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'><qgis version=\"3.28\" "
             f"styleCategories=\"Symbology|Labeling\">{ren}{lab}</qgis>")
        con.execute('INSERT INTO layer_styles (f_table_catalog,f_table_schema,f_table_name,f_geometry_column,styleName,'
                    'styleQML,styleSLD,useAsDefault,description,owner,update_time) VALUES (?,?,?,?,?,?,?,?,?,?,'
                    "strftime('%Y-%m-%dT%H:%M:%SZ','now'))", ('', '', lay, 'geom', lay, q, '', 1, 'stile predefinito', ''))
    con.commit(); con.close()


def excel(f, fogli, note=None):
    """fogli: {nome: DataFrame}; note: {nome: [righe di testo sopra la tabella]}"""
    note = note or {}
    with pd.ExcelWriter(nuovo(f), engine='openpyxl') as w:
        for n, d in fogli.items():
            r0 = len(note.get(n, [])) + (1 if note.get(n) else 0)
            d.to_excel(w, sheet_name=n, index=False, startrow=r0)
    wb = load_workbook(f)
    for n, d in fogli.items():
        ws = wb[n]
        r0 = len(note.get(n, [])) + (1 if note.get(n) else 0)
        for k, t in enumerate(note.get(n, []), 1):
            ws.cell(k, 1, t).font = Font(bold=(k == 1), italic=(k > 1))
        for c in ws[r0 + 1]:
            c.font = Font(bold=True, color='FFFFFF'); c.fill = PatternFill('solid', fgColor='2F5597')
            c.alignment = Alignment(wrap_text=True, vertical='center')
        for k, col in enumerate(d.columns, 1):
            lun = max([len(str(col))] + [len(str(v)) for v in d[col].head(300)])
            ws.column_dimensions[ws.cell(r0 + 1, k).column_letter].width = min(max(10, lun + 2), 70)
        ws.freeze_panes = ws.cell(r0 + 2, 2)
        if 'Classe' in ' '.join(d.columns):
            for k, col in enumerate(d.columns, 1):
                if col.startswith('Classe'):
                    for r in range(r0 + 2, r0 + 2 + len(d)):
                        v = ws.cell(r, k).value
                        if v in CLS:
                            ws.cell(r, k).fill = PatternFill('solid', fgColor=CLS[v][1:])
                            ws.cell(r, k).font = Font(color='FFFFFF' if v != 'quasi compatibile' else '000000')
    wb.save(f)


# ---------- dati ----------
T = pd.read_csv(p('consegna_situazioni_dubbie_v3', 'situazioni_dubbie_212.csv')).set_index('ID')
I = gpd.read_file(p('drive_ponti_iniziali', 'ponti_iniziali.shp')).to_crs(32633).set_index('ID')
PI = pd.read_csv(p('ricalcolo_iniziali', 'parametri morfologici.csv'))
PI['ID'] = PI.ID.astype(int); PI = PI.set_index('ID')
PF = pd.read_csv(p('ricalcolo_212', 'parametri morfologici.csv'))
PF['ID'] = PF.ID.astype(int); PF = PF.set_index('ID')
pc = pd.read_csv(p('ricalcolo_212', 'ponti.csv')).set_index('id')
F = gpd.GeoDataFrame(geometry=gpd.points_from_xy(pc.X, pc.Y), index=pc.index, crs=4326).to_crs(32633)
assert sorted(T.index) == sorted(I.index) == list(range(1, 213))
mossi = sorted(I.index[I.spost_m > 0])
solo_porz = sorted(I.index[(I.spost_m == 0) & (I.modificato == 'si')])
assert set(mossi) == set(PI.index)


def categoria(i):
    m = str(I.motivo[i])
    if i in solo_porz:
        return 'solo porzione di calcolo allargata'
    if 'relazione' in m or 'affluente' in m:
        return 'sezione secondo la relazione di ispezione (multi-asta)'
    if 'tombino' in m:
        return 'sezione sul taglio del tombino'
    if 'soglia' in m:
        return 'sezione sul tracciato KML (fosso piccolo, soglia ridotta)'
    return 'sezione sul tracciato KML'


# ---------- 0. modifiche al codice ----------
d0 = cartella('0_modifiche_codice')
shutil.copy2(p('ricalcolo_212', 'pysheds_bridges_5m.py'), d0)
cod = open(p('ricalcolo_212', 'pysheds_bridges_5m.py'), encoding='utf-8').read().splitlines()
righe = [f'riga {k}: {t.strip()}' for k, t in enumerate(cod, 1) if '[MODIFICA' in t]
with open(os.path.join(d0, 'elenco_modifiche.txt'), 'w', encoding='utf-8') as f:
    f.write('Modifiche al codice pysheds_bridges.py (righe marcate [MODIFICA 5 m] in pysheds_bridges_5m.py)\n\n'
            'Le modifiche riguardano solo la lettura dei dati e l\'organizzazione del calcolo:\n'
            '1. DEM e Curve Number letti da un unico file tif (mosaico) invece dei file .asc per finestra.\n'
            '2. Un solo lancio per tutti i 212 ponti: il codice elabora una porzione alla volta (limiti in ponti.csv)\n'
            '   e alla fine unisce parametri, bacini e reticolo; le porzioni gia\' elaborate vengono saltate.\n'
            '3. Soglia del reticolo 4000 celle da 25 m2 = 0.1 km2 (era 500 celle), avviso di aggancio a 10 m (era 50).\n'
            '4. resolve_flats con eps=1e-6 e max_iter=10000 (con i valori di default le grandi aree piatte restano\n'
            '   senza direzione di deflusso).\n'
            '5. Colonna facoltativa "soglia" in ponti.csv: soglia di aggancio ridotta per i fossi piccoli (10 ponti).\n'
            '6. Avviso se il bacino tocca il bordo della porzione (possibile bacino troncato).\n'
            '7. Compatibilita\' con numpy 2 (np.in1d, conversione del bacino in uint8).\n\n'
            'Le formule dei parametri morfometrici, la catena fill_pits - fill_depressions - resolve_flats - D8 -\n'
            'accumulo e lo snap_to_mask non sono cambiati. Verifica: il ricalcolo dei 212 ponti con questo codice\n'
            'riproduce esattamente i valori del database consegnato.\n\nRighe marcate nel codice:\n' + '\n'.join(righe) + '\n')

# ---------- 1. prima analisi ----------
d1 = cartella('1_prima_analisi')
rows = []
for i in range(1, 213):
    r = T.A_relazione_km2[i]
    a = PI.A_km2[i] if i in mossi else T.A_calcolata_km2[i]
    rows.append({'ID': i, 'SP': T.SP[i], 'km': T.km[i], 'Nome_opera': T.Nome_opera[i], 'A_relazione_km2': r,
                 'A_prima_analisi_km2': round(a, 3),
                 'Diff_perc': None if pd.isna(r) else round((a - r) / r * 100, 1),
                 'Classe_prima_analisi': classe(a, r),
                 'Punto_poi_spostato': 'si' if i in mossi else 'no'})
A1 = pd.DataFrame(rows)
# controllo: per i ponti non spostati la classe coincide con quella finale
ok = A1[A1.Punto_poi_spostato == 'no'].set_index('ID')
assert (ok.Classe_prima_analisi == T.loc[ok.index, 'Classe'].replace({'senza area': 'senza area relazione'})).all()
g1 = gpd.GeoDataFrame(A1.copy(), geometry=list(I.geometry.loc[A1.ID]), crs=32633)
g1['X_UTM33N'] = g1.geometry.x.round(2); g1['Y_UTM33N'] = g1.geometry.y.round(2)
f1 = nuovo(os.path.join(d1, 'prima_analisi.gpkg'))
g1.to_file(f1, layer='punti_prima_analisi', driver='GPKG')
BI = gpd.read_file(p('ricalcolo_iniziali', 'bacini_afferenti.geojson')).to_crs(32633)
BI['ID'] = BI.ID.astype(int)
BI = BI[['ID', 'geometry']].merge(A1[['ID', 'A_relazione_km2', 'A_prima_analisi_km2', 'Classe_prima_analisi']], on='ID')
BI['Etichetta'] = [f'{i} prima analisi ({a:g} km2)' for i, a in zip(BI.ID, BI.A_prima_analisi_km2)]
BI.sort_values('A_prima_analisi_km2', ascending=False).to_file(f1, layer='bacini_prima_analisi_ponti_spostati', driver='GPKG')
salva_stili(f1, {
    'punti_prima_analisi': (categorized('Classe_prima_analisi', [(c, c, lambda n, c=c: sym_point(n, CLS[c], 2.6, 'square'))
                                                                for c in CLS]), labels('ID', 8)),
    'bacini_prima_analisi_ponti_spostati': (categorized('Classe_prima_analisi', [(c, c, lambda n, c=c: sym_fill(n, CLS[c], 0.6, 15, True))
                                                                                for c in CLS]), labels('Etichetta', 8, '#555555', 100000, 0)),
})
cnt1 = A1.Classe_prima_analisi.value_counts()
excel(os.path.join(d1, 'prima_analisi.xlsx'), {'Prima_analisi_212': A1}, {'Prima_analisi_212': [
    'Prima analisi: codice lanciato sui punti nella posizione iniziale',
    'Per i 23 ponti poi spostati l\'area e\' ricalcolata con il codice invariato sulla posizione iniziale; per gli altri coincide con quella finale.',
    'Classi: compatibile |diff| <= 15%; quasi compatibile |diff| <= 25%, oppure |diff| <= 0.1 km2 e |diff| <= 50%; altrimenti non compatibile.']})

# ---------- 2. spostamento dei punti ----------
d2 = cartella('2_spostamento_punti')
fin_cls = T.Classe.replace({'senza area': 'senza area relazione'})
rows, linee = [], []
for i in mossi + solo_porz:
    r = T.A_relazione_km2[i]
    ai = PI.A_km2[i] if i in mossi else None
    af = T.A_calcolata_km2[i]
    rows.append({'ID': i, 'Nome_opera': T.Nome_opera[i], 'Tipo_modifica': categoria(i),
                 'Spostamento_m': round(float(I.spost_m[i]), 1), 'Porzione_iniziale': I.porz_ini[i],
                 'Porzione_finale': I.porz_fin[i],
                 'Soglia_aggancio_celle': '' if pd.isna(I.soglia[i]) else int(I.soglia[i]),
                 'Motivo': I.motivo[i], 'A_relazione_km2': r,
                 'A_prima_km2': '' if ai is None else round(ai, 3),
                 'Classe_prima': A1.set_index('ID').Classe_prima_analisi[i] if i in mossi else '(punto non spostato)',
                 'A_finale_km2': af, 'Diff_finale_perc': T.Diff_perc[i], 'Classe_finale': fin_cls[i],
                 'Caso_dubbio_finale': T.Categoria[i]})
    if i in mossi:
        linee.append({'ID': i, 'Tipo_modifica': categoria(i), 'Spostamento_m': round(float(I.spost_m[i]), 1),
                      'Etichetta': f'{i}: {I.spost_m[i]:.0f} m', 'geometry': LineString([I.geometry[i], F.geometry[i]])})
S2 = pd.DataFrame(rows).sort_values('ID')
f2 = nuovo(os.path.join(d2, 'spostamento_punti.gpkg'))
gpd.GeoDataFrame(linee, crs=32633).to_file(f2, layer='spostamenti', driver='GPKG')
gi = gpd.GeoDataFrame(S2[S2.ID.isin(mossi)].copy(), geometry=list(I.geometry.loc[mossi]), crs=32633)
gf = gpd.GeoDataFrame(S2[S2.ID.isin(mossi)].copy(), geometry=list(F.geometry.loc[mossi]), crs=32633)
gi.to_file(f2, layer='posizione_iniziale', driver='GPKG')
gf.to_file(f2, layer='posizione_finale', driver='GPKG')
salva_stili(f2, {
    'spostamenti': (categorized('Tipo_modifica', [(c, c, lambda n, c=c: sym_line(n, MOT[c], 0.8, True)) for c in MOT if c in set(S2.Tipo_modifica) and c != 'solo porzione di calcolo allargata']),
                    labels('Etichetta', 8, '#000000', 25000)),
    'posizione_iniziale': (single(sym_point('0', '#ffffff', 3.0, 'square')), labels('ID', 8, '#555555', 25000)),
    'posizione_finale': (categorized('Tipo_modifica', [(c, c, lambda n, c=c: sym_point(n, MOT[c], 3.2)) for c in MOT if c in set(S2.Tipo_modifica)]),
                         labels('ID', 9)),
})
# riepilogo delle classi prima e dopo
ordine = list(CLS)
cnt_f = fin_cls.value_counts()
R2 = pd.DataFrame({'Classe': ordine,
                   'Prima analisi (212 ponti)': [int(cnt1.get(c, 0)) for c in ordine],
                   'Finale (212 ponti)': [int(cnt_f.get(c, 0)) for c in ordine],
                   'Prima analisi (23 ponti spostati)': [int((A1[A1.ID.isin(mossi)].Classe_prima_analisi == c).sum()) for c in ordine],
                   'Finale (23 ponti spostati)': [int((fin_cls.loc[mossi] == c).sum()) for c in ordine]})
C = pd.read_csv(p('ricalcolo_centri', 'confronto_centri_212.csv'))
C['Esito'] = ['identico' if pd.isna(q) or q == '' else ('stessa area, altri parametri diversi' if d == 0 else
              ('area diversa meno del 2%' if abs(d) < 2 else 'bacino diverso (altra asta)'))
              for q, d in zip(C.Parametri_diversi, C.Diff_area_perc)]
C = C.rename(columns={'A_orig_km2': 'A_punto_usato_km2', 'A_centri_km2': 'A_punto_al_centro_cella_km2',
                      'Snap_orig_m': 'Aggancio_punto_usato_m', 'Snap_centri_m': 'Aggancio_centro_cella_m'})
C = C[['ID', 'A_punto_usato_km2', 'A_punto_al_centro_cella_km2', 'Diff_area_perc', 'Aggancio_punto_usato_m',
       'Aggancio_centro_cella_m', 'Esito', 'Parametri_diversi']]
RC = C.Esito.value_counts().rename_axis('Esito').reset_index(name='Ponti')
excel(os.path.join(d2, 'spostamento_punti.xlsx'),
      {'Riepilogo_classi': R2, 'Ponti_modificati': S2, 'Verifica_centro_cella': C, 'Riepilogo_centro_cella': RC},
      {'Riepilogo_classi': ['Effetto dello spostamento dei punti sulle classi di compatibilita\'',
                            'Codice invariato; cambia solo la posizione del punto (23 ponti) o l\'estensione della porzione di calcolo (8 ponti).'],
       'Ponti_modificati': ['Ponti modificati tra prima analisi e analisi finale',
                            'Regola: sezione dove il tracciato del ponte nel KML attraversa il reticolo, cella con accumulo maggiore; l\'area della relazione non entra nella scelta.',
                            'Eccezioni dichiarate: 107, 108, 109, 111, 196 sezione della relazione di ispezione (multi-asta); 105 taglio del tombino.'],
       'Verifica_centro_cella': ['Verifica: codice rilanciato con i punti al centro della cella del reticolo',
                                 'Il punto al centro e\' alla stessa distanza (3.5 m) dai 4 angoli usati da snap_to_mask: la scelta della cella diventa arbitraria.',
                                 'Con il punto usato (1.25 m dall\'angolo in alto a sinistra) la cella agganciata e\' sempre quella che contiene il punto.']})

# ---------- 3. confronto aree (dalla versione 1) ----------
d3 = cartella('3_confronto_aree')
for a, b in (('1_reticolo_idrografico.gpkg', 'reticolo_idrografico.gpkg'), ('2_bacini_codice.gpkg', 'bacini_codice.gpkg'),
             ('3_punti_attraversamenti.gpkg', 'punti_attraversamenti.gpkg')):
    shutil.copy2(os.path.join(V1, a), os.path.join(d3, b))
# reticolo disegnato spostato di mezza cella (+2.5 m E, -2.5 m N): passa per i centri delle celle e sui punti.
# I dati del reticolo non cambiano.
salva_stili(os.path.join(d3, 'reticolo_idrografico.gpkg'),
            {'reticolo_idrografico': (single(sym_line_spostata('0', '#2b7bff', 0.4, 2.5, -2.5)), '')})
A3 = T.reset_index()[['ID', 'SP', 'km', 'Nome_opera', 'A_relazione_km2', 'A_calcolata_km2', 'Diff_km2', 'Diff_perc', 'Classe']]
A3['Classe'] = A3.Classe.replace({'senza area': 'senza area relazione'})
A3 = A3.merge(PF[['S', 'AE_m', 'Relief_m', 'Longest_flow_length_km', 'Basin_Perimeter_km', 'Curve_Number_mean',
                  'Reach_Slope_Centered', 'Snap_Distance_m']].reset_index(), on='ID')
R3 = A3.Classe.value_counts().reindex(ordine).fillna(0).astype(int).rename_axis('Classe').reset_index(name='Ponti')
excel(os.path.join(d3, 'confronto_aree.xlsx'), {'Riepilogo': R3, 'Confronto_212': A3},
      {'Confronto_212': ['Confronto tra area calcolata dal codice e area della relazione (212 ponti)',
                         'Ponti 21 e 190: area della relazione corretta (13.33 e 2.167 km2).']})

# ---------- 4. casi dubbi (dalla versione 1) ----------
d4 = os.path.join(out, '4_casi_dubbi')
if os.path.exists(d4):
    shutil.rmtree(d4)
shutil.copytree(os.path.join(V1, '4_casi_dubbi'), d4)

# ---------- 5. verifica manuale ID100 ----------
d5 = cartella('5_verifica_manuale_ID100')
shutil.copy2(p('upload_verifica', 'ed7fea45-ID100_VERIFICA_MANUALE_ATTRAVERSAMENTO.xlsm'),
             os.path.join(d5, 'ID100_VERIFICA_MANUALE_ATTRAVERSAMENTO.xlsm'))
for f in ('Manuale_verifica_generico.pdf', 'Manuale_verifica_generico.docx', 'Foglio_calcolo_verifica_generico.xlsx'):
    shutil.copy2(os.path.join(MAN, f), d5)
q = os.path.join(d5, 'Verifiche_Manuali_QGIS')
if os.path.exists(q):
    shutil.rmtree(q)
shutil.copytree(p('upload_verifica', 'qgis', 'Verifiche_Manuali'), q,
                ignore=shutil.ignore_patterns('p100_percorsi_lung.gpkg', 'p100_percorsi_sorgenti.gpkg'))

print('prima analisi', cnt1.to_dict())
print('finale', cnt_f.to_dict())
print(R2.to_string(index=False))
print(RC.to_string(index=False))
