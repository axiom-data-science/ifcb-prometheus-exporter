FROM mambaorg/micromamba:1.5.1-bullseye
LABEL org.opencontainers.image.authors="Developer <dev@axiomdatascience.com>"

LABEL org.opencontainers.image.licenses="MIT"

ENV PROJECT_NAME=ifcb-prometheus-exporter
ENV PROJECT_ROOT=/opt/ifcb-prometheus-exporter

COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
RUN micromamba install -y -n base -f /tmp/environment.yml && \
    micromamba clean --all --yes && \
    rm /tmp/environment.yml

COPY --chown=$MAMBA_USER:$MAMBA_USER ifcb_prometheus_exporter $PROJECT_ROOT/ifcb_prometheus_exporter
COPY --chown=$MAMBA_USER:$MAMBA_USER tests $PROJECT_ROOT/tests
COPY --chown=$MAMBA_USER:$MAMBA_USER pyproject.toml MANIFEST.in .flake8 conftest.py README.rst requirements.txt LICENSE HISTORY.rst $PROJECT_ROOT/

WORKDIR $PROJECT_ROOT/
RUN /opt/conda/bin/pip install .
