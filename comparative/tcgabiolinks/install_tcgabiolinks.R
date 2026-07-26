options(
  timeout = 1800,
  BioC_mirror = "https://bioconductor.posit.co"
)

for (attempt in seq_len(3)) {
  BiocManager::install(
    "TCGAbiolinks",
    ask = FALSE,
    update = FALSE,
    Ncpus = 2
  )
  if (requireNamespace("TCGAbiolinks", quietly = TRUE)) {
    cat(as.character(packageVersion("TCGAbiolinks")), "\n")
    quit(status = 0)
  }
  message("TCGAbiolinks installation attempt ", attempt, " failed; retrying missing dependencies")
}

stop("TCGAbiolinks could not be installed after three attempts")
