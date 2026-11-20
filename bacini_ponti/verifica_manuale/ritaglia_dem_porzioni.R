# Ritaglia dal DEM unico le porzioni dei ponti indicati, per caricarle una alla volta (limite 30 MB per file).
# Ogni porzione e' ritagliata esattamente come la legge il codice pysheds_bridges_5m.py: stessa finestra di celle
# (limiti xmin, ymin, xmax, ymax di ponti.csv arrotondati alla cella) e stessi valori in centimetri interi.
# Se un file supera i 29 MB viene diviso in due meta' (nord e sud).
#
# Requisiti: R con il pacchetto terra (una volta sola: install.packages("terra")).
# Uso: modificare i tre percorsi qui sotto e lanciare in RStudio (source) oppure da PowerShell:
#   Rscript "C:\Users\ladya\Downloads\ritaglia_dem_porzioni.R"
# Si possono anche passare i percorsi e gli ID da riga di comando:
#   Rscript ritaglia_dem_porzioni.R <dem.tif> <ponti.csv> <cartella_uscita> [ID ID ...]   (oppure "tutti")

library(terra)

# ---- impostazioni ----
dem_path <- "C:/Users/ladya/Downloads/dem5m_unico_v4.tif"   # DEM unico v4
csv_path <- "C:/Users/ladya/Downloads/ponti.csv"           # ponti.csv della consegna (cambiare se e' altrove)
out_dir  <- "C:/Users/ladya/Downloads/porzioni_da_caricare" # cartella nuova
ids <- c(13, 19, 72, 107, 108, 109, 111, 117, 118, 154, 164, 196)  # multi-asta e canali di bonifica

a <- commandArgs(trailingOnly = TRUE)
if (length(a) >= 3) { dem_path <- a[1]; csv_path <- a[2]; out_dir <- a[3] }
if (length(a) >= 4) ids <- if (a[4] == "tutti") "tutti" else as.integer(a[4:length(a)])
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

r <- rast(dem_path)
P <- read.csv(csv_path)
P$id <- as.integer(P$id)
if (!identical(ids, "tutti")) P <- P[P$id %in% ids, ]
porz <- P[!duplicated(P$porzione), ]
cat(nrow(porz), "porzioni per i ponti", sort(P$id), "\n")

x0 <- xmin(r); y0 <- ymax(r); dx <- res(r)[1]; dy <- res(r)[2]
scr <- function(z, f) {
  # valori in centimetri interi, come nel DEM unico (terra restituisce le quote in metri)
  z <- round(z * 100)
  writeRaster(z, f, overwrite = TRUE, datatype = "INT4S", NAflag = -999999,
              gdal = c("COMPRESS=DEFLATE", "PREDICTOR=2", "ZLEVEL=9", "TILED=YES"))
  mb <- file.size(f) / 1024^2
  cat(sprintf("%-26s %6.1f MB  md5 %s\n", basename(f), mb, unname(tools::md5sum(f))))
  mb
}
for (k in seq_len(nrow(porz))) {
  p <- porz[k, ]
  # stessa finestra di celle del codice (from_bounds arrotondato alla cella)
  c0 <- round((p$xmin - x0) / dx); r0 <- round((y0 - p$ymax) / dy)
  nc <- round((p$xmax - p$xmin) / dx); nr <- round((p$ymax - p$ymin) / dy)
  e <- ext(x0 + c0 * dx, x0 + (c0 + nc) * dx, y0 - (r0 + nr) * dy, y0 - r0 * dy)
  z <- crop(r, e, snap = "near")
  ponti <- paste(sort(P$id[P$porzione == p$porzione]), collapse = ", ")
  cat(p$porzione, ": ", ncol(z), " x ", nrow(z), " celle, ponti ", ponti, "\n", sep = "")
  f <- file.path(out_dir, paste0("dem_", p$porzione, ".tif"))
  if (scr(z, f) > 29) {
    # troppo grande: due meta' (nord e sud) da caricare separatamente
    file.remove(f)
    m <- floor(nr / 2)
    scr(crop(z, ext(xmin(e), xmax(e), ymax(e) - m * dy, ymax(e))), file.path(out_dir, paste0("dem_", p$porzione, "_nord.tif")))
    scr(crop(z, ext(xmin(e), xmax(e), ymin(e), ymax(e) - m * dy)), file.path(out_dir, paste0("dem_", p$porzione, "_sud.tif")))
  }
}
cat("fatto: caricare i file della cartella", out_dir, "uno alla volta\n")
