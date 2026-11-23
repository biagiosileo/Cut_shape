"""
Progetto QGIS delle situazioni dubbie, versione 5 (snella): 4 layer + reticolo spento + sfondo, un segnalibro per
ponte segnalato ("ID - categoria"). Uso (PyQGIS): python progetto_qgis_v5.py <cartella> [cartella immagini]
"""
import os
import sys

from qgis.core import (QgsApplication, QgsBookmark, QgsCoordinateReferenceSystem, QgsMapRendererParallelJob,
                       QgsMapSettings, QgsProject, QgsRasterLayer, QgsRectangle, QgsReferencedRectangle, QgsVectorLayer)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor

cart = os.path.abspath(sys.argv[1])
img = sys.argv[2] if len(sys.argv) > 2 else None
app = QgsApplication([], False); app.initQgis()
prj = QgsProject.instance()
prj.setCrs(QgsCoordinateReferenceSystem('EPSG:32633'))
prj.writeEntryBool('Paths', '/Absolute', False)
gp = os.path.join(cart, 'situazioni_dubbie.gpkg')
root = prj.layerTreeRoot()
L = {}
for tab, nome, vis in (('ponti', 'Ponti (punto = sezione di calcolo), colore = categoria', True),
                       ('aste_sotto_il_ponte', 'Aste sotto il ponte, con area calcolata dal codice', True),
                       ('tracciato_kml', 'Tracciato del ponte nel KML', True),
                       ('bacini_segnalati', 'Bacini dei ponti segnalati', True),
                       ('reticolo', 'Reticolo del codice (0.1 km2)', False)):
    lyr = QgsVectorLayer(f'{gp}|layername={tab}', nome, 'ogr')
    assert lyr.isValid(), tab
    prj.addMapLayer(lyr, False)
    root.addLayer(lyr).setItemVisibilityChecked(vis)
    L[tab] = lyr
osm = QgsRasterLayer('type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0',
                     'Sfondo OpenStreetMap', 'wms')
if osm.isValid():
    prj.addMapLayer(osm, False); root.addLayer(osm)
bm = prj.bookmarkManager()
segn = [f for f in L['ponti'].getFeatures() if f['Categoria'] != 'nessuna']
for f in sorted(segn, key=lambda f: int(f['ID'])):
    p = f.geometry().asPoint()
    b = QgsBookmark(); b.setName(f"{int(f['ID'])} - {f['Categoria']}"); b.setGroup('Situazioni dubbie')
    b.setExtent(QgsReferencedRectangle(QgsRectangle(p.x() - 500, p.y() - 500, p.x() + 500, p.y() + 500), prj.crs()))
    bm.addBookmark(b)
ext = L['ponti'].extent(); ext.scale(1.05)
prj.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(ext, prj.crs()))
f_qgs = os.path.join(cart, 'situazioni_dubbie.qgs')
prj.write(f_qgs)
att = os.path.join(cart, 'situazioni_dubbie_attachments.zip')
if os.path.exists(att):
    os.remove(att)
print('progetto', f_qgs, '; segnalibri', len(bm.bookmarks()))
if img:
    os.makedirs(img, exist_ok=True)
    lay = [l for l in root.layerOrder() if l.name() != 'Sfondo OpenStreetMap' and root.findLayer(l.id()).isVisible()]
    for b in bm.bookmarks():
        if b.name().split(' - ')[0] in ('13', '107', '164'):
            ms = QgsMapSettings(); ms.setLayers(lay); ms.setDestinationCrs(prj.crs()); ms.setExtent(b.extent())
            ms.setOutputSize(QSize(900, 900)); ms.setBackgroundColor(QColor('white')); ms.setOutputDpi(100)
            j = QgsMapRendererParallelJob(ms); j.start(); j.waitForFinished()
            j.renderedImage().save(os.path.join(img, f'v5_{b.name().split(" - ")[0]}.png'))
    ms = QgsMapSettings(); ms.setLayers(lay); ms.setDestinationCrs(prj.crs()); ms.setExtent(ext)
    ms.setOutputSize(QSize(1200, 1200)); ms.setBackgroundColor(QColor('white'))
    j = QgsMapRendererParallelJob(ms); j.start(); j.waitForFinished(); j.renderedImage().save(os.path.join(img, 'v5_insieme.png'))
app.exitQgis()
