"""
Progetto QGIS della cartella condivisa (percorsi relativi): carica i file 1-4 in gruppi, con gli stili salvati
nei GeoPackage, e crea i segnalibri spaziali per i 212 attraversamenti e per i casi dubbi.

Uso (PyQGIS): QT_QPA_PLATFORM=offscreen python3 progetto_cartella_condivisa.py <cartella condivisa> [cartella immagini]
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
    ('4. Casi dubbi', '4_casi_dubbi/casi_dubbi.gpkg', [
        ('casi_dubbi', 'Casi dubbi, colore = categoria'),
        ('spostamento_sezione', 'Distanza sezione di calcolo - ponte (oltre 10 m)'),
        ('ponte_kml', 'Ponte nel KML (tracciato)'),
        ('ponte_database', 'Ponte nel database (coordinate inizio-fine)')]),
    ('3. Attraversamenti', '3_punti_attraversamenti.gpkg', [
        ('punti_attraversamenti', 'Sezioni di calcolo dei 212 attraversamenti, colore = classe')]),
    ('2. Bacini del codice', '2_bacini_codice.gpkg', [
        ('bacini_codice', 'Bacini del codice, colore = classe')]),
    ('1. Reticolo del codice', '1_reticolo_idrografico.gpkg', [
        ('reticolo_idrografico', 'Reticolo idrografico (soglia 0.1 km2)')]),
]
root = prj.layerTreeRoot()
L = {}
for ng, f, lista in gruppi:
    g = root.addGroup(ng)
    for tab, nome in lista:
        lyr = QgsVectorLayer(f'{os.path.join(cart, f)}|layername={tab}', nome, 'ogr')
        assert lyr.isValid(), tab
        prj.addMapLayer(lyr, False); g.addLayer(lyr); L[tab] = lyr
osm = QgsRasterLayer('type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0',
                     'Sfondo OpenStreetMap', 'wms')
if osm.isValid():
    prj.addMapLayer(osm, False); root.addLayer(osm)

bm = prj.bookmarkManager()
for tab, gr, campo in (('casi_dubbi', 'Casi dubbi', 'Categoria'), ('punti_attraversamenti', 'Tutti gli attraversamenti', 'Classe')):
    for ft in sorted(L[tab].getFeatures(), key=lambda f: int(f['ID'])):
        p = ft.geometry().asPoint()
        b = QgsBookmark(); b.setName(f"{int(ft['ID'])} - {ft[campo]}"); b.setGroup(gr)
        b.setExtent(QgsReferencedRectangle(QgsRectangle(p.x() - 600, p.y() - 600, p.x() + 600, p.y() + 600), prj.crs()))
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
    lay = [l for l in root.layerOrder() if l.name() != 'Sfondo OpenStreetMap']
    for nome, e, size in [('cartella_insieme', ext, (1400, 1400))] + [
            (f'cartella_{b.name().split(" - ")[0]}', b.extent(), (900, 900)) for b in bm.bookmarks()
            if b.group() == 'Casi dubbi' and b.name().split(' - ')[0] in ('90', '13')]:
        ms = QgsMapSettings(); ms.setLayers(lay); ms.setDestinationCrs(prj.crs()); ms.setExtent(e)
        ms.setOutputSize(QSize(*size)); ms.setBackgroundColor(QColor('white')); ms.setOutputDpi(100)
        j = QgsMapRendererParallelJob(ms); j.start(); j.waitForFinished()
        j.renderedImage().save(os.path.join(img, nome + '.png'))
app.exitQgis()
