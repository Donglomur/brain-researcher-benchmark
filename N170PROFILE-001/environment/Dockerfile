FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS dependencies
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates python3 python3-venv python3-pip && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.2.6 scipy==1.14.1 mne==1.12.1 pytest==8.4.1 pytest-json-ctrf==0.3.5 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
FROM dependencies AS source
COPY stage_data.py source_manifest.json /opt/source/
RUN timeout --kill-after=10s 900s python3 -I -B /opt/source/stage_data.py \
      --manifest /opt/source/source_manifest.json --destination /app/data/n170profile \
      --work-dir /source_capture

FROM dependencies AS runtime
COPY --from=source /app/data/n170profile /app/data/n170profile
COPY --from=source /source_capture /opt/source_capture
COPY stage_data.py /opt/source/stage_data.py
COPY source_manifest.json SOURCE_NOTICE.md method_contract.json output_schema.json measurement_kernel.py ANALYSIS_CONTRACT.md OUTPUT_CONTRACT.md /app/
WORKDIR /app
RUN mkdir -p /app/output
