# Taglia il DEM unico v4 nelle 8 porzioni dei ponti multi-asta e dei canali di bonifica.
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
  "porzione_14", 636489.0001, 4479778.3481, 648164.0001, 4484648.3481, "19 107 108",
  "porzione_17", 628269.0001, 4496533.3481, 649184.0001, 4530288.3481, "164",
  "porzione_18", 587244.0001, 4470213.3481, 618859.0001, 4492658.3481, "72",
  "porzione_19", 588814.0001, 4495853.3481, 624144.0001, 4516728.3481, "196",
  "porzione_28", 634459.0001, 4463148.3481, 640314.0001, 4470453.3481, "117 118",
  "porzione_35", 646084.0001, 4474363.3481, 652659.0001, 4480098.3481, "111",
  "porzione_54", 637829.0001, 4442588.3481, 642439.0001, 4446938.3481, "13 154",
  "porzione_57", 642789.0001, 4476783.3481, 649439.0001, 4481938.3481, "109"),
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
