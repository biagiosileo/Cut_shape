import sys
f = sys.argv[1]
s = open(f, encoding='utf-8').read()
R = []
def r(a, b):
    R.append((a, b))

r('''    (stessa shape, stessa risoluzione, stesso CRS).
  - CSV dei ponti (input_csv) con colonne id, X, Y, dove X e Y sono
    coordinate geografiche WGS84 (longitudine, latitudine).
''', '''    (stessa shape, stessa risoluzione, stesso CRS).
  - CSV dei ponti (input_csv) con colonne id, X, Y, dove X e Y sono
    coordinate geografiche WGS84 (longitudine, latitudine), piu' le colonne
    porzione, xmin, ymin, xmax, ymax (porzione di DEM da leggere, in UTM 33N)
    e la colonna facoltativa soglia (soglia di aggancio ridotta per i fossi).
    L'id e' quello del database (1-212) e viene riportato invariato in uscita.
''')
r('''import json

# ================== CONFIGURAZIONE ==================''', '''import json

# ================== CONFIGURAZIONE ==================
# Nomi dei file, cercati nella cartella da cui si lancia lo script.''')
r('''# Il file ASCII grid del DEM non porta con se' informazioni di CRS. Sulla
# base dell'estensione delle coordinate (xllcorner/yllcorner dell'ordine di
# 6*10^5 / 4.5*10^6 m) e dell'area di studio (Matera, Basilicata), il CRS
# del DEM e' UTM 33N; viene dichiarato esplicitamente qui e passato a
# pysheds al momento della lettura (vedi sezione "Caricamento raster").
DEM_CRS''', '''# CRS del DEM: UTM 33N (WGS84). Nel codice iniziale il DEM era un ASCII grid
# senza CRS e il CRS veniva dichiarato qui; il DEM unico GeoTIFF e' gia' in
# EPSG:32633, il valore resta dichiarato esplicitamente e viene passato a
# pysheds al momento della lettura di ogni porzione (funzione leggi_porzione).
DEM_CRS''')
r('''DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)

# ---------------- Caricamento raster ----------------
# Il file ASCII grid del DEM non porta con se' informazioni di CRS, e il
# meccanismo di rilevamento automatico di GDAL/rasterio (usato da
# Grid.from_raster) non recupera un CRS valido per questo file. Si usa
# quindi il metodo from_ascii/read_ascii di pysheds, che accetta il CRS
# esplicitamente invece di doverlo dedurre dal file.
dem_crs_obj''', '''# Codici D8 delle 8 direzioni nell'ordine N, NE, E, SE, S, SW, W, NW
# (convenzione ESRI usata da pysheds).
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)

# ---------------- Caricamento raster ----------------
# Oggetto CRS passato a pysheds (ViewFinder) per ogni porzione letta.
# Nel codice iniziale qui si leggeva l'intero DEM ASCII con Grid.from_ascii;
# ora il DEM unico (troppo grande per la memoria) si legge a porzioni:
# vedi le due modalita' di lancio qui sotto.
dem_crs_obj''')
r('''CARTELLA_PORZIONI = "porzioni"
if len(sys.argv) == 1:''', '''# Cartella dei risultati intermedi, un gruppo di file per porzione:
#   porzioni/<porzione>_parametri.csv, _bacini_afferenti.geojson, _reticolo_idrografico.geojson
CARTELLA_PORZIONI = "porzioni"
if len(sys.argv) == 1:
    # Lancio senza argomenti: elenco delle porzioni presenti in ponti.csv.''')
r('''        subprocess.run([sys.executable, os.path.abspath(__file__), porz], check=True)
    tab = pd.concat(''', '''        # lo script rilancia se stesso con il nome della porzione: ogni porzione gira in un
        # processo separato, cosi' la memoria (DEM, accumulo, direzioni) viene liberata alla fine
        subprocess.run([sys.executable, os.path.abspath(__file__), porz], check=True)
    # Unione dei parametri di tutte le porzioni in un solo CSV, ordinato per ID del database.
    tab = pd.concat(''')
r('''    feats = []
    for p in porzioni:''', '''    # Unione dei poligoni dei bacini in un solo GeoJSON, ordinati per ID.
    feats = []
    for p in porzioni:''')
r('''    rami = []
    for p in porzioni:''', '''    # lettura dei rami di tutte le porzioni, unione geometrica, fusione dei tratti contigui
    rami = []
    for p in porzioni:''')
r('''    ret.insert(0, 'id_ramo', range(1, len(ret) + 1))''', '''    # numero progressivo del ramo e lunghezza in metri come attributi
    ret.insert(0, 'id_ramo', range(1, len(ret) + 1))''')
r('''PORZIONE = sys.argv[1]
_ponti = pd.read_csv(input_csv)''', '''# Lancio con un argomento (python pysheds_bridges_5m.py porzione_NN), fatto in automatico
# dalla modalita' generale: si elaborano solo i ponti di quella porzione.
PORZIONE = sys.argv[1]
_ponti = pd.read_csv(input_csv)''')
r('''_limiti = tuple(_ponti.iloc[0][['xmin', 'ymin', 'xmax', 'ymax']])''', '''# limiti della porzione (UTM 33N), uguali per tutti i ponti della stessa porzione
_limiti = tuple(_ponti.iloc[0][['xmin', 'ymin', 'xmax', 'ymax']])''')
r('''    with rasterio.open(path) as src:
        w = from_bounds(''', '''    with rasterio.open(path) as src:
        # finestra di righe e colonne del raster corrispondente ai limiti, arrotondata alle celle
        w = from_bounds(''')
r('''        a = src.read(1, window=w)
        affine = src.window_transform(w)
        senza_dato''', '''        a = src.read(1, window=w)
        # georeferenziazione della sola finestra letta
        affine = src.window_transform(w)
        # celle senza dato (nodata del file o NaN), da marcare con nodata_out
        senza_dato''')
r('''        a = a.astype(dtype) * src.scales[0] + src.offsets[0]
    a[senza_dato] = nodata_out
    vf =''', '''        # conversione nel tipo richiesto e da centimetri a metri (scala 0,01, offset 0)
        a = a.astype(dtype) * src.scales[0] + src.offsets[0]
    a[senza_dato] = nodata_out
    # raster pysheds con affine, nodata e CRS della porzione
    vf =''')
r('''dem = leggi_porzione(dem_path, _limiti, np.float64, -9999.0)
_v = dem != -9999''', '''# DEM della porzione in metri (float64, senza dato = -9999)
dem = leggi_porzione(dem_path, _limiti, np.float64, -9999.0)
# arrotondamento al centimetro: elimina i residui della conversione cm -> m
_v = dem != -9999''')
r('''grid = Grid(viewfinder=dem.viewfinder)
cn_grid = leggi_porzione(''', '''# griglia pysheds definita sulla porzione del DEM
grid = Grid(viewfinder=dem.viewfinder)
# Curve Number sulla stessa porzione (stessa griglia del DEM; senza dato = NaN)
cn_grid = leggi_porzione(''')
r('''# ---------------- Condizionamento del DEM ----------------
pit_filled''', '''# ---------------- Condizionamento del DEM ----------------
# 1) riempimento delle singole celle depresse (pit)
# 2) riempimento delle depressioni piu' estese
# 3) risoluzione delle aree piatte (leggera pendenza artificiale verso l'uscita)
pit_filled''')
r('''# ---------------- Direzione di flusso e accumulo ----------------
fdir''', '''# ---------------- Direzione di flusso e accumulo ----------------
# direzione D8 di ogni cella e numero di celle drenate da ciascuna cella (accumulo)
fdir''')
r('''slope = compute_d8_max_slope(inflated_dem''', '''# pendenza locale (m/m) di tutte le celle della porzione, sul DEM condizionato
slope = compute_d8_max_slope(inflated_dem''')
r('''with open(os.path.join(CARTELLA_PORZIONI, f"{PORZIONE}_reticolo_idrografico.geojson"), "w") as f:''', '''# reticolo della porzione; la modalita' generale lo unisce poi a quello delle altre porzioni
with open(os.path.join(CARTELLA_PORZIONI, f"{PORZIONE}_reticolo_idrografico.geojson"), "w") as f:''')
r('''basin_features = []
''', '''# elenco dei poligoni dei bacini dei ponti della porzione
basin_features = []
''')
r('''# ---------------- Coordinate dei ponti ----------------
# Il file ASCII grid del DEM non porta con se informazioni di CRS: si usa
# quindi il CRS dichiarato in DEM_CRS. Le coordinate del CSV, in BRIDGE_CSV_CRS
# (WGS84 geografiche), vengono trasformate nel CRS del DEM prima di ogni
# operazione sulla griglia.''', '''# ---------------- Coordinate dei ponti ----------------
# Le coordinate del CSV, in BRIDGE_CSV_CRS (WGS84 geografiche), vengono
# trasformate nel CRS del DEM (DEM_CRS, UTM 33N) prima di ogni operazione
# sulla griglia.''')
r('''xmin, ymin, xmax, ymax = grid.bbox
''', '''# estensione della porzione: un ponte fuori da questi limiti viene escluso
xmin, ymin, xmax, ymax = grid.bbox
''')
r('''for _, row in df.iterrows():
    bridge_id = row['id']''', '''# ==================== Ciclo sui ponti della porzione ====================
for _, row in df.iterrows():
    # ID del database (1-212): resta invariato in tutti gli output
    bridge_id = row['id']''')
r('''        _soglia = ACC_THRESHOLD
        if''', '''        # di norma si aggancia al reticolo con acc > ACC_THRESHOLD (0,1 km2); se in ponti.csv
        # la colonna soglia e' compilata, si usa quel valore (es. 1000 celle = 0,025 km2)
        _soglia = ACC_THRESHOLD
        if''')
r('''        x_snap, y_snap = grid.snap_to_mask(acc > _soglia, (x, y))
        snap_distance_m''', '''        # spostamento del punto sulla cella di reticolo piu' vicina
        x_snap, y_snap = grid.snap_to_mask(acc > _soglia, (x, y))
        # distanza dello spostamento, riportata in uscita (Snap_Distance_m)
        snap_distance_m''')
r('''        _b = np.asarray(basin)
        if''', '''        # basta una cella del bacino nelle prime/ultime 2 righe o colonne della porzione
        _b = np.asarray(basin)
        if''')
r('''    dem_basin = np.asarray(dem, dtype=float).copy()
    dem_basin[~basin] = np.nan''', '''    # quote reali (non condizionate) del solo bacino, NaN fuori dal bacino
    dem_basin = np.asarray(dem, dtype=float).copy()
    dem_basin[~basin] = np.nan''')
r('''    n_cells = int(np.sum(basin))
    A =''', '''    # area (km2) = numero di celle x area della cella (25 m2);
    # S = pendenza media di bacino (m/m); AE = quota media di bacino (m)
    n_cells = int(np.sum(basin))
    A =''')
r('''    basin_geom = polygonize_basin(grid, basin)''', '''    # poligono del bacino, salvato con ID e area
    basin_geom = polygonize_basin(grid, basin)''')
r('''    col_idx, row_idx = grid.nearest_cell(x_snap, y_snap)
    cell_slope''', '''    # riga e colonna della sezione di chiusura e pendenza locale in quella cella
    col_idx, row_idx = grid.nearest_cell(x_snap, y_snap)
    cell_slope''')
r('''    relief = float(np.nanmax(dem_basin)''', '''    # descrittori derivati: rilievo, form factor, CN medio, Melton, integrale ipsometrico,
    # rapporto di allungamento, fattore di forma (formule invariate rispetto al codice iniziale)
    relief = float(np.nanmax(dem_basin)''')
r('''    results.append({
        'ID': bridge_id,''', '''    # una riga di risultati per ponte (stesse colonne del codice iniziale)
    results.append({
        'ID': bridge_id,''')
r('''_out_porzione = os.path.join(''', '''# ---------------- Salvataggio dei risultati della porzione ----------------
# la modalita' generale li riunisce in "parametri morfologici.csv", bacini_afferenti.geojson
# e reticolo_idrografico.geojson
_out_porzione = os.path.join(''')
for a, b in R:
    assert s.count(a) == 1, a[:80]
    s = s.replace(a, b)
open(f, 'w', encoding='utf-8').write(s)
