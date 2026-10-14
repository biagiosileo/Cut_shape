"""
Probabile origine dell'errore per i ponti non compatibili, con controlli che
non usano l'area del database:
  1. coerenza monte-valle: se la sezione di un ponte A cade nel bacino di un
     ponte B, A e' a monte di B e deve avere area minore; si segnalano le
     coppie in cui l'area DB di A supera quella di B di oltre il 15%;
  2. larghezza dell'alveo inciso (database): stima A = a*W^b ricavata sui
     ponti in cui il tracciato interseca un solo corso (senza usare l'area DB);
     un'area e' "implausibile" se dista piu' di 2 deviazioni standard (in log);
  3. corso compatibile con la larghezza entro 100 m dal tracciato.

Aggiunge le colonne all'Excel dei risultati e crea il GeoPackage per la
verifica manuale con i soli ponti non compatibili (ID del database).

Uso: python origine_errore.py <Risultati_5m_ibrido.xlsx> <risultati_5m.gpkg>
        <controllo_coordinate.gpkg> <Database.xlsx> <cartella_toppe> <out_dir>
"""
import os
import sqlite3
import sys

import numpy as np
import pandas as pd
import geopandas as gpd
from affine import Affine

TOL = 0.15
xlsx, rgpkg, cgpkg, dbx, tdir, out = sys.argv[1:7]
os.makedirs(out, exist_ok=True)

t = pd.read_excel(xlsx, sheet_name=None)
P = t['Ponti'].set_index('ID')
adb = P['Area database (km²)']
a5 = P['Area calcolata 5 m (km²)']
ok = P['Compatibile (±15%)'] == True  # noqa: E712
db = pd.read_excel(dbx).rename(columns={'Unnamed: 0': 'ID'})
db = db[pd.to_numeric(db.ID, errors='coerce').notna()]
db['ID'] = db.ID.astype(int)
W = pd.to_numeric(db.set_index('ID')['LARGHEZZA ALVEO INCISO (m)'], errors='coerce')

bac = gpd.read_file(rgpkg, layer='bacini').set_index('ID')
sez = gpd.read_file(rgpkg, layer='sezioni_chiusura').set_index('ID')
trc = gpd.read_file(cgpkg, layer='tracciato_usato').set_index('ID')

# 1. coerenza monte-valle
coppie = []
si = sez.sindex
for b, poly in bac.geometry.items():
    for a in sez.index[list(si.query(poly, predicate='intersects'))]:
        if a != b and a5[a] < a5[b] * 0.999:
            coppie.append((a, b))
C = pd.DataFrame(coppie, columns=['ID_monte', 'ID_valle'])
C['A_db_monte'] = C.ID_monte.map(adb)
C['A_db_valle'] = C.ID_valle.map(adb)
C['A_calc_monte'] = C.ID_monte.map(a5)
C['A_calc_valle'] = C.ID_valle.map(a5)
C['Violazione_DB'] = C.A_db_monte > C.A_db_valle * (1 + TOL)
viol = C[C.Violazione_DB]
note_mv = {}
for _, r in viol.iterrows():
    note_mv.setdefault(r.ID_monte, []).append(
        f'DB {r.A_db_monte:g} km² ma è a monte dell\'ID {r.ID_valle} (DB {r.A_db_valle:g} km²)')
    note_mv.setdefault(r.ID_valle, []).append(
        f'DB {r.A_db_valle:g} km² ma è a valle dell\'ID {r.ID_monte} (DB {r.A_db_monte:g} km²)')

# 2. larghezza alveo
rif = P[(P['Aggancio'] == 'sul tracciato') & (P['N. corsi intersecati'] <= 1)].index
d = pd.DataFrame({'a': a5, 'w': W}).loc[rif].dropna()
d = d[d.w > 0]
bb, aa = np.polyfit(np.log(d.w), np.log(d.a), 1)
sd = float(np.std(np.log(d.a) - (aa + bb * np.log(d.w))))
A_w = np.exp(aa + bb * np.log(W.where(W > 0)))
z_db = (np.log(adb.where(adb > 0)) - np.log(A_w)) / sd
z_calc = (np.log(a5) - np.log(A_w)) / sd

# 3. corso compatibile con la larghezza vicino al tracciato
A_guid = {}
for i in P.index[~ok & adb.notna()]:
    if pd.isna(A_w.get(i)) or i not in trc.index:
        continue
    z = np.load(os.path.join(tdir, f'id{i:03d}.npz'))
    A = z['acc_km2']
    T = Affine(*z['transform'])
    R, Cc = np.mgrid[0:A.shape[0], 0:A.shape[1]]
    X, Y = T * (Cc + 0.5, R + 0.5)
    line = trc.geometry[i]
    pts = np.array([line.interpolate(f, normalized=True).coords[0] for f in np.linspace(0, 1, 21)])
    dd = np.min(np.hypot(X[..., None] - pts[:, 0], Y[..., None] - pts[:, 1]), axis=2)
    m = (dd <= 100) & (A >= 0.1)
    if m.any():
        c = A[m]
        A_guid[i] = float(c[np.argmin(np.abs(np.log(c / A_w[i])))])
A_guid = pd.Series(A_guid)

coord_err = {83, 90, 143, 77, 204}
db_anomali = {98, 99, 101, 103, 129, 151}


def origine(i):
    if pd.isna(adb[i]):
        return 'Area DB mancante'
    if ok[i]:
        return 'Compatibile'
    zdb, zc = z_db.get(i), z_calc.get(i)
    db_impl = pd.notna(zdb) and abs(zdb) > 2
    c_impl = pd.notna(zc) and abs(zc) > 2
    g = A_guid.get(i)
    guid_ok = pd.notna(g) and abs(g / adb[i] - 1) <= TOL
    if i in db_anomali:
        return 'Database: valore anomalo'
    if i in coord_err:
        return 'Coordinate: errore nel database/KML'
    if i in note_mv and not c_impl:
        return 'Database: incoerente con i ponti a monte/valle'
    if guid_ok:
        return 'Calcolo: aggancio al corso sbagliato (corso compatibile entro 100 m)'
    if db_impl and not c_impl:
        return 'Database: area implausibile per la larghezza dell\'alveo'
    if c_impl and not db_impl:
        return 'Calcolo/posizione: area calcolata implausibile per la larghezza dell\'alveo'
    return 'Indeterminato: serve verifica su ortofoto'


P['Probabile origine errore'] = [origine(i) for i in P.index]
P['Area stimata da larghezza alveo (km²)'] = A_w
P['Larghezza alveo inciso DB (m)'] = W
P['Scarto DB vs larghezza (dev.std)'] = z_db
P['Scarto calcolata vs larghezza (dev.std)'] = z_calc
P['Area corso compatibile con larghezza entro 100 m (km²)'] = A_guid
P['Coerenza monte-valle'] = pd.Series({k: '; '.join(v) for k, v in note_mv.items()})
t['Ponti'] = P.reset_index()
t['Coppie monte-valle'] = C
t['Origine errore'] = P[P['Probabile origine errore'] != 'Compatibile'].reset_index()[
    ['ID', 'Strada', 'Progressiva', 'Area database (km²)', 'Area calcolata 5 m (km²)', 'Differenza %',
     'Probabile origine errore', 'Larghezza alveo inciso DB (m)', 'Area stimata da larghezza alveo (km²)',
     'Scarto DB vs larghezza (dev.std)', 'Scarto calcolata vs larghezza (dev.std)',
     'Area corso compatibile con larghezza entro 100 m (km²)', 'Coerenza monte-valle', 'Segnalazioni']]
t['Metodo'] = pd.concat([t['Metodo'], pd.DataFrame({'Metodo': [
    f'Probabile origine dell\'errore (solo indicativa): coerenza monte-valle tra ponti (sezione di un ponte nel '
    f'bacino di un altro); larghezza dell\'alveo inciso del database con A = {np.exp(aa):.3f}·W^{bb:.2f} '
    f'(stimata su {len(d)} ponti con tracciato che interseca un solo corso, senza usare l\'area DB; '
    f'dev.std {sd:.2f} in log, "implausibile" oltre 2 dev.std); corso compatibile con la larghezza entro 100 m '
    f'dal tracciato.']})], ignore_index=True)
xo = os.path.join(out, os.path.basename(xlsx))
with pd.ExcelWriter(xo, engine='openpyxl') as w:
    for name, df in t.items():
        df.to_excel(w, sheet_name=name[:31], index=False)
        ws = w.sheets[name[:31]]
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(
                max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 60)
        ws.freeze_panes = 'B2'
        for j, n in enumerate(df.columns, 1):
            if n == 'Differenza %':
                for row in ws.iter_rows(min_row=2, min_col=j, max_col=j):
                    row[0].number_format = '0.0%'

# ---------------- GeoPackage per la verifica manuale ----------------
nc = P.index[(~ok) & adb.notna()]
att = P.loc[nc, ['Gruppo', 'Strada', 'Progressiva', 'Nome opera', 'Area database (km²)',
                 'Area calcolata 5 m (km²)', 'Differenza %', 'Esito', 'Probabile origine errore',
                 'Larghezza alveo inciso DB (m)', 'Area stimata da larghezza alveo (km²)',
                 'Area corso compatibile con larghezza entro 100 m (km²)', 'Coerenza monte-valle',
                 'Segnalazioni']].copy()
att.columns = ['Gruppo', 'Strada', 'Progressiva', 'Nome_opera', 'A_DB_km2', 'A_calc_km2', 'Diff_pct', 'Esito',
               'Origine_errore', 'Larghezza_alveo_m', 'A_da_larghezza_km2', 'A_corso_vicino_km2',
               'Monte_valle', 'Segnalazioni']
att['Diff_pct'] = att.Diff_pct * 100
att['Verificato'] = ''
att['Esito_verifica'] = ''
att['Note_verifica'] = ''
att = att.reset_index()
gp = os.path.join(out, 'verifica_ponti_non_compatibili.gpkg')
if os.path.exists(gp):
    os.remove(gp)
cl = {n: gpd.read_file(cgpkg, layer=n).set_index('ID') for n in
      ('input_script', 'db_inizio', 'db_fine', 'kml_abbinato', 'db_attraversamento_inizio_fine')}


def strato(src, nome, extra=None):
    g = src.loc[src.index.intersection(nc), ['geometry']].reset_index()
    g = g.merge(att[['ID', 'Strada', 'Progressiva', 'A_DB_km2', 'A_calc_km2', 'Origine_errore']], on='ID')
    if extra is not None:
        g = g.merge(extra, on='ID', how='left')
    gpd.GeoDataFrame(g, geometry='geometry', crs=32633).to_file(gp, layer=nome, driver='GPKG')


g = cl['input_script'].loc[nc, ['geometry']].reset_index().merge(att, on='ID')
gpd.GeoDataFrame(g, geometry='geometry', crs=32633).to_file(gp, layer='ponti_da_verificare', driver='GPKG')
strato(sez, 'sezione_chiusura_calcolata')
strato(bac, 'bacino_calcolato')
strato(trc, 'tracciato_kml')
strato(cl['kml_abbinato'], 'punto_kml')
strato(cl['db_inizio'], 'db_inizio')
strato(cl['db_fine'], 'db_fine')
strato(cl['db_attraversamento_inizio_fine'], 'db_segmento_inizio_fine')
# strato vuoto da compilare: sezione corretta digitalizzata su ortofoto
vuoto = gpd.GeoDataFrame({'ID': pd.Series([], dtype='int64'), 'Note': pd.Series([], dtype='str')},
                         geometry=gpd.GeoSeries([], crs=32633), crs=32633)
vuoto.to_file(gp, layer='sezione_corretta_DA_DIGITALIZZARE', driver='GPKG', geometry_type='Point')

# stili QGIS di default salvati nel GeoPackage
STILI = {
    'ponti_da_verificare': ('marker', 'circle', '0,0,0,255', '3.2', True),
    'sezione_chiusura_calcolata': ('marker', 'cross_fill', '26,152,80,255', '4', False),
    'punto_kml': ('marker', 'star', '242,194,0,255', '4.5', False),
    'db_inizio': ('marker', 'triangle', '192,0,0,255', '3', False),
    'db_fine': ('marker', 'square', '192,0,0,255', '2.6', False),
    'sezione_corretta_DA_DIGITALIZZARE': ('marker', 'diamond', '0,170,255,255', '4.5', True),
    'tracciato_kml': ('line', None, '90,90,90,255', '0.9', False),
    'db_segmento_inizio_fine': ('line', None, '192,0,0,255', '0.4', False),
    'bacino_calcolato': ('fill', None, '123,50,148,255', '0.5', False),
}


def qml(kind, shape, col, size, label):
    if kind == 'marker':
        lay = (f'<layer class="SimpleMarker" enabled="1" pass="0" locked="0"><Option type="Map">'
               f'<Option name="name" value="{shape}" type="QString"/><Option name="color" value="{col}" type="QString"/>'
               f'<Option name="size" value="{size}" type="QString"/>'
               f'<Option name="outline_color" value="255,255,255,255" type="QString"/>'
               f'<Option name="outline_width" value="0.3" type="QString"/></Option></layer>')
    elif kind == 'line':
        lay = (f'<layer class="SimpleLine" enabled="1" pass="0" locked="0"><Option type="Map">'
               f'<Option name="line_color" value="{col}" type="QString"/>'
               f'<Option name="line_width" value="{size}" type="QString"/></Option></layer>')
    else:
        lay = (f'<layer class="SimpleFill" enabled="1" pass="0" locked="0"><Option type="Map">'
               f'<Option name="style" value="no" type="QString"/>'
               f'<Option name="outline_color" value="{col}" type="QString"/>'
               f'<Option name="outline_width" value="{size}" type="QString"/></Option></layer>')
    lab = ''
    if label:
        lab = ('<labeling type="simple"><settings calloutType="simple"><text-style fieldName="ID" fontSize="9" '
               'textColor="0,0,0,255" fontWeight="75"><text-buffer bufferDraw="1" bufferSize="1" '
               'bufferColor="255,255,255,255"/></text-style><placement placement="0" dist="1.5"/>'
               '<rendering/></settings></labeling>')
    return (f'<!DOCTYPE qgis><qgis version="3.28" styleCategories="Symbology|Labeling">'
            f'<renderer-v2 type="singleSymbol" symbollevels="0" enableorderby="0" forceraster="0">'
            f'<symbols><symbol type="{kind}" name="0" alpha="1" clip_to_extent="1" force_rhr="0">{lay}</symbol>'
            f'</symbols><rotation/><sizescale/></renderer-v2>{lab}'
            f'<labelsEnabled>{1 if label else 0}</labelsEnabled></qgis>')


con = sqlite3.connect(gp)
con.execute("""CREATE TABLE IF NOT EXISTS layer_styles (id INTEGER PRIMARY KEY AUTOINCREMENT,
  f_table_catalog TEXT(256), f_table_schema TEXT(256), f_table_name TEXT(256), f_geometry_column TEXT(256),
  styleName TEXT(30), styleQML TEXT, styleSLD TEXT, useAsDefault BOOLEAN, description TEXT, owner TEXT(30),
  ui TEXT(30), update_time DATETIME DEFAULT CURRENT_TIMESTAMP)""")
for nome, (k, s, c, z, lb) in STILI.items():
    con.execute("INSERT INTO layer_styles (f_table_catalog,f_table_schema,f_table_name,f_geometry_column,styleName,"
                "styleQML,styleSLD,useAsDefault,description) VALUES ('','',?, 'geom', ?, ?, '', 1, 'stile verifica')",
                (nome, nome, qml(k, s, c, z, lb)))
con.execute("INSERT OR IGNORE INTO gpkg_contents (table_name, data_type, identifier, description) "
            "VALUES ('layer_styles', 'attributes', 'layer_styles', 'stili QGIS')")
con.commit()
con.close()
print(P['Probabile origine errore'].value_counts().to_string())
print('non compatibili nel GeoPackage:', len(nc))
