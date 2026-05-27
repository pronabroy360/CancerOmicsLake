# Architecture

CancerOmicsLake follows a layered lakehouse pattern:

1. Ingestion: GDC/GTEx metadata and open-access files.
2. Bronze: raw files + source metadata.
3. Silver: standardized typed entities and facts.
4. Gold: analysis-ready marts and graph exports.
5. Consumption: FastAPI + Streamlit + Neo4j/Graphify exports.
