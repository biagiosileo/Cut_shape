"""
Test del DEM unico v3 (ponti 6, 105, 107, 108, 109, 111, 113, 155, 196, 198) con un solo comando.

Estrarre lo zip in una cartella nuova (es. C:\\PONTI\\test_v2) e lanciare:
    python esegui_test.py C:\\PONTI
dove C:\\PONTI e' la cartella che contiene il tuo dem5m_unico.tif e cn5m_unico.tif.

Lo script, nella cartella dello zip:
  1) crea dem5m_unico.tif = il tuo DEM unico + le patch (alto Agri, costa di Nova Siri, Scanzano e Bernalda, tombini del 105 e del 198); il tuo DEM non cambia;
  2) copia cn5m_unico.tif;
  3) lancia pysheds_bridges_5m.py con ponti.csv (212 ponti);
  4) stampa i risultati dei ponti 6 e 105.
Se si interrompe, rilanciare lo stesso comando: riprende da dove era arrivato.
"""
import glob
import os
import shutil
import subprocess
import sys

import pandas as pd
import rasterio
from rasterio.windows import Window, from_bounds

qui = os.path.dirname(os.path.abspath(__file__))
os.chdir(qui)
base = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(qui)
dem_orig, cn_orig = os.path.join(base, 'dem5m_unico.tif'), os.path.join(base, 'cn5m_unico.tif')
for f in (dem_orig, cn_orig):
    if not os.path.exists(f):
        sys.exit(f'Non trovo {f}: indicare la cartella che contiene dem5m_unico.tif e cn5m_unico.tif')
if os.path.abspath(base) == qui:
    sys.exit('Estrarre lo zip in una cartella diversa da quella del DEM unico originale.')

if not os.path.exists('dem5m_unico.tif'):
    print('1/3 creo il DEM unico v3 (qualche minuto)...', flush=True)
    with rasterio.open(dem_orig) as src:
        prof = src.profile
        prof.update(BIGTIFF='IF_SAFER', predictor=2, zstd_level=9)
        with rasterio.open('dem5m_unico_tmp.tif', 'w', **prof) as dst:
            dst.scales, dst.offsets = src.scales, src.offsets
            for r0 in range(0, src.height, 1024):
                w = Window(0, r0, src.width, min(1024, src.height - r0))
                dst.write(src.read(1, window=w), 1, window=w)
            for p in sorted(glob.glob('patch_*.tif')):
                with rasterio.open(p) as pt:
                    w = from_bounds(*pt.bounds, transform=src.transform).round_offsets().round_lengths()
                    dst.write(pt.read(1), 1, window=w)
    os.replace('dem5m_unico_tmp.tif', 'dem5m_unico.tif')
else:
    print('1/3 DEM unico v3 gia\' presente', flush=True)
if not os.path.exists('cn5m_unico.tif'):
    print('2/3 copio cn5m_unico.tif', flush=True)
    shutil.copy(cn_orig, 'cn5m_unico.tif')
print('3/3 lancio il codice (come il run completo: richiede lo stesso tempo)...', flush=True)
subprocess.run([sys.executable, 'pysheds_bridges_5m.py'], check=True)
r = pd.read_csv('parametri morfologici.csv')
r['ID'] = r.ID.astype(int)
print('\nRighe:', len(r))
print(r[r.ID.isin([6, 105, 107, 108, 109, 111, 113, 155, 196, 198])][['ID', 'Snap_Distance_m', 'A_km2']].to_string(index=False))
print('Attesi (km2): 6=1582,7 105=0,114 107=0,744 108=0,270 109=0,262 111=15,794 113=7,861 155=23,982 196=0,834 198=0,570')
