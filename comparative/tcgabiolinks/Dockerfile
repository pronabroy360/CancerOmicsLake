FROM bioconductor/bioconductor_docker@sha256:359702d482e70e343d2a436731b7c6deffd1ec184a1f1700de5d64b0c97cacba

LABEL org.opencontainers.image.title="CancerOmicsLake TCGAbiolinks comparison runtime"
LABEL org.opencontainers.image.description="Pinned Bioconductor 3.21 runtime for comparative evidence only"

COPY install_tcgabiolinks.R /tmp/install_tcgabiolinks.R

RUN Rscript /tmp/install_tcgabiolinks.R \
    && rm /tmp/install_tcgabiolinks.R

COPY run_comparative_tasks.R /opt/canceromicslake/run_comparative_tasks.R
