"""
Passo 3 dell'analisi a 5 m: bacino finale di ogni ponte e parametri
morfometrici, con la regola di aggancio scelta.

Per ogni finestra (dem5_finestre.py) si legge il puntatore D8 (codici Whitebox)
e il DEM ibrido; per ogni ponte si chiude il bacino nella cella scelta
(aggancio_5m.py) e si calcolano:
  A        area (km2) e quota di area da DEM 5 m / 30 m ricampionato
  P        perimetro del poligono del bacino (buchi riempiti, semplificato a
           mezza cella per togliere la scalettatura dei bordi delle celle)
  L        percorso di flusso piu' lungo fino alla sezione (km)
  Lb       lunghezza del bacino: distanza in linea retta dalla sezione al
           punto del confine piu' lontano (km)
  R        rilievo = quota max - quota min nel bacino (m); AE quota media
  S        pendenza media di bacino (massima pendenza discendente D8)
  CN       Curve Number medio sulle sole celle con CN valido (0 = nodata);
           quota di area coperta dal CN
  pendenza di tratto su 500 m centrati sulla sezione (250 m a monte lungo il
  ramo con area maggiore, 250 m a valle)
  derivati: FF=A/L2, Re=2*sqrt(A/pi)/L, Rf_b=A/Lb2, Shape=L/sqrt(A),
  Kc=P/(2*sqrt(pi*A)), Rc=4*pi*A/P2, Melton=(R/1000)/sqrt(A), HI, Rr=(R/1000)/Lb,
  Rrel=R/(P*1000)

Uso: python bacini_5m_finali.py <cartella_run> <aggancio.csv> <colonna_area> <soglia_km2>
                                <cartella_cn5> <out_dir>
"""
import glob
import json
import os
import sys

import numpy as np
np.in1d = np.isin
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.features import shapes
from rasterio.merge import merge
from shapely.geometry import shape, Polygon, MultiPolygon, Point
from pysheds.grid import Grid

DIRMAP_WBT = (128, 1, 2, 4, 8, 16, 32, 64)   # N, NE, E, SE, S, SW, W, NW
OFF = {1: (-1, 1), 2: (0, 1), 4: (1, 1), 8: (1, 0), 16: (1, -1), 32: (0, -1), 64: (-1, -1), 128: (-1, 0)}
OPP = {1: 16, 16: 1, 2: 32, 32: 2, 4: 64, 64: 4, 8: 128, 128: 8}
TRATTO_M = 500.0
C5 = 5.0

run, agg_csv, col, soglia, cn_dir, out = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5], sys.argv[6]
os.makedirs(out, exist_ok=True)
meta = json.load(open(os.path.join(run, 'finestre.json')))
agg = pd.read_csv(agg_csv)
agg = agg[np.isclose(agg.Soglia_km2, soglia)].set_index('ID')
cella_col = col.replace('A_', 'Cella_')
cn_files = sorted(glob.glob(os.path.join(cn_dir, '**', '*.tif'), recursive=True))
cn_idx = [(f, rasterio.open(f).bounds) for f in cn_files]


def passo(dr, dc):
    return float(np.hypot(dr * C5, dc * C5))


def lunghezza_max(sub, mk, ro, co):
    """Distanza massima lungo il D8 dalle celle del bacino alla sezione (m),
    con salti di puntatore (pointer jumping) vettoriali."""
    h, w = mk.shape
    idx = np.flatnonzero(mk)
    pos = np.full(h * w, -1, np.int64)
    pos[idx] = np.arange(idx.size)
    rr, cc = np.divmod(idx, w)
    code = sub.ravel()[idx]
    dr = np.zeros(idx.size, np.int64)
    dc = np.zeros(idx.size, np.int64)
    for k_, (a_, b_) in OFF.items():
        sel_ = code == k_
        dr[sel_], dc[sel_] = a_, b_
    r2, c2 = rr + dr, cc + dc
    ok = (code > 0) & (r2 >= 0) & (r2 < h) & (c2 >= 0) & (c2 < w)
    nxt = np.arange(idx.size)
    nxt[ok] = pos[r2[ok] * w + c2[ok]]
    nxt[nxt < 0] = np.arange(idx.size)[nxt < 0]
    root = pos[ro * w + co]
    nxt[root] = root
    d = np.where(nxt != np.arange(idx.size), np.hypot(dr, dc) * C5, 0.0)
    while True:
        d = d + d[nxt]
        n2 = nxt[nxt]
        if np.array_equal(n2, nxt):
            break
        nxt = n2
    return float(d.max())


def poligono(mask, T):
    geoms = [shape(g) for g, v in shapes(mask.astype(np.uint8), mask=mask, transform=T) if v == 1]
    polys = []
    for g in geoms:
        for p in (g.geoms if isinstance(g, MultiPolygon) else [g]):
            polys.append(Polygon(p.exterior))
    if not polys:
        return None
    big = max(polys, key=lambda p: p.area)
    return big


# Una finestra per processo (SOLO_FINESTRA) per contenere la memoria; i
# risultati per finestra si uniscono con UNISCI=1.
solo = [int(v) for v in os.environ.get('SOLO_FINESTRA', '').split(',') if v != '']
if os.environ.get('UNISCI'):
    parti = sorted(glob.glob(os.path.join(out, 'parti', 'parametri_f*.csv')))
    pd.concat([pd.read_csv(f) for f in parti]).sort_values('ID').to_csv(
        os.path.join(out, 'bacini_5m_parametri.csv'), index=False)
    gp = os.path.join(out, 'bacini_5m.gpkg')
    if os.path.exists(gp):
        os.remove(gp)
    for lay in ('bacini', 'sezioni_chiusura'):
        g = pd.concat([gpd.read_file(f, layer=lay) for f in
                       sorted(glob.glob(os.path.join(out, 'parti', 'bacini_f*.gpkg')))])
        gpd.GeoDataFrame(g, crs=32633).sort_values('ID').to_file(gp, layer=lay, driver='GPKG')
    print('uniti', len(parti))
    sys.exit()
os.makedirs(os.path.join(out, 'parti'), exist_ok=True)
for fin in meta['finestre']:
    k = fin['k']
    if solo and k not in solo:
        continue
    righe, poli, sezioni = [], [], []
    ids = [i for i in fin['ponti'] if i in agg.index]
    if not ids:
        continue
    p_ptr = os.path.join(run, 'finestre', f'f{k:03d}_puntatore.tif')
    grid = Grid.from_raster(p_ptr)
    fdir = grid.read_raster(p_ptr)
    ptr = np.asarray(fdir)
    T = grid.affine
    H, W = ptr.shape
    with rasterio.open(os.path.join(run, 'finestre', f'f{k:03d}_dem_ibrido.tif')) as s:
        dem = s.read(1).astype(np.float32)
        dem[dem == s.nodata] = np.nan
    with rasterio.open(os.path.join(run, 'finestre', f'f{k:03d}_fonte5m.tif')) as s:
        f5 = s.read(1).astype(bool)
    acc = np.asarray(grid.accumulation(fdir, dirmap=DIRMAP_WBT), dtype=np.float32) * np.float32(C5 * C5 / 1e6)
    cn = np.zeros((H, W), np.uint8)
    sel = [f for f, b in cn_idx if b.left < T.c + W * C5 and b.right > T.c and b.bottom < T.f and b.top > T.f - H * C5]
    if sel:
        m, _ = merge(sel, bounds=(T.c, T.f - H * C5, T.c + W * C5, T.f), res=C5, nodata=0)
        cn[:] = m[0][:H, :W]
    for i in ids:
        a = agg.loc[i]
        if pd.isna(a.get(cella_col)):
            continue
        rp, cp = map(int, str(a[cella_col]).split(','))
        npz = np.load(os.path.join(run, 'toppe', f'id{i:03d}.npz'))
        r0, c0 = npz['offset']
        r, c = int(r0 + rp), int(c0 + cp)
        mask = np.asarray(grid.catchment(x=c, y=r, fdir=fdir, dirmap=DIRMAP_WBT, xytype='index'), dtype=bool)
        R_, C_ = np.nonzero(mask)
        rb0, rb1, cb0, cb1 = R_.min(), R_.max() + 1, C_.min(), C_.max() + 1
        mk = mask[rb0:rb1, cb0:cb1]
        Tb = T * T.translation(cb0, rb0)
        n = int(mk.sum())
        A = n * C5 * C5 / 1e6
        frac5 = float(f5[rb0:rb1, cb0:cb1][mk].mean())
        poly = poligono(mk, Tb)
        x_out, y_out = T * (c + 0.5, r + 0.5)
        P = poly.simplify(C5 / 2).length / 1000 if poly is not None else np.nan
        Lb = max(Point(x_out, y_out).distance(Point(p)) for p in poly.exterior.coords) / 1000 if poly else np.nan
        # percorso di flusso piu' lungo fino alla sezione
        L = lunghezza_max(ptr[rb0:rb1, cb0:cb1], mk, r - rb0, c - cb0) / 1000
        z = dem[rb0:rb1, cb0:cb1][mk]
        zmin, zmax, AE = np.nanmin(z), np.nanmax(z), np.nanmean(z)
        Rl = zmax - zmin
        # pendenza D8 (massima discendente) calcolata solo sull'ingombro del bacino
        zb = dem[max(rb0 - 1, 0):rb1 + 1, max(cb0 - 1, 0):cb1 + 1].astype(np.float64)
        pr, pc = rb0 - max(rb0 - 1, 0), cb0 - max(cb0 - 1, 0)
        zp = np.pad(zb, 1, mode='edge')
        hb, wb_ = zb.shape
        sl = np.zeros_like(zb)
        for code, (dr, dc) in OFF.items():
            nb = zp[1 + dr:1 + dr + hb, 1 + dc:1 + dc + wb_]
            sl = np.fmax(sl, np.where((zb - nb) > 0, (zb - nb) / passo(dr, dc), 0))
        S = float(np.nanmean(sl[pr:pr + mk.shape[0], pc:pc + mk.shape[1]][mk]))
        del zb, zp, sl
        cnv = cn[rb0:rb1, cb0:cb1][mk]
        cnv = cnv[cnv > 0]
        CN = float(cnv.mean()) if cnv.size else np.nan
        cn_cop = cnv.size / n
        # pendenza di tratto centrata
        def su(rr, cc, d_target):
            d = 0.0
            while d < d_target:
                best, ba = None, -1
                for code, (dr, dc) in OFF.items():
                    r2, c2 = rr + dr, cc + dc
                    if 0 <= r2 < H and 0 <= c2 < W and ptr[r2, c2] == OPP[code] and acc[r2, c2] >= soglia \
                            and acc[r2, c2] > ba:
                        best, ba = (r2, c2, passo(dr, dc)), acc[r2, c2]
                if best is None:
                    break
                rr, cc, d = best[0], best[1], d + best[2]
            return rr, cc, d

        def giu(rr, cc, d_target):
            d = 0.0
            while d < d_target:
                off = OFF.get(int(ptr[rr, cc]))
                if off is None:
                    break
                r2, c2 = rr + off[0], cc + off[1]
                if not (0 <= r2 < H and 0 <= c2 < W) or np.isnan(dem[r2, c2]):
                    break
                rr, cc, d = r2, c2, d + passo(*off)
            return rr, cc, d

        ru, cu, du = su(r, c, TRATTO_M / 2)
        rd, cd, dd = giu(r, c, TRATTO_M / 2)
        tratto = (dem[ru, cu] - dem[rd, cd]) / (du + dd) if du + dd > 0 else np.nan
        o = {'ID': i, 'Finestra': k, 'X_sezione': x_out, 'Y_sezione': y_out, 'A_km2': A,
             'A_check_acc_km2': acc[r, c], 'Quota_area_DEM5m': frac5,
             'Bacino_ibrido': frac5 < 0.999, 'P_km': P, 'L_km': L, 'Lb_km': Lb,
             'Quota_min_m': zmin, 'Quota_max_m': zmax, 'AE_m': AE, 'Rilievo_m': Rl, 'S_media': S,
             'CN_medio': CN, 'Quota_area_con_CN': cn_cop,
             'Pendenza_tratto_500m': tratto, 'Lunghezza_tratto_m': du + dd}
        o['FF'] = A / L ** 2 if L > 0 else np.nan
        o['Elongazione_Re'] = 2 * np.sqrt(A / np.pi) / L if L > 0 else np.nan
        o['Forma_Lb_Rf'] = A / Lb ** 2 if Lb > 0 else np.nan
        o['Shape_factor'] = L / np.sqrt(A) if A > 0 else np.nan
        o['Compattezza_Kc'] = P / (2 * np.sqrt(np.pi * A)) if A > 0 else np.nan
        o['Circolarita_Rc'] = 4 * np.pi * A / P ** 2 if P > 0 else np.nan
        o['Melton'] = (Rl / 1000) / np.sqrt(A) if A > 0 else np.nan
        o['Integrale_ipsometrico'] = (AE - zmin) / Rl if Rl > 0 else np.nan
        o['Rapporto_rilievo_Rr'] = (Rl / 1000) / Lb if Lb > 0 else np.nan
        o['Rilievo_relativo'] = Rl / (P * 1000) if P > 0 else np.nan
        righe.append(o)
        if poly is not None:
            poli.append({'ID': i, 'A_km2': A, 'Quota_area_DEM5m': frac5, 'geometry': poly})
        sezioni.append({'ID': i, 'A_km2': A, 'geometry': Point(x_out, y_out)})
        print(f"ID {i}: A={A:.3f} km2 L={L:.2f} km 5m={frac5:.2f}", flush=True)
    del dem, f5, acc, ptr, fdir, grid, cn
    pd.DataFrame(righe).to_csv(os.path.join(out, 'parti', f'parametri_f{k:03d}.csv'), index=False)
    gp = os.path.join(out, 'parti', f'bacini_f{k:03d}.gpkg')
    if os.path.exists(gp):
        os.remove(gp)
    gpd.GeoDataFrame(poli, crs=32633).to_file(gp, layer='bacini', driver='GPKG')
    gpd.GeoDataFrame(sezioni, crs=32633).to_file(gp, layer='sezioni_chiusura', driver='GPKG')
    print('finestra', k, 'fatta', len(righe), flush=True)
