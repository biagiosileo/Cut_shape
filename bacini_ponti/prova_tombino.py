"""
Prova "apertura del tombino": nei punti in cui il rilevato stradale fa da diga nel DEM, si incide un taglio
attraverso la strada in corrispondenza del ponte e si ricalcola il bacino.

Per ogni ponte (porzione di ponti.csv, DEM unico, stessa catena del codice dell'utente):
  - taglio: segmento lungo LUNGHEZZA_M, perpendicolare al tracciato del ponte nel KML e centrato sul suo
    punto medio; le celle toccate vengono portate alla quota minima lungo il taglio meno BRUCIA_M (come
    l'incisione del reticolo di riferimento);
  - sezione: tra le celle del taglio entro TOLL_M dal tracciato, quella con accumulo maggiore (l'acqua che
    passa sotto il ponte);
  - bacino: catchment da quella cella; lo stesso calcolo senza taglio serve da confronto.
Il DEM unico non viene modificato: il taglio esiste solo in memoria per la prova.

Uso: python prova_tombino.py <dem5m_unico.tif> <ponti.csv> <controllo_coordinate.gpkg> <Database.xlsx>
        <out_dir> <id> [<id> ...]
"""
import os
import sys

import numpy as np
np.in1d = np.isin
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import rasterio
from pyproj import Proj
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
from rasterio.features import rasterize, shapes
from rasterio.windows import from_bounds
from shapely.geometry import LineString, Point, box, shape
from shapely.ops import unary_union

DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
LUNGHEZZA_M = 60.0
BRUCIA_M = 5.0
TOLL_M = 10.0
C5 = 5.0

dem_path, csv_path, gpkg, dbx, out = sys.argv[1:6]
ids = [int(i) for i in sys.argv[6:]]
os.makedirs(out, exist_ok=True)
P = pd.read_csv(csv_path).set_index('id')
k = gpd.read_file(gpkg, layer='kml_abbinato').set_index('ID').to_crs(32633)
kt = gpd.read_file(gpkg, layer='kml_tracciati').to_crs(32633).set_index('nome').geometry
tu = gpd.read_file(gpkg, layer='tracciato_usato').set_index('ID').to_crs(32633).geometry
db = pd.read_excel(dbx).rename(columns={'Unnamed: 0': 'ID'})
db = db[pd.to_numeric(db.ID, errors='coerce').notna()]
db['ID'] = db.ID.astype(int)
db = db.set_index('ID')
adb = pd.to_numeric(db['SUPERFICIE BACINO (km2)'], errors='coerce')
crs = Proj('EPSG:32633', preserve_units=True)


def taglio(t):
    c = np.array(t.coords)
    v = c[-1] - c[0]
    v = v / np.hypot(*v)
    n = np.array([-v[1], v[0]])
    m = np.array(t.interpolate(0.5, normalized=True).coords[0])
    return LineString([m - n * LUNGHEZZA_M / 2, m + n * LUNGHEZZA_M / 2])


def poligono(mask, T):
    r, c = np.where(mask)
    sub = mask[r.min():r.max() + 1, c.min():c.max() + 1].astype('uint8')
    return unary_union([shape(s) for s, v in shapes(sub, mask=sub.astype(bool), transform=T * T.translation(c.min(), r.min()))])


righe, linee, bacini = [], [], []
for i in ids:
    t = kt.get(k.loc[i, 'KML_nome'])
    t = t if t is not None else tu[i]
    cut = taglio(t)
    p = P.loc[i]
    with rasterio.open(dem_path) as src:
        w = from_bounds(p.xmin, p.ymin, p.xmax, p.ymax, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w)
        T = src.window_transform(w)
        z0 = (a.astype(np.float64) * src.scales[0]).astype(np.float32)
        nd = a == src.nodata
    z0[nd] = -9999
    mcut = rasterize([(cut, 1)], out_shape=z0.shape, transform=T, all_touched=True).astype(bool) & ~nd
    vicino = rasterize([(t.buffer(TOLL_M), 1)], out_shape=z0.shape, transform=T, all_touched=True).astype(bool)
    ris = {}
    for versione in ('senza taglio', 'con taglio'):
        z = z0.copy()
        if versione == 'con taglio':
            z[mcut] = z0[mcut].min() - BRUCIA_M
        vf = ViewFinder(affine=T, shape=z.shape, nodata=np.float32(-9999), crs=crs)
        grid = Grid(viewfinder=vf)
        dem = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(Raster(z, vf))), eps=1e-6, max_iter=10000)
        fdir = grid.flowdir(dem, dirmap=DIRMAP)
        acc = np.asarray(grid.accumulation(fdir, dirmap=DIRMAP))
        rr, cc = np.where(mcut & vicino)
        q = np.argmax(acc[rr, cc])
        xs, ys = T.c + (cc[q] + 0.5) * C5, T.f - (rr[q] + 0.5) * C5
        bm = np.asarray(grid.catchment(x=int(cc[q]), y=int(rr[q]), fdir=fdir, dirmap=DIRMAP, xytype='index'))
        A = bm.sum() * C5 * C5 / 1e6
        ris[versione] = (A, xs, ys, float(acc[rr[q], cc[q]]))
        bacini.append({'ID': i, 'versione': versione, 'A_km2': round(A, 4), 'geometry': poligono(bm, T)})
        print(i, versione, round(A, 4), flush=True)
    linee.append({'ID': i, 'tipo': 'taglio tombino', 'geometry': cut})
    linee.append({'ID': i, 'tipo': 'tracciato ponte', 'geometry': t})
    a1, x1, y1, acc1 = ris['con taglio']
    righe.append({'ID': i, 'Nome opera': str(db.loc[i, 'Nome opera']).strip(), 'Area DB (km²)': adb[i],
                  'Area senza taglio (km²)': round(ris['senza taglio'][0], 4), 'Area con taglio (km²)': round(a1, 4),
                  'Diff % con taglio': round(a1 / adb[i] - 1, 3),
                  'Esito': ('compatibile' if abs(a1 / adb[i] - 1) <= .15 else 'quasi compatibile'
                            if abs(a1 / adb[i] - 1) <= .25 else 'non compatibile'),
                  'X sezione': round(x1, 2), 'Y sezione': round(y1, 2), 'Accumulo sezione (celle)': int(acc1)})
    # scheda
    b = box(*cut.buffer(250).bounds)
    with rasterio.open(dem_path) as src:
        ww = from_bounds(*b.bounds, transform=src.transform).round_offsets().round_lengths()
        zz = src.read(1, window=ww).astype(float) * src.scales[0]
        Tw = src.window_transform(ww)
    gy, gx = np.gradient(zz, 5.0)
    sl, asp = np.pi / 2 - np.arctan(np.hypot(gx, gy)), np.arctan2(-gx, gy)
    hs = np.sin(np.radians(45)) * np.sin(sl) + np.cos(np.radians(45)) * np.cos(sl) * np.cos(np.radians(315) - asp)
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.imshow(hs, extent=[Tw.c, Tw.c + zz.shape[1] * 5, Tw.f - zz.shape[0] * 5, Tw.f], cmap='gray')
    for bb in [x for x in bacini if x['ID'] == i]:
        gpd.GeoSeries([bb['geometry'].intersection(b)]).boundary.plot(
            ax=ax, color='#888888' if bb['versione'] == 'senza taglio' else '#d7191c', lw=1.4,
            ls='--' if bb['versione'] == 'senza taglio' else '-')
    gpd.GeoSeries([cut]).plot(ax=ax, color='#1e6edc', lw=2)
    gpd.GeoSeries([t]).plot(ax=ax, color='#ff7800', lw=4)
    ax.plot(x1, y1, 'o', mfc='#ffc800', mec='k', ms=9)
    ax.set_xlim(b.bounds[0], b.bounds[2]); ax.set_ylim(b.bounds[1], b.bounds[3])
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(f"ID {i}: area DB {adb[i]:g} km² | senza taglio {ris['senza taglio'][0]:.3f} | con taglio {a1:.3f}",
                 fontsize=10)
    fig.text(0.02, 0.02, 'arancio: ponte (KML) - blu: taglio del rilevato - grigio tratteggiato: bacino senza taglio - '
             'rosso: bacino con taglio', fontsize=7)
    fig.savefig(os.path.join(out, f'ID{i:03d}_tombino.png'), dpi=110, bbox_inches='tight')
    plt.close(fig)
pd.DataFrame(righe).to_csv(os.path.join(out, 'prova_tombino.csv'), index=False)
gpd.GeoDataFrame(linee, crs=32633).to_file(os.path.join(out, 'prova_tombino.gpkg'), layer='linee', driver='GPKG')
gpd.GeoDataFrame(bacini, crs=32633).to_file(os.path.join(out, 'prova_tombino.gpkg'), layer='bacini', driver='GPKG')
print(pd.DataFrame(righe).drop(columns=['Nome opera']).to_string())
