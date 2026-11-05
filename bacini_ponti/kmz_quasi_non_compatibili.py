"""
KMZ unico per Google Earth con i ponti quasi compatibili e non compatibili.
Per ogni ponte (sottocartella "ID n – SP km"): punto di localizzazione e tracciato del KMZ originale (stili originali)
e punto usato nell'analisi, colorato per classe (celeste = quasi compatibile, giallo = non compatibile), con una
scheda che riporta classe, aree e note.

Uso: python kmz_quasi_non_compatibili.py <qnc_ponti.kmz> <qnc_ponti_analisi.shp> <out.kmz>
"""
import sys
import zipfile
import xml.etree.ElementTree as ET

import geopandas as gpd

src, shp, out = sys.argv[1:4]
NS = '{http://www.opengis.net/kml/2.2}'
for p, u in [('', 'http://www.opengis.net/kml/2.2'), ('gx', 'http://www.google.com/kml/ext/2.2'),
             ('kml', 'http://www.opengis.net/kml/2.2'), ('atom', 'http://www.w3.org/2005/Atom')]:
    ET.register_namespace(p, u)
with zipfile.ZipFile(src) as z:
    r = ET.fromstring(z.read('doc.kml'))
doc = r.find(NS + 'Document')
doc.find(NS + 'name').text = 'Ponti quasi compatibili e non compatibili'
# stili del punto di analisi (colori KML in aabbggrr)
for sid, col in [('analisi_quasi', 'ffeed7bd'), ('analisi_non', 'ff00e1ff')]:
    st = ET.Element(NS + 'Style', id=sid)
    ic = ET.SubElement(st, NS + 'IconStyle')
    ET.SubElement(ic, NS + 'color').text = col
    ET.SubElement(ic, NS + 'scale').text = '1.3'
    ET.SubElement(ET.SubElement(ic, NS + 'Icon'), NS + 'href').text = \
        'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'
    ET.SubElement(ET.SubElement(st, NS + 'LabelStyle'), NS + 'scale').text = '0.9'
    doc.insert(1, st)
P = gpd.read_file(shp).to_crs(4326).set_index('ID')
for c in ('nome', 'note', 'comune', 'area_kml'):
    P[c] = P[c].fillna('').astype(str).replace('nan', '')
f = lambda v, d=3: f'{v:,.{d}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
for cart in doc.findall(NS + 'Folder'):
    for sf in cart.findall(NS + 'Folder'):
        i = int(sf.findtext(NS + 'name').split()[1])
        p = P.loc[i]
        titolo = f'ID {i} – {p.SP} km {p.km}' + (f' – {p["nome"]}' if p['nome'] else '')
        sf.find(NS + 'name').text = titolo
        scheda = (f'<b>{p.classe.upper()}</b><br/>Area database: {f(p.A_db_km2)} km²<br/>'
                  f'Area calcolata: {f(p.A_calc_km2)} km²<br/>Differenza: {p.diff_pct:+.1f}%<br/>'
                  f'Comune: {p.comune}<br/>Area: {p.area_kml or "-"}' + (f'<br/>Note: {p.note}' if p.note else ''))
        ET.SubElement(sf, NS + 'description').text = scheda
        pm = ET.SubElement(sf, NS + 'Placemark')
        ET.SubElement(pm, NS + 'name').text = f'ID {i} – punto usato nell\'analisi'
        ET.SubElement(pm, NS + 'description').text = scheda
        ET.SubElement(pm, NS + 'styleUrl').text = '#analisi_quasi' if p.classe.startswith('quasi') else '#analisi_non'
        ET.SubElement(ET.SubElement(pm, NS + 'Point'), NS + 'coordinates').text = f'{p.geometry.x:.9f},{p.geometry.y:.9f},0'
        ET.SubElement(sf, NS + 'open').text = '0'
    cart.find(NS + 'name').text += f' ({len(cart.findall(NS + "Folder"))})'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('doc.kml', ET.tostring(r, encoding='utf-8', xml_declaration=True))
print('ok', out)
