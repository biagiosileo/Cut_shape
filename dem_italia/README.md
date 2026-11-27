# DEM d'Italia – 1 km, EPSG:3035

`dem_italia_1km_3035.tif`: GeoTIFF float32, 998 × 1285 celle da 1000 m, EPSG:3035 (ETRS89-LAEA),
griglia allineata alla griglia di riferimento EEA (coordinate multiple di 1000 m),
nodata = -9999, compressione deflate, con piramidi.

- **Quota**: media delle quote Copernicus DEM GLO-90 (90 m) nella cella, in m s.l.m. (geoide EGM2008).
  È un DSM, cioè include vegetazione ed edifici. Nelle celle a maggioranza acqua (lagune) è la media areale, con l'acqua a 0.
- **Estensione**: territorio nazionale secondo i confini regionali ISTAT (generalizzati, openpolis/geojson-italy)
  più San Marino e Vaticano. La linea di costa viene dal DEM (cella tenuta se almeno metà è terra) o da ISTAT
  (cella tenuta se almeno metà è territorio ISTAT); le isole più piccole di una cella tengono la loro cella più terrestre.
- **Area totale**: 302.307 km² (dato ISTAT 302.068 km²). Quote da -4,6 a 4518 m (Monte Bianco, media su 1 km²).

Per rigenerare il file: `make_dem_italia.py` (vedi la docstring per le fonti). Per i controlli e l'anteprima: `anteprima_dem.py`.

## Fonti e citazioni

Legenda: ✅ verificato su una fonte primaria durante l'elaborazione · ⚠️ da verificare (non ho potuto
aprire la pagina ufficiale da questo ambiente, il dato è riportato a memoria).

### Quote: Copernicus DEM GLO-90
- ✅ **Prodotto**: Copernicus DEM, istanza GLO-90 (sorgente `COP-DEM_GLO-90-DGED`), modello digitale
  di superficie (DSM) a 3 secondi d'arco (~90 m). Include edifici, infrastrutture e vegetazione.
  Fonte: readme del bucket AWS (`https://copernicus-dem-90m.s3.amazonaws.com/readme.html`).
- ✅ **Produttori**: DLR e Airbus Defence and Space GmbH, per il programma Copernicus (UE/ESA);
  i dati derivano da TanDEM-X (metadati XML di ogni tile, sorgente `TDM1_DEM__04_*`).
- ✅ **Copia usata**: Registry of Open Data on AWS, bucket `s3://copernicus-dem-90m/`
  (`https://copernicus-dem-90m.s3.amazonaws.com/`), tile COG con data di pubblicazione 2022-05-09.
  Ho usato 81 tile tra 35°N e 47°N e tra 6°E e 18°E, scaricati il 2026-11-27.
- ⚠️ **DOI del prodotto (ESA)**: https://doi.org/10.5270/ESA-c5d3d65
- ⚠️ **Licenza**: GLO-90 è distribuito con la licenza Copernicus DEM pubblica (uso gratuito, anche
  commerciale, con attribuzione): https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model
  Attenzione: il PDF `INFO/eula_F.pdf` allegato ai tile AWS è intitolato "Licence for the use of
  Copernicus DEM instances COP-DEM-GLO-30-R and COP-DEM-EEA-10-R", cioè le istanze a diffusione
  ristretta, non GLO-90. Per un uso formale controlla la licenza GLO-90 sul sito Copernicus.
- **Attribuzione**:
  - ⚠️ dalla licenza pubblica GLO-90: "produced using Copernicus WorldDEM-90 © DLR e.V. 2010-2014 and
    © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA;
    all rights reserved" (è la dicitura che ho scritto nei metadati del GeoTIFF);
  - ✅ dal PDF allegato ai tile (art. 4.4 e 4.5), per prodotti derivati: "produced using products
    © DLR e.V. (2014-2018) and © Airbus Defence and Space GmbH (year of production) provided under
    COPERNICUS by the European Union and ESA, all rights reserved" e, in ogni pubblicazione,
    "EO data provided under COPERNICUS by the European Union and ESA."

### Confini (solo per l'estensione, non per le quote)
- ✅ ISTAT, *Confini delle unità amministrative a fini statistici*, versione al 1° gennaio 2026, limiti
  regionali non generalizzati, ridistribuiti da openpolis sotto CC BY
  (`https://github.com/openpolis/geojson-italy`, file `geojson/limits_IT_regions.geojson`).
- ✅ Natural Earth, *Admin 0 – Countries* 1:10m (`nvkelso/natural-earth-vector` su GitHub), di pubblico
  dominio: solo per San Marino, Vaticano e gli Stati confinanti.

### Elaborazione
Ricampionamento a 1 km in EPSG:3035 con media e maschera nazionale: `make_dem_italia.py` in questo repository.
Dicitura suggerita per figure e relazioni:

> DEM a 1 km (EPSG:3035) ottenuto per media dal Copernicus DEM GLO-90 (doi:10.5270/ESA-c5d3d65),
> ritagliato sui confini ISTAT al 1/1/2026. Produced using Copernicus WorldDEM-90 © DLR e.V. 2010-2014 and
> © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA;
> all rights reserved. EO data provided under COPERNICUS by the European Union and ESA.
