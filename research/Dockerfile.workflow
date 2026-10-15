FROM --platform=linux/amd64 violafanfani/tcga-data-nf:0.0.18@sha256:fa4ff40bb59beeeb385ff3a86a4f04697baf0dd3c790b2debaea8aab588917eb

RUN python3 -m pip install --no-cache-dir polars==1.42.1 numpy==2.2.6

ENV ENGINEERING_PYTHON=/usr/bin/python3
WORKDIR /app
