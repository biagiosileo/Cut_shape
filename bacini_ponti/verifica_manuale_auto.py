"""
Verifica di un ponte eseguita con la procedura del manuale (passi A0-B7) in automatico, con gli stessi algoritmi di
QGIS/GRASS del manuale, via PyQGIS. Tutti i file hanno il prefisso pNNN_ come nel manuale; ogni algoritmo lanciato
e' registrato con i suoi parametri in pNNN_cronologia.txt.

Uso (Python di QGIS):
  QT_QPA_PLATFORM=offscreen /usr/bin/python3.12 -I verifica_manuale_auto.py <ID> <ponti.csv> <dem5m_unico_v4.tif>
      <cn5m_unico.tif> <buffer_m> <out_dir>
"""
import csv
import datetime
import json
import os
import sys

sys.path.append('/usr/share/qgis/python/plugins')
import numpy as np
from osgeo import gdal
from pyproj import Transformer
from qgis.core import QgsApplication, QgsVectorLayer

app = QgsApplication([], False)
app.initQgis()
from processing.core.Processing import Processing  # noqa: E402
Processing.initialize()
import processing  # noqa: E402

ID, ponti, dem, cn, buf, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5]), sys.argv[6]
os.makedirs(out, exist_ok=True)
p = lambda nome: os.path.join(out, f'p{ID}_{nome}')
crono = open(p('cronologia.txt'), 'w', encoding='utf-8')
crono.write(f'Verifica ponte {ID} - procedura del manuale eseguita con script PyQGIS/GRASS\n'
            f'avvio {datetime.datetime.now():%Y-%m-%d %H:%M:%S}\n\n')


def run(passo, alg, par):
    crono.write(f'[{datetime.datetime.now():%H:%M:%S}] {passo} {alg}\n{json.dumps(par, indent=1, default=str)}\n\n')
    crono.flush()
    return processing.run(alg, par)


def testo(f):
    return QgsVectorLayer(f'file://{f}?delimiter=,&xField=X&yField=Y&crs=EPSG:32633', os.path.basename(f), 'delimitedtext')


def vlayer(f):
    return QgsVectorLayer(f, os.path.basename(f), 'ogr')


def valore(f, campo):
    return [ft[campo] for ft in vlayer(f).getFeatures()]


misure = {}
MAX_SORGENTI = 200

# A0 - ponte (stesso punto del database / codice)
with open(ponti) as fp:
    r = {row['id']: row for row in csv.DictReader(fp)}[ID]
soglia = int(r['soglia']) if r['soglia'] else 4000
x, y = Transformer.from_crs(4326, 32633, always_xy=True).transform(float(r['X']), float(r['Y']))
with open(p('ponte.csv'), 'w') as f:
    f.write(f'ID,X,Y\n{ID},{x:.3f},{y:.3f}\n')
run('A0', 'native:createpointslayerfromtable', {'INPUT': testo(p('ponte.csv')), 'XFIELD': 'X', 'YFIELD': 'Y',
    'TARGET_CRS': 'EPSG:32633', 'OUTPUT': p('ponte.gpkg')})
crono.write(f'soglia reticolo: {soglia} celle\n\n')

# A1 - area di lavoro e ritagli
run('A1', 'native:buffer', {'INPUT': p('ponte.gpkg'), 'DISTANCE': buf, 'SEGMENTS': 5, 'DISSOLVE': False,
    'OUTPUT': p('area_lavoro.gpkg')})
e = vlayer(p('area_lavoro.gpkg')).extent()
win = f'{e.xMinimum()},{e.xMaximum()},{e.yMinimum()},{e.yMaximum()} [EPSG:32633]'
run('A1', 'gdal:cliprasterbyextent', {'INPUT': dem, 'PROJWIN': win, 'OUTPUT': p('dem_ritaglio.tif')})
run('A1', 'gdal:cliprasterbyextent', {'INPUT': cn, 'PROJWIN': win, 'OUTPUT': p('cn.tif')})
# A2 - quote in metri
run('A2', 'gdal:translate', {'INPUT': p('dem_ritaglio.tif'), 'EXTRA': '-unscale -ot Float32', 'OUTPUT': p('dem_m.tif')})
# A3 - r.watershed
run('A3', 'grass7:r.watershed', {'elevation': p('dem_m.tif'), 'threshold': soglia, '-s': True, '-a': True,
    'GRASS_REGION_CELLSIZE_PARAMETER': 5, 'accumulation': p('accumulo.tif'), 'drainage': p('direzioni.tif'),
    'stream': p('reticolo.tif')})

# A4 - sezione: cella del reticolo piu' vicina al ponte (centro della cella)
ds = gdal.Open(p('reticolo.tif'))
gt = ds.GetGeoTransform()
st = ds.ReadAsArray()
nd = ds.GetRasterBand(1).GetNoDataValue()
rr, cc = np.nonzero((st != nd) & (st > 0) if nd is not None else st > 0)
cx, cy = gt[0] + (cc + 0.5) * gt[1], gt[3] + (rr + 0.5) * gt[5]
k = np.argmin(np.hypot(cx - x, cy - y))
xs, ys = float(cx[k]), float(cy[k])
acc = gdal.Open(p('accumulo.tif')).ReadAsArray()[rr[k], cc[k]]
with open(p('sezione.csv'), 'w') as f:
    f.write(f'id,X,Y\n{ID},{xs:.2f},{ys:.2f}\n')
run('A4', 'native:createpointslayerfromtable', {'INPUT': testo(p('sezione.csv')), 'XFIELD': 'X',
    'YFIELD': 'Y', 'TARGET_CRS': 'EPSG:32633', 'OUTPUT': p('sezione.gpkg')})
crono.write(f'A4 sezione: cella del reticolo piu\' vicina al ponte, centro {xs:.2f}, {ys:.2f}; accumulo {acc}\n\n')
misure.update(XS=xs, YS=ys, accumulo_sezione=float(acc))

# A5 - bacino
run('A5', 'grass7:r.water.outlet', {'input': p('direzioni.tif'), 'coordinates': f'{xs},{ys} [EPSG:32633]',
    'GRASS_REGION_CELLSIZE_PARAMETER': 5, 'output': p('bacino.tif')})
run('A5', 'gdal:polygonize', {'INPUT': p('bacino.tif'), 'BAND': 1, 'FIELD': 'DN', 'OUTPUT': p('bacino_tutti.gpkg')})
run('A5', 'native:extractbyexpression', {'INPUT': p('bacino_tutti.gpkg'), 'EXPRESSION': '"DN" = 1',
    'OUTPUT': p('bacino_poligono.gpkg')})

# A6 - controllo del bordo
b = vlayer(p('bacino_poligono.gpkg')).extent()
d = ds.RasterXSize * gt[1]
ritaglio = (gt[0], gt[3] + ds.RasterYSize * gt[5], gt[0] + d, gt[3])
margine = min(b.xMinimum() - ritaglio[0], b.yMinimum() - ritaglio[1], ritaglio[2] - b.xMaximum(), ritaglio[3] - b.yMaximum())
misure['margine_bordo_m'] = round(margine, 1)
misure['tocca_bordo'] = 'si' if margine < 5 else 'no'
crono.write(f'A6 margine minimo bacino - bordo del ritaglio: {margine:.1f} m; tocca il bordo: {misure["tocca_bordo"]}\n\n')

# B1 - coordinate
run('B1', 'native:addxyfields', {'INPUT': p('ponte.gpkg'), 'CRS': 'EPSG:32633', 'PREFIX': 'utm_', 'OUTPUT': p('ponte_xy.gpkg')})
run('B1', 'native:addxyfields', {'INPUT': p('ponte_xy.gpkg'), 'CRS': 'EPSG:4326', 'PREFIX': 'wgs_',
    'OUTPUT': p('ponte_coordinate.gpkg')})
f = next(vlayer(p('ponte_coordinate.gpkg')).getFeatures())
misure.update(X=f['utm_x'], Y=f['utm_y'], LON=f['wgs_x'], LAT=f['wgs_y'])

# B2 - area e perimetro (sul piano)
run('B2', 'native:fieldcalculator', {'INPUT': p('bacino_poligono.gpkg'), 'FIELD_NAME': 'area_km2', 'FIELD_TYPE': 0,
    'FIELD_LENGTH': 12, 'FIELD_PRECISION': 4, 'FORMULA': 'area(@geometry) / 1000000', 'OUTPUT': p('bacino_PA0.gpkg')})
run('B2', 'native:fieldcalculator', {'INPUT': p('bacino_PA0.gpkg'), 'FIELD_NAME': 'perim_km', 'FIELD_TYPE': 0,
    'FIELD_LENGTH': 12, 'FIELD_PRECISION': 4, 'FORMULA': 'perimeter(@geometry) / 1000', 'OUTPUT': p('bacino_PA.gpkg')})
# B3 - quote e CN (statistiche zonali: 2 media, 5 minimo, 6 massimo)
run('B3', 'native:zonalstatisticsfb', {'INPUT': p('bacino_PA.gpkg'), 'INPUT_RASTER': p('dem_m.tif'), 'COLUMN_PREFIX': 'dem_',
    'STATISTICS': [2, 5, 6], 'OUTPUT': p('bacino_PAQ.gpkg')})
run('B3', 'native:zonalstatisticsfb', {'INPUT': p('bacino_PAQ.gpkg'), 'INPUT_RASTER': p('cn.tif'), 'COLUMN_PREFIX': 'cn_',
    'STATISTICS': [2], 'OUTPUT': p('bacino_PAQC.gpkg')})
# B4 - pendenza D8 sul DEM riempito
run('B4', 'grass7:r.fill.dir', {'input': p('dem_m.tif'), 'format': 0, 'output': p('dem_riempito.tif'),
    'direction': p('dir_fill.tif'), 'areas': p('area_problema.tif'), 'GRASS_REGION_CELLSIZE_PARAMETER': 5})
espr = ('max(0, (A-A[-1,0])/5, (A-A[1,0])/5, (A-A[0,-1])/5, (A-A[0,1])/5, (A-A[-1,-1])/7.0711, '
        '(A-A[-1,1])/7.0711, (A-A[1,-1])/7.0711, (A-A[1,1])/7.0711)')
run('B4', 'grass7:r.mapcalc.simple', {'a': p('dem_riempito.tif'), 'expression': espr,
    'GRASS_REGION_CELLSIZE_PARAMETER': 5, 'output': p('pendenza_D8.tif')})
run('B4', 'native:zonalstatisticsfb', {'INPUT': p('bacino_PAQC.gpkg'), 'INPUT_RASTER': p('pendenza_D8.tif'),
    'COLUMN_PREFIX': 'S_', 'STATISTICS': [2], 'OUTPUT': p('bacino.gpkg')})
f = next(vlayer(p('bacino.gpkg')).getFeatures())
misure.update(A=f['area_km2'], P=f['perim_km'], AE=f['dem_mean'], ZMIN=f['dem_min'], ZMAX=f['dem_max'],
              CN=f['cn_mean'], S=f['S_mean'])
# B5 - pendenza della cella di chiusura
run('B5', 'native:rastersampling', {'INPUT': p('sezione.gpkg'), 'RASTERCOPY': p('pendenza_D8.tif'), 'COLUMN_PREFIX': 'CS_',
    'OUTPUT': p('sezione_pendenza.gpkg')})
misure['CS'] = valore(p('sezione_pendenza.gpkg'), 'CS_1')[0]

# B6 - percorso di flusso piu' lungo
run('B6', 'gdal:rastercalculator', {'INPUT_A': p('accumulo.tif'), 'BAND_A': 1, 'INPUT_B': p('bacino.tif'), 'BAND_B': 1,
    'FORMULA': 'where((A == 1) & (B == 1), 1, 0)', 'NO_DATA': 0, 'RTYPE': 0, 'OUTPUT': p('sorgenti.tif')})
run('B6', 'native:pixelstopoints', {'INPUT_RASTER': p('sorgenti.tif'), 'RASTER_BAND': 1, 'FIELD_NAME': 'VALUE',
    'OUTPUT': p('sorgenti_punti.gpkg')})
misure['n_sorgenti'] = vlayer(p('sorgenti_punti.gpkg')).featureCount()
partenze = p('sorgenti_punti.gpkg')
if misure['n_sorgenti'] > MAX_SORGENTI:
    # troppe sorgenti: i percorsi di r.path proseguono fino al bordo del ritaglio e il file diventa di decine di GB.
    # Sulle direzioni di r.watershed si calcola la distanza di flusso di ogni sorgente fino alla sezione e si lancia
    # r.path solo dalle MAX_SORGENTI piu' lontane: il percorso piu' lungo e' per forza tra queste.
    dr = gdal.Open(p('direzioni.tif')).ReadAsArray()
    bac = gdal.Open(p('bacino.tif')).ReadAsArray() == 1
    so = gdal.Open(p('sorgenti.tif')).ReadAsArray() == 1
    passo = {1: (-1, 1), 2: (-1, 0), 3: (-1, -1), 4: (0, -1), 5: (1, -1), 6: (1, 0), 7: (1, 1), 8: (0, 1)}
    dist = np.full(dr.shape, -1.0)
    i0, j0 = int((ys - gt[3]) / gt[5]), int((xs - gt[0]) / gt[1])
    dist[i0, j0] = 0.0
    for i, j in zip(*np.nonzero(bac)):
        cam = []
        while dist[i, j] < 0 and bac[i, j] and dr[i, j] in passo:
            cam.append((i, j))
            di, dj = passo[int(dr[i, j])]
            i, j = i + di, j + dj
        d0 = dist[i, j] if dist[i, j] >= 0 else np.nan
        for (a, b2) in reversed(cam):
            di, dj = passo[int(dr[a, b2])]
            d0 = d0 + (7.0711 if di and dj else 5.0)
            dist[a, b2] = d0
    ii, jj = np.nonzero(so)
    ordine = np.argsort(-dist[ii, jj])[:MAX_SORGENTI]
    with open(p('sorgenti_candidate.csv'), 'w') as f:
        f.write('id,X,Y,dist_sezione_m\n')
        for n, k2 in enumerate(ordine, 1):
            f.write(f'{n},{gt[0] + (jj[k2] + 0.5) * gt[1]:.2f},{gt[3] + (ii[k2] + 0.5) * gt[5]:.2f},{dist[ii[k2], jj[k2]]:.2f}\n')
    run('B6', 'native:createpointslayerfromtable', {'INPUT': testo(p('sorgenti_candidate.csv')), 'XFIELD': 'X',
        'YFIELD': 'Y', 'TARGET_CRS': 'EPSG:32633', 'OUTPUT': p('sorgenti_candidate.gpkg')})
    partenze = p('sorgenti_candidate.gpkg')
    crono.write(f'B6 sorgenti {misure["n_sorgenti"]} > {MAX_SORGENTI}: r.path lanciato dalle {MAX_SORGENTI} sorgenti con '
                f'distanza di flusso dalla sezione maggiore (max {dist[ii, jj].max():.2f} m), calcolata sulle '
                f'direzioni di r.watershed\n\n')
run('B6', 'grass7:r.path', {'input': p('direzioni.tif'), 'format': 2, 'start_points': partenze,
    'vector_path': p('percorsi_sorgenti.gpkg'), 'raster_path': 'TEMPORARY_OUTPUT', 'GRASS_REGION_CELLSIZE_PARAMETER': 5})
run('B6', 'grass7:r.path', {'input': p('direzioni.tif'), 'format': 2, 'start_points': p('sezione.gpkg'),
    'vector_path': p('percorso_sezione.gpkg'), 'raster_path': 'TEMPORARY_OUTPUT', 'GRASS_REGION_CELLSIZE_PARAMETER': 5})
for a, b in (('percorsi_sorgenti', 'percorsi_lung'), ('percorso_sezione', 'percorso_sezione_lung')):
    run('B6', 'native:fieldcalculator', {'INPUT': p(a + '.gpkg'), 'FIELD_NAME': 'lung_m', 'FIELD_TYPE': 0,
        'FIELD_LENGTH': 12, 'FIELD_PRECISION': 2, 'FORMULA': 'length(@geometry)', 'OUTPUT': p(b + '.gpkg')})
run('B6', 'native:extractbyexpression', {'INPUT': p('percorsi_lung.gpkg'), 'EXPRESSION': '"lung_m" = maximum("lung_m")',
    'OUTPUT': p('percorso_piu_lungo.gpkg')})
misure['LMAX'] = valore(p('percorso_piu_lungo.gpkg'), 'lung_m')[0]
misure['LSEZ'] = max(valore(p('percorso_sezione_lung.gpkg'), 'lung_m'))

# B7 - tratto centrato sulla sezione
run('B7', 'native:interpolatepoint', {'INPUT': p('percorso_sezione_lung.gpkg'), 'DISTANCE': 250,
    'OUTPUT': p('punto_valle.gpkg')})
run('B7', 'native:interpolatepoint', {'INPUT': p('percorso_piu_lungo.gpkg'),
    'DISTANCE': misure['LMAX'] - misure['LSEZ'] - 250, 'OUTPUT': p('punto_monte.gpkg')})
for a in ('punto_valle', 'punto_monte'):
    run('B7', 'native:rastersampling', {'INPUT': p(a + '.gpkg'), 'RASTERCOPY': p('dem_m.tif'), 'COLUMN_PREFIX': 'quota_',
        'OUTPUT': p(a + '_quota.gpkg')})
misure.update(ZUP=valore(p('punto_monte_quota.gpkg'), 'quota_1')[0], ZDN=valore(p('punto_valle_quota.gpkg'), 'quota_1')[0],
              DUP=250, DDN=250, FB='no')
# controllo del canale principale: accumulo lungo gli ultimi 250 m prima della sezione
pm = next(vlayer(p('punto_monte.gpkg')).getFeatures()).geometry().asPoint()
c, rw = int((pm.x() - gt[0]) / gt[1]), int((pm.y() - gt[3]) / gt[5])
misure['accumulo_punto_monte'] = float(gdal.Open(p('accumulo.tif')).ReadAsArray()[rw, c])

for t in ('bacino_PA0',):
    os.remove(p(t + '.gpkg'))
json.dump(misure, open(p('misure.json'), 'w'), indent=1, default=float)
crono.write('MISURE\n' + json.dumps(misure, indent=1, default=float) + f'\nfine {datetime.datetime.now():%H:%M:%S}\n')
crono.close()
print(json.dumps(misure, indent=1, default=float))
