"""
Progetto QGIS delle situazioni dubbie (versione 4, con le aste sotto i ponti): apre situazioni_dubbie.gpkg con i layer in ordine, divisi in
gruppi, con nomi leggibili e un segnalibro per ogni ponte segnalato (Visualizza > Segnalibri spaziali).
Percorsi relativi: il progetto va tenuto nella stessa cartella del GeoPackage.

Uso (PyQGIS): QT_QPA_PLATFORM=offscreen python3 progetto_qgis_v3.py <cartella consegna> [cartella immagini di controllo]
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
app = QgsApplication([], False)
app.initQgis()
prj = QgsProject.instance()
prj.setCrs(QgsCoordinateReferenceSystem('EPSG:32633'))
prj.writeEntryBool('Paths', '/Absolute', False)
gp = os.path.join(cart, 'situazioni_dubbie.gpkg')

# gruppi dall'alto verso il basso; dentro ogni gruppo i layer sono nell'ordine di disegno (il primo sta sopra)
gruppi = [
    ('Ponti (punto = sezione di calcolo del codice)', [
        ('ponti_segnalati', 'Ponti segnalati, colore = categoria'),
        ('ponti_non_segnalati', 'Ponti senza situazioni dubbie')]),
    ('Posizione del ponte', [
        ('spostamento_sezione', 'Distanza sezione di calcolo - ponte (oltre 10 m)'),
        ('ponte_kml', 'Ponte nel KML (tracciato)'),
        ('ponte_database', 'Ponte nel database (coordinate inizio-fine)')]),
    ('Idrografia calcolata dal codice', [
        ('aste_sotto_il_ponte', 'Aste sotto il ponte: area calcolata dal codice in ogni incrocio tracciato-reticolo'),
        ('reticolo_codice', 'Reticolo idrografico del codice'),
        ('bacini_codice', 'Bacini del codice (ponti segnalati)')]),
]
root = prj.layerTreeRoot()
layers = {}
for nome_g, lista in gruppi:
    g = root.addGroup(nome_g)
    for tab, nome in lista:
        lyr = QgsVectorLayer(f'{gp}|layername={tab}', nome, 'ogr')
        assert lyr.isValid(), tab
        prj.addMapLayer(lyr, False)
        g.addLayer(lyr)
        layers[tab] = lyr
# sfondo OpenStreetMap (serve la connessione a internet; si puo' spegnere)
osm = QgsRasterLayer('type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0',
                     'Sfondo OpenStreetMap', 'wms')
if osm.isValid():
    prj.addMapLayer(osm, False)
    root.addLayer(osm)

# segnalibri: uno per ponte segnalato, 1.2 km attorno alla sezione, nominati "ID - categoria"
bm = prj.bookmarkManager()
ps = layers['ponti_segnalati']
for f in sorted(ps.getFeatures(), key=lambda f: int(f['ID'])):
    p = f.geometry().asPoint()
    r = QgsReferencedRectangle(QgsRectangle(p.x() - 600, p.y() - 600, p.x() + 600, p.y() + 600), prj.crs())
    b = QgsBookmark(); b.setName(f"{int(f['ID'])} - {f['Categoria']}"); b.setExtent(r); b.setGroup('Ponti segnalati')
    bm.addBookmark(b)

ext = layers['bacini_codice'].extent(); ext.combineExtentWith(layers['ponti_segnalati'].extent()); ext.scale(1.05)
prj.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(ext, prj.crs()))
f_qgs = os.path.join(cart, 'situazioni_dubbie.qgs')
prj.write(f_qgs)
print('progetto', f_qgs, '; segnalibri', len(bm.bookmarks()))


def render(estensione, f_png, size=(1600, 1200)):
    ordine = [l for l in root.layerOrder() if l.name() != 'Sfondo OpenStreetMap']
    ms = QgsMapSettings(); ms.setLayers(ordine); ms.setDestinationCrs(prj.crs())
    ms.setExtent(estensione); ms.setOutputSize(QSize(*size)); ms.setBackgroundColor(QColor('white'))
    ms.setOutputDpi(110)
    j = QgsMapRendererParallelJob(ms); j.start(); j.waitForFinished(); j.renderedImage().save(f_png)


if img:
    os.makedirs(img, exist_ok=True)
    render(ext, os.path.join(img, 'insieme.png'))
    for b in bm.bookmarks():
        i = b.name().split(' - ')[0]
        if i in ('107', '13', '15', '77', '164', '196'):
            render(b.extent(), os.path.join(img, f'ponte_{i}.png'), (1000, 1000))
app.exitQgis()
