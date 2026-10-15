# Calcolo dei bacini dei 212 ponti (versione finale)

Risultato di riferimento: **168 ponti compatibili su 207** con area nel database (tolleranza ±15%).
`pysheds_bridges_ORIGINALE.py` non è modificato e non è incluso qui.

## Installazione (Python 3.10 o successivo)

    pip install numpy pandas geopandas pyogrio shapely rasterio pyproj pysheds whitebox-workflows openpyxl scipy matplotlib

## Dati di ingresso (sola lettura), in una cartella così organizzata

    dati/
      dem30/        dem30_bacino_01.tif ... dem30_bacino_13.tif
      dem5/         dtm5m_bacino_*.tif (tutti i tasselli dei 13 gruppi)
      cn5/          cn5m_bacino_01.tif ... cn5m_bacino_13.tif
      gruppi/       Bacino_01_ponti.csv ... Bacino_13_ponti.csv   (id, X, Y in WGS84)
      reticolo/     reticolo_tagliato.shp (+ .dbf .shx .prj .cpg)
      doc.kml
      Database_nuovo_11_08_2026.xlsx

## Esecuzione

    python esegui_pipeline.py <cartella dati> <cartella risultati>

Ad esempio, su Windows:

    python esegui_pipeline.py C:\PONTI_Controllo_coordinate\dati C:\PONTI_Controllo_coordinate\risultati_v2

La cartella dei risultati deve stare fuori da quella dei dati. L'esecuzione è ripartibile: i passi già
completati vengono saltati. Tempo indicativo: 40-60 minuti; memoria: circa 10 GB per la finestra più grande.

## Passi (script richiamati da esegui_pipeline.py)

1. `mosaico_dem30.py` – mosaico dei DEM a 30 m.
2. `controllo_coordinate.py`, `intersezione_tracciati.py` – coordinate DB/KML/input e tracciati dei ponti.
3. `bacini30_ingombro.py` – ingombro dei bacini a 30 m (dimensiona le finestre a 5 m).
4. `dem5_finestre.py` – DEM 5 m ibrido (30 m solo fuori dalla copertura a 5 m), reticolo di riferimento
   inciso di 5 m, riempimento delle depressioni + D8 (Whitebox), accumulo.
5. `aggancio_5m.py`, `scelta_soglia_5m.py` – sezione di chiusura all'intersezione tracciato KML-reticolo,
   soglia del reticolo 0,1 km² scelta con validazione incrociata.
6. `bacini_5m_finali.py` – bacini e parametri morfometrici.
7. `risultati_5m.py`, `confronto_reticolo_riferimento.py`, `origine_errore.py` – Excel, GeoPackage, segnalazioni.

Controlli e prodotti aggiuntivi: `verifica_parametri.py` (controlli sui parametri morfometrici),
`criticita_database.py`, `confronto_aste_ispra.py`, `export_non_compatibili.py`, `grafici_5m.py`.
