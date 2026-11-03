"""
Lancio completo con un solo comando: DEM unico v3 + codice pysheds_bridges_5m.py sui 212 ponti.

Uso (PowerShell), dopo aver estratto lo zip in una cartella nuova, es. C:\\PONTI\\consegna_finale:
    python esegui.py C:\\PONTI
dove C:\\PONTI e' la cartella che contiene il DEM unico originale dem5m_unico.tif.
Se nella cartella dello zip c'e' gia' dem5m_unico_v3.tif (DEM finale inviato a parte), l'argomento non serve.

Passi:
  1) prepara dem5m_unico.tif nella cartella dello zip:
     - se c'e' dem5m_unico_v3.tif lo usa cosi' com'e';
     - altrimenti copia il DEM unico originale e vi scrive sopra le 6 patch (patch_*.tif):
       alto Agri (Copernicus), costa di Nova Siri, Scanzano e Bernalda, tombini dei ponti 105 e 198;
       il risultato e' identico, cella per cella, a dem5m_unico_v3.tif; il DEM originale non viene modificato;
  2) lancia pysheds_bridges_5m.py (usa dem5m_unico.tif, cn5m_unico.tif e ponti.csv);
  3) controlla che le righe siano 212 e che gli ID siano 1-212.
Se si interrompe, rilanciare lo stesso comando: le porzioni gia' elaborate (cartella porzioni/) vengono saltate.
Prima di un lancio da zero cancellare la cartella porzioni/.
"""
import glob
import os
import subprocess
import sys

import pandas as pd
import rasterio
from rasterio.windows import Window, from_bounds

# si lavora sempre nella cartella dello zip
qui = os.path.dirname(os.path.abspath(__file__))
os.chdir(qui)

# ---- 1) DEM unico v3 ----
if os.path.exists('dem5m_unico.tif'):
    print("1/3 dem5m_unico.tif gia' presente nella cartella, lo uso.", flush=True)
elif os.path.exists('dem5m_unico_v3.tif'):
    print('1/3 uso dem5m_unico_v3.tif (rinominato in dem5m_unico.tif, il nome letto dal codice).', flush=True)
    os.replace('dem5m_unico_v3.tif', 'dem5m_unico.tif')
else:
    if len(sys.argv) < 2:
        sys.exit("Indicare la cartella del DEM unico originale: python esegui.py C:\\PONTI")
    dem_orig = os.path.join(sys.argv[1], 'dem5m_unico.tif')
    if not os.path.exists(dem_orig):
        sys.exit(f'Non trovo {dem_orig}')
    if os.path.abspath(sys.argv[1]) == qui:
        sys.exit("Estrarre lo zip in una cartella diversa da quella del DEM originale.")
    print('1/3 creo il DEM unico v3 = DEM originale + patch (qualche minuto)...', flush=True)
    with rasterio.open(dem_orig) as src:
        prof = src.profile
        prof.update(BIGTIFF='IF_SAFER', predictor=2, zstd_level=9)
        with rasterio.open('dem5m_unico_tmp.tif', 'w', **prof) as dst:
            # stessa scala (cm -> m) e offset del DEM originale
            dst.scales, dst.offsets = src.scales, src.offsets
            # copia del DEM originale a blocchi di 1024 righe (memoria contenuta)
            for r0 in range(0, src.height, 1024):
                w = Window(0, r0, src.width, min(1024, src.height - r0))
                dst.write(src.read(1, window=w), 1, window=w)
            # ogni patch e' un rettangolo sulla stessa griglia: sostituisce le celle in quella finestra
            for p in sorted(glob.glob('patch_*.tif')):
                with rasterio.open(p) as pt:
                    w = from_bounds(*pt.bounds, transform=src.transform).round_offsets().round_lengths()
                    dst.write(pt.read(1), 1, window=w)
                print('   patch applicata:', p, flush=True)
    os.replace('dem5m_unico_tmp.tif', 'dem5m_unico.tif')

# ---- 2) codice ----
print('2/3 lancio pysheds_bridges_5m.py (alcune ore per tutte le porzioni)...', flush=True)
subprocess.run([sys.executable, 'pysheds_bridges_5m.py'], check=True)

# ---- 3) controllo ----
r = pd.read_csv('parametri morfologici.csv')
ids = sorted(r.ID.astype(int))
print(f"3/3 righe: {len(r)}; ID 1-212 tutti presenti: {ids == list(range(1, 213))}")
print("Output: 'parametri morfologici.csv', bacini_afferenti.geojson, reticolo_idrografico.geojson")
