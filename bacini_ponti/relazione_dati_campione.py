"""
Dati per la relazione di verifica del codice pysheds_bridges_5m.py su un campione di ponti.

Per ogni ponte (porzione del DEM unico, stessa lettura del codice):
  METODO A (codice): pysheds fill_pits + fill_depressions + resolve_flats(eps=1e-6, max_iter=10000),
     D8, accumulo, snap_to_mask(acc > 4000), catchment  -> bacino A, sezione A.
  RICALCOLO INDIPENDENTE dei parametri sul bacino A con codice scritto qui, senza riusare le
     funzioni del codice: area da conteggio celle e da poligono, quote e CN da statistiche zonali,
     perimetro dalla geometria del poligono, percorso di flusso piu' lungo con propagazione delle
     distanze verso valle (pointer jumping) invece della ricerca a ritroso, pendenze D8 riscritte.
  METODO B (indipendente, WhiteboxTools): breaching a costo minimo, D8, accumulo, reticolo > 4000
     celle, sezione = cella del reticolo B attraversata dal tracciato KML con accumulo massimo (o la
     piu' vicina al tracciato), watershed -> bacino B.
Salva per ogni ponte un .npz con i dati delle figure e un CSV con tutti i valori.

Uso: python relazione_dati_campione.py <dem5m_unico.tif> <cn5m_unico.tif> <ponti.csv>
        <controllo_coordinate.gpkg> <out_dir> <ID> [ID ...]
"""
import json
import os
import sys
import time

import numpy as np
np.in1d = np.isin
import pandas as pd
import geopandas as gpd
import rasterio
import shapely
from rasterio.features import rasterize, shapes
from rasterio.windows import from_bounds
from pyproj import Proj, Transformer
from shapely.geometry import shape
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
import whitebox_workflows as wb

dem_p, cn_p, csv_p, cgpkg, out = sys.argv[1:6]
ids = [int(v) for v in sys.argv[6:]]
os.makedirs(out, exist_ok=True)
SOGLIA = 4000
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
OFF = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}
WBOFF = {1: (-1, 1), 2: (0, 1), 4: (1, 1), 8: (1, 0), 16: (1, -1), 32: (0, -1), 64: (-1, -1), 128: (-1, 0)}
P = pd.read_csv(csv_p).set_index('id')
TR = gpd.read_file(cgpkg, layer='tracciato_usato').set_index('ID').geometry
INI = gpd.read_file(cgpkg, layer='db_inizio').set_index('ID').geometry
FIN = gpd.read_file(cgpkg, layer='db_fine').set_index('ID').geometry
crs_p = Proj('EPSG:32633', preserve_units=True)
to_utm = Transformer.from_crs(4326, 32633, always_xy=True)
wbe = wb.WbEnvironment()


def leggi(path, lim, dtype, nod):
    with rasterio.open(path) as s:
        w = from_bounds(*lim, transform=s.transform).round_offsets().round_lengths()
        a = s.read(1, window=w)
        T = s.window_transform(w)
        senza = (a == s.nodata) | np.isnan(a) if s.nodata is not None else np.isnan(a)
        a = a.astype(dtype) * s.scales[0] + s.offsets[0]
    a[senza] = nod
    return a, T


def pendenza_d8(Z, cs):
    """massima pendenza discendente verso le 8 celle vicine (riscritta)"""
    H, W = Z.shape
    out_ = np.zeros_like(Z)
    Zp = np.pad(Z, 1, mode='edge')
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            d = cs * (np.sqrt(2) if dr and dc else 1)
            nb = Zp[1 + dr:1 + dr + H, 1 + dc:1 + dc + W]
            out_ = np.maximum(out_, np.clip((Z - nb) / d, 0, None))
    return out_


def distanza_a_valle(mask, fdir, r0, c0, cs, off):
    """distanza lungo il flusso D8 di ogni cella del bacino dalla sezione (pointer jumping)"""
    rr, cc = np.nonzero(mask)
    n = len(rr)
    idx = -np.ones(mask.shape, np.int32)
    idx[rr, cc] = np.arange(n)
    nxt = np.arange(n, dtype=np.int32)
    step = np.zeros(n)
    f = fdir[rr, cc]
    for code, (dr, dc) in off.items():
        k = f == code
        r2, c2 = rr[k] + dr, cc[k] + dc
        ok = (r2 >= 0) & (r2 < mask.shape[0]) & (c2 >= 0) & (c2 < mask.shape[1])
        kk = np.nonzero(k)[0][ok]
        j = idx[r2[ok], c2[ok]]
        good = j >= 0
        nxt[kk[good]] = j[good]
        step[kk[good]] = cs * (np.sqrt(2) if dr and dc else 1)
    o = idx[r0, c0]
    nxt[o], step[o] = o, 0.0
    d = step.copy()
    for _ in range(64):
        d2 = d + d[nxt]
        n2 = nxt[nxt]
        if np.array_equal(n2, nxt):
            break
        d, nxt = d2, n2
    D = np.full(mask.shape, np.nan)
    D[rr, cc] = d
    return D


def percorso(r, c, fdir, off, mask, maxn=10 ** 7):
    pts = [(r, c)]
    for _ in range(maxn):
        v = int(fdir[r, c])
        if v not in off:
            break
        dr, dc = off[v]
        r, c = r + dr, c + dc
        if not (0 <= r < mask.shape[0] and 0 <= c < mask.shape[1]) or not mask[r, c]:
            break
        pts.append((r, c))
    return pts


def hillshade(Z, cs):
    Z = np.where(Z < -1000, np.nan, Z)
    gy, gx = np.gradient(Z, cs)
    slope = np.arctan(np.hypot(gx, gy))
    asp = np.arctan2(-gx, gy)
    az, alt = np.radians(315), np.radians(45)
    hs = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - asp)
    return np.nan_to_num(hs, nan=0.5).astype(np.float32)


def ricampiona(a, f, modo='max'):
    if f == 1:
        return a
    H, W = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    b = a[:H, :W].reshape(H // f, f, W // f, f)
    return {'max': b.max(axis=(1, 3)), 'mean': np.nanmean(b, axis=(1, 3)), 'any': b.any(axis=(1, 3))}[modo]


righe = []
for i in ids:
    t0 = time.time()
    r = P.loc[i]
    lim = (r.xmin, r.ymin, r.xmax, r.ymax)
    grande = (r.xmax - r.xmin) * (r.ymax - r.ymin) / 25 > 1.2e8
    dt = np.float32 if grande else np.float64
    z, T = leggi(dem_p, lim, dt, -9999.0)
    z[z != -9999] = np.round(z[z != -9999], 2)
    cs = T.a
    # ---------------- METODO A: stessa sequenza del codice ----------------
    vf = ViewFinder(affine=T, shape=z.shape, nodata=z.dtype.type(-9999), crs=crs_p)
    grid = Grid(viewfinder=vf)
    dem = Raster(z.copy(), vf)
    infl = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem)), eps=1e-6, max_iter=10000)
    fdir = grid.flowdir(infl, dirmap=DIRMAP)
    acc = grid.accumulation(fdir, dirmap=DIRMAP)
    x, y = to_utm.transform(r.X, r.Y)
    xs, ys = grid.snap_to_mask(acc > SOGLIA, (x, y))
    bA = np.asarray(grid.catchment(x=xs, y=ys, fdir=fdir, dirmap=DIRMAP, xytype='coordinate')).astype(bool)
    cA, rA = grid.nearest_cell(xs, ys)
    fd = np.asarray(fdir).astype(np.int16)  # codici D8 fino a 128: int16 basta e dimezza la memoria
    del fdir
    accA = np.asarray(acc).astype(np.float32)
    infl = np.asarray(infl)
    del acc, dem
    # ---------------- RICALCOLO INDIPENDENTE sul bacino A ----------------
    slope = pendenza_d8(infl.astype(np.float64) if not grande else infl, cs)
    del infl
    zb = np.where(bA, z, np.nan).astype(np.float64)
    cn, _ = leggi(cn_p, lim, np.float32, np.nan)
    polA = [shape(g) for g, v in shapes(bA.astype(np.uint8), mask=bA, transform=T) if v == 1]
    polyA = shapely.unary_union(polA)
    n = int(bA.sum())
    Dv = distanza_a_valle(bA, fd, rA, cA, cs, OFF)
    L = float(np.nanmax(Dv))
    rf, cf = np.unravel_index(np.nanargmax(Dv), Dv.shape)
    pathA = percorso(rf, cf, fd, OFF, bA)
    # pendenza del tratto centrato (500 m): monte lungo il ramo con accumulo massimo, valle lungo D8
    def monte(r_, c_, dist):
        d = 0.0
        while d < dist:
            best = None
            for code, (dr, dc) in OFF.items():
                r2, c2 = r_ - dr, c_ - dc
                if 0 <= r2 < fd.shape[0] and 0 <= c2 < fd.shape[1] and fd[r2, c2] == code and accA[r2, c2] > SOGLIA:
                    if best is None or accA[r2, c2] > accA[best]:
                        best = (r2, c2)
            if best is None:
                break
            d += cs * (np.sqrt(2) if (best[0] - r_) and (best[1] - c_) else 1)
            r_, c_ = best
        return r_, c_, d

    def valle(r_, c_, dist):
        d = 0.0
        while d < dist:
            v = int(fd[r_, c_])
            if v not in OFF:
                break
            dr, dc = OFF[v]
            if not (0 <= r_ + dr < fd.shape[0] and 0 <= c_ + dc < fd.shape[1]):
                break
            d += cs * (np.sqrt(2) if dr and dc else 1)
            r_, c_ = r_ + dr, c_ + dc
        return r_, c_, d
    ru, cu, du = monte(rA, cA, 250.0)
    rd, cd, dd = valle(rA, cA, 250.0)
    reach = (z[ru, cu] - z[rd, cd]) / (du + dd) if du + dd > 0 else np.nan
    zmin, zmax = float(np.nanmin(zb)), float(np.nanmax(zb))
    ind = {
        'ID': i, 'A_celle': n, 'A_km2': n * cs * cs / 1e6, 'A_poligono_km2': polyA.area / 1e6,
        'S': float(np.mean(slope[bA])), 'AE_m': float(np.nanmean(zb)), 'Quota_min_m': zmin, 'Quota_max_m': zmax,
        'Relief_m': zmax - zmin, 'L_km': L / 1000, 'P_km': (polyA.length if polyA.geom_type == 'Polygon' else
                                                            sum(g.length for g in polyA.geoms)) / 1000,
        'CN_medio': float(np.nanmean(cn[bA])), 'Quota_area_con_CN': float(np.isfinite(cn[bA]).mean()),
        'Cell_Slope': float(slope[rA, cA]), 'Reach_Slope': float(reach), 'Reach_Length_m': du + dd,
        'Sezione_A_x': xs, 'Sezione_A_y': ys,
    }
    del slope, Dv
    zv = zb[bA]
    del zb
    # ---------------- METODO B: WhiteboxTools ----------------
    tif = os.path.join(out, f'tmp_{i}.tif')
    with rasterio.open(tif, 'w', driver='GTiff', height=z.shape[0], width=z.shape[1], count=1, dtype='float32',
                       crs='EPSG:32633', transform=T, nodata=-9999) as d:
        d.write(z.astype(np.float32), 1)
    w_dem = wbe.read_raster(tif)
    w_br = wbe.hydrology.breach_depressions_least_cost(dem=w_dem, fill_deps=True)
    w_ptr = wbe.hydrology.d8_pointer(dem=w_br)
    w_acc = wbe.hydrology.d8_flow_accum(input=w_ptr, out_type='cells', input_is_pointer=True)
    wbe.write_raster(w_acc, tif.replace('.tif', '_acc.tif'))
    wbe.write_raster(w_ptr, tif.replace('.tif', '_ptr.tif'))
    del w_dem, w_br, w_acc
    with rasterio.open(tif.replace('.tif', '_acc.tif')) as s:
        accB = s.read(1).astype(np.float32)
    ptrB = None
    if not grande:
        with rasterio.open(tif.replace('.tif', '_ptr.tif')) as s:
            ptrB = s.read(1).astype(np.int16)
    reteB = accB > SOGLIA
    tr = TR[i]
    tocca = rasterize([(tr, 1)], out_shape=z.shape, transform=T, all_touched=True).astype(bool) & reteB
    if tocca.any():
        k = np.argmax(np.where(tocca, accB, -1))
        rB, cB = np.unravel_index(k, z.shape)
        regola = 'intersezione tracciato-reticolo'
    else:
        yy, xx = np.nonzero(reteB)
        px, py = T * (xx + 0.5, yy + 0.5)
        dd_ = shapely.distance(shapely.points(px, py), tr)
        k = int(np.argmin(dd_))
        rB, cB = yy[k], xx[k]
        regola = f'reticolo piu vicino al tracciato ({dd_[k]:.0f} m)'
    # ritaglio del reticolo B per la figura di dettaglio, poi si libera la memoria del metodo B
    h = int(300 / cs)
    r0_, r1_ = max(rA - h, 0), min(rA + h, z.shape[0])
    c0_, c1_ = max(cA - h, 0), min(cA + h, z.shape[1])
    z_reteB = reteB[r0_:r1_, c0_:c1_].copy()
    if grande:
        del accB, reteB, tocca
    # bacino B: watershed Whitebox dalla sezione B
    xB, yB = T * (cB + 0.5, rB + 0.5)
    p_pt = tif.replace('.tif', '_secB.shp')
    gpd.GeoDataFrame({'ID': [i]}, geometry=gpd.points_from_xy([xB], [yB]), crs=32633).to_file(p_pt)
    ws = wbe.hydrology.watershed(d8_pntr=w_ptr, pour_pts=wbe.read_vector(p_pt))
    wbe.write_raster(ws, tif.replace('.tif', '_ws.tif'))
    del ws, w_ptr
    with rasterio.open(tif.replace('.tif', '_ws.tif')) as s:
        wsa = s.read(1)
        bB = (wsa > 0) & ((wsa != s.nodata) if s.nodata is not None else True)
    del wsa
    xB, yB = T * (cB + 0.5, rB + 0.5)
    # percorso piu' lungo del bacino B (saltato per le porzioni molto grandi: limite di memoria)
    DvB = None if grande else distanza_a_valle(bB, ptrB, rB, cB, cs, WBOFF)
    del ptrB
    zbB = np.where(bB, z, np.nan)
    inter, uni = (bA & bB).sum(), (bA | bB).sum()
    if grande:  # poligono su griglia 4x piu' grossolana (solo per la figura e il GeoPackage): limite di memoria
        bB4 = ricampiona(bB, 4, 'any')
        T4 = T * rasterio.Affine.scale(4)
        polB = shapely.unary_union([shape(g) for g, v in shapes(bB4.astype(np.uint8), mask=bB4, transform=T4) if v == 1])
        del bB4
    else:
        polB = shapely.unary_union([shape(g) for g, v in shapes(bB.astype(np.uint8), mask=bB, transform=T) if v == 1])
    ind.update({'A_B_km2': bB.sum() * cs * cs / 1e6, 'IoU_AB': inter / uni, 'Solo_A_km2': (bA & ~bB).sum() * cs * cs / 1e6,
                'Solo_B_km2': (bB & ~bA).sum() * cs * cs / 1e6,
                'L_B_km': float(np.nanmax(DvB)) / 1000 if DvB is not None else np.nan,
                'AE_B_m': float(np.nanmean(zbB)), 'Relief_B_m': float(np.nanmax(zbB) - np.nanmin(zbB)),
                'CN_B': float(np.nanmean(cn[bB])), 'P_B_km': np.nan if grande else (polB.length / 1000 if polB.geom_type == 'Polygon'
                                                                       else sum(g.length for g in polB.geoms) / 1000),
                'Sezione_B_x': xB, 'Sezione_B_y': yB, 'Regola_sezione_B': regola,
                'Dist_sezioni_AB_m': float(np.hypot(xB - xs, yB - ys))})
    del zbB
    # ---------------- dati per le figure ----------------
    # zoom sull'attraversamento: +-300 m attorno alla sezione A
    del DvB
    Tz = T * rasterio.Affine.translation(c0_, r0_)
    zoom = dict(z_hs=hillshade(z[r0_:r1_, c0_:c1_].astype(np.float64), cs), z_reteA=accA[r0_:r1_, c0_:c1_] > SOGLIA,
                z_reteB=z_reteB, z_T=np.array(Tz)[:6])
    # bacino intero, ricampionato a max ~1400 px
    u = bA | bB
    rr_ = np.nonzero(u.any(axis=1))[0]
    cc_ = np.nonzero(u.any(axis=0))[0]
    del u
    pad = 40
    R0, R1 = max(rr_.min() - pad, 0), min(rr_.max() + pad, z.shape[0])
    C0, C1 = max(cc_.min() - pad, 0), min(cc_.max() + pad, z.shape[1])
    f = max(1, int(np.ceil(max(R1 - R0, C1 - C0) / 1400)))
    Tb = T * rasterio.Affine.translation(C0, R0) * rasterio.Affine.scale(f)
    # ritagli ricampionati in precisione singola, liberando ogni array appena usato (memoria)
    b_reteA = ricampiona(accA[R0:R1, C0:C1] > SOGLIA * max(1, f * f / 4), f, 'any')
    del accA
    b_Am = ricampiona(bA[R0:R1, C0:C1], f, 'any')
    b_Bm = ricampiona(bB[R0:R1, C0:C1], f, 'any')
    del bB
    cn_r = ricampiona(cn[R0:R1, C0:C1], f, 'mean').astype(np.float32)
    del cn
    zz = z[R0:R1, C0:C1].astype(np.float32)
    zz[zz < -1000] = np.nan
    zz_r = ricampiona(zz, f, 'mean').astype(np.float32)
    del zz
    pth = np.array([T * (c_ + 0.5, r_ + 0.5) for r_, c_ in pathA])
    q = np.linspace(0, 1, 101)
    hyps_z = np.quantile(zv[np.isfinite(zv)], 1 - q)
    np.savez_compressed(os.path.join(out, f'id{i:03d}.npz'), **zoom,
                        b_hs=hillshade(zz_r.astype(np.float64), cs * f), b_dem=zz_r, b_cn=cn_r,
                        b_A=b_Am, b_B=b_Bm, b_reteA=b_reteA,
                        b_T=np.array(Tb)[:6], path=pth, hyps_q=q, hyps_z=hyps_z,
                        secA=np.array([xs, ys]), secB=np.array([xB, yB]))
    gpd.GeoDataFrame({'ID': [i, i], 'metodo': ['A codice', 'B indipendente']}, geometry=[polyA, polB],
                     crs=32633).to_file(os.path.join(out, f'id{i:03d}_bacini.gpkg'))
    import glob as _g
    for fn in _g.glob(tif.replace('.tif', '*')):
        os.remove(fn)
    righe.append(ind)
    pd.DataFrame(righe).to_csv(os.path.join(out, f'valori_{"_".join(map(str, ids))}.csv'), index=False)
    print(i, f'{time.time() - t0:.0f} s', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in ind.items()
                                            if k in ('A_km2', 'A_B_km2', 'IoU_AB', 'L_km', 'L_B_km', 'S', 'CN_medio')},
          flush=True)
