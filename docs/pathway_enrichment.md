# Pathway Enrichment Methodology

## Research Question

For each cancer type and consensus candidate gene set, which annotated biological pathways
are over-represented beyond chance relative to the tested background?

## Inputs

- **Consensus candidates**: `data/gold/gold_consensus_candidate_genes.parquet` provides per-cancer
  gene triage decisions (`prioritized`, `watchlist`, `deprioritized`) and publication tiers
  (`strong_candidate`, `research_candidate`, `exploratory`).
- **Pathway library**: `data/bronze/reference/pathways/reactome_pathways.gmt` — the canonical
  Reactome pathways gene-set file in GMT (Gene Matrix Transposed) format.

### GMT layout

The official Reactome `ReactomePathways.gmt` is a tab-delimited file with one pathway per line:

```
<pathway_name>\t<R-HSA-XXXXX>\t<gene_1>\t<gene_2>\t...
```

- Column 1: human-readable pathway name (e.g. `Cell Cycle`).
- Column 2: stable Reactome pathway identifier (e.g. `R-HSA-1640170`).
- Column 3 and beyond: HGNC gene symbols that belong to the pathway.

The parser (`load_gmt_pathways`) tolerates three GMT layouts:

1. Official Reactome (id in column 2).
2. Mixed/custom (id in column 1 or embedded in a longer string).
3. MSigDB-style (no `R-HSA-*` id; slugified name is used as the pathway id).

Gene symbols are normalized to upper case, de-duplicated, and sorted. The pathway identifier
is extracted via `re.search(r"R-HSA-\d+", ...)`; if no Reactome id is found, a slugified
uppercase name is used.

### Acquiring the GMT

The repo includes an idempotent downloader that fetches pinned Reactome release 97 into the
bronze reference layer:

```bash
make fetch-reactome-gmt
# or, to force a re-download:
REFRESH_GMT=1 make fetch-reactome-gmt
# or, to skip in CI / offline sandboxes:
SKIP_GMT_FETCH=1 make run-pathway-enrichment
```

The script (`scripts/fetch_reactome_gmt.sh`):

- Reuses a cached file only when its release and SHA-256 match its provenance sidecar.
- Validates every GMT row, rejects duplicate pathway identifiers, and requires at least 1,000 pathways.
- Extracts and validates in a same-filesystem temporary directory before atomically replacing the cache.
- Preserves a validated release-97 cache if a refresh fails.
- Records release, source URL, access time, license, file size, pathway count, and checksums in
  `outputs/reports/reactome_gmt_acquisition_report.json` and a bronze-layer provenance sidecar.

The GMT itself is not committed to git (`data/` is gitignored). Reproducibility comes from the
pinned Reactome release, source URL, and recorded SHA-256 checksums. Reactome annotation data and
derived files are distributed under CC0 1.0; attribution and release citation are still retained.
The acquisition used for this project should be cited as `ReactomePathways.gmt, Reactome, release 97,
https://reactome.org/download-data/` with the access date recorded in the provenance report.

## Candidate Sets

Three candidate sets are evaluated per cancer:

| Candidate set | Filter |
|---|---|
| `prioritized` | `consensus_decision IN ('prioritized')` |
| `watchlist_plus_prioritized` | `consensus_decision IN ('prioritized', 'watchlist')` |
| `research_candidate_plus` | `publication_tier IN ('strong_candidate', 'research_candidate')` |

## Statistical Test

For each `(cancer_type, candidate_set, pathway)` triple:

- `M` = background size = number of unique gene symbols tested for that cancer type
  (i.e. the union of all genes appearing in the consensus mart for that cancer).
- `K` = pathway size = number of pathway genes that appear in the background
  (post-intersection, so pathways larger than the background are not artificially penalized).
- `n` = candidate size = number of candidate genes in the candidate set.
- `k` = overlap = number of candidate genes that are also in the (intersected) pathway.

The one-tailed hypergeometric over-representation p-value is:

```
p = hypergeom.sf(k - 1, M, K, n)
```

Pathways with `K < 5` or `K > 500` (post-intersection) are excluded. Triples with `k < 2`
are excluded.

## Multiple Testing Correction

Benjamini-Hochberg FDR is applied **independently within each `(cancer_type, candidate_set)`
group**, not across the full result set. This matches the biological interpretation: each
candidate set defines its own family of hypotheses.

## Tiering

Each row is assigned an `enrichment_tier`:

- `fdr_enriched` — `fdr_q_value <= 0.05` AND `overlap_gene_count >= 3`.
- `nominal` — `p_value <= 0.05` but not `fdr_enriched`.
- `limited` — neither of the above.

`enrichment_score` is a bounded reviewer-prioritization score in `[0, 1]` combining FDR
strength (55%), overlap count (25%), and enrichment ratio (20%). It is an engineering
calibration, not a probability of biological truth.

## Outputs

- `data/gold/gold_pathway_enrichment.parquet` — the analytics mart.
- `outputs/reports/pathway_enrichment_report.json` — run metadata, status, tier counts,
  elapsed time, and the candidate sets / size filters applied.

## Guardrails

- Pathway enrichment is **hypothesis generation over a candidate set**, not mechanistic proof,
  causal inference, or clinical actionability.
- The tested background (`M`) is the union of genes in the consensus mart for that cancer.
  Results are not portable to a different background definition.
- Reactome pathways are curated from the literature and carry their own publication bias.
- Gene symbol identifier space must match between the consensus mart and the GMT. The Reactome
  GMT uses HGNC symbols; ensure the consensus layer does not silently switch to Ensembl or
  Entrez identifiers.
- Tiny pathways (2-4 genes) and very large pathways (>500 genes) are excluded because their
  hypergeometric p-values are unstable or uninformative.

## Reproducibility

```bash
# 1. Ensure the Reactome GMT is on disk (idempotent).
make fetch-reactome-gmt

# 2. Run the enrichment layer.
make run-pathway-enrichment

# 3. Verify the output.
.venv/bin/python -c "
import polars as pl
df = pl.read_parquet('data/gold/gold_pathway_enrichment.parquet')
print(df.head(20))
print('tier counts:', df.group_by('enrichment_tier').len().sort('enrichment_tier').to_dicts())
"
```
