# Shared-task adapter. Normalization and reference filtering use the published R package.
suppressPackageStartupMessages(library(NetworkDataCompanion))
suppressPackageStartupMessages(library(jsonlite))
args <- commandArgs(trailingOnly = TRUE)
mode <- args[1]
obj <- get("NetworkDataCompanion", asNamespace("NetworkDataCompanion"))$new()

write_expression <- function(values, path, precise=FALSE) {
  if (precise) {
    labels <- dimnames(values)
    values <- matrix(sprintf("%.17g", values), nrow=nrow(values), dimnames=labels)
  }
  frame <- data.frame(gene_id=rownames(values), values, check.names=FALSE)
  write.table(frame, path, sep="\t", quote=FALSE, row.names=FALSE)
}

if (mode == "runtime") {
  write_json(list(R = R.version.string, platform = R.version$platform,
                 NDC = as.character(packageVersion("NetworkDataCompanion")),
                 edgeR = as.character(packageVersion("edgeR")),
                 memory_limit_bytes=if(file.exists("/sys/fs/cgroup/memory.max")) as.numeric(readLines("/sys/fs/cgroup/memory.max")) else NA,
                 cpu_quota=if(file.exists("/sys/fs/cgroup/cpu.max")) readLines("/sys/fs/cgroup/cpu.max") else NA,
                 normalization_source = paste(deparse(obj$logCPMNormalization), collapse="\n"),
                 filtering_source = paste(deparse(obj$filterGenesByNormExpression), collapse="\n"),
                 boundary_kept = obj$filterGenesByNormExpression(data.frame(
                     a=c(1,.999,2),b=c(0,0,3),c=c(0,0,0),d=c(0,0,0),e=c(0,0,0)),1.0,.2)),
             args[2], auto_unbox=TRUE, pretty=TRUE)
  quit(status=0)
}

read_counts <- function(path) {
  header <- strsplit(readLines(path, n=1L), "\t")[[1]]
  if (length(header)<3L || header[1]!="gene_id" || anyDuplicated(header)) stop("Missing gene/sample metadata")
  frame <- read.delim(path, row.names=1, check.names=FALSE)
  values <- as.matrix(frame)
  storage.mode(values) <- "double"
  if (nrow(values)<2 || ncol(values)<2 || anyNA(values) || any(!is.finite(values)) || any(values<0)) stop("Invalid counts")
  if (anyDuplicated(rownames(values)) || anyDuplicated(colnames(values)) || any(colSums(values)<=0)) stop("Invalid measurement keys or library")
  marker <- Sys.getenv("ENGINEERING_PAUSE_MARKER", "")
  if (nchar(marker)>0L) {writeLines("input parsed; output not committed",marker); Sys.sleep(120)}
  values
}

write_filtered <- function(normalized, target, tool) {
  if(tool=="reference") {
    keep <- obj$filterGenesByNormExpression(as.data.frame(normalized),1.0,.2)
    write_expression(normalized[keep,,drop=FALSE],target)
  } else {
    intermediate <- paste0(target,".normalized.tsv")
    write_expression(normalized,intermediate,precise=TRUE)
    status <- system2(Sys.getenv("ENGINEERING_PYTHON","python"),
        c("src/operations/engineering_runtime.py","cpm","--input",intermediate,"--output",target))
    if(status!=0L) stop("CancerOmicsLake filtering extension failed")
    unlink(intermediate)
  }
}

if (mode == "normalize") {
  values <- read_counts(args[2])
  cpm <- obj$logCPMNormalization(values)$CPM
  write_expression(cpm, args[3], precise=TRUE)
  quit(status=0)
}

if (mode == "make-rds") {
  suppressPackageStartupMessages(library(SummarizedExperiment))
  suppressPackageStartupMessages(library(rtracklayer))
  values <- read_counts(args[2])
  metadata <- read.delim(args[3],row.names=1,check.names=FALSE)
  metadata <- metadata[colnames(values),,drop=FALSE]
  annotation <- import(args[4])
  annotation <- annotation[annotation$type=="gene"]
  positions <- match(rownames(values),annotation$gene_id)
  if(anyNA(positions)) stop("Raw genes absent from cached annotation")
  ranges <- annotation[positions]
  names(ranges) <- rownames(values)
  object <- SummarizedExperiment(assays=list(raw_counts=values),rowRanges=ranges,
                                colData=DataFrame(metadata))
  saveRDS(object,args[5])
  quit(status=0)
}

if (mode %in% c("reference","extension")) {
  values <- read_counts(args[2])
  cpm <- obj$logCPMNormalization(values)$CPM
  write_filtered(cpm,args[3],mode)
  quit(status=0)
}

if (mode == "batch") {
  workloads <- read_json(args[2], simplifyVector=TRUE)
  tool <- args[3]
  output <- args[4]
  dir.create(output, recursive=TRUE, showWarnings=FALSE)
  rows <- list()
  for (i in seq_len(nrow(workloads))) {
    entry <- workloads[i,]
    values <- read_counts(entry$input)
    repetitions <- if(Sys.getenv("ENGINEERING_PREFLIGHT","")=="1") 1L else 9L
    for (iteration in seq_len(repetitions)) {
      started <- proc.time()[["elapsed"]]
      normalized <- obj$logCPMNormalization(values)$CPM
      normalization_seconds <- proc.time()[["elapsed"]] - started
      target <- file.path(output, paste0(entry$key, ".tsv"))
      write_filtered(normalized,target,tool)
      elapsed <- proc.time()[["elapsed"]] - started
      rows[[length(rows)+1L]] <- data.frame(key=entry$key, tool=tool, iteration=iteration,
         measured=iteration>2L, elapsed_seconds=elapsed, normalization_seconds=normalization_seconds,
         output_bytes=file.info(target)$size)
    }
  }
  write.csv(do.call(rbind, rows), file.path(output, "timings.csv"), row.names=FALSE)
  memory_path <- "/sys/fs/cgroup/memory.peak"
  write_json(list(peak_memory_bytes=if(file.exists(memory_path)) as.numeric(readLines(memory_path)) else NA,
                  output_scope="whole tool batch including shared normalization and child processes"),
             file.path(output,"memory.json"),auto_unbox=TRUE,pretty=TRUE,na="null")
  quit(status=0)
}
stop("Unknown external worker mode")
