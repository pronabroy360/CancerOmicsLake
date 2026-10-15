args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) stop("Expected input and output TSV paths")
if (as.character(packageVersion("RobustRankAggreg")) != "1.2.1") {
  stop("RobustRankAggreg package version drift")
}
input <- read.delim(args[1], check.names = FALSE, stringsAsFactors = FALSE)
if (!identical(names(input), c("gene_id", "adjacent_rank", "gtex_rank"))) {
  stop("Unexpected rank input schema")
}
n <- nrow(input)
if (n < 2L || anyDuplicated(input$gene_id) || anyNA(input)) stop("Invalid gene rows")
for (column in c("adjacent_rank", "gtex_rank")) {
  if (!identical(sort(as.integer(input[[column]])), seq_len(n))) stop("Ranks must be permutations")
}
ranks <- as.matrix(input[c("adjacent_rank", "gtex_rank")]) / n
rownames(ranks) <- input$gene_id
result <- RobustRankAggreg::aggregateRanks(rmat = ranks, N = n, method = "RRA", exact = FALSE)
if (nrow(result) != n || anyDuplicated(result$Name)) stop("RRA lost or duplicated genes")
scores <- result$Score[match(input$gene_id, result$Name)]
if (anyNA(scores) || any(!is.finite(scores))) stop("RRA produced invalid scores")
write.table(data.frame(gene_id = input$gene_id, score = scores), file = args[2],
            sep = "\t", row.names = FALSE, quote = FALSE)
