"""
Verifica indipendente dell'estrazione del bacino (metodo B) rispetto al codice dell'utente
(metodo A, pysheds: fill_pits + fill_depressions + resolve_flats, D8, snap_to_mask, catchment).

Metodo B, stesso DEM e stessa sezione, software e algoritmi diversi (WhiteboxTools):
  - breaching delle depressioni a costo minimo (le depressioni vengono scavate, non riempite;
    quelle residue riempite) invece del riempimento;
  - puntatore D8 e accumulo Whitebox; reticolo = accumulo > 4000 celle (0,1 km2);
  - sezione ricavata di nuovo, con la stessa regola ma sul reticolo B: cella del reticolo
    attraversata dal tracciato KML del ponte con accumulo massimo; se il tracciato non tocca
    il reticolo, cella del reticolo piu' vicina al tracciato (la sezione A non viene usata);
  - bacino con watershed Whitebox.
Confronto: area A e B, intersezione/unione (IoU) dei due bacini, area solo in A e solo in B.

Uso: python verifica_bacino_alternativo.py <dem5m_unico.tif> <ponti.csv> <cartella porzioni del codice>
        <controllo_coordinate.gpkg> <out_dir> <ID> [ID ...]
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.features import rasterize, shapes
from rasterio.windows import from_bounds
from shapely.geometry import shape
import whitebox_workflows as wb

dem_p, csv_p, porz_dir, cgpkg, out = sys.argv[1:6]
ids = [int(v) for v in sys.argv[6:]]
TR = gpd.read_file(cgpkg, layer='tracciato_usato').set_index('ID').geometry
os.makedirs(out, exist_ok=True)
SOGLIA = 4000
P = pd.read_csv(csv_p).set_index('id')
wbe = wb.WbEnvironment()
righe = []
for i in ids:
    r = P.loc[i]
    lim = (r.xmin, r.ymin, r.xmax, r.ymax)
    with rasterio.open(dem_p) as s:
        w = from_bounds(*lim, transform=s.transform).round_offsets().round_lengths()
        a = s.read(1, window=w)
        T = s.window_transform(w)
        nd = a == s.nodata
        z = (a.astype(np.float64) * s.scales[0]).round(2).astype(np.float32)
        crs = s.crs
    z[nd] = -9999
    tif = os.path.join(out, f'id{i:03d}_dem.tif')
    with rasterio.open(tif, 'w', driver='GTiff', height=z.shape[0], width=z.shape[1], count=1, dtype='float32',
                       crs=crs, transform=T, nodata=-9999) as d:
        d.write(z, 1)
    del a, z
    dem = wbe.read_raster(tif)
    br = wbe.hydrology.breach_depressions_least_cost(dem=dem, fill_deps=True)
    ptr = wbe.hydrology.d8_pointer(dem=br)
    acc = wbe.hydrology.d8_flow_accum(input=ptr, out_type='cells', input_is_pointer=True)
    p_acc = os.path.join(out, f'id{i:03d}_acc.tif')
    wbe.write_raster(acc, p_acc)
    with rasterio.open(p_acc) as s:
        A = s.read(1)
    # sezione B: intersezione tracciato KML - reticolo B (stessa regola del calcolo di riferimento)
    rete = A > SOGLIA
    tr = TR[i]
    tocca = rasterize([(tr, 1)], out_shape=A.shape, transform=T, all_touched=True).astype(bool) & rete
    if tocca.any():
        k = np.argmax(np.where(tocca, A, -1))
        rr0, cc0 = np.unravel_index(k, A.shape)
        regola = 'intersezione tracciato-reticolo'
    else:
        ys, xs = np.nonzero(rete)
        px, py = T * (xs + 0.5, ys + 0.5)
        import shapely
        dd = shapely.distance(shapely.points(px, py), tr)
        k = int(np.argmin(dd))
        rr0, cc0 = ys[k], xs[k]
        regola = f'reticolo piu vicino al tracciato ({dd[k]:.0f} m)'
    cx, cy = T * (cc0 + 0.5, rr0 + 0.5)
    del A, rete
    ptA = gpd.GeoDataFrame({'ID': [i]}, geometry=gpd.points_from_xy([r.X], [r.Y]), crs=4326).to_crs(crs)
    pt = gpd.GeoDataFrame({'ID': [i]}, geometry=gpd.points_from_xy([cx], [cy]), crs=crs)
    p_sn = os.path.join(out, f'id{i:03d}_sezione_B.shp')
    pt.to_file(p_sn)
    ws = wbe.hydrology.watershed(d8_pntr=ptr, pour_pts=wbe.read_vector(p_sn))
    p_ws = os.path.join(out, f'id{i:03d}_bacino_B.tif')
    wbe.write_raster(ws, p_ws)
    with rasterio.open(p_ws) as s:
        B = s.read(1)
        B = (B > 0) & (B != s.nodata) if s.nodata is not None else B > 0
    # bacino del codice (metodo A) dal GeoJSON della porzione
    fA = os.path.join(porz_dir, f'{r.porzione}_bacini_afferenti.geojson')
    geomA = []
    if os.path.exists(fA):  # se manca il poligono del codice si confronta solo l'area
        gj = json.load(open(fA))
        geomA = [shape(f['geometry']) for f in gj['features'] if int(f['properties']['ID']) == i]
    MA = rasterize(geomA, out_shape=B.shape, transform=T).astype(bool) if geomA else np.zeros_like(B)
    cel = T.a * -T.e / 1e6
    aA, aB = MA.sum() * cel, B.sum() * cel
    inter, uni = (MA & B).sum() * cel, (MA | B).sum() * cel
    righe.append({'ID': i, 'Area A codice pysheds (km²)': round(aA, 4), 'Area B Whitebox breaching (km²)': round(aB, 4),
                  'Differenza B/A %': (aB / aA - 1) if aA else np.nan, 'IoU': inter / uni if uni else np.nan,
                  'Solo in A (km²)': round(aA - inter, 4), 'Solo in B (km²)': round(aB - inter, 4),
                  'Distanza sezione B - sezione A (m)': round(float(pt.geometry.iloc[0].distance(ptA.geometry.iloc[0])), 1),
                  'Regola sezione B': regola})
    polB = [shape(g) for g, v in shapes(B.astype(np.uint8), mask=B, transform=T) if v == 1]
    gpd.GeoDataFrame({'ID': [i] * len(polB)}, geometry=polB, crs=crs).dissolve('ID').to_file(
        os.path.join(out, f'id{i:03d}_bacino_B.gpkg'))
    for f in (tif, p_acc):
        os.remove(f)
    print(righe[-1], flush=True)
pd.DataFrame(righe).to_csv(os.path.join(out, 'confronto_bacini_A_B.csv'), index=False)
