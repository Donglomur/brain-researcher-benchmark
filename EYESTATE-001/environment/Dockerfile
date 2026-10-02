FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl git && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.2.6 scipy==1.17.0 scikit-learn==1.8.0 pandas==2.3.3 \
      nibabel==5.4.2 nilearn==0.13.1 pytest==8.4.1 pytest-json-ctrf==0.3.5 && \
    rm -rf /var/lib/apt/lists/*
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /app

FROM dependencies AS source
COPY stage_source.py source_manifest.json /opt/source/
RUN python3 /opt/source/stage_source.py --destination /app/data/eyestate

FROM dependencies AS runtime
COPY --from=source /app/data/eyestate /app/data/eyestate
COPY stage_source.py source_manifest.json /opt/source/
COPY method_contract.json /app/method_contract.json
