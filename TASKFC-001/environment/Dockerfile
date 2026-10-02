FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS dependencies
ENV DEBIAN_FRONTEND=noninteractive \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
    PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.2.6 scipy==1.17.0 scikit-learn==1.8.0 pandas==2.3.3 \
      nibabel==5.4.2 nilearn==0.13.1 pytest==8.4.1 pytest-json-ctrf==0.3.5 && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app

FROM dependencies AS source
COPY stage_data.py source_manifest.json /opt/source/
RUN timeout --kill-after=10s 1250s python3 /opt/source/stage_data.py --manifest /opt/source/source_manifest.json \
      --destination /app/data/taskfc --work-dir /source_capture

FROM dependencies AS runtime
COPY --from=source /app/data/taskfc /app/data/taskfc
COPY stage_data.py /opt/source/stage_data.py
COPY source_manifest.json /app/source_manifest.json
COPY method_contract.json /app/method_contract.json
COPY output_schema.json /app/output_schema.json
COPY SOURCE_NOTICE.md /app/SOURCE_NOTICE.md
