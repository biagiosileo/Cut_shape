"""
Schermate per il manuale delle variabili morfologiche (verifica autonoma: input shape ponti, DEM unito, CN): da eseguire dentro QGIS (qgis --lang it --code schermate_qgis_manuale.py),
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
        DEM = os.environ['DEM_UNITO']
        CN = os.environ['CN_FILE']
        demu = raster(DEM, 'dem5m_unico_v4')
        cnl = raster(CN, 'cn5m_unico')
        pa = vettore(f('ponti_analisi.shp'), 'ponti_analisi', 'ponte')
        etichetta(pa, 'ID')
        finestra_principale([pa, demu], QgsRectangle(600000, 4455000, 650000, 4485000), 'N00_qgis_input.png')
        dialogo('native:extractbyattribute', {'INPUT': f('ponti_analisi.shp'), 'FIELD': 'ID', 'OPERATOR': 0, 'VALUE': '100',
                'OUTPUT': f('p100_ponte.gpkg')}, 'NA0_estrai_per_attributo.png', 900, 560)
        dialogo('native:buffer', {'INPUT': f('p100_ponte.gpkg'), 'DISTANCE': 3000, 'SEGMENTS': 5,
                'OUTPUT': f('p100_area_lavoro.gpkg')}, 'NA1a_buffer.png', 900, 700)
        ext = '619645.2501,625645.2501,4466207.0981,4472207.0981 [EPSG:32633]'
        dialogo('gdal:cliprasterbyextent', {'INPUT': DEM, 'PROJWIN': ext, 'OUTPUT': f('p100_dem_ritaglio.tif')},
                'NA1b_ritaglia_dem.png')
        dialogo('gdal:cliprasterbyextent', {'INPUT': CN, 'PROJWIN': ext, 'OUTPUT': f('p100_cn.tif')}, 'NA1c_ritaglia_cn.png')
        omb = raster(f('p100_ombreggiatura.tif'), 'ombreggiatura')
        ret = raster(f('p100_reticolo_mask.tif'), 'p100_reticolo', 'reticolo')
        area = vettore(f('p100_area_lavoro.gpkg'), 'area_di_lavoro', 'codice')
        bq = vettore(f('p100_bacino.gpkg'), 'p100_bacino', 'qgis')
        ponte = vettore(f('p100_ponte.gpkg'), 'ponte_100', 'ponte')
        mappa([ponte, bq, area, ret, omb], QgsRectangle(619400, 4466000, 625900, 4472400), 'NA1d_mappa_area_lavoro.png', 900, 880)
        # B6: celle sorgenti
        dialogo('native:rastercalc', {'LAYERS': [f('p100_accumulo.tif'), f('p100_bacino.tif')],
                'EXPRESSION': 'if ( "p100_accumulo@1" = 1 AND "p100_bacino@1" = 1, 1, 0/0 )',
                'OUTPUT': f('p100_sorgenti.tif')}, 'NB6a_calcolatore_sorgenti.png', 950, 760)
        dialogo('native:pixelstopoints', {'INPUT_RASTER': f('p100_sorgenti.tif'), 'RASTER_BAND': 1, 'FIELD_NAME': 'v',
                'OUTPUT': f('p100_sorgenti_punti.gpkg')}, 'NB6b_pixel_in_punti.png', 900, 560)
        dialogo('grass7:r.path', {'input': f('p100_direzioni.tif'), 'format': 2, 'start_points': f('p100_sorgenti_punti.gpkg'),
                'vector_path': f('p100_percorsi_sorgenti.gpkg'), 'GRASS_REGION_CELLSIZE_PARAMETER': 5,
                'GRASS_OUTPUT_TYPE_PARAMETER': 2}, 'NB6c_r_path_sorgenti.png', 950, 900)
        dialogo('grass7:r.path', {'input': f('p100_direzioni.tif'), 'format': 2, 'start_points': f('p100_sezione.gpkg'),
                'vector_path': f('p100_percorso_sezione.gpkg'), 'GRASS_REGION_CELLSIZE_PARAMETER': 5,
                'GRASS_OUTPUT_TYPE_PARAMETER': 2}, 'NB6d_r_path_sezione.png', 950, 900)
        dialogo('native:fieldcalculator', {'INPUT': f('p100_percorsi_sorgenti.gpkg'), 'FIELD_NAME': 'lung_m', 'FIELD_TYPE': 0,
                'FIELD_PRECISION': 2, 'FORMULA': '$length', 'OUTPUT': f('p100_percorsi_lung.gpkg')}, 'NB6e_lunghezza_percorsi.png')
        dialogo('native:extractbyexpression', {'INPUT': f('p100_percorsi_lung.gpkg'),
                'EXPRESSION': '"lung_m" = maximum("lung_m")', 'OUTPUT': f('p100_percorso_piu_lungo.gpkg')},
                'NB6f_estrai_massimo.png', 900, 600)
        src = vettore(f('p100_sorgenti_punti.gpkg'), 'celle_sorgenti', 'sezione')
        src.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol.createSimple(
            {'name': 'circle', 'color': '255,140,0', 'size': '0.9', 'outline_style': 'no'})))
        lun = linea(f('p100_percorso_piu_lungo.gpkg'), 'percorso_piu_lungo', '230,0,0', '1.0')
        sez = linea(f('p100_percorso_sezione.gpkg'), 'percorso_dalla_sezione', '20,20,20', '0.9', 'dash')
        mappa([ponte, lun, sez, src, bq, omb], QgsRectangle(621800, 4468900, 623300, 4470900), 'NB6g_mappa_sorgenti.png', 900, 1100)
        dialogo('native:interpolatepoint', {'INPUT': f('p100_percorso_piu_lungo.gpkg'), 'DISTANCE': 1542.32,
                'OUTPUT': f('p100_punto_monte.gpkg')}, 'NB7a_interpola_monte.png', 900, 520)
        dialogo('native:interpolatepoint', {'INPUT': f('p100_percorso_sezione.gpkg'), 'DISTANCE': 250,
                'OUTPUT': f('p100_punto_valle.gpkg')}, 'NB7b_interpola_valle.png', 900, 520)
        dialogo('native:addxyfields', {'INPUT': f('p100_ponte_xy.gpkg'), 'CRS': 'EPSG:4326', 'PREFIX': 'wgs_',
                'OUTPUT': f('p100_ponte_coordinate.gpkg')}, 'NB1b_campi_xy_wgs84.png', 900, 520)
        dialogo('native:addxyfields', {'INPUT': f('p100_ponte.gpkg'), 'CRS': 'EPSG:32633', 'PREFIX': 'utm_',
                'OUTPUT': f('p100_ponte_xy.gpkg')}, 'NB1a_campi_xy_utm.png', 900, 520)
        try:
            pc = vettore(f('p100_ponte_coordinate.gpkg'), 'ponte_coordinate', 'ponte')
            t = iface.showAttributeTable(pc); attendi(1200); t.setMinimumSize(1300, 160); t.resize(1300, 160); attendi(800)
            salva(t, 'NB1c_tabella_coordinate.png'); t.close()
        except Exception:
            LOG.write('ERRORE NB1c\n' + traceback.format_exc())
    except Exception:
        LOG.write('ERRORE GENERALE\n' + traceback.format_exc())
    LOG.close()
    QgsApplication.exit(0)


QTimer.singleShot(6000, main)
