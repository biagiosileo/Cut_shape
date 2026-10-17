"""Applica al codice dell'utente le modifiche per il DEM unico letto a porzioni."""
import sys

s = open(sys.argv[1], encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)


M = '# [MODIFICA 5 m]'
rep('''Input attesi:
  - DEM in formato ASCII grid (dem_path), in CRS proiettato (metrico).''', f'''{M} DEM unico letto a porzioni.
Lanciato senza argomenti, lo script elabora una porzione alla volta, ciascuna in un
processo separato (memoria liberata tra una porzione e l'altra), poi riunisce i
risultati in output_csv e bacini_afferenti.geojson. Le porzioni (colonne porzione,
xmin, ymin, xmax, ymax del CSV) contengono per intero i bacini dei loro ponti.
Una porzione gia' elaborata (file in porzioni/) viene saltata: il lancio si puo'
interrompere e riprendere. Per una sola porzione: python pysheds_bridges_5m.py porzione_NN

Input attesi:
  - DEM unico in GeoTIFF (dem_path), in CRS proiettato (metrico); quote in cm con scala 0,01.''')
rep('import numpy as np\n', f'''import numpy as np
{M} compatibilita' con numpy 2 (pysheds usa np.in1d, rimosso in numpy 2)
if not hasattr(np, "in1d"):
    np.in1d = np.isin
import os
import sys
import subprocess
import rasterio
from rasterio.windows import from_bounds
from pysheds.sview import Raster, ViewFinder
''')
rep('dem_path = "dtm_mt.asc"\ncn_path = "curve_number.tif"\ninput_csv = "matera_bridges.csv"\n',
    f'dem_path = "dem5m_unico.tif"  {M}\ncn_path = "cn5m_unico.tif"  {M}\n'
    f'input_csv = "ponti.csv"  {M} id, X, Y + porzione, xmin, ymin, xmax, ymax\n')
rep('ACC_THRESHOLD = 500\n', f'ACC_THRESHOLD = 4000  {M} 4000 celle x 25 m2 = 0,1 km2 (era 500)\n')
rep('SNAP_DISTANCE_WARNING_M = 50.0\n', f"SNAP_DISTANCE_WARNING_M = 10.0  {M} i punti sono gia' sul reticolo (era 50)\n")
rep('''dem_crs_obj = Proj(DEM_CRS, preserve_units=True)
grid = Grid.from_ascii(dem_path, crs=dem_crs_obj)
dem = grid.read_ascii(dem_path, crs=dem_crs_obj)
cn_grid = grid.read_raster(cn_path)
''', f'''dem_crs_obj = Proj(DEM_CRS, preserve_units=True)

{M} ---- modalita' generale: una porzione per processo, poi unione dei risultati ----
CARTELLA_PORZIONI = "porzioni"
if len(sys.argv) == 1:
    os.makedirs(CARTELLA_PORZIONI, exist_ok=True)
    porzioni = sorted(pd.read_csv(input_csv)['porzione'].unique())
    for n, porz in enumerate(porzioni, 1):
        fatto = os.path.join(CARTELLA_PORZIONI, f"{{porz}}_parametri.csv")
        if os.path.exists(fatto):
            print(f"[{{n}}/{{len(porzioni)}}] {{porz}}: gia' elaborata, saltata.")
            continue
        print(f"[{{n}}/{{len(porzioni)}}] {{porz}}: avvio.", flush=True)
        subprocess.run([sys.executable, os.path.abspath(__file__), porz], check=True)
    tab = pd.concat([pd.read_csv(os.path.join(CARTELLA_PORZIONI, f"{{p}}_parametri.csv")) for p in porzioni])
    tab.sort_values('ID').to_csv(output_csv, index=False)
    feats = []
    for p in porzioni:
        with open(os.path.join(CARTELLA_PORZIONI, f"{{p}}_bacini_afferenti.geojson")) as f:
            gj = json.load(f)
        feats += gj['features']
    gj['features'] = sorted(feats, key=lambda ft: ft['properties']['ID'])
    with open("bacini_afferenti.geojson", "w") as f:
        json.dump(gj, f)
    print(f"Completato: {{len(tab)}} ponti in {{output_csv}}, bacini in bacini_afferenti.geojson.")
    sys.exit(0)

{M} ---- modalita' porzione: si leggono solo la porzione di DEM e di CN ----
PORZIONE = sys.argv[1]
_ponti = pd.read_csv(input_csv)
_ponti = _ponti[_ponti['porzione'] == PORZIONE]
if _ponti.empty:
    raise SystemExit(f"Nessun ponte nella porzione {{PORZIONE}}.")
_limiti = tuple(_ponti.iloc[0][['xmin', 'ymin', 'xmax', 'ymax']])
print(f"{{PORZIONE}}: {{len(_ponti)}} ponti.")


def leggi_porzione(path, limiti, dtype, nodata_out):
    """Legge solo la porzione richiesta; applica il fattore di scala del file
    (il DEM unico e' salvato in centimetri interi con scala 0,01)."""
    with rasterio.open(path) as src:
        w = from_bounds(*limiti, transform=src.transform).round_offsets().round_lengths()
        a = src.read(1, window=w)
        affine = src.window_transform(w)
        senza_dato = (a == src.nodata) | np.isnan(a) if src.nodata is not None else np.isnan(a)
        a = a.astype(dtype) * src.scales[0] + src.offsets[0]
    a[senza_dato] = nodata_out
    vf = ViewFinder(affine=affine, shape=a.shape, nodata=a.dtype.type(nodata_out), crs=dem_crs_obj)
    return Raster(a, vf)


dem = leggi_porzione(dem_path, _limiti, np.float64, -9999.0)
_v = dem != -9999
dem[_v] = np.round(dem[_v], 2)  # quote in metri al cm
del _v
grid = Grid(viewfinder=dem.viewfinder)
cn_grid = leggi_porzione(cn_path, _limiti, np.float32, np.nan)
''')
rep('inflated_dem = grid.resolve_flats(flooded)\n',
    f'''{M} con i valori di default (eps=1e-5, max_iter=1000) sulle grandi aree piatte
# l'innalzamento supera 1 cm e crea pozzi artificiali che interrompono il bacino (ponti 24, 25)
inflated_dem = grid.resolve_flats(flooded, eps=1e-6, max_iter=10000)
''')
rep('with open("reticolo_idrografico.geojson", "w") as f:',
    f'with open(os.path.join(CARTELLA_PORZIONI, f"{{PORZIONE}}_reticolo_idrografico.geojson"), "w") as f:  {M}')
rep('print(f"Reticolo salvato in reticolo_idrografico.geojson',
    'print(f"Reticolo salvato in {CARTELLA_PORZIONI}/{PORZIONE}_reticolo_idrografico.geojson')
rep('df = pd.read_csv(input_csv)\n', f'df = _ponti[["id", "X", "Y"]]  {M} solo i ponti della porzione\n')
rep('    basin_int = basin.astype(np.uint8)\n',
    f'    basin_int = np.asarray(basin).astype(np.uint8)  {M} evita errore di casting con numpy 2\n')
rep('pd.DataFrame(results).to_csv(output_csv, index=False)\nprint(f"Elaborazione completata. File salvato: {output_csv}")',
    f'''_out_porzione = os.path.join(CARTELLA_PORZIONI, f"{{PORZIONE}}_parametri.csv")  {M}
pd.DataFrame(results).to_csv(_out_porzione, index=False)
print(f"Elaborazione completata. File salvato: {{_out_porzione}}")''')
rep("    'features': basin_features,\n}\nwith open(\"bacini_afferenti.geojson\", \"w\") as f:",
    f"    'features': basin_features,\n}}\nwith open(os.path.join(CARTELLA_PORZIONI, f\"{{PORZIONE}}_bacini_afferenti.geojson\"), \"w\") as f:  {M}")
rep('print(f"Bacini afferenti salvati in bacini_afferenti.geojson "',
    'print(f"Bacini afferenti salvati in {CARTELLA_PORZIONI}/{PORZIONE}_bacini_afferenti.geojson "')
open(sys.argv[2], 'w', encoding='utf-8').write(s)
