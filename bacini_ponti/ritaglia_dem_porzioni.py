"""
Ritaglia dal DEM unico le porzioni dei ponti indicati, per poterle caricare una alla volta (limite 30 MB per file).
Ogni porzione e' ritagliata esattamente come la legge il codice pysheds_bridges_5m.py (stessa finestra di celle,
stessi valori in centimetri, stessa scala 0.01), con compressione ZSTD: i risultati del codice sulle porzioni
sono identici a quelli ottenuti sul DEM intero.

Uso (PowerShell, nell'ambiente Python con rasterio usato per esegui.py):
    python ritaglia_dem_porzioni.py <dem5m_unico_v4.tif> <ponti.csv> <cartella_uscita> [ID ID ...]
Senza ID ritaglia le porzioni dei ponti multi-asta e dei canali di bonifica:
    13 19 72 107 108 109 111 117 118 154 164 196
Stampa nome, dimensione e impronta MD5 di ogni file: se un file supera i 30 MB lo segnala.
"""
import hashlib
import os
import sys

import pandas as pd
import rasterio
from rasterio.windows import from_bounds

dem_path, csv_path, out = sys.argv[1:4]
ids = [int(i) for i in sys.argv[4:]] or [13, 19, 72, 107, 108, 109, 111, 117, 118, 154, 164, 196]
os.makedirs(out, exist_ok=True)
P = pd.read_csv(csv_path)
P['id'] = P['id'].astype(int)
P = P[P['id'].isin(ids)]
porzioni = P.groupby('porzione').first()
print(f'{len(porzioni)} porzioni per i ponti {sorted(P["id"])}')
with rasterio.open(dem_path) as src:
    for nome, r in porzioni.iterrows():
        # stessa finestra del codice: from_bounds(xmin, ymin, xmax, ymax) arrotondata alle celle
        w = from_bounds(r.xmin, r.ymin, r.xmax, r.ymax, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w)
        prof = src.profile.copy()
        prof.update(width=a.shape[1], height=a.shape[0], transform=src.window_transform(w), compress='zstd',
                    zstd_level=22, predictor=2, tiled=True, blockxsize=256, blockysize=256, BIGTIFF='NO')
        f = os.path.join(out, f'dem_{nome}.tif')
        with rasterio.open(f, 'w', **prof) as dst:
            dst.scales, dst.offsets = src.scales, src.offsets
            dst.write(a, 1)
        mb = os.path.getsize(f) / 1024 ** 2
        md5 = hashlib.md5(open(f, 'rb').read()).hexdigest()
        ponti = sorted(P.loc[P.porzione == nome, 'id'])
        print(f'{os.path.basename(f):24s} {mb:6.1f} MB  md5 {md5}  ponti {ponti}' + ('  SUPERA 30 MB' if mb > 30 else ''))
print('fatto: caricare i file dem_porzione_*.tif uno alla volta')
