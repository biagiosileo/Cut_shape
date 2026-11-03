"""
Calcolo di parametri morfometrici di bacino per ponti fluviali.

Per ciascun ponte fornito in ingresso, lo script:
  1. condiziona il DEM (pit filling, depression filling, resolve flats);
  2. calcola direzione di flusso D8 e accumulo di flusso;
  3. estrae il reticolo idrografico (soglia di accumulo configurabile);
  4. delinea il bacino idrografico chiuso alla sezione del ponte;
  5. calcola area, pendenza media, quota media, curve number medio, form
     factor, lunghezza del percorso di flusso piu lungo, perimetro e un
     insieme di descrittori morfometrici derivati (Melton, integrale
     ipsometrico, compattezza, circolarita, ecc.);
  6. calcola la pendenza locale di canale su un tratto centrato sulla
     sezione del ponte, risalendo/scendendo il reticolo idrografico;
  7. converte in poligono vettoriale il bacino delineato per ciascun ponte.

# [MODIFICA 5 m] DEM unico letto a porzioni.
Lanciato senza argomenti, lo script elabora una porzione alla volta, ciascuna in un
processo separato (memoria liberata tra una porzione e l'altra), poi riunisce i
risultati in output_csv, bacini_afferenti.geojson e reticolo_idrografico.geojson. Le porzioni (colonne porzione,
xmin, ymin, xmax, ymax del CSV) contengono per intero i bacini dei loro ponti.
Una porzione gia' elaborata (file in porzioni/) viene saltata: il lancio si puo'
interrompere e riprendere. Per una sola porzione: python pysheds_bridges_5m.py porzione_NN

Input attesi:
  - DEM unico in GeoTIFF (dem_path), in CRS proiettato (metrico); quote in cm con scala 0,01.
  - Raster Curve Number (cn_path), allineato alla stessa griglia del DEM
    (stessa shape, stessa risoluzione, stesso CRS).
  - CSV dei ponti (input_csv) con colonne id, X, Y, dove X e Y sono
    coordinate geografiche WGS84 (longitudine, latitudine), piu' le colonne
    porzione, xmin, ymin, xmax, ymax (porzione di DEM da leggere, in UTM 33N)
    e la colonna facoltativa soglia (soglia di aggancio ridotta per i fossi).
    L'id e' quello del database (1-212) e viene riportato invariato in uscita.

Output:
  - CSV con un record per ponte e i parametri morfometrici calcolati
    (output_csv).
  - GeoJSON del reticolo idrografico estratto, per controllo visivo in un
    software GIS (reticolo_idrografico.geojson).
  - GeoJSON dei bacini afferenti, un poligono per ponte, con proprieta
    ID e A_km2 (bacini_afferenti.geojson).
"""
from pysheds.grid import Grid
from pyproj import Transformer, Proj
import pandas as pd
import numpy as np
# [MODIFICA 5 m] compatibilita' con numpy 2 (pysheds usa np.in1d, rimosso in numpy 2)
if not hasattr(np, "in1d"):
    np.in1d = np.isin
import os
import sys
import subprocess
import rasterio
from rasterio.windows import from_bounds
from pysheds.sview import Raster, ViewFinder
import json

# ================== CONFIGURAZIONE ==================
# Nomi dei file, cercati nella cartella da cui si lancia lo script.
dem_path = "dem5m_unico.tif"  # [MODIFICA 5 m]
cn_path = "cn5m_unico.tif"  # [MODIFICA 5 m]
input_csv = "ponti.csv"  # [MODIFICA 5 m] id, X, Y + porzione, xmin, ymin, xmax, ymax
output_csv = "parametri morfologici.csv"

# CRS del DEM: UTM 33N (WGS84). Nel codice iniziale il DEM era un ASCII grid
# senza CRS e il CRS veniva dichiarato qui; il DEM unico GeoTIFF e' gia' in
# EPSG:32633, il valore resta dichiarato esplicitamente e viene passato a
# pysheds al momento della lettura di ogni porzione (funzione leggi_porzione).
DEM_CRS = "EPSG:32633"

# CRS delle coordinate dei ponti nel CSV in ingresso (WGS84 geografiche).
BRIDGE_CSV_CRS = "EPSG:4326"

# Soglia di accumulo di flusso (numero di celle contribuenti) che definisce
# una cella come appartenente al reticolo idrografico. Da tarare sul DEM in
# uso, confrontando l'istogramma di grid.accumulation() con l'idrografia nota
# dell'area di studio.
ACC_THRESHOLD = 4000  # [MODIFICA 5 m] 4000 celle x 25 m2 = 0,1 km2 (era 500)

# Lunghezza del tratto di canale (in metri), centrato sulla sezione del
# ponte, su cui viene calcolata la pendenza locale (meta' a monte, meta' a
# valle lungo il reticolo idrografico).
REACH_LENGTH_CENTERED_M = 500.0

# grid.snap_to_mask sposta il punto sulla cella di canale piu' vicina senza
# alcun limite di distanza incorporato: se il punto originale e' lontano da
# qualunque cella del reticolo (coordinate imprecise, soglia troppo alta,
# tributario mancante), l'aggancio puo' avvenire comunque, anche a grande
# distanza o sul corso d'acqua sbagliato, senza segnalarlo. Questa soglia
# (in metri) genera un avviso esplicito quando la distanza di snap la supera,
# cosi' da poter controllare visivamente i casi dubbi in un software GIS.
SNAP_DISTANCE_WARNING_M = 10.0  # [MODIFICA 5 m] i punti sono gia' sul reticolo (era 50)

# Codici D8 delle 8 direzioni nell'ordine N, NE, E, SE, S, SW, W, NW
# (convenzione ESRI usata da pysheds).
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)

# ---------------- Caricamento raster ----------------
# Oggetto CRS passato a pysheds (ViewFinder) per ogni porzione letta.
# Nel codice iniziale qui si leggeva l'intero DEM ASCII con Grid.from_ascii;
# ora il DEM unico (troppo grande per la memoria) si legge a porzioni:
# vedi le due modalita' di lancio qui sotto.
dem_crs_obj = Proj(DEM_CRS, preserve_units=True)

# [MODIFICA 5 m] ---- modalita' generale: una porzione per processo, poi unione dei risultati ----
# Cartella dei risultati intermedi, un gruppo di file per porzione:
#   porzioni/<porzione>_parametri.csv, _bacini_afferenti.geojson, _reticolo_idrografico.geojson
CARTELLA_PORZIONI = "porzioni"
if len(sys.argv) == 1:
    # Lancio senza argomenti: elenco delle porzioni presenti in ponti.csv.
    os.makedirs(CARTELLA_PORZIONI, exist_ok=True)
    porzioni = sorted(pd.read_csv(input_csv)['porzione'].unique())
    for n, porz in enumerate(porzioni, 1):
        fatto = os.path.join(CARTELLA_PORZIONI, f"{porz}_parametri.csv")
        if os.path.exists(fatto):
            print(f"[{n}/{len(porzioni)}] {porz}: gia' elaborata, saltata.")
            continue
        print(f"[{n}/{len(porzioni)}] {porz}: avvio.", flush=True)
        # lo script rilancia se stesso con il nome della porzione: ogni porzione gira in un
        # processo separato, cosi' la memoria (DEM, accumulo, direzioni) viene liberata alla fine
        subprocess.run([sys.executable, os.path.abspath(__file__), porz], check=True)
    # Unione dei parametri di tutte le porzioni in un solo CSV, ordinato per ID del database.
    tab = pd.concat([pd.read_csv(os.path.join(CARTELLA_PORZIONI, f"{p}_parametri.csv")) for p in porzioni])
    tab.sort_values('ID').to_csv(output_csv, index=False)
    # Unione dei poligoni dei bacini in un solo GeoJSON, ordinati per ID.
    feats = []
    for p in porzioni:
        with open(os.path.join(CARTELLA_PORZIONI, f"{p}_bacini_afferenti.geojson")) as f:
            gj = json.load(f)
        feats += gj['features']
    gj['features'] = sorted(feats, key=lambda ft: ft['properties']['ID'])
    with open("bacini_afferenti.geojson", "w") as f:
        json.dump(gj, f)
    # reticolo unico: i rami delle porzioni vengono dissolti, cosi' i tratti comuni a porzioni
    # sovrapposte compaiono una volta sola; la linea viene spezzata alle confluenze
    import geopandas as gpd
    import shapely
    from shapely.geometry import shape
    # lettura dei rami di tutte le porzioni, unione geometrica, fusione dei tratti contigui
    rami = []
    for p in porzioni:
        with open(os.path.join(CARTELLA_PORZIONI, f"{p}_reticolo_idrografico.geojson")) as f:
            rami += [shape(ft['geometry']) for ft in json.load(f)['features']]
    unito = shapely.line_merge(shapely.unary_union(rami))
    ret = gpd.GeoDataFrame(geometry=[unito], crs=DEM_CRS).explode(index_parts=False).reset_index(drop=True)
    ret['geometry'] = shapely.simplify(ret.geometry.values, 0.01)  # toglie solo i vertici allineati (1 cm)
    ret = ret[~ret.geometry.is_empty & (ret.geometry.length > 0)].reset_index(drop=True)
    # numero progressivo del ramo e lunghezza in metri come attributi
    ret.insert(0, 'id_ramo', range(1, len(ret) + 1))
    ret['lung_m'] = ret.geometry.length.round(1)
    ret.to_file("reticolo_idrografico.geojson", driver="GeoJSON")
    print(f"Reticolo unico in reticolo_idrografico.geojson: {len(ret)} tratti, "
          f"{ret['lung_m'].sum() / 1000:.0f} km (CRS: {DEM_CRS}).")
    print(f"Completato: {len(tab)} ponti in {output_csv}, bacini in bacini_afferenti.geojson.")
    sys.exit(0)

# [MODIFICA 5 m] ---- modalita' porzione: si leggono solo la porzione di DEM e di CN ----
# Lancio con un argomento (python pysheds_bridges_5m.py porzione_NN), fatto in automatico
# dalla modalita' generale: si elaborano solo i ponti di quella porzione.
PORZIONE = sys.argv[1]
_ponti = pd.read_csv(input_csv)
_ponti = _ponti[_ponti['porzione'] == PORZIONE]
if _ponti.empty:
    raise SystemExit(f"Nessun ponte nella porzione {PORZIONE}.")
# limiti della porzione (UTM 33N), uguali per tutti i ponti della stessa porzione
_limiti = tuple(_ponti.iloc[0][['xmin', 'ymin', 'xmax', 'ymax']])
print(f"{PORZIONE}: {len(_ponti)} ponti.")


def leggi_porzione(path, limiti, dtype, nodata_out):
    """Legge solo la porzione richiesta; applica il fattore di scala del file
    (il DEM unico e' salvato in centimetri interi con scala 0,01)."""
    with rasterio.open(path) as src:
        # finestra di righe e colonne del raster corrispondente ai limiti, arrotondata alle celle
        w = from_bounds(*limiti, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w)
        # georeferenziazione della sola finestra letta
        affine = src.window_transform(w)
        # celle senza dato (nodata del file o NaN), da marcare con nodata_out
        senza_dato = (a == src.nodata) | np.isnan(a) if src.nodata is not None else np.isnan(a)
        # conversione nel tipo richiesto e da centimetri a metri (scala 0,01, offset 0)
        a = a.astype(dtype) * src.scales[0] + src.offsets[0]
    a[senza_dato] = nodata_out
    # raster pysheds con affine, nodata e CRS della porzione
    vf = ViewFinder(affine=affine, shape=a.shape, nodata=a.dtype.type(nodata_out), crs=dem_crs_obj)
    return Raster(a, vf)


# DEM della porzione in metri (float64, senza dato = -9999)
dem = leggi_porzione(dem_path, _limiti, np.float64, -9999.0)
# arrotondamento al centimetro: elimina i residui della conversione cm -> m
_v = dem != -9999
dem[_v] = np.round(dem[_v], 2)  # quote in metri al cm
del _v
# griglia pysheds definita sulla porzione del DEM
grid = Grid(viewfinder=dem.viewfinder)
# Curve Number sulla stessa porzione (stessa griglia del DEM; senza dato = NaN)
cn_grid = leggi_porzione(cn_path, _limiti, np.float32, np.nan)

if cn_grid.shape != dem.shape:
    raise ValueError(
        "Il raster Curve Number non ha la stessa shape del DEM "
        f"(CN: {cn_grid.shape}, DEM: {dem.shape}). I due raster vanno "
        "riallineati sulla stessa griglia (es. con rasterio.warp.reproject) "
        "prima di procedere."
    )

# ---------------- Condizionamento del DEM ----------------
# 1) riempimento delle singole celle depresse (pit)
# 2) riempimento delle depressioni piu' estese
# 3) risoluzione delle aree piatte (leggera pendenza artificiale verso l'uscita)
pit_filled = grid.fill_pits(dem)
flooded = grid.fill_depressions(pit_filled)
# [MODIFICA 5 m] con i valori di default (eps=1e-5, max_iter=1000) sulle grandi aree piatte
# l'innalzamento supera 1 cm e crea pozzi artificiali che interrompono il bacino (ponti 24, 25)
inflated_dem = grid.resolve_flats(flooded, eps=1e-6, max_iter=10000)

# ---------------- Direzione di flusso e accumulo ----------------
# direzione D8 di ogni cella e numero di celle drenate da ciascuna cella (accumulo)
fdir = grid.flowdir(inflated_dem, dirmap=DIRMAP)
acc = grid.accumulation(fdir, dirmap=DIRMAP)

# ---------------- Geometria D8 ----------------
# Offset (riga, colonna) associati a ciascun codice di direzione D8 usato da
# pysheds (DIRMAP), e relativa direzione opposta (necessaria per risalire il
# reticolo a ritroso rispetto al flusso). Definiti una sola volta e riusati
# sia per il calcolo della pendenza sia per il tracciamento del reticolo.
DIR_OFFSETS = {
    64: (-1, 0),   # N
    128: (-1, 1),  # NE
    1: (0, 1),     # E
    2: (1, 1),     # SE
    4: (1, 0),     # S
    8: (1, -1),    # SW
    16: (0, -1),   # W
    32: (-1, -1),  # NW
}
DIR_OPPOSITE = {64: 4, 4: 64, 128: 8, 8: 128, 1: 16, 16: 1, 2: 32, 32: 2}

cellsize_x = grid.affine.a
cellsize_y = -grid.affine.e  # affine.e e negativo per convenzione (Nord->Sud)
diag_len = float(np.hypot(cellsize_x, cellsize_y))
DIR_DISTANCES = {
    64: cellsize_y, 4: cellsize_y,                    # N, S
    1: cellsize_x, 16: cellsize_x,                    # E, W
    128: diag_len, 2: diag_len, 8: diag_len, 32: diag_len,  # diagonali
}

# ---------------- Pendenza di bacino ----------------
# La pendenza locale di ciascuna cella e' definita come la massima pendenza
# discendente (dislivello/distanza) verso una delle 8 celle adiacenti
# (metodo D8), coerentemente con la definizione di "local maximum slope"
# della metodologia di riferimento (D'Angelo et al., 2025) e con la stessa
# logica D8 gia' usata per la direzione di flusso.
def compute_d8_max_slope(elevation, offsets, distances):
    """Calcola, per ciascuna cella della matrice elevation, la massima
    pendenza discendente (dislivello/distanza) verso una delle 8 celle
    adiacenti secondo lo schema di direzioni D8. Le celle di bordo sono
    trattate per replicazione del bordo (nessun confronto oltre il limite
    della matrice)."""
    Z = np.asarray(elevation, dtype=float)
    Zpad = np.pad(Z, 1, mode='edge')
    max_slope = np.zeros_like(Z)
    for code, (dr, dc) in offsets.items():
        neighbor = Zpad[1 + dr:1 + dr + Z.shape[0], 1 + dc:1 + dc + Z.shape[1]]
        drop = (Z - neighbor) / distances[code]
        max_slope = np.maximum(max_slope, np.where(drop > 0, drop, 0.0))
    return max_slope


# pendenza locale (m/m) di tutte le celle della porzione, sul DEM condizionato
slope = compute_d8_max_slope(inflated_dem, DIR_OFFSETS, DIR_DISTANCES)

# ---------------- Reticolo idrografico ----------------
# Estrazione della rete vettoriale dei rami di canale, per controllo visivo
# (sovrapposizione a DEM/idrografia nota in un software GIS) e a supporto
# della taratura di ACC_THRESHOLD.
river_network = grid.extract_river_network(fdir, acc > ACC_THRESHOLD, dirmap=DIRMAP)
n_branches = len(river_network.get('features', []))
print(f"Reticolo idrografico estratto: {n_branches} rami (soglia acc > {ACC_THRESHOLD} celle).")

# Le coordinate delle geometrie sono nel CRS del DEM (metri, non gradi), ma
# il formato GeoJSON assume WGS84 (EPSG:4326) quando non viene dichiarato
# esplicitamente un CRS diverso: senza questa dichiarazione, un software GIS
# interpreterebbe le coordinate piane come se fossero gradi, con un
# posizionamento privo di senso. Si aggiunge quindi il CRS esplicitamente.
epsg_code = DEM_CRS.split(':')[-1]
river_network['crs'] = {
    'type': 'name',
    'properties': {'name': f'urn:ogc:def:crs:EPSG::{epsg_code}'}
}

# reticolo della porzione; la modalita' generale lo unisce poi a quello delle altre porzioni
with open(os.path.join(CARTELLA_PORZIONI, f"{PORZIONE}_reticolo_idrografico.geojson"), "w") as f:  # [MODIFICA 5 m]
    json.dump(river_network, f)
print(f"Reticolo salvato in {CARTELLA_PORZIONI}/{PORZIONE}_reticolo_idrografico.geojson (CRS: {DEM_CRS}).")

# ---------------- Bacini afferenti (vettoriale) ----------------
# Ogni bacino delineato per un ponte (maschera booleana) viene convertito in
# poligono con grid.polygonize, che si appoggia a rasterio.features.shapes.
# I poligoni di tutti i ponti vengono raccolti in un'unica FeatureCollection,
# con lo stesso schema di CRS esplicito usato per il reticolo idrografico.
def polygonize_basin(grid_obj, basin_mask):
    """Converte la maschera booleana di un bacino in una geometria GeoJSON
    (Polygon o MultiPolygon se il bacino risultasse in piu' parti separate),
    nello stesso CRS della griglia. Restituisce None se la maschera non
    produce alcun poligono."""
    basin_uint8 = basin_mask.astype(np.uint8)
    shapes = list(grid_obj.polygonize(basin_uint8))
    polygons = [geom for geom, value in shapes if value == 1]
    if not polygons:
        return None
    if len(polygons) == 1:
        return polygons[0]
    return {
        'type': 'MultiPolygon',
        'coordinates': [p['coordinates'] for p in polygons],
    }


# elenco dei poligoni dei bacini dei ponti della porzione
basin_features = []

# La pendenza di tratto e calcolata risalendo/scendendo il reticolo in forma
# raster (maschera acc > ACC_THRESHOLD), cella per cella, seguendo alle
# confluenze il ramo con accumulo maggiore (canale principale).
fdir_arr = np.asarray(fdir)
acc_arr = np.asarray(acc)
dem_arr = np.asarray(dem, dtype=float)  # quota reale, non condizionata
n_rows_grid, n_cols_grid = fdir_arr.shape


def upstream_main_channel_cell(row, col):
    """Restituisce la cella immediatamente a monte lungo il reticolo
    idrografico (acc > ACC_THRESHOLD), selezionando il ramo con accumulo di
    flusso maggiore in corrispondenza di una confluenza. Restituisce None se
    la cella corrisponde a una testata del reticolo."""
    best = None
    best_acc = -1.0
    for code, (dr, dc) in DIR_OFFSETS.items():
        rr, cc = row + dr, col + dc
        if 0 <= rr < n_rows_grid and 0 <= cc < n_cols_grid:
            if fdir_arr[rr, cc] == DIR_OPPOSITE[code] and acc_arr[rr, cc] > ACC_THRESHOLD:
                if acc_arr[rr, cc] > best_acc:
                    best_acc = acc_arr[rr, cc]
                    best = (rr, cc)
    return best


def trace_upstream(row0, col0, dist_target, max_steps=10000):
    """Risale il canale principale a partire da (row0, col0) fino a
    percorrere una distanza planimetrica pari a dist_target lungo il
    reticolo, o fino a raggiungere una testata. Restituisce la cella di
    arrivo e la distanza effettivamente percorsa: (row, col, distanza)."""
    row, col = row0, col0
    dist_accum = 0.0
    for _ in range(max_steps):
        if dist_accum >= dist_target:
            break
        nxt = upstream_main_channel_cell(row, col)
        if nxt is None:
            break
        dr, dc = nxt[0] - row, nxt[1] - col
        step_len = diag_len if (dr != 0 and dc != 0) else (cellsize_y if dr != 0 else cellsize_x)
        dist_accum += step_len
        row, col = nxt
    return row, col, dist_accum


def trace_downstream(row0, col0, dist_target, max_steps=10000):
    """Segue la direzione di flusso D8 a partire da (row0, col0) fino a
    percorrere una distanza planimetrica pari a dist_target, o fino a
    raggiungere un bordo della griglia o una cella con direzione di flusso
    non definita. Restituisce la cella di arrivo e la distanza
    effettivamente percorsa: (row, col, distanza)."""
    row, col = row0, col0
    dist_accum = 0.0
    for _ in range(max_steps):
        if dist_accum >= dist_target:
            break
        code = int(fdir_arr[row, col])
        offset = DIR_OFFSETS.get(code)
        if offset is None:
            break
        dr, dc = offset
        rr, cc = row + dr, col + dc
        if not (0 <= rr < n_rows_grid and 0 <= cc < n_cols_grid):
            break
        step_len = diag_len if (dr != 0 and dc != 0) else (cellsize_y if dr != 0 else cellsize_x)
        dist_accum += step_len
        row, col = rr, cc
    return row, col, dist_accum


def longest_flow_path_bfs(row0, col0, basin_mask):
    """Calcola la distanza planimetrica massima, lungo la direzione di
    flusso D8, tra la sezione di chiusura (row0, col0) e la cella piu'
    lontana all'interno del bacino delineato (basin_mask). Esplora il
    bacino a ritroso rispetto alla direzione di flusso, dalla sezione di
    chiusura verso monte, visitando ciascuna cella una sola volta, e
    restituisce la distanza cumulata massima riscontrata."""
    from collections import deque
    max_dist = 0.0
    visited = np.zeros(basin_mask.shape, dtype=bool)
    queue = deque()
    queue.append((row0, col0, 0.0))
    visited[row0, col0] = True
    while queue:
        r, c, d = queue.popleft()
        if d > max_dist:
            max_dist = d
        for code, (dr, dc) in DIR_OFFSETS.items():
            rr, cc = r + dr, c + dc
            if 0 <= rr < n_rows_grid and 0 <= cc < n_cols_grid:
                if (not visited[rr, cc]) and basin_mask[rr, cc] and fdir_arr[rr, cc] == DIR_OPPOSITE[code]:
                    step_len = diag_len if (dr != 0 and dc != 0) else (cellsize_y if dr != 0 else cellsize_x)
                    visited[rr, cc] = True
                    queue.append((rr, cc, d + step_len))
    return max_dist


def reach_slope_centered(row0, col0, total_length_m, max_steps=10000):
    """Calcola la pendenza media su un tratto di canale centrato sulla cella
    (row0, col0), esteso per meta' a monte e meta' a valle lungo il reticolo
    idrografico, per una lunghezza complessiva pari a total_length_m.
    Restituisce la pendenza (positiva se il canale scende verso valle) e la
    lunghezza complessiva effettivamente percorsa: (pendenza, lunghezza)."""
    half = total_length_m / 2.0
    row_up, col_up, dist_up = trace_upstream(row0, col0, half, max_steps)
    row_down, col_down, dist_down = trace_downstream(row0, col0, half, max_steps)
    elev_up = dem_arr[row_up, col_up]
    elev_down = dem_arr[row_down, col_down]
    total_dist = dist_up + dist_down
    if total_dist <= 0 or np.isnan(elev_up) or np.isnan(elev_down):
        return np.nan, total_dist
    return float((elev_up - elev_down) / total_dist), total_dist


# ---------------- Coordinate dei ponti ----------------
# Le coordinate del CSV, in BRIDGE_CSV_CRS (WGS84 geografiche), vengono
# trasformate nel CRS del DEM (DEM_CRS, UTM 33N) prima di ogni operazione
# sulla griglia.
print("CRS dichiarato per il DEM:", DEM_CRS)
transformer = Transformer.from_crs(BRIDGE_CSV_CRS, DEM_CRS, always_xy=True)

# estensione della porzione: un ponte fuori da questi limiti viene escluso
xmin, ymin, xmax, ymax = grid.bbox

df = _ponti[["id", "X", "Y"] + (["soglia"] if "soglia" in _ponti else [])]  # [MODIFICA 5 m] solo i ponti della porzione
results = []
print(f"Elaborazione di {len(df)} ponti.")

# ==================== Ciclo sui ponti della porzione ====================
for _, row in df.iterrows():
    # ID del database (1-212): resta invariato in tutti gli output
    bridge_id = row['id']
    lon, lat = row['X'], row['Y']
    x, y = transformer.transform(lon, lat)
    print(f"Ponte {bridge_id}: avvio elaborazione (potrebbe richiedere qualche minuto "
          f"alla prima esecuzione, per la compilazione JIT di numba).")

    if not (xmin <= x <= xmax and ymin <= y <= ymax):
        print(f"Ponte {bridge_id}: coordinate trasformate ({x:.1f}, {y:.1f}) "
              f"fuori dall'estensione del DEM ({xmin:.1f}-{xmax:.1f}, "
              f"{ymin:.1f}-{ymax:.1f}); ponte escluso.")
        continue

    # Individuazione della cella di canale piu vicina al ponte, sulla base
    # della soglia di accumulo di flusso. snap_to_mask non applica alcun
    # limite di distanza: la distanza effettiva viene quindi calcolata e
    # controllata esplicitamente qui sotto.
    try:
        # [MODIFICA 5 m] soglia per singolo ponte (colonna facoltativa "soglia" di ponti.csv, per i fossi piccoli)
        # di norma si aggancia al reticolo con acc > ACC_THRESHOLD (0,1 km2); se in ponti.csv
        # la colonna soglia e' compilata, si usa quel valore (es. 1000 celle = 0,025 km2)
        _soglia = ACC_THRESHOLD
        if "soglia" in row and pd.notna(row["soglia"]):
            _soglia = int(row["soglia"])
            print(f"Ponte {bridge_id}: soglia di aggancio ridotta a {_soglia} celle.")
        # spostamento del punto sulla cella di reticolo piu' vicina
        x_snap, y_snap = grid.snap_to_mask(acc > _soglia, (x, y))
        # distanza dello spostamento, riportata in uscita (Snap_Distance_m)
        snap_distance_m = float(np.hypot(x_snap - x, y_snap - y))
        print(f"Ponte {bridge_id}: snap completato (distanza dal punto originale: "
              f"{snap_distance_m:.1f} m).")
        if snap_distance_m > SNAP_DISTANCE_WARNING_M:
            print(f"Ponte {bridge_id}: ATTENZIONE - distanza di snap elevata "
                  f"({snap_distance_m:.1f} m > {SNAP_DISTANCE_WARNING_M:.0f} m); "
                  f"verificare in un software GIS che il punto sia stato agganciato "
                  f"al corso d'acqua corretto.")
    except Exception as e:
        print(f"Ponte {bridge_id}: snap del punto non riuscito ({e}); ponte escluso.")
        continue

    # Delineazione del bacino idrografico chiuso alla sezione del ponte.
    try:
        basin = grid.catchment(x=x_snap, y=y_snap, fdir=fdir, dirmap=DIRMAP,
                                xytype='coordinate')
        print(f"Ponte {bridge_id}: bacino delineato ({int(np.sum(basin))} celle).")
        # [MODIFICA 5 m] controllo: un bacino che arriva al bordo della porzione puo' essere troncato
        # basta una cella del bacino nelle prime/ultime 2 righe o colonne della porzione
        _b = np.asarray(basin)
        if _b[:2].any() or _b[-2:].any() or _b[:, :2].any() or _b[:, -2:].any():
            print(f"Ponte {bridge_id}: ATTENZIONE - il bacino arriva al bordo di {PORZIONE}: "
                  f"possibile bacino troncato, allargare la porzione (xmin, ymin, xmax, ymax in {input_csv}).")
    except Exception as e:
        print(f"Ponte {bridge_id}: delineazione del bacino non riuscita ({e}); ponte escluso.")
        continue

    if not np.any(basin):
        print(f"Ponte {bridge_id}: bacino delineato vuoto; ponte escluso.")
        continue

    # quote reali (non condizionate) del solo bacino, NaN fuori dal bacino
    dem_basin = np.asarray(dem, dtype=float).copy()
    dem_basin[~basin] = np.nan

    # ==================== Parametri morfometrici di bacino ====================
    # area (km2) = numero di celle x area della cella (25 m2);
    # S = pendenza media di bacino (m/m); AE = quota media di bacino (m)
    n_cells = int(np.sum(basin))
    A = n_cells * (cellsize_x * cellsize_y) / 1e6          # km^2
    S = float(np.nanmean(slope[basin]))
    AE = float(np.nanmean(dem_basin))

    # poligono del bacino, salvato con ID e area
    basin_geom = polygonize_basin(grid, basin)
    if basin_geom is not None:
        basin_features.append({
            'type': 'Feature',
            'geometry': basin_geom,
            'properties': {'ID': bridge_id, 'A_km2': round(A, 3)},
        })
        print(f"Ponte {bridge_id}: poligono del bacino generato.")
    else:
        print(f"Ponte {bridge_id}: poligonizzazione del bacino non riuscita (nessun poligono).")

    # riga e colonna della sezione di chiusura e pendenza locale in quella cella
    col_idx, row_idx = grid.nearest_cell(x_snap, y_snap)
    cell_slope = float(slope[row_idx, col_idx])

    L = longest_flow_path_bfs(row_idx, col_idx, basin) / 1000  # km
    print(f"Ponte {bridge_id}: lunghezza massima del percorso di flusso calcolata.")

    # descrittori derivati: rilievo, form factor, CN medio, Melton, integrale ipsometrico,
    # rapporto di allungamento, fattore di forma (formule invariate rispetto al codice iniziale)
    relief = float(np.nanmax(dem_basin) - np.nanmin(dem_basin))  # m
    FF = A / (L ** 2) if L > 0 else np.nan
    CN_mean = np.nanmean(np.asarray(cn_grid, dtype=float)[basin])

    melton = (relief / 1000) / np.sqrt(A) if A > 0 else np.nan  # rilievo in km / sqrt(area in km^2)
    hyps_integral = (AE - np.nanmin(dem_basin)) / relief if relief > 0 else np.nan
    diameter_circle = 2 * np.sqrt(A / np.pi)                # km
    elongation_ratio = diameter_circle / L if L > 0 else np.nan
    shape_factor = L / np.sqrt(A) if A > 0 else np.nan

    # ---- Pendenza di tratto centrata sulla sezione del ponte ----
    reach_slope_c, reach_length_c_actual_m = reach_slope_centered(
        row_idx, col_idx, REACH_LENGTH_CENTERED_M
    )
    reach_slope_c_is_fallback = False
    if np.isnan(reach_slope_c):
        # In assenza di un tratto di canale sufficientemente esteso attorno
        # alla sezione (es. bacino di dimensioni ridotte), si adotta la
        # pendenza media di bacino come valore di riferimento.
        reach_slope_c = S
        reach_slope_c_is_fallback = True

    # ---- Perimetro del bacino, tracciando il confine reale della maschera ----
    basin_int = np.asarray(basin).astype(np.uint8)  # [MODIFICA 5 m] evita errore di casting con numpy 2
    edges = 0
    edges += np.sum(basin_int[:, :-1] != basin_int[:, 1:])   # confini verticali interni
    edges += np.sum(basin_int[:-1, :] != basin_int[1:, :])   # confini orizzontali interni
    edges += np.sum(basin_int[0, :]) + np.sum(basin_int[-1, :])   # bordo griglia (righe)
    edges += np.sum(basin_int[:, 0]) + np.sum(basin_int[:, -1])   # bordo griglia (colonne)
    perimeter_m = float(edges) * cellsize_x   # assume celle approssimativamente quadrate
    perimeter_km = perimeter_m / 1000

    compactness = (perimeter_km / (2 * np.sqrt(np.pi * A))) if A > 0 else np.nan
    circularity = (4 * np.pi * A) / (perimeter_km ** 2) if perimeter_km > 0 else np.nan
    relief_ratio = (relief / 1000) / L if L > 0 else np.nan       # km/km
    relative_relief = relief / perimeter_m if perimeter_m > 0 else np.nan  # m/m

    # una riga di risultati per ponte (stesse colonne del codice iniziale)
    results.append({
        'ID': bridge_id,
        'Longitude': lon,
        'Latitude': lat,
        'X_UTM33N': round(x, 2),
        'Y_UTM33N': round(y, 2),
        'Snap_Distance_m': round(snap_distance_m, 1),
        'A_km2': round(A, 3),
        'S': round(S, 5),
        'AE_m': round(AE, 2),
        'Longest_flow_length_km': round(L, 3),
        'Relief_m': round(relief, 2),
        'Form_factor_FF': round(FF, 4),
        'Curve_Number_mean': round(CN_mean, 2) if not np.isnan(CN_mean) else None,
        'Melton_relative_relief': round(melton, 4),
        'Hypsometric_integral': round(hyps_integral, 4),
        'Elongation_ratio': round(elongation_ratio, 4),
        'Shape_factor': round(shape_factor, 4),
        'Cell_Slope': round(cell_slope, 5),
        'Reach_Slope_Centered': round(reach_slope_c, 5),
        'Reach_Length_Centered_m': round(reach_length_c_actual_m, 1),
        'Reach_Slope_Centered_is_fallback': reach_slope_c_is_fallback,
        'Basin_Perimeter_km': round(perimeter_km, 3),
        'Compactness': round(compactness, 4),
        'Circularity': round(circularity, 4),
        'Relief_Ratio': round(relief_ratio, 4),
        'Relative_relief': round(relative_relief, 4),
    })
    print(f"Ponte {bridge_id}: completato (A={A:.3f} km2, S={S:.4f}).")

# ---------------- Salvataggio dei risultati della porzione ----------------
# la modalita' generale li riunisce in "parametri morfologici.csv", bacini_afferenti.geojson
# e reticolo_idrografico.geojson
_out_porzione = os.path.join(CARTELLA_PORZIONI, f"{PORZIONE}_parametri.csv")  # [MODIFICA 5 m]
pd.DataFrame(results).to_csv(_out_porzione, index=False)
print(f"Elaborazione completata. File salvato: {_out_porzione}")

basin_collection = {
    'type': 'FeatureCollection',
    'crs': {
        'type': 'name',
        'properties': {'name': f'urn:ogc:def:crs:EPSG::{epsg_code}'}
    },
    'features': basin_features,
}
with open(os.path.join(CARTELLA_PORZIONI, f"{PORZIONE}_bacini_afferenti.geojson"), "w") as f:  # [MODIFICA 5 m]
    json.dump(basin_collection, f)
print(f"Bacini afferenti salvati in {CARTELLA_PORZIONI}/{PORZIONE}_bacini_afferenti.geojson "
      f"({len(basin_features)} poligoni, CRS: {DEM_CRS}).")
