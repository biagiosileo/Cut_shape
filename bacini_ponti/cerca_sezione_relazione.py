"""
Cerca la sezione il cui bacino riproduce la relazione di ispezione (area, altitudine media, pendenza media).

Per ogni ponte: stessa catena del codice dell'utente (fill_pits, fill_depressions, resolve_flats, D8, accumulo)
su una finestra di RAGGIO_FIN_M attorno al ponte; candidati = celle entro RAGGIO_M dal ponte con area tra
0,6 e 1,6 volte quella della relazione (una ogni 15 m); per ciascun candidato bacino, quota media (DEM
condizionato, come il codice) e pendenza media (massima pendenza D8, come il codice); punteggio =
|dA|/A + |dAE|/AE + |dS|/S. Si riportano i migliori candidati con la distanza dal ponte.

Uso: python cerca_sezione_relazione.py <dem.tif> <ponti.csv> <relazioni.csv: ID,A,AE,S> <out.csv>
        [--raggio 1000] [--finestra 4000]
"""
import sys

import numpy as np
np.in1d = np.isin
import pandas as pd
import rasterio
from pyproj import Proj, Transformer
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
from rasterio.windows import from_bounds

DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
arg = sys.argv[1:]
RAGGIO_M = float(arg[arg.index('--raggio') + 1]) if '--raggio' in arg else 1000.0
FIN_M = float(arg[arg.index('--finestra') + 1]) if '--finestra' in arg else 4000.0
dem_path, pcsv, rcsv, out = arg[:4]
P = pd.read_csv(pcsv).set_index('id')
Rl = pd.read_csv(rcsv).set_index('ID')
tr = Transformer.from_crs(4326, 32633, always_xy=True)
tg = Transformer.from_crs(32633, 4326, always_xy=True)
crs = Proj('EPSG:32633', preserve_units=True)
OFF = [(-1, 0, 5.0), (-1, 1, 7.0711), (0, 1, 5.0), (1, 1, 7.0711), (1, 0, 5.0), (1, -1, 7.0711), (0, -1, 5.0), (-1, -1, 7.0711)]


def pendenza(z):
    s = np.zeros(z.shape, np.float32)
    H, W = z.shape
    for dr, dc, d in OFF:
        zz = np.full(z.shape, np.nan, np.float32)
        zz[max(dr, 0):H + min(dr, 0), max(dc, 0):W + min(dc, 0)] = z[max(-dr, 0):H + min(-dr, 0), max(-dc, 0):W + min(-dc, 0)]
        s = np.fmax(s, np.where(np.isfinite(zz), (z - zz) / d, 0))
    return np.maximum(s, 0)


righe = []
for i, rel in Rl.iterrows():
    x, y = tr.transform(P.X[i], P.Y[i])
    fin = max(FIN_M, 3 * np.sqrt(rel.A * 1e6))
    with rasterio.open(dem_path) as src:
        w = from_bounds(x - fin, y - fin, x + fin, y + fin, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w, boundless=True, fill_value=src.nodata)
        T = src.window_transform(w)
        z = (a.astype(np.float64) * src.scales[0]).astype(np.float32)
        z[a == src.nodata] = -9999
    vf = ViewFinder(affine=T, shape=z.shape, nodata=np.float32(-9999), crs=crs)
    grid = Grid(viewfinder=vf)
    dem = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(Raster(z, vf))), eps=1e-6, max_iter=10000)
    fdir = grid.flowdir(dem, dirmap=DIRMAP)
    acc = np.asarray(grid.accumulation(fdir, dirmap=DIRMAP))
    D = np.asarray(dem, dtype=np.float32)
    D = np.where(D <= -9000, np.nan, D)
    S = pendenza(D)
    r0, c0 = ~T * (x, y)
    k = int(RAGGIO_M / 5) + 1
    r0, c0 = int(r0), int(c0)
    ra, ca = max(r0 - k, 0), max(c0 - k, 0)
    Wn = acc[ra:r0 + k + 1, ca:c0 + k + 1] * 25 / 1e6
    ii, jj = np.where((Wn >= 0.6 * rel.A) & (Wn <= 1.6 * rel.A))
    cand = {}
    for a_, b_ in zip(ii + ra, jj + ca):
        d = np.hypot((a_ - r0) * 5, (b_ - c0) * 5)
        if d <= RAGGIO_M:
            key = (a_ // 3, b_ // 3)
            if key not in cand or acc[a_, b_] > acc[cand[key]]:
                cand[key] = (a_, b_)
    ris = []
    for a_, b_ in list(cand.values())[:400]:
        m = np.asarray(grid.catchment(x=int(b_), y=int(a_), fdir=fdir, dirmap=DIRMAP, xytype='index'))
        A = m.sum() * 25 / 1e6
        AE = float(np.nanmean(D[m]))
        Sm = float(np.nanmean(S[m]))
        sc = abs(A / rel.A - 1) + abs(AE / rel.AE - 1) + abs(Sm / (rel.S / 100) - 1)
        xc, yc = T.c + (b_ + 0.5) * 5, T.f - (a_ + 0.5) * 5
        ris.append((sc, A, AE, 100 * Sm, np.hypot(xc - x, yc - y), xc, yc))
    ris.sort()
    for sc, A, AE, Sm, d, xc, yc in ris[:5]:
        lon, lat = tg.transform(xc - 1.25, yc + 1.25)
        righe.append({'ID': i, 'A_rel': rel.A, 'AE_rel': rel.AE, 'S_rel': rel.S, 'A': round(A, 3), 'AE': round(AE, 1),
                      'S': round(Sm, 1), 'punteggio': round(sc, 3), 'dist_ponte_m': round(d), 'X': round(lon, 9),
                      'Y': round(lat, 9)})
    print(pd.DataFrame([r for r in righe if r['ID'] == i]).to_string(index=False), flush=True)
pd.DataFrame(righe).to_csv(out, index=False)
