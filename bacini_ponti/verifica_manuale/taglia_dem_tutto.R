# Taglia TUTTO il DEM unico v4 in tessere da caricare (limite 30 MB per file), per ricalcolare i 212 ponti.
# Le tessere stanno sulla stessa griglia del DEM (nessun ricampionamento) e le quote escono in centimetri interi,
# come nel DEM originale: rimontate, ridanno il DEM identico cella per cella.
# Si parte da blocchi di 8000 x 8000 celle; ogni blocco oltre 29 MB viene diviso in 4, e cosi' via.
# Le tessere senza dati (tutte nodata) non vengono scritte.
# Alla fine scrive elenco_tessere.csv (nome, posizione in celle, MB, MD5): caricare anche quello.
#
# Prima volta: install.packages("terra")
# Poi: aprire in RStudio e premere Source (oppure: Rscript "C:\Users\ladya\Downloads\taglia_dem_tutto.R")
# Il DEM originale viene solo letto, non modificato.

library(terra)

dem_path <- "C:/Users/ladya/Downloads/dem5m_unico_v4.tif"
out_dir  <- "C:/Users/ladya/Downloads/tessere_dem"
blocco   <- 8000   # celle per lato del blocco iniziale
limite   <- 29     # MB

dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)
r <- rast(dem_path)
x0 <- xmin(r); y0 <- ymax(r); dx <- res(r)[1]; dy <- res(r)[2]
NC <- ncol(r); NR <- nrow(r)
cat("DEM:", NC, "x", NR, "celle\n")

elenco <- data.frame()

taglia <- function(c0, r0, nc, nr) {
  # finestra in celle intere: colonne c0..c0+nc-1, righe r0..r0+nr-1 (0 = angolo in alto a sinistra)
  e <- ext(x0 + c0 * dx, x0 + (c0 + nc) * dx, y0 - (r0 + nr) * dy, y0 - r0 * dy)
  z <- crop(r, e, snap = "near")
  nome <- sprintf("tessera_r%05d_c%05d_%dx%d.tif", r0, c0, nc, nr)
  if (global(!is.na(z), "sum", na.rm = TRUE)[1, 1] == 0) {
    cat(sprintf("%-40s vuota, saltata\n", nome))
    return(invisible())
  }
  f <- file.path(out_dir, nome)
  writeRaster(round(z * 100), f, overwrite = TRUE, datatype = "INT4S", NAflag = -999999,
              gdal = c("COMPRESS=DEFLATE", "PREDICTOR=2", "ZLEVEL=9", "TILED=YES"))
  mb <- file.size(f) / 1024^2
  if (mb > limite) {
    # troppo grande: divido in 4 sempre su celle intere
    file.remove(f)
    cat(sprintf("%-40s %6.1f MB, divido in 4\n", nome, mb))
    h <- nc %/% 2; v <- nr %/% 2
    taglia(c0,     r0,     h,      v)
    taglia(c0 + h, r0,     nc - h, v)
    taglia(c0,     r0 + v, h,      nr - v)
    taglia(c0 + h, r0 + v, nc - h, nr - v)
  } else {
    md5 <- unname(tools::md5sum(f))
    cat(sprintf("%-40s %6.1f MB  md5 %s\n", nome, mb, md5))
    elenco <<- rbind(elenco, data.frame(file = nome, col0 = c0, riga0 = r0, ncol = nc, nrig = nr,
                                        MB = round(mb, 2), md5 = md5))
  }
}

for (r0 in seq(0, NR - 1, by = blocco)) {
  for (c0 in seq(0, NC - 1, by = blocco)) {
    taglia(c0, r0, min(blocco, NC - c0), min(blocco, NR - r0))
  }
}

write.csv(elenco, file.path(out_dir, "elenco_tessere.csv"), row.names = FALSE)
cat("\nFatto:", nrow(elenco), "tessere,", round(sum(elenco$MB), 1), "MB in totale.\n")
cat("Caricare tutti i file della cartella", out_dir, "(anche elenco_tessere.csv)\n")
