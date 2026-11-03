# Unisce le due parti del DEM unico v3 in dem5m_unico_v3.tif e controlla che il file sia identico all'originale.
# Usa solo R base (nessun pacchetto da installare).
#
# Uso: mettere questo script e i due file dem5m_unico_v3_parte1.bin e dem5m_unico_v3_parte2.bin
# nella stessa cartella (es. C:\PONTI\consegna_finale) e lanciare da PowerShell:
#   Rscript C:\PONTI\consegna_finale\unisci_dem.R
# oppure in RStudio: setwd("C:/PONTI/consegna_finale"); source("unisci_dem.R")

# ---- cartella di lavoro: quella dello script se lanciato con Rscript ----
arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(arg) == 1) setwd(dirname(normalizePath(sub("^--file=", "", arg))))

parti <- c("dem5m_unico_v3_parte1.bin", "dem5m_unico_v3_parte2.bin")
uscita <- "dem5m_unico_v3.tif"

# impronte MD5 attese (calcolate sui file originali)
md5_parti <- c("2692f5b9b18d9524bf18fa69ee3c2cfb", "ebfa26ee558b2f591474a24b9ce13e7b")
md5_dem <- "66a11d767d897099672b296a4db6256a"

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
cat("Creato", uscita, "(", round(file.size(uscita) / 1024^2), "MB ), identico al DEM v3.\n")
cat("Ora si possono cancellare i due file .bin.\n")
