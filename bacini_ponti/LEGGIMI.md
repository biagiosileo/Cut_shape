# Ricalcolo aree dei bacini dei ponti (v2, DEM 30 m)

Script derivati da `pysheds_bridges_ORIGINALE.py` (non modificato, non incluso qui).
I dati di ingresso sono solo letti; i risultati vanno in una cartella separata.

1. `mosaico_dem30.py <cartella_tif> <mosaico.tif>`: unisce i 13 `dem30_bacino_NN.tif`.
2. `bacini_dem30_v2.py <mosaico.tif> <cmp.csv> <cartella_risultati>`: area per ognuno dei 212 ID
   con la regola originale e con le regole "accumulo massimo entro R m", controllo del troncamento,
   ricerca lungo il corso.
3. `excel_confronto_v2.py <aree_dem30_v2.csv> <out.xlsx>`: Excel di confronto con il database (±15%).

Requisiti: pysheds 0.5, rasterio, pyproj, pandas, openpyxl.
