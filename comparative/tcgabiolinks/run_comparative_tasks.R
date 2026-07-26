suppressPackageStartupMessages(library(TCGAbiolinks))

output_dir <- "/evidence"
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

write_json <- function(value, name) {
  jsonlite::write_json(
    value,
    file.path(output_dir, name),
    auto_unbox = TRUE,
    pretty = TRUE,
    na = "null"
  )
}

case_count <- function(rows) {
  submitter_ids <- as.character(rows[["cases.submitter_id"]])
  submitter_ids <- unique(submitter_ids[!is.na(submitter_ids) & submitter_ids != ""])
  if (length(submitter_ids) > 0) {
    return(length(submitter_ids))
  }
  case_ids <- as.character(rows[["cases"]])
  length(unique(case_ids[!is.na(case_ids) & case_ids != ""]))
}

started_at <- Sys.time()
projects <- c("TCGA-BRCA", "TCGA-COAD", "TCGA-LUAD")
expression_queries <- list()
cohort_rows <- list()

for (project in projects) {
  query <- GDCquery(
    project = project,
    data.category = "Transcriptome Profiling",
    data.type = "Gene Expression Quantification",
    workflow.type = "STAR - Counts",
    access = "open"
  )
  rows <- getResults(query)
  expression_queries[[project]] <- rows
  cohort_rows[[project]] <- data.frame(
    project_id = project,
    file_count = nrow(rows),
    sample_count = length(unique(rows$sample.submitter_id)),
    case_count = case_count(rows),
    source_updated_at = max(rows$updated_datetime),
    stringsAsFactors = FALSE
  )
}

cohorts <- do.call(rbind, cohort_rows)
write.csv(
  cohorts[order(cohorts$project_id), ],
  file.path(output_dir, "cohort_discovery.csv"),
  row.names = FALSE,
  quote = TRUE
)

brca <- expression_queries[["TCGA-BRCA"]]
brca_tumor <- brca[brca$sample_type == "Primary Tumor", ]
write_json(
  list(
    project_id = "TCGA-BRCA",
    gene_symbol = "TP53",
    tcga_query_file_count = nrow(brca),
    tcga_primary_tumor_sample_count = length(unique(brca_tumor$sample.submitter_id)),
    tcga_workflow = "STAR - Counts",
    gtex_reference_available_in_package_api = FALSE,
    summary_computed = FALSE
  ),
  "expression_capability.json"
)

mutation_query <- GDCquery(
  project = "TCGA-LUAD",
  data.category = "Simple Nucleotide Variation",
  data.type = "Masked Somatic Mutation",
  workflow.type = "Aliquot Ensemble Somatic Variant Merging and Masking",
  access = "open"
)
mutation_rows <- getResults(mutation_query)
write_json(
  list(
    project_id = "TCGA-LUAD",
    gene_symbol = "TP53",
    mutation_file_count = nrow(mutation_rows),
    profiled_case_metadata_count = case_count(mutation_rows),
    workflow = unique(mutation_rows$analysis_workflow_type),
    protein_altering_numerator_computed = FALSE,
    mutation_frequency_computed = FALSE
  ),
  "mutation_capability.json"
)

exports <- sort(getNamespaceExports("TCGAbiolinks"))
write_json(
  list(
    package = "TCGAbiolinks",
    package_version = as.character(packageVersion("TCGAbiolinks")),
    bioconductor_version = as.character(BiocManager::version()),
    r_version = paste(R.version$major, R.version$minor, sep = "."),
    exported_functions = exports,
    gtex_named_exports = exports[grepl("GTEx", exports, ignore.case = TRUE)],
    graph_named_exports = exports[grepl("graph|neo4j|graphml", exports, ignore.case = TRUE)],
    started_at = format(started_at, tz = "UTC", usetz = TRUE),
    completed_at = format(Sys.time(), tz = "UTC", usetz = TRUE),
    wall_time_seconds = as.numeric(difftime(Sys.time(), started_at, units = "secs"))
  ),
  "runtime.json"
)
