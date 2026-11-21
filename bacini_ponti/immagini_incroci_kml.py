"""
Immagini dei ponti indicati: reticolo del codice, tracciati KML, posizione iniziale e finale del punto.
Uso (PyQGIS): QT_QPA_PLATFORM=offscreen python3 immagini_incroci_kml.py <cartella v2> <controllo_coordinate.gpkg> <out> ID [ID ...]
"""
import os
import sys

from qgis.core import (QgsApplication, QgsCoordinateReferenceSystem, QgsLineSymbol, QgsMapRendererParallelJob,
                       QgsMapSettings, QgsPalLayerSettings, QgsProject, QgsRectangle, QgsTextFormat,
                       QgsVectorLayer, QgsVectorLayerSimpleLabeling)
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor

v2, gpkg, out = sys.argv[1:4]
ids = [int(a) for a in sys.argv[4:]]
os.makedirs(out, exist_ok=True)
app = QgsApplication([], False); app.initQgis()


def lay(f, t, n):
    l = QgsVectorLayer(f'{f}|layername={t}', n, 'ogr'); assert l.isValid(), t
    QgsProject.instance().addMapLayer(l, False); return l


kml = lay(gpkg, 'kml_tracciati', 'kml')
kml.setRenderer(kml.renderer().__class__(QgsLineSymbol.createSimple({'line_color': '0,230,0,255', 'line_width': '1.6'})))
ret = lay(os.path.join(v2, '3_confronto_aree', 'reticolo_idrografico.gpkg'), 'reticolo_idrografico', 'ret')
pf = lay(os.path.join(v2, '3_confronto_aree', 'punti_attraversamenti.gpkg'), 'punti_attraversamenti', 'pf')
pi = lay(os.path.join(v2, '2_spostamento_punti', 'spostamento_punti.gpkg'), 'posizione_iniziale', 'pi')
for l in (pf,):
    s = QgsPalLayerSettings(); s.fieldName = 'ID'; f = QgsTextFormat(); f.setSize(10); s.setFormat(f)
    l.setLabeling(QgsVectorLayerSimpleLabeling(s)); l.setLabelsEnabled(True)
for i in ids:
    p = next(pf.getFeatures(f'"ID" = {i}')).geometry().asPoint()
    r = QgsRectangle(p.x() - 250, p.y() - 250, p.x() + 250, p.y() + 250)
    ms = QgsMapSettings(); ms.setLayers([pf, pi, kml, ret]); ms.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:32633'))
    ms.setExtent(r); ms.setOutputSize(QSize(700, 700)); ms.setBackgroundColor(QColor('white')); ms.setOutputDpi(96)
    j = QgsMapRendererParallelJob(ms); j.start(); j.waitForFinished()
    j.renderedImage().save(os.path.join(out, f'incroci_{i}.png'))
app.exitQgis()
