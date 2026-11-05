"""
Shapefile dei ponti quasi compatibili e non compatibili con gli elementi del KMZ di ciascun attraversamento.

Scrive in <out_dir> (EPSG:32633):
  qnc_ponti_analisi.shp       punto usato nell'analisi (da ponti_analisi.shp)
  qnc_kml_localizzazione.shp  punto di localizzazione del KMZ (cartelle *_localizzazione)
  qnc_kml_tracciato.shp       tracciato del ponte del KMZ (cartelle *_tracciato)
  qnc_ponti.kmz               gli stessi elementi del KMZ originale (stili compresi), solo per questi ponti
Attributi comuni: ID (database), classe, A_db_km2 (corretta per i refusi), A_calc_km2, diff_pct, SP, km, nome,
comune e area (dai poligoni del KMZ), kml_nome / kml_cart.

Uso: python shape_quasi_non_compatibili_kml.py <Localizzazione_ponti_Database.kmz> <ponti_analisi.shp>
        <controllo_coordinate.gpkg> <parametri_morfologici.csv> <Database.xlsx> <note_relazioni.csv> <out_dir>
"""
import copy
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point, Polygon

kmz, shp, gpkg, pcsv, dbx, ncsv, out = sys.argv[1:8]
os.makedirs(out, exist_ok=True)
QUASI = [44, 72, 85, 102, 103, 104, 106, 109, 116, 124, 129, 151, 200]
NON = [13, 19, 58, 117, 118, 154, 164, 174]
NS = '{http://www.opengis.net/kml/2.2}'
ET.register_namespace('', 'http://www.opengis.net/kml/2.2')
ET.register_namespace('gx', 'http://www.google.com/kml/ext/2.2')
ET.register_namespace('kml', 'http://www.opengis.net/kml/2.2')
ET.register_namespace('atom', 'http://www.w3.org/2005/Atom')

# ---- lettura del KMZ: tutti i placemark con cartella, nome e geometria
with zipfile.ZipFile(kmz) as z:
    nome_kml = [n for n in z.namelist() if n.lower().endswith('.kml')][0]
    radice = ET.fromstring(z.read(nome_kml))


def coord(t):
    return [tuple(map(float, c.split(',')[:2])) for c in t.split()]


PM = []


def visita(e, cartella):
    for c in e:
        if c.tag == NS + 'Folder':
            visita(c, c.findtext(NS + 'name'))
        elif c.tag == NS + 'Placemark':
            g = None
            p = c.find(f'.//{NS}Point/{NS}coordinates')
            l = c.find(f'.//{NS}LineString/{NS}coordinates')
            q = c.find(f'.//{NS}Polygon//{NS}outerBoundaryIs//{NS}coordinates')
            if p is not None:
                g = Point(coord(p.text)[0])
            elif l is not None:
                g = LineString(coord(l.text))
            elif q is not None:
                g = Polygon(coord(q.text))
            PM.append({'cartella': cartella or '', 'nome': (c.findtext(NS + 'name') or '').strip(), 'geometry': g, 'el': c})
        else:
            visita(c, cartella)


visita(radice, '')
K = gpd.GeoDataFrame(PM, geometry='geometry', crs=4326).to_crs(32633)
punti = K[K.geom_type == 'Point']
linee = K[K.geom_type == 'LineString']
poli = K[K.geom_type == 'Polygon']
comuni = poli[~poli.nome.str.lower().str.startswith('area')]
aree = poli[poli.nome.str.lower().str.startswith('area')]

# ---- abbinamento ID -> elementi del KMZ (stesso abbinamento usato nell'analisi)
kab = gpd.read_file(gpkg, layer='kml_abbinato').set_index('ID')
tus = gpd.read_file(gpkg, layer='tracciato_usato').set_index('ID').to_crs(32633)
pa = gpd.read_file(shp).set_index('ID')
U = pd.read_csv(pcsv)
U['ID'] = U.ID.astype(int)
U = U.set_index('ID')
db = pd.read_excel(dbx).rename(columns={'Unnamed: 0': 'ID'})
db = db[pd.to_numeric(db.ID, errors='coerce').notna()]
db['ID'] = db.ID.astype(int)
db = db.set_index('ID')
N = pd.read_csv(ncsv).set_index('ID')

righe_pa, righe_pt, righe_ln, el_pt, el_ln = [], [], [], [], []
for i in QUASI + NON:
    a_db = pd.to_numeric(db.loc[i, 'SUPERFICIE BACINO (km2)'], errors='coerce')
    if i in N.index and pd.notna(N.loc[i, 'Area_DB_corretta']):
        a_db = float(N.loc[i, 'Area_DB_corretta'])
    a_c = float(U.loc[i, 'A_km2'])
    nome = str(db.loc[i, 'Nome opera']).strip()
    base = {'ID': i, 'classe': 'quasi compatibile' if i in QUASI else 'non compatibile',
            'A_db_km2': round(float(a_db), 3), 'A_calc_km2': round(a_c, 3), 'diff_pct': round(100 * (a_c / a_db - 1), 1),
            'SP': str(db.loc[i, 'NUOVA NUMERAZIONE']), 'km': str(db.loc[i, 'Progressiva km']),
            'nome': '' if nome in ('-', 'nan') else nome,
            'note': str(N.loc[i, 'Correzione'])[:250] if i in N.index else ''}
    # punto di localizzazione del KMZ: per nome (abbinamento dell'analisi), il piu' vicino al punto abbinato
    kn = kab.loc[i, 'KML_nome']
    cand = punti[punti.nome == kn]
    gk = gpd.GeoSeries([kab.loc[i, 'geometry']], crs=kab.crs).to_crs(32633).iloc[0]
    pk = cand.loc[cand.distance(gk).idxmin()] if len(cand) else punti.loc[punti.distance(gk).idxmin()]
    # tracciato del KMZ: la linea che coincide con il tracciato usato nell'analisi
    tl = tus.loc[i, 'geometry']
    lk = linee.loc[linee.geometry.apply(lambda g: g.hausdorff_distance(tl)).idxmin()]
    d_tr = lk.geometry.hausdorff_distance(tl)
    com = comuni[comuni.contains(pk.geometry)].nome.tolist()
    ar = aree[aree.contains(pk.geometry)].nome.tolist()
    base.update({'comune': ', '.join(sorted(set(com))), 'area_kml': ', '.join(ar)})
    righe_pa.append({**base, 'kml_nome': pk.nome, 'geometry': pa.loc[i, 'geometry']})
    righe_pt.append({**base, 'kml_nome': pk.nome, 'kml_cart': pk.cartella, 'geometry': pk.geometry})
    righe_ln.append({**base, 'kml_nome': lk.nome, 'kml_cart': lk.cartella, 'lung_m': round(lk.geometry.length, 1),
                     'geometry': lk.geometry})
    el_pt.append((i, pk.el))
    el_ln.append((i, lk.el))
    print(f'{i:4d} {base["classe"]:18s} punto "{pk.nome}"  tracciato "{lk.nome}" (scarto {d_tr:.1f} m)  {base["comune"]}')

for nome, righe in [('qnc_ponti_analisi', righe_pa), ('qnc_kml_localizzazione', righe_pt), ('qnc_kml_tracciato', righe_ln)]:
    gpd.GeoDataFrame(righe, geometry='geometry', crs=32633).to_file(os.path.join(out, nome + '.shp'), encoding='utf-8')
pd.DataFrame(righe_pa).drop(columns='geometry').to_csv(os.path.join(out, 'qnc_elenco.csv'), index=False)

# ---- KMZ ridotto: stessi placemark e stili del KMZ originale, in due cartelle (quasi / non compatibili)
doc = radice.find(NS + 'Document')
nuovo = ET.Element(NS + 'kml')
d2 = ET.SubElement(nuovo, NS + 'Document')
ET.SubElement(d2, NS + 'name').text = 'Ponti quasi e non compatibili'
for e in doc:
    if e.tag in (NS + 'Style', NS + 'StyleMap'):
        d2.append(copy.deepcopy(e))
for titolo, lista in [('Quasi compatibili', QUASI), ('Non compatibili', NON)]:
    f = ET.SubElement(d2, NS + 'Folder')
    ET.SubElement(f, NS + 'name').text = titolo
    for i in lista:
        sf = ET.SubElement(f, NS + 'Folder')
        ET.SubElement(sf, NS + 'name').text = f'ID {i}'
        for ii, el in el_pt + el_ln:
            if ii == i:
                c = copy.deepcopy(el)
                c.find(NS + 'name').text = f'ID {i} – {c.findtext(NS + "name")}'
                sf.append(c)
with zipfile.ZipFile(os.path.join(out, 'qnc_ponti.kmz'), 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('doc.kml', ET.tostring(nuovo, encoding='utf-8', xml_declaration=True))
print('scritto', out)
