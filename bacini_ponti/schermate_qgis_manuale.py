"""
Schermate per il manuale di verifica: da eseguire dentro QGIS (qgis --lang it --code schermate_qgis_manuale.py),
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


def main():
    try:
        mw = iface.mainWindow()
        mw.showNormal()
        mw.resize(1500, 950)
        mw.move(0, 0)
        attendi(1500)
        # ---- layer
        dem = raster(f('p100_dem_m.tif'), 'p100_dem_m', 'dem')
        omb = raster(f('p100_ombreggiatura.tif'), 'ombreggiatura')
        ret = raster(f('p100_reticolo_mask.tif'), 'p100_reticolo', 'reticolo')
        acc = raster(f('p100_accumulo.tif'), 'p100_accumulo', 'acc')
        ponte = vettore(f('p100_ponte.gpkg'), 'ponte_100', 'ponte')
        etichetta(ponte, 'nome')
        sez = vettore(f('p100_sezione.gpkg'), 'sezione_di_chiusura', 'sezione')
        etichetta(sez, 'nome')
        bq = vettore(f('p100_bacino_parametri.gpkg'), 'p100_bacino_QGIS', 'qgis')
        bc = vettore(f('p100_bacino_codice.gpkg'), 'p100_bacino_codice', 'codice')
        df = vettore(f('p100_differenza.gpkg'), 'differenza_simmetrica', 'diff')
        ext_bac = QgsRectangle(621700, 4469000, 623400, 4470900)
        ext_zoom = QgsRectangle(622600, 4469170, 622690, 4469240)
        ext_por = QgsRectangle(603339, 4464253, 627669, 4473458)

        # ---- schermate della finestra principale
        finestra_principale([dem, omb], ext_por, '00_qgis_progetto.png')

        # Passo 3
        menu(iface.rasterMenu(), 'Estrazione', '03a_menu_raster_estrazione.png')
        dialogo('gdal:cliprasterbyextent', {'INPUT': f('../dem_v4/dem5m_unico_v4.tif'), 'PROJWIN': POR,
                                            'OUTPUT': f('p100_dem_ritaglio.tif')}, '03b_ritaglia_raster.png')
        # Passo 4
        menu(iface.rasterMenu(), 'Conversione', '04a_menu_raster_conversione.png')
        dialogo('gdal:translate', {'INPUT': f('p100_dem_ritaglio.tif'), 'EXTRA': '-unscale -ot Float32',
                                   'OUTPUT': f('p100_dem_m.tif')}, '04b_converti.png')
        # Passo 5
        try:
            tb = mw.findChild(__import__('qgis.PyQt.QtWidgets', fromlist=['QDockWidget']).QDockWidget,
                              'ProcessingToolbox')
            tb.show()
            tb.raise_()
            sb = tb.findChild(__import__('qgis.gui', fromlist=['QgsFilterLineEdit']).QgsFilterLineEdit)
            sb.setText('r.watershed')
            attendi(1500)
            salva(tb, '05a_strumenti_processing_rwatershed.png')
        except Exception:
            LOG.write('ERRORE 05a\n' + traceback.format_exc())
        dialogo('grass7:r.watershed', {'elevation': f('p100_dem_m.tif'), 'threshold': 4000, '-s': True, '-a': True,
                                       'accumulation': f('p100_accumulo.tif'), 'drainage': f('p100_direzioni.tif'),
                                       'stream': f('p100_reticolo.tif'), 'GRASS_REGION_CELLSIZE_PARAMETER': 5},
                '05b_r_watershed.png', 950, 1000)
        mappa([ponte, ret, omb, dem], ext_bac, '05c_mappa_reticolo.png')
        # Passo 6
        mappa([sez, ponte, ret, acc], ext_zoom, '06a_mappa_sezione_zoom.png', 1000, 780)
        finestra_principale([sez, ponte, ret, acc], ext_zoom, '06b_qgis_sezione.png')
        # Passo 7
        dialogo('grass7:r.water.outlet', {'input': f('p100_direzioni.tif'),
                                          'coordinates': '622646.50012207,4469205.8480835 [EPSG:32633]',
                                          'output': f('p100_bacino.tif'), 'GRASS_REGION_CELLSIZE_PARAMETER': 5},
                '07a_r_water_outlet.png')
        dialogo('gdal:polygonize', {'INPUT': f('p100_bacino.tif'), 'BAND': 1, 'FIELD': 'DN',
                                    'OUTPUT': f('p100_bacino_tutti.gpkg')}, '07b_poligonizza.png')
        dialogo('native:extractbyexpression', {'INPUT': f('p100_bacino_tutti.gpkg'), 'EXPRESSION': '"DN" = 1',
                                               'OUTPUT': f('p100_bacino.gpkg')}, '07c_estrai_dn1.png')
        mappa([ponte, bq, ret, omb, dem], ext_bac, '07d_mappa_bacino.png')
        # Passo 8
        dialogo('native:fieldcalculator', {'INPUT': f('p100_bacino.gpkg'), 'FIELD_NAME': 'area_km2',
                                           'FIELD_TYPE': 0, 'FIELD_PRECISION': 4, 'FORMULA': '$area / 1000000',
                                           'OUTPUT': f('p100_b1.gpkg')}, '08a_calcolatore_area.png')
        dialogo('native:fieldcalculator', {'INPUT': f('p100_b1.gpkg'), 'FIELD_NAME': 'perim_km',
                                           'FIELD_TYPE': 0, 'FIELD_PRECISION': 4, 'FORMULA': '$perimeter / 1000',
                                           'OUTPUT': f('p100_b2.gpkg')}, '08b_calcolatore_perimetro.png')
        # Passo 9
        dialogo('native:zonalstatisticsfb', {'INPUT': f('p100_b2.gpkg'), 'INPUT_RASTER': f('p100_dem_m.tif'),
                                             'RASTER_BAND': 1, 'COLUMN_PREFIX': 'dem_', 'STATISTICS': [2, 5, 6],
                                             'OUTPUT': f('p100_b3.gpkg')}, '09a_statistiche_zonali_dem.png')
        dialogo('native:zonalstatisticsfb', {'INPUT': f('p100_b3.gpkg'), 'INPUT_RASTER': f('p100_cn.tif'),
                                             'RASTER_BAND': 1, 'COLUMN_PREFIX': 'cn_', 'STATISTICS': [2],
                                             'OUTPUT': f('p100_b4.gpkg')}, '09b_statistiche_zonali_cn.png')
        # Passo 10
        dialogo('native:slope', {'INPUT': f('p100_dem_m.tif'), 'Z_FACTOR': 1,
                                 'OUTPUT': f('p100_pendenza_gradi.tif')}, '10a_pendenza.png', 900, 560)
        dialogo('native:rastercalc', {'LAYERS': [f('p100_pendenza_gradi.tif')],
                                      'EXPRESSION': 'tan("p100_pendenza_gradi@1" * 0.0174533) * 100',
                                      'OUTPUT': f('p100_pendenza_perc.tif')}, '10b_calcolatore_raster.png', 950, 800)
        dialogo('native:zonalstatisticsfb', {'INPUT': f('p100_b4.gpkg'), 'INPUT_RASTER': f('p100_pendenza_perc.tif'),
                                             'RASTER_BAND': 1, 'COLUMN_PREFIX': 'pend_', 'STATISTICS': [2],
                                             'OUTPUT': f('p100_bacino_parametri.gpkg')}, '10c_statistiche_pendenza.png')
        try:
            t = iface.showAttributeTable(bq)
            attendi(1500)
            t.setMinimumSize(1400, 260)
            t.resize(1400, 260)
            attendi(800)
            salva(t, '10d_tabella_attributi.png')
            t.close()
        except Exception:
            LOG.write('ERRORE 10d\n' + traceback.format_exc())
        # Passo 11
        dialogo('native:symmetricaldifference', {'INPUT': f('p100_bacino_codice.gpkg'),
                                                 'OVERLAY': f('p100_bacino.gpkg'),
                                                 'OUTPUT': f('p100_differenza.gpkg')}, '11a_differenza_simmetrica.png')
        mappa([df, bc, bq, ponte, omb], ext_bac, '11b_mappa_confronto.png')
        mappa([df, bc, bq, ponte, omb], QgsRectangle(622550, 4469150, 622900, 4469420), '11c_mappa_confronto_zoom.png')
        # Cronologia
        try:
            from processing.gui.HistoryDialog import HistoryDialog
            h = HistoryDialog()
            h.resize(1100, 600)
            h.show()
            attendi(1500)
            salva(h, '12_cronologia_processing.png')
            h.close()
        except Exception:
            LOG.write('ERRORE 12\n' + traceback.format_exc())
    except Exception:
        LOG.write('ERRORE GENERALE\n' + traceback.format_exc())
    LOG.close()
    QgsApplication.exit(0)


QTimer.singleShot(6000, main)
