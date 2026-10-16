"""
Confronto dei nuovi file (KMZ "Localizzazione_ponti_Database" ed Excel
"Elenco_ponti_complessivo_per_Provincia_MT") con i dati gia' usati, senza
modificare i risultati esistenti.

Per ogni ID del database (1-212):
  KML nuovo  - punto e tracciato abbinati per strada+progressiva (o, in
               mancanza, per vicinanza); spostamento rispetto al KML vecchio;
               area del bacino all'intersezione tracciato nuovo - reticolo
               (stesse toppe a 5 m del calcolo finale), se il tracciato e'
               cambiato.
  Elenco     - riga abbinata per coordinate iniziali (entro 25 m) o per
               strada+progressiva; differenze di coordinate e progressiva;
               colonna "Intercetta asta fluviale/canale?", comune, cod. IOP,
               note.

Uso: python confronto_nuovi_dati.py <doc_nuovo.kml> <Elenco.xlsx> <controllo_coordinate.gpkg>
        <Risultati_5m_ibrido.xlsx> <cartella_toppe> <soglia_km2> <out_dir>
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import geopandas as gpd
from affine import Affine
from shapely.geometry import LineString, Point

TOL = 0.15
kml_p, elenco_p, cgpkg, res_xlsx, tdir, soglia, out = sys.argv[1:8]
soglia = float(soglia)
os.makedirs(out, exist_ok=True)
NS = {'k': 'http://www.opengis.net/kml/2.2'}
OFF = {1: (-1, 1), 2: (0, 1), 4: (1, 1), 8: (1, 0), 16: (1, -1), 32: (0, -1), 64: (-1, -1), 128: (-1, 0)}


def norm_sp(s):
    m = re.search(r'SP\s*(\d+)', str(s).upper())
    return f'SP{m.group(1)}' if m else None


def norm_km(s):
    m = re.search(r'(\d+)\s*\+\s*(\d+)', str(s))
    return f'{int(m.group(1))}+{int(m.group(2)):03d}' if m else None


def parse_latlon(v):
    if not isinstance(v, str):
        return None
    vals = re.findall(r'\d+[.,]\d+', v)
    if len(vals) != 2:
        return None
    a, b = (float(x.replace(',', '.')) for x in vals)
    if not (39 < a < 42 and 15 < b < 18):
        a, b = b, a
    return (a, b) if (39 < a < 42 and 15 < b < 18) else None


def utm(lon, lat):
    g = gpd.GeoSeries(gpd.points_from_xy(lon, lat), crs=4326).to_crs(32633)
    return g.x.values, g.y.values


# ---------------- KML nuovo ----------------
pts, lns = [], []


def walk(e):
    for ch in e:
        t = ch.tag.split('}')[1]
        if t in ('Folder', 'Document'):
            walk(ch)
        elif t == 'Placemark':
            n = (ch.findtext('k:name', default='', namespaces=NS) or '').strip()
            p = ch.find('.//k:Point/k:coordinates', NS)
            l = ch.find('.//k:LineString/k:coordinates', NS)
            if p is not None:
                lon, lat = map(float, p.text.strip().split(',')[:2])
                pts.append({'nome': n, 'lon': lon, 'lat': lat})
            elif l is not None:
                cc = [tuple(map(float, c.split(',')[:2])) for c in l.text.split()]
                lns.append({'nome': n, 'coords': cc})


walk(ET.parse(kml_p).getroot())
K = pd.DataFrame(pts)
K['x'], K['y'] = utm(K.lon, K.lat)
K['SP'], K['km'] = K.nome.map(norm_sp), K.nome.map(norm_km)
L = gpd.GeoDataFrame({'nome': [l['nome'] for l in lns]},
                     geometry=[LineString(l['coords']) for l in lns], crs=4326).to_crs(32633)

inp = gpd.read_file(cgpkg, layer='input_script').set_index('ID')
kv = gpd.read_file(cgpkg, layer='kml_abbinato').set_index('ID')
tv = gpd.read_file(cgpkg, layer='tracciato_usato').set_index('ID')
cc = pd.read_csv(os.path.join(os.path.dirname(cgpkg), 'controllo_coordinate.csv')).set_index('ID')
P = pd.read_excel(res_xlsx, sheet_name='Ponti').set_index('ID')
adb = P['Area database (km²)']

righe, usati = [], set()
for i in P.index:
    sp1, sp2, km = norm_sp(cc.SP[i]), norm_sp(cc.SP_GoogleEarth[i]), norm_km(cc.km[i])
    c = K[(K.km == km) & K.SP.isin([sp1, sp2])]
    modo = 'strada+km'
    if c.empty:
        c = K[K.km == km]
        modo = 'solo km'
    ref = inp.geometry[i]
    # strada+km univoco: vale sempre (la distanza e' solo riportata);
    # solo km: accettato entro 500 m; altrimenti il punto piu' vicino
    if c.empty or (modo == 'solo km' and np.hypot(c.x - ref.x, c.y - ref.y).min() > 500):
        c = K
        modo = 'vicinanza'
    j = np.hypot(c.x - ref.x, c.y - ref.y).idxmin()
    o = {'ID': i, 'KMLn_nome': K.nome[j], 'KMLn_abbinamento': modo, 'kx': K.x[j], 'ky': K.y[j]}
    o['KMLn_dist_input_m'] = float(np.hypot(K.x[j] - ref.x, K.y[j] - ref.y))
    o['KMLn_spost_da_KML_vecchio_m'] = Point(K.x[j], K.y[j]).distance(kv.geometry[i]) if i in kv.index else np.nan
    t = L[L.nome == K.nome[j]]
    if t.empty:
        dd = L.distance(Point(K.x[j], K.y[j]))
        t = L.loc[[dd.idxmin()]] if dd.min() <= 50 else t
    if not t.empty:
        ln = t.geometry.iloc[0]
        o['_trac'] = ln
        o['Tracciato_nuovo_m'] = ln.length
        if i in tv.index:
            o['Tracciato_spost_m'] = ln.hausdorff_distance(tv.geometry[i])
    if K.nome[j] in usati:
        o['KMLn_duplicato'] = True
    usati.add(K.nome[j])
    righe.append(o)
N = pd.DataFrame(righe).set_index('ID')


# area all'intersezione tracciato nuovo - reticolo (toppe a 5 m del calcolo finale)
def area_tracciato(i, line):
    z = np.load(os.path.join(tdir, f'id{i:03d}.npz'))
    A, ptr = z['acc_km2'], z['ptr']
    T = Affine(*z['transform'])
    H, W = A.shape
    inv = ~T
    xmin, ymin, xmax, ymax = line.bounds
    c0, r0 = inv * (xmin - 100, ymax + 100)
    c1, r1 = inv * (xmax + 100, ymin - 100)
    hit, segs = [], []
    for r in range(max(int(r0), 0), min(int(r1) + 1, H)):
        for c in range(max(int(c0), 0), min(int(c1) + 1, W)):
            if A[r, c] < soglia or int(ptr[r, c]) not in OFF:
                continue
            dr, dc = OFF[int(ptr[r, c])]
            if not (0 <= r + dr < H and 0 <= c + dc < W):
                continue
            s = LineString([T * (c + .5, r + .5), T * (c + dc + .5, r + dr + .5)])
            segs.append((s, A[r, c]))
            if s.intersects(line):
                hit.append(A[r, c])
    if hit:
        return float(max(hit)), 'sul tracciato'
    if segs:
        s, a = min(segs, key=lambda t: t[0].distance(line))
        return float(a), f'reticolo più vicino ({s.distance(line):.0f} m)'
    return np.nan, 'nessun reticolo'


for i in N.index:
    if pd.notna(N.loc[i].get('Tracciato_spost_m')) and N.Tracciato_spost_m[i] > 1:
        a, tipo = area_tracciato(i, N._trac[i])
        N.loc[i, 'A_tracciato_nuovo_km2'] = a
        N.loc[i, 'Aggancio_tracciato_nuovo'] = tipo

# ---------------- Elenco complessivo ----------------
E = pd.read_excel(elenco_p, header=1)
E.columns = [str(c).strip() for c in E.columns]
E = E[E['NUOVA NUMERAZIONE'].notna() | E['Nome opera'].notna()].copy()
col_int = [c for c in E.columns if c.startswith('Intercetta')][0]
ini = E['Coordinate iniziali [Lat., Long.]'].map(parse_latlon)
fin = E['Coordinate finali [Lat., Long.]'].map(parse_latlon)
ok_i = ini.notna()
E['ex'], E['ey'] = np.nan, np.nan
x, y = utm([v[1] for v in ini[ok_i]], [v[0] for v in ini[ok_i]])
E.loc[ok_i, 'ex'], E.loc[ok_i, 'ey'] = x, y
ok_f = fin.notna()
E['fx'], E['fy'] = np.nan, np.nan
x, y = utm([v[1] for v in fin[ok_f]], [v[0] for v in fin[ok_f]])
E.loc[ok_f, 'fx'], E.loc[ok_f, 'fy'] = x, y
E['SPn'] = E['NUOVA NUMERAZIONE'].map(norm_sp)
E['SPg'] = E['DENOMINAZIONE GOOGLE EARTH'].map(norm_sp)
E['kmn'] = E['Progressiva km'].map(norm_km)
dbi = gpd.read_file(cgpkg, layer='db_inizio').set_index('ID').geometry
dbf = gpd.read_file(cgpkg, layer='db_fine').set_index('ID').geometry
el = []
for i in P.index:
    o = {'ID': i}
    m = pd.Series(False, index=E.index)
    if i in dbi.index:
        d = np.hypot(E.ex - dbi[i].x, E.ey - dbi[i].y)
        if d.min() <= 25:
            m = d == d.min()
            o['Elenco_abbinamento'] = f'coordinate iniziali ({d.min():.1f} m)'
    if not m.any():
        sp1, sp2, km = norm_sp(cc.SP[i]), norm_sp(cc.SP_GoogleEarth[i]), norm_km(cc.km[i])
        m = (E.kmn == km) & (E.SPn.isin([sp1, sp2]) | E.SPg.isin([sp1, sp2]))
        if m.sum() == 1:
            o['Elenco_abbinamento'] = 'strada+km'
    if m.sum() != 1:
        o['Elenco_abbinamento'] = 'non trovato' if m.sum() == 0 else f'ambiguo ({int(m.sum())} righe)'
        el.append(o)
        continue
    r = E[m].iloc[0]
    o['Elenco_riga_excel'] = int(r.name) + 3
    o['Elenco_strada'] = r['NUOVA NUMERAZIONE']
    o['Elenco_progressiva'] = r['Progressiva km']
    o['Elenco_nome_opera'] = r['Nome opera']
    o['Elenco_comune'] = r['Comune']
    o['Elenco_cod_IOP'] = r['Cod. IOP']
    o['Intercetta_asta_canale'] = r[col_int]
    o['Elenco_note'] = r['Note']
    if i in dbi.index and pd.notna(r.ex):
        o['Diff_coord_iniziali_m'] = float(np.hypot(r.ex - dbi[i].x, r.ey - dbi[i].y))
    if i in dbf.index and pd.notna(r.fx):
        o['Diff_coord_finali_m'] = float(np.hypot(r.fx - dbf[i].x, r.fy - dbf[i].y))
        o['Elenco_dist_inizio_fine_m'] = float(np.hypot(r.fx - r.ex, r.fy - r.ey)) if pd.notna(r.ex) else np.nan
    o['Progressiva_diversa'] = norm_km(r['Progressiva km']) != norm_km(cc.km[i])
    el.append(o)
EL = pd.DataFrame(el).set_index('ID')

# ---------------- Sintesi per ID ----------------
D = P[['Strada', 'Progressiva', 'Area database (km²)', 'Area calcolata 5 m (km²)', 'Compatibile (±15%)',
       'Esito']].join(N.drop(columns=['_trac', 'kx', 'ky'], errors='ignore')).join(EL)
D['Dist_inizio_fine_DB_m'] = cc.Dist_inizio_fine_m
if 'A_tracciato_nuovo_km2' in D:
    D['Compatibile_tracciato_nuovo'] = np.where(D.A_tracciato_nuovo_km2.notna() & adb.notna(),
                                                (D.A_tracciato_nuovo_km2 / adb - 1).abs() <= TOL, None)


def novita(r):
    s = []
    it = str(r.get('Intercetta_asta_canale', '')).strip().lower()
    if it.startswith('no'):
        s.append('censimento: NON intercetta asta fluviale/canale')
    elif it.startswith('si'):
        s.append('censimento: intercetta asta fluviale/canale')
    if pd.notna(r.get('KMLn_spost_da_KML_vecchio_m')) and r.KMLn_spost_da_KML_vecchio_m > 5:
        s.append(f'punto KML spostato di {r.KMLn_spost_da_KML_vecchio_m:.0f} m')
    if pd.notna(r.get('Tracciato_spost_m')) and r.Tracciato_spost_m > 5:
        s.append(f'tracciato KML spostato (fino a {r.Tracciato_spost_m:.0f} m)')
    if pd.notna(r.get('Diff_coord_iniziali_m')) and r.Diff_coord_iniziali_m > 5:
        s.append(f'coord. iniziali diverse dal DB ({r.Diff_coord_iniziali_m:.0f} m)')
    if pd.notna(r.get('Diff_coord_finali_m')) and r.Diff_coord_finali_m > 5:
        s.append(f'coord. finali diverse dal DB ({r.Diff_coord_finali_m:.0f} m)')
    if r.get('Progressiva_diversa') is True:
        s.append(f'progressiva diversa ({r.Elenco_progressiva})')
    n = str(r.get('Elenco_note', ''))
    if n and n != 'nan' and n.lower() not in ('elaborati', 'word'):
        s.append(f'nota: {n}')
    if pd.notna(r.get('Compatibile_tracciato_nuovo')):
        s.append('con il tracciato nuovo: ' + ('COMPATIBILE' if r.Compatibile_tracciato_nuovo else 'non compatibile')
                 + f' ({r.A_tracciato_nuovo_km2:.3g} km²)')
    return '; '.join(s)


D['Novità dai nuovi file'] = [novita(r) for _, r in D.iterrows()]
D.to_csv(os.path.join(out, 'confronto_nuovi_dati.csv'))
with pd.ExcelWriter(os.path.join(out, 'Nuovi_dati_confronto.xlsx'), engine='openpyxl') as w:
    D.reset_index().to_excel(w, sheet_name='Confronto per ID', index=False)
    ws = w.sheets['Confronto per ID']
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(
            max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 55)
    ws.freeze_panes = 'B2'
    ws.auto_filter.ref = ws.dimensions
# opere del censimento non presenti nel database
abb = set(EL.Elenco_riga_excel.dropna().astype(int))
extra = E[~(E.index + 3).isin(abb)][['NUOVA NUMERAZIONE', 'Progressiva km', 'Nome opera', 'Comune', col_int, 'Note',
                                     'Coordinate iniziali [Lat., Long.]']]
extra.to_csv(os.path.join(out, 'censimento_opere_non_nel_database.csv'), index_label='riga_excel_meno_3')
gpd.GeoDataFrame(D.reset_index()[['ID', 'Novità dai nuovi file']],
                 geometry=gpd.points_from_xy(N.kx.reindex(D.index), N.ky.reindex(D.index)), crs=32633) \
    .to_file(os.path.join(out, 'kml_nuovo_punti.gpkg'), layer='punti_kml_nuovo', driver='GPKG')
gpd.GeoDataFrame({'ID': N.index}, geometry=list(N._trac), crs=32633).to_file(
    os.path.join(out, 'kml_nuovo_punti.gpkg'), layer='tracciati_kml_nuovo', driver='GPKG')
pd.set_option('display.width', 250)
print('KML nuovo:', len(K), 'punti,', len(L), 'tracciati; abbinamenti', N.KMLn_abbinamento.value_counts().to_dict())
print('punti spostati >5 m:', int((N.KMLn_spost_da_KML_vecchio_m > 5).sum()),
      '; tracciati spostati >5 m:', int((N.Tracciato_spost_m > 5).sum()))
print('Elenco:', len(E), 'righe; abbinamenti', EL.Elenco_abbinamento.str.split(' ').str[0].value_counts().to_dict())
print('Intercetta:', EL.Intercetta_asta_canale.astype(str).str.strip().str.lower().value_counts().to_dict())
print('opere del censimento non nel database:', len(extra))
