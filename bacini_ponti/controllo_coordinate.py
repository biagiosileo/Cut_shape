"""
Controllo di coerenza delle coordinate dei 212 attraversamenti tra:
  - database (coordinate iniziali e finali dell'attraversamento);
  - doc.kml (punti di localizzazione e tracciati);
  - coordinate usate come input dello script per ciascun gruppo.

Produce un GeoPackage per QGIS (EPSG:32633) e una tabella Excel con distanze
e segnalazioni, una riga per ID. I file di ingresso sono solo letti.

Uso:
  python controllo_coordinate.py <Database.xlsx> <doc.kml> <input_ponti.csv> <cartella_out>
input_ponti.csv: ID, Longitude, Latitude (WGS84), file (gruppo); es. cmp.csv.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point

CRS_OUT = 32633
# Soglie (m) per le segnalazioni.
SOGLIA_INIZIO_FINE_M = 300.0   # distanza inizio-fine oltre cui l'attraversamento e' sospetto
SOGLIA_CONFRONTO_M = 50.0      # scarto tra fonti oltre cui si segnala
SOGLIA_KML_ABBINAMENTO_M = 500.0

db_path, kml_path, input_csv, out_dir = sys.argv[1:5]
os.makedirs(out_dir, exist_ok=True)
NS = {'k': 'http://www.opengis.net/kml/2.2'}


def num(s):
    """'40,571735°' / '16.574194 °' -> float."""
    return float(s.replace(',', '.'))


def parse_latlon(v):
    """Testo 'lat°, lon°' (separatore decimale . o ,) -> (lat, lon) o None."""
    if not isinstance(v, str):
        return None
    vals = re.findall(r'\d+[.,]\d+', v)
    if len(vals) != 2:
        return None
    lat, lon = num(vals[0]), num(vals[1])
    if not (39 < lat < 42 and 15 < lon < 18):   # lat/lon invertiti?
        lat, lon = lon, lat
    if not (39 < lat < 42 and 15 < lon < 18):
        return None
    return lat, lon


def norm_sp(s):
    m = re.search(r'SP\s*(\d+)', str(s).upper())
    return f'SP{m.group(1)}' if m else None


def norm_km(s):
    m = re.search(r'(\d+)\s*\+\s*(\d+)', str(s))
    return f'{int(m.group(1))}+{int(m.group(2)):03d}' if m else None


def to_utm(lon, lat):
    p = gpd.GeoSeries(gpd.points_from_xy(lon, lat), crs=4326).to_crs(CRS_OUT)
    return p.x.values, p.y.values


# ---------------- Database ----------------
db = pd.read_excel(db_path).rename(columns={'Unnamed: 0': 'ID'})
db = db[pd.to_numeric(db.ID, errors='coerce').notna()].copy()
db['ID'] = db.ID.astype(int)
ini = db['Coordinate iniziali [Lat., Long.]'].map(parse_latlon)
fin = db['Coordinate finali [Lat., Long.]'].map(parse_latlon)
T = pd.DataFrame({
    'ID': db.ID.values,
    'SP': db['NUOVA NUMERAZIONE'].values,
    'SP_GoogleEarth': db['DENOMINAZIONE GOOGLE EARTH'].values,
    'km': db['Progressiva km'].values,
    'Nome_opera': db['Nome opera'].values,
    'A_db_km2': pd.to_numeric(db['SUPERFICIE BACINO (km2)'], errors='coerce').values,
    'Coord_ini_testo': db['Coordinate iniziali [Lat., Long.]'].values,
    'Coord_fin_testo': db['Coordinate finali [Lat., Long.]'].values,
})
for pref, s in (('ini', ini), ('fin', fin)):
    T[f'{pref}_lat'] = [v[0] if v else np.nan for v in s]
    T[f'{pref}_lon'] = [v[1] if v else np.nan for v in s]
    x, y = to_utm(T[f'{pref}_lon'].fillna(0), T[f'{pref}_lat'].fillna(0))
    ok = T[f'{pref}_lat'].notna()
    T[f'{pref}_x'] = np.where(ok, x, np.nan)
    T[f'{pref}_y'] = np.where(ok, y, np.nan)
T['Dist_inizio_fine_m'] = np.hypot(T.ini_x - T.fin_x, T.ini_y - T.fin_y)
T['mid_x'] = T[['ini_x', 'fin_x']].mean(axis=1)
T['mid_y'] = T[['ini_y', 'fin_y']].mean(axis=1)

# ---------------- Input dei gruppi ----------------
inp = pd.read_csv(input_csv)[['ID', 'Longitude', 'Latitude', 'file']]
inp['in_x'], inp['in_y'] = to_utm(inp.Longitude, inp.Latitude)
T = T.merge(inp.rename(columns={'file': 'Gruppo'}), on='ID', how='left')
T['Dist_input_medio_DB_m'] = np.hypot(T.in_x - T.mid_x, T.in_y - T.mid_y)

# ---------------- KML ----------------
root = ET.parse(kml_path).getroot()
kpt, klin = [], []


def walk(el, cartella):
    for ch in el:
        tag = ch.tag.split('}')[1]
        if tag == 'Folder':
            walk(ch, ch.findtext('k:name', default='', namespaces=NS))
        elif tag == 'Placemark':
            nome = (ch.findtext('k:name', default='', namespaces=NS) or '').strip()
            pt = ch.find('.//k:Point/k:coordinates', NS)
            ln = ch.find('.//k:LineString/k:coordinates', NS)
            if pt is not None:
                lon, lat = map(float, pt.text.strip().split(',')[:2])
                kpt.append(dict(nome=nome, cartella=cartella, lon=lon, lat=lat))
            elif ln is not None:
                cc = [tuple(map(float, c.split(',')[:2])) for c in ln.text.split()]
                klin.append(dict(nome=nome, cartella=cartella, coords=cc))
        elif tag in ('Document',):
            walk(ch, cartella)


walk(root, '')
K = pd.DataFrame(kpt)
K['x'], K['y'] = to_utm(K.lon, K.lat)
K['SP'] = K.nome.map(norm_sp)
K['km'] = K.nome.map(norm_km)
L = gpd.GeoDataFrame(pd.DataFrame(klin).drop(columns='coords'),
                     geometry=[LineString(c) if len(c) > 1 else Point(c[0]) for c in (k['coords'] for k in klin)],
                     crs=4326).to_crs(CRS_OUT)
L['SP'] = L.nome.map(norm_sp)
L['km'] = L.nome.map(norm_km)
L['Lunghezza_m'] = L.length

# Abbinamento DB -> punto KML: stessa strada (numerazione nuova o Google Earth)
# e stessa progressiva; altrimenti il punto KML piu' vicino entro soglia.
T['kmn'] = T.km.map(norm_km)
T['sp1'] = T.SP.map(norm_sp)
T['sp2'] = T.SP_GoogleEarth.map(norm_sp)
ref_x = T.mid_x.fillna(T.in_x)
ref_y = T.mid_y.fillna(T.in_y)
abb, usati = [], set()
for i, r in T.iterrows():
    cand = K[(K.km == r.kmn) & (K.SP.isin([r.sp1, r.sp2]))]
    modo = 'strada+km'
    if cand.empty:
        cand = K[K.km == r.kmn]
        modo = 'solo km'
    if not cand.empty:
        d = np.hypot(cand.x - ref_x[i], cand.y - ref_y[i])
        j = d.idxmin()
        if modo == 'solo km' and d[j] > SOGLIA_KML_ABBINAMENTO_M:
            cand = pd.DataFrame()
    if cand.empty:
        d = np.hypot(K.x - ref_x[i], K.y - ref_y[i])
        j = d.idxmin()
        modo = 'piu vicino' if d[j] <= SOGLIA_KML_ABBINAMENTO_M else 'non trovato'
    abb.append((j if modo != 'non trovato' else None, modo))
T['KML_idx'] = [a[0] for a in abb]
T['KML_abbinamento'] = [a[1] for a in abb]
T['KML_nome'] = [K.nome[j] if j is not None else None for j in T.KML_idx]
T['KML_cartella'] = [K.cartella[j] if j is not None else None for j in T.KML_idx]
T['kml_x'] = [K.x[j] if j is not None else np.nan for j in T.KML_idx]
T['kml_y'] = [K.y[j] if j is not None else np.nan for j in T.KML_idx]
T['Dist_input_KML_m'] = np.hypot(T.in_x - T.kml_x, T.in_y - T.kml_y)
T['Dist_medio_DB_KML_m'] = np.hypot(T.mid_x - T.kml_x, T.mid_y - T.kml_y)
# Tracciato KML con stesso nome del punto
ln_by_name = {n: g for n, g in L.groupby('nome')}
T['KML_tracciato_m'] = [ln_by_name[n].Lunghezza_m.iloc[0] if n in ln_by_name else np.nan for n in T.KML_nome]
T['Dist_tracciato_input_m'] = [ln_by_name[n].geometry.iloc[0].distance(Point(x, y)) if n in ln_by_name else np.nan
                               for n, x, y in zip(T.KML_nome, T.in_x, T.in_y)]
dup = T.KML_nome.duplicated(keep=False) & T.KML_nome.notna()


def segnala(r, dupl):
    s = []
    if pd.isna(r.ini_x) or pd.isna(r.fin_x):
        s.append('coordinata DB iniziale o finale mancante/illeggibile')
    if r.Dist_inizio_fine_m > SOGLIA_INIZIO_FINE_M:
        s.append(f'inizio-fine DB distanti {r.Dist_inizio_fine_m:.0f} m')
    if r.Dist_input_medio_DB_m > SOGLIA_CONFRONTO_M:
        s.append(f'input script lontano {r.Dist_input_medio_DB_m:.0f} m dal punto medio DB')
    if r.KML_abbinamento == 'non trovato':
        s.append('nessun punto KML abbinato')
    elif r.KML_abbinamento != 'strada+km':
        s.append(f'KML abbinato per {r.KML_abbinamento}')
    if r.Dist_medio_DB_KML_m > SOGLIA_CONFRONTO_M:
        s.append(f'KML lontano {r.Dist_medio_DB_KML_m:.0f} m dal punto medio DB')
    if dupl:
        s.append('stesso punto KML abbinato a piu ID')
    return '; '.join(s)


T['Segnalazioni'] = [segnala(r, d) for (_, r), d in zip(T.iterrows(), dup)]
T['N_segnalazioni'] = T.Segnalazioni.map(lambda s: 0 if not s else s.count(';') + 1)

# ---------------- Uscite ----------------
gpkg = os.path.join(out_dir, 'controllo_coordinate.gpkg')
if os.path.exists(gpkg):
    os.remove(gpkg)
base = ['ID', 'Gruppo', 'SP', 'km', 'Nome_opera', 'A_db_km2']


def strato(nome, xcol, ycol, extra=()):
    g = T[T[xcol].notna()]
    gdf = gpd.GeoDataFrame(g[base + list(extra)], geometry=gpd.points_from_xy(g[xcol], g[ycol]), crs=CRS_OUT)
    gdf.to_file(gpkg, layer=nome, driver='GPKG')


strato('db_inizio', 'ini_x', 'ini_y', ['Coord_ini_testo'])
strato('db_fine', 'fin_x', 'fin_y', ['Coord_fin_testo'])
strato('input_script', 'in_x', 'in_y', ['Dist_input_medio_DB_m', 'Dist_input_KML_m', 'Segnalazioni', 'N_segnalazioni'])
strato('kml_abbinato', 'kml_x', 'kml_y', ['KML_nome', 'KML_abbinamento', 'Dist_input_KML_m'])
g = T[T.ini_x.notna() & T.fin_x.notna()]
gpd.GeoDataFrame(g[base + ['Dist_inizio_fine_m']],
                 geometry=[LineString([(a, b), (c, d)]) for a, b, c, d in zip(g.ini_x, g.ini_y, g.fin_x, g.fin_y)],
                 crs=CRS_OUT).to_file(gpkg, layer='db_attraversamento_inizio_fine', driver='GPKG')
g = T[T.kml_x.notna() & T.in_x.notna()]
gpd.GeoDataFrame(g[base + ['Dist_input_KML_m', 'KML_nome']],
                 geometry=[LineString([(a, b), (c, d)]) for a, b, c, d in zip(g.in_x, g.in_y, g.kml_x, g.kml_y)],
                 crs=CRS_OUT).to_file(gpkg, layer='scarto_input_kml', driver='GPKG')
gpd.GeoDataFrame(K[['nome', 'cartella', 'SP', 'km']], geometry=gpd.points_from_xy(K.x, K.y),
                 crs=CRS_OUT).to_file(gpkg, layer='kml_punti_tutti', driver='GPKG')
L.to_file(gpkg, layer='kml_tracciati', driver='GPKG')

cols = ['ID', 'Gruppo', 'SP', 'SP_GoogleEarth', 'km', 'Nome_opera', 'A_db_km2', 'Coord_ini_testo', 'Coord_fin_testo',
        'Dist_inizio_fine_m', 'Dist_input_medio_DB_m', 'KML_nome', 'KML_cartella', 'KML_abbinamento',
        'Dist_input_KML_m', 'Dist_medio_DB_KML_m', 'KML_tracciato_m', 'Dist_tracciato_input_m',
        'N_segnalazioni', 'Segnalazioni']
T[cols].to_csv(os.path.join(out_dir, 'controllo_coordinate.csv'), index=False)
kml_non_usati = K[~K.index.isin([j for j in T.KML_idx if j is not None])]
kml_non_usati[['nome', 'cartella', 'lon', 'lat']].to_csv(os.path.join(out_dir, 'kml_punti_non_abbinati.csv'), index=False)
print(f"KML: {len(K)} punti, {len(L)} tracciati; abbinamenti: {T.KML_abbinamento.value_counts().to_dict()}")
print(f"KML non abbinati a nessun ID: {len(kml_non_usati)}")
print("Salvati", gpkg)
