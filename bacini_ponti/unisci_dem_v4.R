# Unisce le due parti del DEM unico v4 in dem5m_unico_v4.tif e controlla che il file sia identico all'originale.
# Usa solo R base (nessun pacchetto da installare).
#
# Uso: mettere questo script e i due file dem5m_unico_v4_parte1.bin e dem5m_unico_v4_parte2.bin
# nella stessa cartella (C:\Users\ladya\Downloads) e lanciare da PowerShell:
#   Rscript C:\Users\ladya\Downloads\unisci_dem_v4.R
# oppure in RStudio: source("C:/Users/ladya/Downloads/unisci_dem_v4.R")

# ---- cartella di lavoro: quella dello script se lanciato con Rscript ----
arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(arg) == 1) setwd(dirname(normalizePath(sub("^--file=", "", arg))))
setwd("C:/Users/ladya/Downloads")   # cartella con i due file .bin

parti <- c("dem5m_unico_v4_parte1.bin", "dem5m_unico_v4_parte2.bin")
uscita <- "dem5m_unico_v4.tif"

# impronte MD5 attese (calcolate sui file originali)
md5_parti <- c("7aaabe5963d8d5bec856e93b81bdd5ad", "a5e6baeb4e08c53456b050ba08d16478")
md5_dem <- "4918f7c45fc1357fec8a0cc981c61939"

# ---- 1) controllo delle due parti ----
for (i in seq_along(parti)) {
  if (!file.exists(parti[i])) stop("Non trovo ", parti[i], " nella cartella ", getwd())
  if (unname(tools::md5sum(parti[i])) != md5_parti[i])
    stop(parti[i], " e' danneggiato o incompleto: scaricarlo di nuovo")
  cat(parti[i], ": ok\n")
}

# ---- 2) unione: le parti vengono scritte una dopo l'altra, a blocchi di 50 MB ----
blocco <- 50 * 1024^2
out <- file(paste0(uscita, ".tmp"), open = "wb")
for (p in parti) {
  con <- file(p, open = "rb")
  repeat {
    x <- readBin(con, what = "raw", n = blocco)
    if (length(x) == 0) break
    writeBin(x, out)
  }
  close(con)
}
close(out)

# ---- 3) controllo del DEM unito ----
if (unname(tools::md5sum(paste0(uscita, ".tmp"))) != md5_dem) {
  stop("Il file unito non coincide con il DEM originale: riprovare")
}
file.rename(paste0(uscita, ".tmp"), uscita)
cat("Creato", uscita, "(", round(file.size(uscita) / 1024^2), "MB ), identico al DEM v4.\n")
cat("Ora si possono cancellare i due file .bin.\n")
