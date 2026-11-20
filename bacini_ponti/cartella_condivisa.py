"""
Cartella da condividere: reticolo, bacini ponte per ponte, punti degli attraversamenti, casi dubbi.
Tutti i dati vengono dalle uscite gia' prodotte (solo lette):
  - ricalcolo dei 212 ponti con il codice pysheds_bridges_5m.py (reticolo, bacini, parametri, ponti.csv);
  - situazioni dubbie versione 3 (Excel e GeoPackage).

Uso: python cartella_condivisa.py <cartella ricalcolo_212> <cartella situazioni dubbie v3> <cartella uscita>
"""
import os
import shutil
import sqlite3
import sys

import geopandas as gpd
import pandas as pd

ric, v3, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
T = pd.read_csv(os.path.join(v3, 'situazioni_dubbie_212.csv')).set_index('ID', drop=False)
Pm = pd.read_csv(os.path.join(ric, 'parametri morfologici.csv'))
Pm['ID'] = Pm['ID'].astype(int)
Pm = Pm.set_index('ID')
pc = pd.read_csv(os.path.join(ric, 'ponti.csv')).set_index('id')
assert sorted(T.index) == list(range(1, 213)) and sorted(Pm.index) == list(range(1, 213))

HEX = {'non compatibile': '#d7191c', 'quasi compatibile': '#f39c33', 'multi-asta': '#8e44ad',
       'pianura e canali': '#2c7bb6', 'area relazione non riproducibile': '#a50f15',
       'sezione lontana dal ponte': '#e6c700', 'coordinate database errate': '#1b9e9e'}
CLS = {'compatibile': '#1a9641', 'quasi compatibile': '#f39c33', 'non compatibile': '#d7191c',
       'senza area relazione': '#9e9e9e'}


def rgba(c, a=255):
    return ','.join(str(int(c[k:k + 2], 16)) for k in (1, 3, 5)) + f',{a}'


def opt(**kw):
    return ''.join(f'<Option name="{k}" value="{v}" type="QString"/>' for k, v in kw.items())


def sym_point(n, c, size=3.0):
    return (f'<symbol type="marker" name="{n}" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleMarker" '
            f'enabled="1" pass="0" locked="0"><Option type="Map">'
            f'{opt(name="circle", color=rgba(c), outline_color="0,0,0,255", outline_width="0.3", size=size)}'
            f'</Option></layer></symbol>')


def sym_line(n, c, w=0.6, dash=False):
    return (f'<symbol type="line" name="{n}" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleLine" '
            f'enabled="1" pass="0" locked="0"><Option type="Map">'
            f'{opt(line_color=rgba(c), line_width=w, line_style="dash" if dash else "solid", capstyle="round")}'
            f'</Option></layer></symbol>')


def sym_fill(n, c, w=0.6, a=30):
    return (f'<symbol type="fill" name="{n}" alpha="1" clip_to_extent="1" force_rhr="0"><layer class="SimpleFill" '
            f'enabled="1" pass="0" locked="0"><Option type="Map">'
            f'{opt(color=rgba(c, a), style="solid", outline_color=rgba(c), outline_width=w)}'
            f'</Option></layer></symbol>')


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
        q = (f"<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'><qgis version=\"3.28\" "
             f"styleCategories=\"Symbology|Labeling\">{ren}{lab}</qgis>")
        con.execute('INSERT INTO layer_styles (f_table_catalog,f_table_schema,f_table_name,f_geometry_column,styleName,'
                    'styleQML,styleSLD,useAsDefault,description,owner,update_time) VALUES (?,?,?,?,?,?,?,?,?,?,'
                    "strftime('%Y-%m-%dT%H:%M:%SZ','now'))", ('', '', lay, 'geom', lay, q, '', 1, 'stile predefinito', ''))
    con.commit(); con.close()


def nuovo(nome):
    f = os.path.join(out, nome)
    if os.path.exists(f):
        os.remove(f)
    return f


info = T[['ID', 'SP', 'km', 'Nome_opera', 'A_relazione_km2', 'A_calcolata_km2', 'Diff_perc', 'Classe', 'Categoria']]
info = info.rename(columns={'Categoria': 'Caso_dubbio'}).reset_index(drop=True)

# 1. reticolo idrografico completo del codice
f1 = nuovo('1_reticolo_idrografico.gpkg')
R = gpd.read_file(os.path.join(ric, 'reticolo_idrografico.geojson')).to_crs(32633)
R.to_file(f1, layer='reticolo_idrografico', driver='GPKG')
salva_stili(f1, {'reticolo_idrografico': (single(sym_line('0', '#2b7bff', 0.4)), '')})

# 2. bacini del codice, un poligono per ponte (dal piu' grande al piu' piccolo: i piccoli stanno sopra)
f2 = nuovo('2_bacini_codice.gpkg')
B = gpd.read_file(os.path.join(ric, 'bacini_afferenti.geojson')).to_crs(32633)
B['ID'] = B['ID'].astype(int)
assert sorted(B.ID) == list(range(1, 213)), 'manca qualche bacino'
par = ['S', 'AE_m', 'Relief_m', 'Longest_flow_length_km', 'Basin_Perimeter_km', 'Curve_Number_mean',
       'Reach_Slope_Centered']
B = B[['ID', 'geometry']].merge(info, on='ID').merge(Pm[par].reset_index(), on='ID')
B['Etichetta'] = [f'{i} ({a:g} km2)' for i, a in zip(B.ID, B.A_calcolata_km2)]
B.sort_values('A_calcolata_km2', ascending=False).to_file(f2, layer='bacini_codice', driver='GPKG')
salva_stili(f2, {'bacini_codice': (categorized('Classe', [(c, c, lambda n, c=c: sym_fill(n, CLS[c])) for c in CLS]),
                                   labels('Etichetta', 8, '#333333', 100000, 0))})

# 3. punti degli attraversamenti su cui e' stato lanciato il codice (sezione di chiusura, ponti.csv)
f3 = nuovo('3_punti_attraversamenti.gpkg')
P = gpd.GeoDataFrame(info.copy(), geometry=gpd.points_from_xy(pc.loc[info.ID, 'X'], pc.loc[info.ID, 'Y']), crs=4326)
P['Lon'] = pc.loc[info.ID, 'X'].values; P['Lat'] = pc.loc[info.ID, 'Y'].values
P = P.to_crs(32633)
P['X_UTM33N'] = P.geometry.x.round(2); P['Y_UTM33N'] = P.geometry.y.round(2)
P['Soglia_aggancio_celle'] = pc.loc[info.ID, 'soglia'].fillna(4000).astype(int).values
P['Distanza_aggancio_m'] = Pm.loc[info.ID, 'Snap_Distance_m'].values
P.to_file(f3, layer='punti_attraversamenti', driver='GPKG')
salva_stili(f3, {'punti_attraversamenti': (categorized('Classe', [(c, c, lambda n, c=c: sym_point(n, CLS[c], 2.6))
                                                                  for c in CLS]), labels('ID', 8))})

# 4. casi dubbi: Excel della versione 3 e GeoPackage con i soli 33 ponti segnalati
os.makedirs(os.path.join(out, '4_casi_dubbi'), exist_ok=True)
shutil.copy2(os.path.join(v3, 'Database_situazioni_dubbie.xlsx'), os.path.join(out, '4_casi_dubbi', 'Database_casi_dubbi.xlsx'))
f4 = os.path.join(out, '4_casi_dubbi', 'casi_dubbi.gpkg')
if os.path.exists(f4):
    os.remove(f4)
g3 = os.path.join(v3, 'situazioni_dubbie.gpkg')
S = gpd.read_file(g3, layer='ponti_segnalati')
ids = set(S.ID.astype(int))
S.to_file(f4, layer='casi_dubbi', driver='GPKG')
for lay in ('ponte_kml', 'ponte_database', 'spostamento_sezione'):
    g = gpd.read_file(g3, layer=lay)
    g[g.ID.astype(int).isin(ids)].to_file(f4, layer=lay, driver='GPKG')
cats = [c for c in HEX if (S.Categoria == c).any()]
salva_stili(f4, {
    'casi_dubbi': (categorized('Categoria', [(c, c, lambda n, c=c: sym_point(n, HEX[c], 3.8)) for c in cats]), labels('ID', 9)),
    'ponte_kml': (single(sym_line('0', '#e31a1c', 1.4)), ''),
    'ponte_database': (categorized('Coordinate', [('corrette', 'ponte nel database (inizio-fine)',
                                                   lambda n: sym_line(n, '#ff00ff', 0.8)),
                                                  ('errate', 'ponte nel database con coordinate errate',
                                                   lambda n: sym_line(n, '#1b9e9e', 0.6, True))]),
                       labels('Nota', 8, '#1b9e9e')),
    'spostamento_sezione': (single(sym_line('0', '#000000', 0.5, True)), labels('Etichetta', 8, '#000000', 25000)),
})
print('reticolo', len(R), '; bacini', len(B), '; punti', len(P), '; casi dubbi', len(S))
print(P.Soglia_aggancio_celle.value_counts().to_dict(), P.Classe.value_counts().to_dict())
