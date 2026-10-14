"""
Confronto tra metodi di estrazione del bacino sullo stesso DEM a 30 m, con
WhiteboxTools (pacchetto whitebox-workflows), per capire quanto l'area dipende
dall'algoritmo e non solo dal DEM.

Metodi (ognuno con il proprio accumulo e la stessa regola di aggancio: cella
piu' vicina con area >= SOGLIA_KM2):
  WBT_fill_D8    riempimento delle depressioni (Wang e Liu) + D8
  WBT_breach_D8  apertura delle depressioni a costo minimo (Lindsay 2016),
                 che "taglia" rilevati e argini invece di allagare a monte, + D8
  WBT_breach_Dinf apertura delle depressioni + D-infinito (Tarboton 1997),
                 il flusso si divide tra due celle
Il metodo dello script (pysheds: fill_pits, fill_depressions, resolve_flats,
D8) e' gia' in aree_dem30_soglia_0.25.csv.

Uso: python metodi_alternativi_wbt.py <dem.tif> <aree_dem30_soglia_0.25.csv> <cartella_out>
"""
import os
import sys

import numpy as np
import pandas as pd
import rasterio
import whitebox_workflows as wb

SOGLIA_KM2 = 0.25
# Distanza massima di apertura (celle) per il breaching; le depressioni non
# risolte entro questa distanza vengono riempite.
BREACH_MAX_DIST = 100
# Raggio di ricerca del punto con area compatibile (solo diagnostica).
RAGGIO_RICERCA_M = 5000.0

dem_path, aree_csv, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(out_dir, exist_ok=True)
wbe = wb.WbEnvironment()
wbe.verbose = False
dem = wbe.read_raster(dem_path)

with rasterio.open(dem_path) as src:
    T = src.transform
    valid = src.read(1) != src.nodata
cell_km2 = abs(T.a * T.e) / 1e6


def accumulo(r):
    """Raster whitebox -> array numpy di celle contribuenti."""
    p = os.path.join(out_dir, '_tmp_acc.tif')
    wbe.write_raster(r, p)
    with rasterio.open(p) as s:
        a = s.read(1).astype(float)
    os.remove(p)
    a[~valid] = np.nan
    return a


print("WBT_fill_D8 ...", flush=True)
filled = wbe.hydrology.fill_depressions(dem=dem)
acc = {'WBT_fill_D8': accumulo(wbe.hydrology.d8_flow_accum(input=filled, out_type='cells'))}
print("WBT_breach_D8 ...", flush=True)
breached = wbe.hydrology.breach_depressions_least_cost(dem=dem, max_dist=BREACH_MAX_DIST, fill_deps=True)
acc['WBT_breach_D8'] = accumulo(wbe.hydrology.d8_flow_accum(input=breached, out_type='cells'))
print("WBT_breach_Dinf ...", flush=True)
acc['WBT_breach_Dinf'] = accumulo(wbe.hydrology.dinf_flow_accum(input=breached, out_type='cells'))

d = pd.read_csv(aree_csv).sort_values('ID')
soglia = SOGLIA_KM2 / cell_km2
inv = ~T
for nome, a in acc.items():
    aree, dist = [], []
    for x, y in zip(d.X_UTM33N, d.Y_UTM33N):
        c0, r0 = inv * (x, y)
        r0, c0 = int(r0), int(c0)
        n = 4
        while True:
            rr, cc = np.mgrid[max(r0 - n, 0):r0 + n + 1, max(c0 - n, 0):c0 + n + 1]
            rr = np.clip(rr, 0, a.shape[0] - 1)
            cc = np.clip(cc, 0, a.shape[1] - 1)
            X, Y = T * (cc + 0.5, rr + 0.5)
            dd = np.hypot(X - x, Y - y)
            m = np.nan_to_num(a[rr, cc]) >= soglia
            if m.any() or n > 2000:
                break
            n *= 2
        i = np.argmin(np.where(m, dd, np.inf))
        aree.append(a[rr.flat[i], cc.flat[i]] * cell_km2 if m.any() else np.nan)
        dist.append(dd.flat[i] if m.any() else np.nan)
    d[f'A_{nome}_km2'] = aree
    d[f'Snap_{nome}_m'] = dist
    # Diagnostica: distanza minima dal ponte di una cella la cui area e'
    # compatibile (±15%) con quella del database, entro RAGGIO_RICERCA_M.
    # Non e' una correzione: misura di quanto andrebbe spostato il punto.
    nr_ = int(RAGGIO_RICERCA_M / abs(T.a)) + 1
    dmin = []
    for x, y, adb in zip(d.X_UTM33N, d.Y_UTM33N, d.A_db_km2):
        if not np.isfinite(adb) or adb <= 0:
            dmin.append(np.nan)
            continue
        c0, r0 = inv * (x, y)
        r0, c0 = int(r0), int(c0)
        r_a, r_b = max(r0 - nr_, 0), min(r0 + nr_ + 1, a.shape[0])
        c_a, c_b = max(c0 - nr_, 0), min(c0 + nr_ + 1, a.shape[1])
        w = a[r_a:r_b, c_a:c_b] * cell_km2
        rr, cc = np.mgrid[r_a:r_b, c_a:c_b]
        X, Y = T * (cc + 0.5, rr + 0.5)
        dd = np.hypot(X - x, Y - y)
        m = (np.abs(np.nan_to_num(w) / adb - 1) <= 0.15) & (dd <= RAGGIO_RICERCA_M)
        dmin.append(float(dd[m].min()) if m.any() else np.nan)
    d[f'Dist_min_compatibile_{nome}_m'] = dmin

out = os.path.join(out_dir, 'aree_metodi_alternativi.csv')
d[['ID', 'A_db_km2', 'A30_km2'] + [c for c in d.columns if c.startswith(('A_WBT', 'Snap_WBT', 'Dist_min'))]] \
    .rename(columns={'A30_km2': 'A_pysheds_fill_D8_km2'}).to_csv(out, index=False)
print("Salvato", out)
