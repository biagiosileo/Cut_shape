"""
Progetto QGIS della cartella condivisa v2 (percorsi relativi), un gruppo per fase del lavoro, stili dai GeoPackage,
segnalibri per i 212 attraversamenti, i ponti modificati e i casi dubbi.

Uso (PyQGIS): QT_QPA_PLATFORM=offscreen python3 progetto_cartella_condivisa_v2.py <cartella v2> [cartella immagini]
"""
import os
import sys

from qgis.core import (QgsApplication, QgsBookmark, QgsCoordinateReferenceSystem, QgsMapRendererParallelJob,
                       QgsMapSettings, QgsProject, QgsRasterLayer, QgsRectangle, QgsReferencedRectangle,
                       QgsVectorLayer)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor

cart = os.path.abspath(sys.argv[1])
img = sys.argv[2] if len(sys.argv) > 2 else None
app = QgsApplication([], False); app.initQgis()
prj = QgsProject.instance()
prj.setCrs(QgsCoordinateReferenceSystem('EPSG:32633'))
prj.writeEntryBool('Paths', '/Absolute', False)
gruppi = [
    ('4. Casi dubbi', True, '4_casi_dubbi/casi_dubbi.gpkg', [
        ('casi_dubbi', 'Casi dubbi, colore = categoria'),
        ('spostamento_sezione', 'Distanza sezione di calcolo - ponte (oltre 10 m)'),
        ('ponte_kml', 'Ponte nel KML (tracciato)'),
        ('ponte_database', 'Ponte nel database (coordinate inizio-fine)')]),
    ('2. Spostamento dei punti', True, '2_spostamento_punti/spostamento_punti.gpkg', [
        ('posizione_finale', 'Posizione finale, colore = tipo di modifica'),
        ('posizione_iniziale', 'Posizione iniziale'),
        ('spostamenti', 'Spostamento (posizione iniziale - finale)')]),
    ('3. Confronto aree (risultato finale)', True, None, [
        ('3_confronto_aree/punti_attraversamenti.gpkg', 'punti_attraversamenti', 'Punti di calcolo dei 212 attraversamenti, colore = classe'),
        ('3_confronto_aree/bacini_codice.gpkg', 'bacini_codice', 'Bacini del codice, colore = classe'),
        ('3_confronto_aree/reticolo_idrografico.gpkg', 'reticolo_idrografico', 'Reticolo del codice (soglia 0.1 km2, disegnato al centro delle celle)')]),
    ('1. Prima analisi', False, '1_prima_analisi/prima_analisi.gpkg', [
        ('punti_prima_analisi', 'Punti della prima analisi, colore = classe'),
        ('bacini_prima_analisi_ponti_spostati', 'Bacini della prima analisi (ponti poi spostati)')]),
]
root = prj.layerTreeRoot()
L = {}
for ng, vis, f, lista in gruppi:
    g = root.addGroup(ng)
    g.setItemVisibilityChecked(vis)
    for el in lista:
        ff, tab, nome = (f, *el) if f else el
        lyr = QgsVectorLayer(f'{os.path.join(cart, ff)}|layername={tab}', nome, 'ogr')
        assert lyr.isValid(), tab
        prj.addMapLayer(lyr, False); g.addLayer(lyr); L[tab] = lyr
    if not vis:
        g.setExpanded(False)
osm = QgsRasterLayer('type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0',
                     'Sfondo OpenStreetMap', 'wms')
if osm.isValid():
    prj.addMapLayer(osm, False); root.addLayer(osm)

bm = prj.bookmarkManager()
for tab, gr, campo, lato in (('casi_dubbi', '4. Casi dubbi', 'Categoria', 600),
                             ('posizione_finale', '2. Ponti modificati', 'Tipo_modifica', 600),
                             ('punti_attraversamenti', '3. Tutti gli attraversamenti', 'Classe', 600)):
    for ft in sorted(L[tab].getFeatures(), key=lambda f: int(f['ID'])):
        pt = ft.geometry().asPoint()
        r = QgsRectangle(pt.x() - lato, pt.y() - lato, pt.x() + lato, pt.y() + lato)
        if tab == 'posizione_finale':
            for h in L['posizione_iniziale'].getFeatures(f'"ID" = {int(ft["ID"])}'):
                q = h.geometry().asPoint()
                if pt.distance(q) < 3000:
                    r.combineExtentWith(QgsRectangle(q.x() - 150, q.y() - 150, q.x() + 150, q.y() + 150))
        b = QgsBookmark(); b.setName(f"{int(ft['ID'])} - {ft[campo]}"); b.setGroup(gr)
        b.setExtent(QgsReferencedRectangle(r, prj.crs()))
        bm.addBookmark(b)
ext = L['punti_attraversamenti'].extent(); ext.scale(1.15)
prj.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(ext, prj.crs()))
f_qgs = os.path.join(cart, 'progetto_ponti.qgs')
prj.write(f_qgs)
att = os.path.join(cart, 'progetto_ponti_attachments.zip')
if os.path.exists(att):
    os.remove(att)
print('progetto', f_qgs, '; segnalibri', len(bm.bookmarks()))

if img:
    os.makedirs(img, exist_ok=True)
    lay = [l for l in root.layerOrder() if l.name() != 'Sfondo OpenStreetMap' and root.findLayer(l.id()).isVisible()]
    scelti = {'2. Ponti modificati': ('64', '103', '196'), '3. Tutti gli attraversamenti': ('44',)}
    for b in bm.bookmarks():
        i = b.name().split(' - ')[0]
        if i in scelti.get(b.group(), ()):
            e = b.extent()
            if i == '44':
                c = e.center(); e = QgsRectangle(c.x() - 40, c.y() - 40, c.x() + 40, c.y() + 40)
            ms = QgsMapSettings(); ms.setLayers(lay); ms.setDestinationCrs(prj.crs()); ms.setExtent(e)
            ms.setOutputSize(QSize(900, 900)); ms.setBackgroundColor(QColor('white')); ms.setOutputDpi(100)
            j = QgsMapRendererParallelJob(ms); j.start(); j.waitForFinished()
            j.renderedImage().save(os.path.join(img, f'v2_{i}.png'))
app.exitQgis()
