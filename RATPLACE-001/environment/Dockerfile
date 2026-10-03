FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS deps
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 \
    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates python3 python3-pip bash coreutils && \
    python3 -m pip install --no-cache-dir --break-system-packages \
    numpy==2.2.6 h5py==3.16.0 pytest==8.4.1 pytest-json-ctrf==0.3.5 && \
    rm -rf /var/lib/apt/lists/*
FROM deps AS source
COPY stage_data.py source_manifest.json /opt/source/
RUN timeout --kill-after=10s 330s python3 -I -B /opt/source/stage_data.py \
    --manifest /opt/source/source_manifest.json --destination /app/data/ratplace \
    --work-dir /source_capture
FROM deps
WORKDIR /app
COPY --from=source /app/data/ratplace /app/data/ratplace
COPY source_manifest.json method_contract.json output_schema.json methods.md SOURCE_NOTICE.md /app/
COPY stage_data.py /opt/source/stage_data.py
RUN chmod -R a-w /app/data/ratplace /opt/source /app/source_manifest.json \
    /app/method_contract.json /app/output_schema.json /app/methods.md /app/SOURCE_NOTICE.md
