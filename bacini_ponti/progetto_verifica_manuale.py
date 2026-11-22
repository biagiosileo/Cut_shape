"""
Progetto QGIS della verifica di un ponte: tutti i layer pNNN_ della cartella (vettori sopra, raster sotto), con
percorsi relativi. Uso (Python di QGIS): python progetto_verifica_manuale.py <cartella> <ID>
"""
import glob
import os
import sys

sys.path.append('/usr/share/qgis/python/plugins')
from qgis.core import (QgsApplication, QgsCoordinateReferenceSystem, QgsProject, QgsRasterLayer, QgsVectorLayer)

app = QgsApplication([], False)
app.initQgis()
cart, ID = sys.argv[1], sys.argv[2]
pr = QgsProject.instance()
pr.setCrs(QgsCoordinateReferenceSystem('EPSG:32633'))
pr.setEllipsoid('NONE')
radice = pr.layerTreeRoot()
gv, gr = radice.addGroup('Vettori'), radice.addGroup('Raster')
ordine_v = ['ponte_coordinate', 'sezione_pendenza', 'punto_monte_quota', 'punto_valle_quota', 'percorso_piu_lungo',
            'percorso_sezione_lung', 'bacino', 'bacino_codice', 'area_lavoro']
vett = sorted(glob.glob(os.path.join(cart, f'p{ID}_*.gpkg')),
              key=lambda f: (ordine_v.index(os.path.basename(f)[len(f'p{ID}_'):-5])
                             if os.path.basename(f)[len(f'p{ID}_'):-5] in ordine_v else 99, f))
for f in vett:
    nome = os.path.basename(f)[:-5]
    if nome.endswith('bacino_codice'):
        for lay in ('p15_bacino_codice', 'porzione_55'):
            l = QgsVectorLayer(f'{f}|layername={lay}', f'{nome} ({lay})' if lay.startswith('porz') else nome, 'ogr')
            pr.addMapLayer(l, False); gv.addLayer(l).setItemVisibilityChecked(False)
        continue
    l = QgsVectorLayer(f, nome, 'ogr')
    pr.addMapLayer(l, False)
    nodo = gv.addLayer(l)
    nodo.setItemVisibilityChecked(nome.split(f'p{ID}_')[1] in ordine_v[:7])
for f in sorted(glob.glob(os.path.join(cart, f'p{ID}_*.tif'))):
    nome = os.path.basename(f)[:-4]
    l = QgsRasterLayer(f, nome)
    pr.addMapLayer(l, False)
    gr.addLayer(l).setItemVisibilityChecked(nome.endswith('dem_m'))
pr.writeEntry('Paths', '/Absolute', False)
out = os.path.join(cart, f'Verifica_Manuale_ID{ID}.qgz')
print(pr.write(out), out, len(pr.mapLayers()))
