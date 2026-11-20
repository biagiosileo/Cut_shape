# Taglia dal DEM unico v4 un'area ALLARGATA attorno ai ponti 13 e 154 (circa 22.6 x 22.4 km), per controllare se il
# loro bacino continua oltre il bordo ovest della porzione_54.
# Unico file necessario: il DEM. I limiti delle porzioni sono gia' scritti qui sotto (sono quelli di ponti.csv).
# I file escono in centimetri interi, sulla stessa griglia del DEM; quelli oltre 29 MB vengono divisi in due
# (nord e sud) per restare sotto il limite di 30 MB di caricamento.
#
# Prima volta: install.packages("terra")
# Poi: aprire in RStudio e premere Source (oppure: Rscript "C:\Users\ladya\Downloads\taglia_dem.R")

library(terra)

dem_path <- "C:/Users/ladya/Downloads/dem5m_unico_v4.tif"
out_dir  <- "C:/Users/ladya/Downloads/porzioni_da_caricare"

porzioni <- data.frame(matrix(c(
  "allargata_13_154", 622829.0001, 4437588.3481, 645439.0001, 4459938.3481, "13 154"),
  ncol = 6, byrow = TRUE), stringsAsFactors = FALSE)
names(porzioni) <- c("nome", "xmin", "ymin", "xmax", "ymax", "ponti")
for (k in 2:5) porzioni[[k]] <- as.numeric(porzioni[[k]])

dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)
r <- rast(dem_path)
x0 <- xmin(r); y0 <- ymax(r); dx <- res(r)[1]; dy <- res(r)[2]

scrivi <- function(z, f) {
  # quote in centimetri interi, come nel DEM unico
  writeRaster(round(z * 100), f, overwrite = TRUE, datatype = "INT4S", NAflag = -999999,
              gdal = c("COMPRESS=DEFLATE", "PREDICTOR=2", "ZLEVEL=9", "TILED=YES"))
  mb <- file.size(f) / 1024^2
  cat(sprintf("%-28s %6.1f MB  md5 %s\n", basename(f), mb, unname(tools::md5sum(f))))
  mb
}

for (k in seq_len(nrow(porzioni))) {
  p <- porzioni[k, ]
  # stessa finestra di celle letta dal codice
  c0 <- round((p$xmin - x0) / dx); r0 <- round((y0 - p$ymax) / dy)
  nc <- round((p$xmax - p$xmin) / dx); nr <- round((p$ymax - p$ymin) / dy)
  e <- ext(x0 + c0 * dx, x0 + (c0 + nc) * dx, y0 - (r0 + nr) * dy, y0 - r0 * dy)
  z <- crop(r, e, snap = "near")
  cat(p$nome, "- ponti", p$ponti, "-", ncol(z), "x", nrow(z), "celle\n")
  f <- file.path(out_dir, paste0("dem_", p$nome, ".tif"))
  if (scrivi(z, f) > 29) {
    file.remove(f)
    m <- floor(nr / 2)
    scrivi(crop(z, ext(xmin(e), xmax(e), ymax(e) - m * dy, ymax(e))), file.path(out_dir, paste0("dem_", p$nome, "_nord.tif")))
    scrivi(crop(z, ext(xmin(e), xmax(e), ymin(e), ymax(e) - m * dy)), file.path(out_dir, paste0("dem_", p$nome, "_sud.tif")))
  }
}
cat("Fatto. Caricare tutti i file della cartella", out_dir, "\n")
