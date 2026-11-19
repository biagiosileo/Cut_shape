"""
Schermate per il manuale di verifica GENERICO (file con prefisso pNNN_): da eseguire dentro QGIS (qgis --lang it --code schermate_qgis_manuale.py),
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
        I = os.environ['INPUT_DIR']
        g = lambda n: os.path.join(I, n)
        EXT = '619645.2501,625645.2501,4466207.0981,4472207.0981 [EPSG:32633]'
        SEZ = '622646.50012207,4469205.8480835 [EPSG:32633]'
        # ---- Parte A
        dialogo('native:extractbyattribute', {'INPUT': g('ponti_analisi.gpkg'), 'FIELD': 'ID', 'OPERATOR': 0,
                'VALUE': 'NNN', 'OUTPUT': f('pNNN_ponte.gpkg')}, 'A0_estrai_per_attributo.png', 900, 560)
        dialogo('native:buffer', {'INPUT': f('pNNN_ponte.gpkg'), 'DISTANCE': 3000, 'SEGMENTS': 5,
                'OUTPUT': f('pNNN_area_lavoro.gpkg')}, 'A1a_buffer.png', 900, 700)
        dialogo('gdal:cliprasterbyextent', {'INPUT': g('dem5m_unico_v4.tif'), 'PROJWIN': EXT,
                'OUTPUT': f('pNNN_dem_ritaglio.tif')}, 'A1b_ritaglia_dem.png')
        dialogo('gdal:cliprasterbyextent', {'INPUT': g('cn5m_unico.tif'), 'PROJWIN': EXT,
                'OUTPUT': f('pNNN_cn.tif')}, 'A1c_ritaglia_cn.png')
        menu(iface.rasterMenu(), 'Conversione', 'A2a_menu_conversione.png')
        dialogo('gdal:translate', {'INPUT': f('pNNN_dem_ritaglio.tif'), 'EXTRA': '-unscale -ot Float32',
                'OUTPUT': f('pNNN_dem_m.tif')}, 'A2b_trasforma.png')
        dialogo('grass7:r.watershed', {'elevation': f('pNNN_dem_m.tif'), 'threshold': 4000, '-s': True, '-a': True,
                'accumulation': f('pNNN_accumulo.tif'), 'drainage': f('pNNN_direzioni.tif'),
                'stream': f('pNNN_reticolo.tif'), 'GRASS_REGION_CELLSIZE_PARAMETER': 5},
                'A3_r_watershed.png', 950, 1000)
        dialogo('native:createpointslayerfromtable', {'INPUT': f('pNNN_sezione.csv'), 'XFIELD': 'X', 'YFIELD': 'Y',
                'TARGET_CRS': 'EPSG:32633', 'OUTPUT': f('pNNN_sezione.gpkg')}, 'A4b_punti_da_tabella.png', 900, 640)
        dialogo('grass7:r.water.outlet', {'input': f('pNNN_direzioni.tif'), 'coordinates': SEZ,
                'output': f('pNNN_bacino.tif'), 'GRASS_REGION_CELLSIZE_PARAMETER': 5}, 'A5a_r_water_outlet.png')
        dialogo('gdal:polygonize', {'INPUT': f('pNNN_bacino.tif'), 'BAND': 1, 'FIELD': 'DN',
                'OUTPUT': f('pNNN_bacino_tutti.gpkg')}, 'A5b_poligonizza.png')
        dialogo('native:extractbyexpression', {'INPUT': f('pNNN_bacino_tutti.gpkg'), 'EXPRESSION': '"DN" = 1',
                'OUTPUT': f('pNNN_bacino.gpkg')}, 'A5c_estrai_dn1.png', 900, 640)
        # ---- Parte B
        dialogo('native:addxyfields', {'INPUT': f('pNNN_ponte.gpkg'), 'CRS': 'EPSG:32633', 'PREFIX': 'utm_',
                'OUTPUT': f('pNNN_ponte_xy.gpkg')}, 'B1a_campi_xy_utm.png', 900, 560)
        dialogo('native:addxyfields', {'INPUT': f('pNNN_ponte_xy.gpkg'), 'CRS': 'EPSG:4326', 'PREFIX': 'wgs_',
                'OUTPUT': f('pNNN_ponte_coordinate.gpkg')}, 'B1b_campi_xy_wgs84.png', 900, 560)
        dialogo('native:fieldcalculator', {'INPUT': f('pNNN_bacino.gpkg'), 'FIELD_NAME': 'area_km2', 'FIELD_TYPE': 0,
                'FIELD_LENGTH': 12, 'FIELD_PRECISION': 4, 'FORMULA': 'area(@geometry) / 1000000',
                'OUTPUT': f('pNNN_bacino_a.gpkg')}, 'B2a_calcolatore_area.png', 950, 820)
        dialogo('native:fieldcalculator', {'INPUT': f('pNNN_bacino_a.gpkg'), 'FIELD_NAME': 'perim_km', 'FIELD_TYPE': 0,
                'FIELD_LENGTH': 12, 'FIELD_PRECISION': 4, 'FORMULA': 'perimeter(@geometry) / 1000',
                'OUTPUT': f('pNNN_bacino_ap.gpkg')}, 'B2b_calcolatore_perimetro.png', 950, 820)
        dialogo('native:zonalstatisticsfb', {'INPUT': f('pNNN_bacino_ap.gpkg'), 'INPUT_RASTER': f('pNNN_dem_m.tif'),
                'RASTER_BAND': 1, 'COLUMN_PREFIX': 'dem_', 'STATISTICS': [2, 5, 6],
                'OUTPUT': f('pNNN_bacino_apq.gpkg')}, 'B3a_statistiche_dem.png')
        dialogo('native:zonalstatisticsfb', {'INPUT': f('pNNN_bacino_apq.gpkg'), 'INPUT_RASTER': f('pNNN_cn.tif'),
                'RASTER_BAND': 1, 'COLUMN_PREFIX': 'cn_', 'STATISTICS': [2],
                'OUTPUT': f('pNNN_bacino_apqc.gpkg')}, 'B3b_statistiche_cn.png')
        dialogo('grass7:r.fill.dir', {'input': f('pNNN_dem_m.tif'), 'format': 0, 'output': f('pNNN_dem_riempito.tif'),
                'direction': f('pNNN_dir_riempito.tif'), 'areas': f('pNNN_aree_problema.tif'),
                'GRASS_REGION_CELLSIZE_PARAMETER': 5}, 'B4a_r_fill_dir.png', 950, 800)
        expr = ('max(0, (A-A[-1,0])/5, (A-A[1,0])/5, (A-A[0,-1])/5, (A-A[0,1])/5, (A-A[-1,-1])/7.0711, '
                '(A-A[-1,1])/7.0711, (A-A[1,-1])/7.0711, (A-A[1,1])/7.0711)')
        dialogo('grass7:r.mapcalc.simple', {'a': f('pNNN_dem_riempito.tif'), 'expression': expr,
                'output': f('pNNN_pendenza_D8.tif'), 'GRASS_REGION_CELLSIZE_PARAMETER': 5},
                'B4b_r_mapcalc.png', 1100, 700)
        dialogo('native:zonalstatisticsfb', {'INPUT': f('pNNN_bacino_apqc.gpkg'), 'INPUT_RASTER': f('pNNN_pendenza_D8.tif'),
                'RASTER_BAND': 1, 'COLUMN_PREFIX': 'S_', 'STATISTICS': [2],
                'OUTPUT': f('pNNN_bacino_misure.gpkg')}, 'B4c_statistiche_pendenza.png')
        dialogo('native:rastersampling', {'INPUT': f('pNNN_sezione.gpkg'), 'RASTERCOPY': f('pNNN_pendenza_D8.tif'),
                'COLUMN_PREFIX': 'CS_', 'OUTPUT': f('pNNN_sezione_pendenza.gpkg')}, 'B5_campiona_cella.png', 900, 600)
        dialogo('native:rastercalc', {'LAYERS': [f('pNNN_accumulo.tif'), f('pNNN_bacino.tif')],
                'EXPRESSION': 'if ( "pNNN_accumulo@1" = 1 AND "pNNN_bacino@1" = 1, 1, 0/0 )',
                'OUTPUT': f('pNNN_sorgenti.tif')}, 'B6a_calcolatore_sorgenti.png', 950, 760)
        dialogo('native:pixelstopoints', {'INPUT_RASTER': f('pNNN_sorgenti.tif'), 'RASTER_BAND': 1, 'FIELD_NAME': 'v',
                'OUTPUT': f('pNNN_sorgenti_punti.gpkg')}, 'B6b_pixel_in_punti.png', 900, 600)
        dialogo('grass7:r.path', {'input': f('pNNN_direzioni.tif'), 'format': 2, 'start_points': f('pNNN_sorgenti_punti.gpkg'),
                'vector_path': f('pNNN_percorsi_sorgenti.gpkg'), 'GRASS_REGION_CELLSIZE_PARAMETER': 5,
                'GRASS_OUTPUT_TYPE_PARAMETER': 2}, 'B6c_r_path_sorgenti.png', 950, 900)
        dialogo('grass7:r.path', {'input': f('pNNN_direzioni.tif'), 'format': 2, 'start_points': f('pNNN_sezione.gpkg'),
                'vector_path': f('pNNN_percorso_sezione.gpkg'), 'GRASS_REGION_CELLSIZE_PARAMETER': 5,
                'GRASS_OUTPUT_TYPE_PARAMETER': 2}, 'B6d_r_path_sezione.png', 950, 900)
        dialogo('native:fieldcalculator', {'INPUT': f('pNNN_percorsi_sorgenti.gpkg'), 'FIELD_NAME': 'lung_m',
                'FIELD_TYPE': 0, 'FIELD_LENGTH': 12, 'FIELD_PRECISION': 2, 'FORMULA': 'length(@geometry)',
                'OUTPUT': f('pNNN_percorsi_lung.gpkg')}, 'B6e_lunghezza.png', 950, 820)
        dialogo('native:extractbyexpression', {'INPUT': f('pNNN_percorsi_lung.gpkg'),
                'EXPRESSION': '"lung_m" = maximum("lung_m")', 'OUTPUT': f('pNNN_percorso_piu_lungo.gpkg')},
                'B6f_estrai_massimo.png', 900, 640)
        dialogo('native:interpolatepoint', {'INPUT': f('pNNN_percorso_sezione_lung.gpkg'), 'DISTANCE': 250,
                'OUTPUT': f('pNNN_punto_valle.gpkg')}, 'B7a_interpola_valle.png', 900, 560)
        dialogo('native:interpolatepoint', {'INPUT': f('pNNN_percorso_piu_lungo.gpkg'), 'DISTANCE': 1542.32,
                'OUTPUT': f('pNNN_punto_monte.gpkg')}, 'B7b_interpola_monte.png', 900, 560)
        dialogo('native:rastersampling', {'INPUT': f('pNNN_punto_monte.gpkg'), 'RASTERCOPY': f('pNNN_dem_m.tif'),
                'COLUMN_PREFIX': 'quota_', 'OUTPUT': f('pNNN_punto_monte_quota.gpkg')}, 'B7c_campiona_quota.png', 900, 600)
        # ---- mappe
        omb = raster(f('pNNN_ombreggiatura.tif'), 'ombreggiatura')
        ret = raster(f('pNNN_reticolo_mask.tif'), 'pNNN_reticolo', 'reticolo')
        acc = raster(f('pNNN_accumulo.tif'), 'pNNN_accumulo', 'acc')
        area = vettore(f('pNNN_area_lavoro.gpkg'), 'pNNN_area_lavoro', 'codice')
        bq = vettore(f('pNNN_bacino.gpkg'), 'pNNN_bacino', 'qgis')
        ponte = vettore(f('pNNN_ponte.gpkg'), 'pNNN_ponte', 'ponte')
        sez = vettore(f('pNNN_sezione.gpkg'), 'pNNN_sezione', 'sezione')
        lun = linea(f('pNNN_percorso_piu_lungo.gpkg'), 'percorso_piu_lungo', '230,0,0', '1.0')
        psz = linea(f('pNNN_percorso_sezione_lung.gpkg'), 'percorso_sezione', '20,20,20', '0.9', 'dash')
        src = vettore(f('pNNN_sorgenti_punti.gpkg'), 'sorgenti', 'sezione')
        src.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol.createSimple(
            {'name': 'circle', 'color': '255,140,0', 'size': '0.9', 'outline_style': 'no'})))
        pm = vettore(f('pNNN_punto_monte_quota.gpkg'), 'punto_monte', 'ponte')
        pv = vettore(f('pNNN_punto_valle_quota.gpkg'), 'punto_valle', 'ponte')
        for l in (pm, pv):
            s = QgsPalLayerSettings(); s.isExpression = True
            s.fieldName = "format_number(quota_1, 2) || ' m'"
            tf = QgsTextFormat(); tf.setSize(13); b = QgsTextBufferSettings(); b.setEnabled(True); b.setSize(1); tf.setBuffer(b)
            s.setFormat(tf); l.setLabeling(QgsVectorLayerSimpleLabeling(s)); l.setLabelsEnabled(True)
        mappa([ponte, ret, omb], QgsRectangle(621700, 4468800, 623600, 4470900), 'M1_reticolo.png')
        mappa([sez, ponte, ret, acc], QgsRectangle(622600, 4469170, 622690, 4469240), 'M2_sezione_zoom.png', 1000, 780)
        mappa([ponte, bq, area, ret, omb], QgsRectangle(619400, 4466000, 625900, 4472400), 'M3_area_lavoro.png', 900, 880)
        mappa([ponte, lun, psz, src, bq, omb], QgsRectangle(621800, 4468900, 623300, 4470900), 'M4_percorsi.png', 900, 1100)
        mappa([pm, pv, ponte, lun, psz, ret, omb], QgsRectangle(622300, 4468900, 623000, 4469550), 'M5_tratto.png', 1000, 920)
    except Exception:
        LOG.write('ERRORE GENERALE\n' + traceback.format_exc())
    LOG.close()
    QgsApplication.exit(0)


QTimer.singleShot(6000, main)
