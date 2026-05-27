# API Spec

Implemented endpoint scaffold:

- `GET /health`
- `GET /metadata/projects`
- `GET /metadata/samples?project_id=TCGA-BRCA`
- `GET /genes/search?query=TP53`
- `GET /expression/gene/{gene_symbol}`
- `GET /expression/tumor-vs-normal/{gene_symbol}`
- `GET /mutations/gene/{gene_symbol}`
- `GET /mutations/cancer/{project_id}`
- `GET /graph/nodes`
- `GET /graph/edges`
- `GET /quality/latest`
