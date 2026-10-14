"""
Ricalcolo dell'area del bacino a monte dei 212 ponti sul DEM a 30 m e
confronto con l'area del database (colonna SUPERFICIE BACINO).

Deriva da pysheds_bridges_ORIGINALE.py (che non viene modificato). Stesso
condizionamento del DEM (fill_pits, fill_depressions, resolve_flats), stessa
direzione di flusso D8 e stesso accumulo; cambiano:
  - DEM: mosaico a 30 m dei 13 ritagli, invece dei 13 DEM a 5 m separati;
  - snap: oltre alla regola originale (cella di reticolo piu' vicina, senza
    limite di distanza) si calcolano le regole "accumulo massimo entro R m";
  - controllo del troncamento: il bacino tocca il limite del DEM?
  - una riga per ognuno dei 212 ID, anche per i ponti non elaborabili.
Si calcola solo l'area (i parametri morfometrici sono un passo successivo).

Uso:
  python bacini_dem30_v2.py <dem_mosaico.tif> <ponti.csv> <cartella_out>
ponti.csv deve contenere: ID, Longitude, Latitude, A_db (km2), file (gruppo),
A_km2 (area dello script originale a 5 m). I file di ingresso sono solo letti.
"""
import os
import sys
from collections import deque

import numpy as np

# pysheds 0.5 usa np.in1d, rimosso in NumPy 2: alias equivalente.
if not hasattr(np, 'in1d'):
    np.in1d = np.isin

import pandas as pd
from pyproj import Transformer
from pysheds.grid import Grid

# ================== CONFIGURAZIONE ==================
DEM_CRS = "EPSG:32633"
BRIDGE_CSV_CRS = "EPSG:4326"
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
TOLLERANZA = 0.15

# Soglia di reticolo equivalente a quella originale: 500 celle da 5 m =
# 0,0125 km2 -> 14 celle da 30 m.
AREA_SOGLIA_KM2 = 0.0125

# Regola principale scelta a priori (non tarata sul database): cella con
# accumulo massimo entro questo raggio dal punto del ponte.
RAGGIO_PRINCIPALE_M = 60.0
# Raggi per l'analisi di sensibilita'.
RAGGI_SENSIBILITA_M = (30.0, 60.0, 90.0, 150.0, 300.0)
# Raggio per la regola "guidata" (solo diagnostica: usa l'area del database).
RAGGIO_GUIDATA_M = 300.0

# Troncamento: il bacino confina con celle nodata/fuori griglia in un punto
# piu' alto di QUOTA_MIN_TRONCAMENTO_M (cosi' la linea di costa, vicina a 0 m,
# non conta come troncamento).
QUOTA_MIN_TRONCAMENTO_M = 20.0

# Ricerca lungo il corso d'acqua (a valle e a monte sul ramo principale) del
# punto in cui l'area eguaglia quella del database.
DIST_RICERCA_ASTA_M = 5000.0

DIR_OFFSETS = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1),
               4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}
DIR_OPPOSITE = {64: 4, 4: 64, 128: 8, 8: 128, 1: 16, 16: 1, 2: 32, 32: 2}

dem_path, ponti_csv, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
for p in (dem_path, ponti_csv):
    if os.path.abspath(out_dir) == os.path.abspath(os.path.dirname(p)):
        sys.exit("La cartella dei risultati deve essere diversa da quella dei dati")
os.makedirs(out_dir, exist_ok=True)

# ---------------- DEM e idrologia ----------------
grid = Grid.from_raster(dem_path)
dem = grid.read_raster(dem_path)
cs_x, cs_y = grid.affine.a, -grid.affine.e
cell_km2 = cs_x * cs_y / 1e6
diag = float(np.hypot(cs_x, cs_y))
soglia_celle = int(np.ceil(AREA_SOGLIA_KM2 / cell_km2))
print(f"DEM {dem.shape}, cella {cs_x:.2f} m, soglia reticolo {soglia_celle} celle")

inflated = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem)))
fdir = grid.flowdir(inflated, dirmap=DIRMAP)
acc = grid.accumulation(fdir, dirmap=DIRMAP)
fdir_a = np.asarray(fdir)
acc_a = np.asarray(acc, dtype=float)
dem_a = np.asarray(dem, dtype=float)
valid = dem_a != dem.nodata
nr, nc = dem_a.shape
print("Direzioni di flusso e accumulo calcolati")


def cella(x, y):
    col, row = ~grid.affine * (x, y)
    return int(np.floor(row)), int(np.floor(col))


def centro(r, c):
    x, y = grid.affine * (c + 0.5, r + 0.5)
    return x, y


def candidati(x, y, raggio):
    """Celle di reticolo (acc >= soglia) il cui centro dista <= raggio dal
    punto: (righe, colonne, distanze)."""
    r0, c0 = cella(x, y)
    n = int(np.ceil(raggio / min(cs_x, cs_y))) + 1
    rs = np.arange(max(r0 - n, 0), min(r0 + n + 1, nr))
    cs = np.arange(max(c0 - n, 0), min(c0 + n + 1, nc))
    R, C = np.meshgrid(rs, cs, indexing='ij')
    X, Y = grid.affine * (C + 0.5, R + 0.5)
    d = np.hypot(X - x, Y - y)
    m = (d <= raggio) & (acc_a[R, C] >= soglia_celle) & valid[R, C]
    return R[m], C[m], d[m]


def vicino_senza_limite(x, y):
    """Regola dello script originale: cella di reticolo piu' vicina, senza
    limite di distanza (si allarga la ricerca finche' se ne trova una)."""
    raggio = 100.0
    while raggio < 50000:
        R, C, d = candidati(x, y, raggio)
        if len(d):
            i = int(np.argmin(d))
            return int(R[i]), int(C[i]), float(d[i])
        raggio *= 2
    return None


def max_acc(x, y, raggio):
    R, C, d = candidati(x, y, raggio)
    if not len(d):
        return None
    i = int(np.argmax(acc_a[R, C]))
    return int(R[i]), int(C[i]), float(d[i])


def guidata(x, y, raggio, a_db):
    R, C, d = candidati(x, y, raggio)
    if not len(d) or not np.isfinite(a_db):
        return None
    err = np.abs(acc_a[R, C] * cell_km2 / a_db - 1)
    i = int(np.argmin(err + d * 1e-9))
    return int(R[i]), int(C[i]), float(d[i])


def area(rc):
    return np.nan if rc is None else float(acc_a[rc[0], rc[1]] * cell_km2)


def troncamento(basin, r_out, c_out):
    """Il bacino confina con nodata o con il bordo della griglia in celle piu'
    alte di QUOTA_MIN_TRONCAMENTO_M e dell'uscita? Restituisce (flag, numero di
    celle di confine coinvolte, quota massima di queste celle)."""
    rows, cols = np.nonzero(basin)
    r0, r1 = rows.min(), rows.max() + 1
    c0, c1 = cols.min(), cols.max() + 1
    b = np.zeros((r1 - r0 + 2, c1 - c0 + 2), bool)
    b[1:-1, 1:-1] = basin[r0:r1, c0:c1]
    v = np.zeros_like(b)
    rr0, rr1, cc0, cc1 = max(r0 - 1, 0), min(r1 + 1, nr), max(c0 - 1, 0), min(c1 + 1, nc)
    v[rr0 - (r0 - 1):rr1 - (r0 - 1), cc0 - (c0 - 1):cc1 - (c0 - 1)] = valid[rr0:rr1, cc0:cc1]
    nod = ~v
    vicino = np.zeros_like(b)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            vicino |= np.roll(np.roll(nod, dr, 0), dc, 1)
    confine = b & vicino
    if not confine.any():
        return False, 0, np.nan
    z = np.full(b.shape, np.nan)
    z[1:-1, 1:-1] = np.where(basin[r0:r1, c0:c1], dem_a[r0:r1, c0:c1], np.nan)
    zc = z[confine]
    soglia = max(QUOTA_MIN_TRONCAMENTO_M, dem_a[r_out, c_out] + QUOTA_MIN_TRONCAMENTO_M)
    alte = zc > soglia
    return bool(alte.any()), int(alte.sum()), float(np.nanmax(zc))


def passo(dr, dc):
    return diag if (dr and dc) else (cs_y if dr else cs_x)


def ricerca_asta(r, c, a_db):
    """Scorre il corso d'acqua a valle (direzione D8) e a monte (ramo con
    accumulo maggiore) per DIST_RICERCA_ASTA_M; restituisce la distanza con
    segno (+ valle, - monte) e l'area del punto con area piu' vicina a a_db."""
    if not np.isfinite(a_db):
        return np.nan, np.nan
    best = (abs(area((r, c)) / a_db - 1), 0.0, area((r, c)))
    rr, cc, dist = r, c, 0.0
    while dist < DIST_RICERCA_ASTA_M:
        off = DIR_OFFSETS.get(int(fdir_a[rr, cc]))
        if off is None:
            break
        r2, c2 = rr + off[0], cc + off[1]
        if not (0 <= r2 < nr and 0 <= c2 < nc) or not valid[r2, c2]:
            break
        dist += passo(*off)
        rr, cc = r2, c2
        a = area((rr, cc))
        if abs(a / a_db - 1) < best[0]:
            best = (abs(a / a_db - 1), dist, a)
    rr, cc, dist = r, c, 0.0
    while dist < DIST_RICERCA_ASTA_M:
        nxt, bacc = None, -1
        for code, (dr, dc) in DIR_OFFSETS.items():
            r2, c2 = rr + dr, cc + dc
            if 0 <= r2 < nr and 0 <= c2 < nc and fdir_a[r2, c2] == DIR_OPPOSITE[code]:
                if acc_a[r2, c2] > bacc:
                    nxt, bacc = (r2, c2, passo(dr, dc)), acc_a[r2, c2]
        if nxt is None or bacc < soglia_celle:
            break
        rr, cc, dist = nxt[0], nxt[1], dist + nxt[2]
        a = area((rr, cc))
        if abs(a / a_db - 1) < best[0]:
            best = (abs(a / a_db - 1), -dist, a)
    return best[1], best[2]


def esito(a, a_db):
    if not (np.isfinite(a) and np.isfinite(a_db)) or a_db <= 0:
        return np.nan, None
    e = a / a_db - 1
    return e, bool(abs(e) <= TOLLERANZA)


# ---------------- Ponti ----------------
df = pd.read_csv(ponti_csv)
tr = Transformer.from_crs(BRIDGE_CSV_CRS, DEM_CRS, always_xy=True)
xmin, ymin, xmax, ymax = grid.bbox
righe = []
for _, p in df.sort_values('ID').iterrows():
    pid = int(p['ID'])
    a_db = float(p['A_db']) if pd.notna(p['A_db']) else np.nan
    x, y = tr.transform(p['Longitude'], p['Latitude'])
    o = {'ID': pid, 'Gruppo': int(p['file']), 'X_UTM33N': round(x, 1), 'Y_UTM33N': round(y, 1),
         'A_db_km2': a_db, 'A_5m_originale_km2': p.get('A_km2', np.nan),
         'Snap_5m_originale_m': p.get('Snap_Distance_m', np.nan)}
    if not (xmin <= x <= xmax and ymin <= y <= ymax):
        o['Stato'] = 'fuori dal DEM'
        righe.append(o)
        print(f"Ponte {pid}: fuori dal DEM")
        continue

    rc_or = vicino_senza_limite(x, y)
    o['A30_vicino_km2'] = area(rc_or)
    o['Snap30_vicino_m'] = rc_or[2] if rc_or else np.nan
    for R in RAGGI_SENSIBILITA_M:
        rc = max_acc(x, y, R)
        o[f'A30_maxacc_{int(R)}m_km2'] = area(rc)
        o[f'Snap30_maxacc_{int(R)}m_m'] = rc[2] if rc else np.nan
    rc_g = guidata(x, y, RAGGIO_GUIDATA_M, a_db)
    o['A30_guidata_300m_km2'] = area(rc_g)
    o['Snap30_guidata_300m_m'] = rc_g[2] if rc_g else np.nan

    rc = max_acc(x, y, RAGGIO_PRINCIPALE_M)
    regola = f'maxacc_{int(RAGGIO_PRINCIPALE_M)}m'
    if rc is None:
        rc, regola = rc_or, 'vicino (nessuna cella di reticolo entro il raggio)'
    if rc is None:
        o['Stato'] = 'snap non riuscito'
        righe.append(o)
        continue
    o['Regola_principale'] = regola
    o['A30_km2'] = area(rc)
    o['Snap30_m'] = rc[2]
    basin = np.asarray(grid.catchment(x=rc[1], y=rc[0], fdir=fdir, dirmap=DIRMAP,
                                      xytype='index'), dtype=bool)
    o['A30_catchment_km2'] = basin.sum() * cell_km2  # controllo: deve = A30_km2
    flag, n_conf, z_conf = troncamento(basin, rc[0], rc[1])
    o['Bacino_troncato'] = flag
    o['Celle_confine_nodata'] = n_conf
    o['Quota_max_confine_nodata_m'] = z_conf
    o['Quota_sezione_m'] = dem_a[rc[0], rc[1]]
    d_asta, a_asta = ricerca_asta(rc[0], rc[1], a_db)
    o['Asta_dist_area_DB_m'] = d_asta
    o['Asta_area_piu_vicina_km2'] = a_asta
    o['Stato'] = 'elaborato'
    for col, a in (('Err_5m_originale', o['A_5m_originale_km2']), ('Err30_vicino', o['A30_vicino_km2']),
                   ('Err30', o['A30_km2']), ('Err30_guidata', o['A30_guidata_300m_km2'])):
        e, ok = esito(a, a_db)
        o[col] = e
        o[col.replace('Err', 'OK')] = ok
    righe.append(o)
    print(f"Ponte {pid}: A_db={a_db} A30={o['A30_km2']:.3f} km2 troncato={flag}")

pd.DataFrame(righe).to_csv(os.path.join(out_dir, 'aree_dem30_v2.csv'), index=False)
print("Salvato", os.path.join(out_dir, 'aree_dem30_v2.csv'))
