"""
Indicazione precompilata (SI / NO / da guardare) per i ponti con posizione proposta, sulle tre domande:
  1) stesso corso d'acqua?  2) punto proposto "sotto il ponte"?  3) lo spostamento scavalca una confluenza?

Stesso DEM e stessa catena del codice dell'utente (DEM unico inciso, D8, accumulo) sulle porzioni della prova.
Per ogni ponte:
  - cella attuale e cella proposta (snap_to_mask con la soglia del ponte);
  - relazione tra le due lungo il flusso: stesso corso (a monte / a valle, distanza lungo l'asta) oppure altro
    corso (distanza di ciascuna dalla confluenza comune);
  - affluenti che entrano tra le due celle (numero, area del maggiore, area totale);
  - distanza del punto proposto dal tracciato del ponte (KML) e soglia "sotto il ponte" =
    max(lunghezza ponte, luce, larghezza alveo) / 2 + MARGINE_M;
  - se il tracciato del ponte attraversa il corso del punto proposto e quello del punto attuale (asta del D8
    entro TOLL_TRACCIATO_M dal tracciato, nei RAGGIO_ASTA_M a monte e a valle della cella).

Uso: python indicazioni_revisione.py <dem5m_unico.tif> <ponti attuali.csv> <ponti_prova_completo.csv>
        <origine_posizioni.csv> <Database.xlsx> <controllo_coordinate.gpkg> <out_dir>
"""
import os
import sys

import numpy as np
np.in1d = np.isin
import geopandas as gpd
import pandas as pd
import rasterio
from pyproj import Proj, Transformer
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
from rasterio.windows import from_bounds
from shapely.geometry import LineString, Point

DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)
PASSO = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}
ACC_THRESHOLD = 4000
MARGINE_M = 20.0
TOLL_TRACCIATO_M = 10.0
RAGGIO_ASTA_M = 300.0
C5 = 5.0

dem_path, csv_att, csv_prova, orig, dbx, gpkg, out = sys.argv[1:8]
os.makedirs(out, exist_ok=True)
A0 = pd.read_csv(csv_att).set_index('id')
P = pd.read_csv(csv_prova).set_index('id')
O = pd.read_csv(orig).set_index('ID').origine
db = pd.read_excel(dbx).rename(columns={'Unnamed: 0': 'ID'})
db = db[pd.to_numeric(db.ID, errors='coerce').notna()]
db['ID'] = db.ID.astype(int)
db = db.set_index('ID')
num = lambda c: pd.to_numeric(db[c].astype(str).str.replace(',', '.').str.extract(r'([\d.]+)')[0], errors='coerce')
adb, lung, luce, alveo = (num('SUPERFICIE BACINO (km2)'), num('LUNGHEZZA COMPLESSIVA (INCLUSE LE SPALLE - m)'),
                          num('LUCE TOT (SPALLA/SPALLA - m)'), num('LARGHEZZA ALVEO INCISO (m)'))
k = gpd.read_file(gpkg, layer='kml_abbinato').set_index('ID').to_crs(32633)
kt = gpd.read_file(gpkg, layer='kml_tracciati').to_crs(32633).set_index('nome').geometry
tu = gpd.read_file(gpkg, layer='tracciato_usato').set_index('ID').to_crs(32633).geometry
tr_utm = Transformer.from_crs('EPSG:4326', 'EPSG:32633', always_xy=True)
crs = Proj('EPSG:32633', preserve_units=True)


def flusso(lim):
    with rasterio.open(dem_path) as src:
        w = from_bounds(*lim, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w)
        T = src.window_transform(w)
        z = (a.astype(np.float64) * src.scales[0]).astype(np.float32)
        z[a == src.nodata] = -9999
    del a
    vf = ViewFinder(affine=T, shape=z.shape, nodata=np.float32(-9999), crs=crs)
    grid = Grid(viewfinder=vf)
    dem = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(Raster(z, vf))), eps=1e-6, max_iter=10000)
    del z
    fdir = grid.flowdir(dem, dirmap=DIRMAP)
    del dem
    return grid, fdir, grid.accumulation(fdir, dirmap=DIRMAP), T


def valle(F, r, c, n):
    """Celle a valle di (r, c), lei compresa, per al massimo n passi."""
    out_ = [(r, c)]
    for _ in range(n):
        d = int(F[r, c])
        if d not in PASSO:
            break
        r, c = r + PASSO[d][0], c + PASSO[d][1]
        if not (0 <= r < F.shape[0] and 0 <= c < F.shape[1]):
            break
        out_.append((r, c))
    return out_


def monte_principale(F, A, r, c, n):
    """Asta principale a monte di (r, c): ad ogni passo la cella entrante con accumulo maggiore."""
    out_ = [(r, c)]
    for _ in range(n):
        best = None
        for d, (dr, dc) in PASSO.items():
            rr, cc = r - dr, c - dc
            if 0 <= rr < F.shape[0] and 0 <= cc < F.shape[1] and F[rr, cc] == d:
                if best is None or A[rr, cc] > A[best]:
                    best = (rr, cc)
        if best is None:
            break
        r, c = best
        out_.append(best)
    return out_


def affluenti(F, A, percorso, soglia):
    """Affluenti di reticolo che entrano nelle celle del percorso (escluso il primo tratto)."""
    trib = []
    insieme = set(percorso)
    for k_, (r, c) in enumerate(percorso[1:], start=1):
        prima = percorso[k_ - 1]
        for d, (dr, dc) in PASSO.items():
            rr, cc = r - dr, c - dc
            if (rr, cc) != prima and (rr, cc) not in insieme and 0 <= rr < F.shape[0] and 0 <= cc < F.shape[1] \
                    and F[rr, cc] == d and A[rr, cc] > soglia:
                trib.append(float(A[rr, cc]) * C5 * C5 / 1e6)
    return trib


def lunghezza(percorso):
    return sum(np.hypot(r2 - r1, c2 - c1) * C5 for (r1, c1), (r2, c2) in zip(percorso[:-1], percorso[1:]))


def linea(T, celle):
    pts = [(T.c + (c + 0.5) * C5, T.f - (r + 0.5) * C5) for r, c in celle]
    return LineString(pts) if len(pts) > 1 else Point(pts[0])


righe = []
ids = sorted(O.index)
for porz, g in P.loc[ids].groupby('porzione'):
    grid, fdir, acc, T = flusso(tuple(g.iloc[0][['xmin', 'ymin', 'xmax', 'ymax']]))
    F, A = np.asarray(fdir), np.asarray(acc)
    nmax = int(RAGGIO_ASTA_M / C5)
    for i, p in g.iterrows():
        soglia = int(p.soglia) if pd.notna(p.get('soglia')) else ACC_THRESHOLD
        tr = kt.get(k.loc[i, 'KML_nome'])
        if tr is None:
            tr = tu.get(i)
        x1, y1 = tr_utm.transform(p.X, p.Y)
        xs1, ys1 = grid.snap_to_mask(acc > soglia, (x1, y1))
        c1, r1 = ~T * (xs1, ys1)
        r1, c1 = int(r1), int(c1)
        q = A0.loc[i]
        x0, y0 = tr_utm.transform(q.X, q.Y)
        dentro = T.c < x0 < T.c + F.shape[1] * C5 and T.f - F.shape[0] * C5 < y0 < T.f
        riga = {'ID': i, 'Origine proposta': O[i], 'A_db_km2': adb[i], 'Soglia_celle': soglia,
                'Lunghezza ponte DB (m)': lung.get(i), 'Luce (m)': luce.get(i), 'Alveo (m)': alveo.get(i)}
        sotto = np.nanmax([lung.get(i, np.nan), luce.get(i, np.nan), alveo.get(i, np.nan), 0]) / 2 + MARGINE_M
        d_tr = tr.distance(Point(xs1, ys1)) if tr is not None else np.nan
        asta1 = linea(T, monte_principale(F, A, r1, c1, nmax)[::-1] + valle(F, r1, c1, nmax)[1:])
        riga.update({'Dist proposto-tracciato (m)': round(d_tr), 'Soglia sotto il ponte (m)': round(sotto),
                     'Sotto il ponte': bool(d_tr <= sotto),
                     'Tracciato attraversa corso proposto': bool(tr is not None and tr.distance(asta1) <= TOLL_TRACCIATO_M)})
        if not dentro:
            riga.update({'Relazione': 'punto attuale fuori dalla porzione (lontano dal ponte)',
                         'Tracciato attraversa corso attuale': False})
        else:
            xs0, ys0 = grid.snap_to_mask(acc > ACC_THRESHOLD, (x0, y0))
            c0, r0 = ~T * (xs0, ys0)
            r0, c0 = int(r0), int(c0)
            asta0 = linea(T, monte_principale(F, A, r0, c0, nmax)[::-1] + valle(F, r0, c0, nmax)[1:])
            riga['Tracciato attraversa corso attuale'] = bool(tr is not None and tr.distance(asta0) <= TOLL_TRACCIATO_M)
            v0, v1 = valle(F, r0, c0, 4000), valle(F, r1, c1, 4000)
            if (r1, c1) in v0:
                perc = v0[:v0.index((r1, c1)) + 1]
                rel = 'stesso corso, proposto a valle'
            elif (r0, c0) in v1:
                perc = v1[:v1.index((r0, c0)) + 1]
                rel = 'stesso corso, proposto a monte'
            else:
                perc = None
                s1 = set(v1)
                j = next((kk for kk, cc_ in enumerate(v0) if cc_ in s1), None)
                if j is None:
                    rel = 'altro corso (nessuna confluenza entro 20 km)'
                else:
                    rel = (f'altro corso, confluenza a {lunghezza(v0[:j + 1]):.0f} m dal punto attuale e '
                           f'{lunghezza(v1[:v1.index(v0[j]) + 1]):.0f} m dal proposto')
            riga['Relazione'] = rel
            if perc is not None:
                t = affluenti(F, A, perc, soglia)
                riga.update({'Distanza lungo asta (m)': round(lunghezza(perc)), 'Affluenti scavalcati': len(t),
                             'Area affluente maggiore (km²)': round(max(t), 3) if t else 0,
                             'Area affluenti totale (km²)': round(sum(t), 3)})
        # indicazione
        o = riga
        if O[i].startswith('sezione sul tracciato'):
            ind, mot = 'SI', "Sezione sul tracciato del ponte nel KML; il punto attuale era lontano dal ponte."
        elif o['Relazione'].startswith('stesso corso'):
            if o['Sotto il ponte']:
                ind = 'SI'
                mot = 'Stesso corso, punto proposto entro l\'impronta del ponte/alveo'
                if o.get('Affluenti scavalcati', 0):
                    mot += (f"; l'affluente ({o['Area affluente maggiore (km²)']} km²) entra all'altezza del ponte: "
                            "verificare che confluisca sotto o subito accanto al ponte")
                    ind = 'SI (confluenza al ponte)'
            elif o.get('Affluenti scavalcati', 0) == 0:
                ind, mot = 'da guardare', 'Stesso corso senza affluenti in mezzo, ma il punto proposto e\' fuori dall\'impronta del ponte'
            else:
                ind, mot = 'da guardare', (f"Stesso corso, fuori dall'impronta del ponte e scavalca "
                                           f"{o['Affluenti scavalcati']} affluente/i: verificare dove confluiscono")
        else:
            if o['Tracciato attraversa corso proposto'] and not o['Tracciato attraversa corso attuale']:
                ind, mot = 'SI', 'Altro corso, ma il tracciato del ponte attraversa il corso proposto e non quello attuale'
            elif o['Tracciato attraversa corso proposto'] and o['Tracciato attraversa corso attuale']:
                ind, mot = 'da guardare', 'Il tracciato attraversa entrambi i corsi: verificare quale scavalca il ponte'
            else:
                ind, mot = 'da guardare', 'Altro corso e il tracciato non lo attraversa: verificare sull\'ortofoto'
        riga['Indicazione'], riga['Motivo'] = ind, mot
        righe.append(riga)
        print(porz, riga, flush=True)
    del grid, fdir, acc, F, A
pd.DataFrame(righe).sort_values('ID').to_csv(os.path.join(out, 'indicazioni_revisione.csv'), index=False)
