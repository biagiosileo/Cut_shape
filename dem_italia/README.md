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

**Attribuzione obbligatoria**: produced using Copernicus WorldDEM-90 © DLR e.V. 2010-2014 and
© Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA;
all rights reserved. Confini: ISTAT (CC BY 3.0 IT) e Natural Earth (pubblico dominio).
