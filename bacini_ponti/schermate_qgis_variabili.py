"""
Schermate per il manuale delle variabili morfologiche (parte B): da eseguire dentro QGIS (qgis --lang it --code schermate_qgis_manuale.py),
con la variabile d'ambiente VERIFICA_DIR = cartella con i file della verifica del ponte di esempio e
SCHERMATE_DIR = cartella di uscita. Apre le finestre reali degli algoritmi con i parametri usati nella verifica,
cattura menu, finestre e mappe e chiude QGIS.
"""
import os
import traceback

import processing
from qgis.core import (QgsApplication, QgsCategorizedSymbolRenderer, QgsColorRampShader, QgsFillSymbol,
                       QgsMapRendererParallelJob, QgsMapSettings, QgsMarkerSymbol, QgsPalLayerSettings,
                       QgsProject, QgsRasterLayer, QgsRasterShader, QgsRectangle, QgsSingleBandPseudoColorRenderer,
                       QgsSingleSymbolRenderer, QgsTextFormat, QgsVectorLayer, QgsVectorLayerSimpleLabeling,
                       QgsTextBufferSettings, QgsStyle)
from qgis.PyQt.QtCore import QSize, QTimer, Qt
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import QApplication
from qgis.utils import iface

W = os.environ['VERIFICA_DIR']
OUT = os.environ['SCHERMATE_DIR']
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'log.txt'), 'w')
f = lambda n: os.path.join(W, n)
POR = '603339.0001,627669.0001,4464253.3481,4473458.3481 [EPSG:32633]'


def attendi(ms=800):
    for _ in range(int(ms / 50)):
        QApplication.processEvents()
        QTimer.singleShot(50, lambda: None)
        import time
        time.sleep(0.05)


def salva(widget, nome):
    try:
        iface.messageBar().clearWidgets()
    except Exception:
        pass
    attendi(600)
    widget.grab().save(os.path.join(OUT, nome))
    LOG.write(f'ok {nome}\n')
    LOG.flush()


def dialogo(alg, par, nome, w=900, h=760):
    try:
        d = processing.createAlgorithmDialog(alg, par)
        d.resize(w, h)
        d.show()
        attendi(1000)
        # apre la sezione "Parametri avanzati", dove stanno opzioni come -unscale
        from qgis.PyQt.QtCore import QMetaObject
        from qgis.PyQt.QtWidgets import QWidget
        g = d.findChild(QWidget, 'grpAdvanced')
        if g is not None and g.isVisible():
            QMetaObject.invokeMethod(g, 'toggleCollapsed')
        attendi(800)
        salva(d, nome)
        # seconda schermata con la parte bassa del modulo (file di uscita), se la finestra scorre
        from qgis.PyQt.QtWidgets import QScrollArea
        for sa in d.findChildren(QScrollArea):
            sb = sa.verticalScrollBar()
            if sb.maximum() > 0 and sa.isVisible():
                sb.setValue(sb.maximum())
                attendi(600)
                salva(d, nome.replace('.png', '_uscite.png'))
                break
        d.close()
    except Exception:
        LOG.write(f'ERRORE {nome}\n{traceback.format_exc()}\n')


def menu(m, sotto, nome):
    try:
        mw = iface.mainWindow()
        m.popup(mw.mapToGlobal(mw.rect().topLeft()) + mw.rect().center() * 0 + __import__('qgis.PyQt.QtCore', fromlist=['QPoint']).QPoint(300, 60))
        attendi(500)
        if sotto:
            for a in m.actions():
                if a.menu() is not None and sotto.lower() in a.text().replace('&', '').lower():
                    m.setActiveAction(a)
                    a.menu().popup(m.mapToGlobal(m.actionGeometry(a).topRight()))
                    attendi(600)
                    scr = QApplication.primaryScreen().grabWindow(0)
                    scr.save(os.path.join(OUT, nome))
                    a.menu().close()
                    break
        else:
            QApplication.primaryScreen().grabWindow(0).save(os.path.join(OUT, nome))
        m.close()
        LOG.write(f'ok {nome}\n')
    except Exception:
        LOG.write(f'ERRORE {nome}\n{traceback.format_exc()}\n')


def raster(path, nome, stile=None):
    lay = QgsRasterLayer(path, nome)
    if stile == 'dem':
        sh = QgsRasterShader()
        rampa = QgsStyle.defaultStyle().colorRamp('Spectral')
        rampa.invert()
        fn = QgsColorRampShader(100, 400, rampa)
        fn.classifyColorRamp(8)
        sh.setRasterShaderFunction(fn)
        r = QgsSingleBandPseudoColorRenderer(lay.dataProvider(), 1, sh)
        r.setClassificationMin(100)
        r.setClassificationMax(400)
        lay.setRenderer(r)
        lay.setOpacity(0.55)
    elif stile == 'reticolo':
        sh = QgsRasterShader()
        fn = QgsColorRampShader()
        fn.setColorRampType(QgsColorRampShader.Exact)
        fn.setColorRampItemList([QgsColorRampShader.ColorRampItem(1, QColor(0, 90, 255), 'reticolo')])
        sh.setRasterShaderFunction(fn)
        lay.setRenderer(QgsSingleBandPseudoColorRenderer(lay.dataProvider(), 1, sh))
    elif stile == 'acc':
        sh = QgsRasterShader()
        fn = QgsColorRampShader(0, 4000, QgsStyle.defaultStyle().colorRamp('Blues'))
        fn.classifyColorRamp(6)
        sh.setRasterShaderFunction(fn)
        lay.setRenderer(QgsSingleBandPseudoColorRenderer(lay.dataProvider(), 1, sh))
    QgsProject.instance().addMapLayer(lay)
    return lay


def vettore(path, nome, stile):
    lay = QgsVectorLayer(path, nome, 'ogr')
    if stile == 'ponte':
        lay.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol.createSimple(
            {'name': 'triangle', 'color': '255,0,0', 'size': '6', 'outline_color': 'black'})))
    elif stile == 'sezione':
        lay.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol.createSimple(
            {'name': 'square', 'color': '255,200,0', 'size': '5', 'outline_color': 'black'})))
    elif stile == 'codice':
        lay.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
            {'color': '0,0,0,0', 'outline_color': '255,0,0', 'outline_width': '0.9'})))
    elif stile == 'qgis':
        lay.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
            {'color': '0,160,0,70', 'outline_color': '0,120,0', 'outline_width': '0.5', 'outline_style': 'dash'})))
    elif stile == 'diff':
        lay.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple(
            {'color': '255,0,255,255', 'outline_color': '255,0,255', 'outline_width': '0.4'})))
    QgsProject.instance().addMapLayer(lay)
    return lay


def etichetta(lay, campo):
    s = QgsPalLayerSettings()
    s.fieldName = campo
    tf = QgsTextFormat()
    tf.setFont(QFont('DejaVu Sans', 13))
    tf.setSize(13)
    b = QgsTextBufferSettings()
    b.setEnabled(True)
    b.setSize(1)
    tf.setBuffer(b)
    s.setFormat(tf)
    lay.setLabeling(QgsVectorLayerSimpleLabeling(s))
    lay.setLabelsEnabled(True)


def mappa(layers, ext, nome, w=1100, h=800):
    ms = QgsMapSettings()
    ms.setLayers(layers)
    ms.setDestinationCrs(layers[0].crs())
    ms.setOutputSize(QSize(w, h))
    ms.setExtent(ext)
    ms.setBackgroundColor(QColor('white'))
    job = QgsMapRendererParallelJob(ms)
    job.start()
    job.waitForFinished()
    job.renderedImage().save(os.path.join(OUT, nome))
    LOG.write(f'ok {nome}\n')


def finestra_principale(layers_on, ext, nome):
    try:
        root = QgsProject.instance().layerTreeRoot()
        for n in root.findLayers():
            n.setItemVisibilityChecked(n.layer() in layers_on)
        c = iface.mapCanvas()
        c.setExtent(ext)
        c.refreshAllLayers()
        attendi(1500)
        c.waitWhileRendering()
        attendi(800)
        salva(iface.mainWindow(), nome)
    except Exception:
        LOG.write(f'ERRORE {nome}\n{traceback.format_exc()}\n')


def linea(path, nome, colore, larg='0.8', tratt='solid'):
    from qgis.core import QgsLineSymbol
    lay = QgsVectorLayer(path, nome, 'ogr')
    lay.setRenderer(QgsSingleSymbolRenderer(QgsLineSymbol.createSimple(
        {'color': colore, 'width': larg, 'line_style': tratt})))
    QgsProject.instance().addMapLayer(lay)
    return lay


def main():
    try:
        mw = iface.mainWindow()
        mw.showNormal()
        mw.resize(1500, 950)
        attendi(1500)
        omb = raster(f('p100_ombreggiatura.tif'), 'ombreggiatura')
        ret = raster(f('p100_reticolo_mask.tif'), 'p100_reticolo', 'reticolo')
        bq = vettore(f('p100_bacino_parametri.gpkg'), 'p100_bacino_QGIS', 'qgis')
        ponte = vettore(f('p100_ponte_utm_xy.gpkg'), 'ponte_100', 'ponte')
        lun = linea(f('p100_percorso_lungo.gpkg'), 'percorso_dal_punto_piu_lontano', '230,0,0', '0.9')
        val = linea(f('p100_percorso_valle.gpkg'), 'percorso_dalla_sezione', '20,20,20', '0.9', 'dash')
        far = vettore(f('p100_punto_lontano.gpkg'), 'punto_piu_lontano', 'sezione')
        etichetta(far, 'nome')
        tra = vettore(f('p100_punti_tratto_quote.gpkg'), 'punti_tratto', 'ponte')
        s = QgsPalLayerSettings()
        s.isExpression = True
        s.fieldName = "if(layer like '%monte%', 'monte 250 m: ', 'valle 250 m: ') || format_number(quota_1, 2) || ' m'"
        tf = QgsTextFormat(); tf.setSize(13); b = QgsTextBufferSettings(); b.setEnabled(True); b.setSize(1); tf.setBuffer(b)
        s.setFormat(tf)
        tra.setLabeling(QgsVectorLayerSimpleLabeling(s)); tra.setLabelsEnabled(True)
        ext_bac = QgsRectangle(621700, 4468800, 623600, 4470900)
        # B1 coordinate
        dialogo('native:createpointslayerfromtable', {'INPUT': f('p100_ponte.csv'), 'XFIELD': 'X', 'YFIELD': 'Y',
                'TARGET_CRS': 'EPSG:4326', 'OUTPUT': f('p100_ponte_wgs84.gpkg')}, 'B1a_punti_da_tabella.png')
        dialogo('native:reprojectlayer', {'INPUT': f('p100_ponte_wgs84.gpkg'), 'TARGET_CRS': 'EPSG:32633',
                'OUTPUT': f('p100_ponte_utm.gpkg')}, 'B1b_riproietta.png', 900, 520)
        dialogo('native:addxyfields', {'INPUT': f('p100_ponte_utm.gpkg'), 'CRS': 'EPSG:32633', 'PREFIX': 'utm_',
                'OUTPUT': f('p100_ponte_utm_xy.gpkg')}, 'B1c_campi_xy.png', 900, 520)
        try:
            t = iface.showAttributeTable(ponte); attendi(1200); t.setMinimumSize(900, 160); t.resize(900, 160); attendi(800)
            salva(t, 'B1d_tabella_ponte.png'); t.close()
        except Exception:
            LOG.write('ERRORE B1d\n' + traceback.format_exc())
        # B4 pendenza D8
        dialogo('grass7:r.fill.dir', {'input': f('p100_dem_m.tif'), 'format': 0, 'output': f('p100_dem_riempito.tif'),
                'direction': f('p100_dir_fill.tif'), 'areas': f('p100_aree_problema.tif'),
                'GRASS_REGION_CELLSIZE_PARAMETER': 5}, 'B4a_r_fill_dir.png', 900, 700)
        expr = ('max(0, (A-A[-1,0])/5, (A-A[1,0])/5, (A-A[0,-1])/5, (A-A[0,1])/5, (A-A[-1,-1])/7.0711, '
                '(A-A[-1,1])/7.0711, (A-A[1,-1])/7.0711, (A-A[1,1])/7.0711)')
        dialogo('grass7:r.mapcalc.simple', {'a': f('p100_dem_riempito.tif'), 'expression': expr,
                'output': f('p100_pendD8_dem_riempito.tif'), 'GRASS_REGION_CELLSIZE_PARAMETER': 5},
                'B4b_r_mapcalc_pendenza_D8.png', 950, 760)
        dialogo('native:zonalstatisticsfb', {'INPUT': f('p100_bacino.gpkg'), 'INPUT_RASTER': f('p100_pendD8_dem_riempito.tif'),
                'RASTER_BAND': 1, 'COLUMN_PREFIX': 's_', 'STATISTICS': [2], 'OUTPUT': f('_z_dem_riempito.gpkg')},
                'B4c_statistiche_zonali_D8.png')
        # B5 pendenza cella
        dialogo('native:rastersampling', {'INPUT': f('p100_sezione_punto.gpkg'), 'RASTERCOPY': f('p100_pendD8_dem_riempito.tif'),
                'COLUMN_PREFIX': 'pend_', 'OUTPUT': f('p100_sezione_pendenza.gpkg')}, 'B5a_campiona_pendenza_cella.png', 900, 560)
        # B6 percorso piu lungo
        dialogo('grass7:r.path', {'input': f('p100_direzioni.tif'), 'format': 2, 'start_points': f('p100_punto_lontano.gpkg'),
                'vector_path': f('p100_percorso_lungo.gpkg'), 'GRASS_REGION_CELLSIZE_PARAMETER': 5,
                'GRASS_OUTPUT_TYPE_PARAMETER': 2}, 'B6a_r_path.png', 950, 900)
        mappa([far, ponte, lun, val, bq, ret, omb], ext_bac, 'B6b_mappa_percorso_lungo.png')
        mappa([far, ponte, lun, val, bq, omb], QgsRectangle(621600, 4468300, 628000, 4471000), 'B6c_mappa_percorsi_valle.png', 1300, 560)
        # B7 pendenza di tratto
        dialogo('native:interpolatepoint', {'INPUT': f('p100_percorso_valle.gpkg'), 'DISTANCE': 250,
                'OUTPUT': f('p100_punto_valle_250.gpkg')}, 'B7a_interpola_valle.png', 900, 520)
        dialogo('native:interpolatepoint', {'INPUT': f('p100_percorso_lungo.gpkg'), 'DISTANCE': 1542.31,
                'OUTPUT': f('p100_punto_monte_250.gpkg')}, 'B7b_interpola_monte.png', 900, 520)
        dialogo('native:rastersampling', {'INPUT': f('p100_punti_tratto.gpkg'), 'RASTERCOPY': f('p100_dem_m.tif'),
                'COLUMN_PREFIX': 'quota_', 'OUTPUT': f('p100_punti_tratto_quote.gpkg')}, 'B7c_campiona_quote.png', 900, 560)
        mappa([tra, ponte, lun, val, ret, omb], QgsRectangle(622300, 4468900, 623000, 4469550), 'B7d_mappa_tratto.png', 1000, 920)
    except Exception:
        LOG.write('ERRORE GENERALE\n' + traceback.format_exc())
    LOG.close()
    QgsApplication.exit(0)


QTimer.singleShot(6000, main)
