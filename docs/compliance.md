# Compliance

Public repository rules:

1. Never commit raw downloaded data.
2. Never commit controlled-access data.
3. Never commit tokens or credentials.
4. Publish aggregate, sample, or synthetic outputs only.
5. Keep open-access mode as default pipeline setting.

## Graph Publication Boundary

The local `data/gold/gold_graph_nodes.parquet` and `gold_graph_edges.parquet` tables may contain open GDC Patient and
Sample UUIDs for internal entity-linkage testing. The `data/` directory is excluded from Git and must not be deposited
as a public release without an explicit review.

Public Neo4j/Graphify exports, API graph endpoints, dashboard graph views, downloads, and hub metrics exclude Patient
and Sample entities by default. Public graph outputs are restricted to aggregate `CancerType`, `Dataset`, `Gene`,
`Pathway`, and `Tissue` nodes and edges whose endpoints both survive that allowlist.

`make run-demo-check-strict` fails if a public graph export contains a `PATIENT:` or `SAMPLE:` identifier. Full graph
tables are an internal engineering artifact, not a repository or publication deliverable.
