FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl git && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.1.3 scipy==1.14.1 pandas==2.2.3 nibabel==5.3.2 \
      scikit-learn==1.5.2 nilearn==0.12.1 pytest==8.4.1 pytest-json-ctrf==0.3.5 && \
    rm -rf /var/lib/apt/lists/*
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /app
RUN python3 -m pip install --break-system-packages --no-cache-dir brainspace==0.1.20
ENV PYTHONDONTWRITEBYTECODE=1

FROM dependencies AS source
COPY stage_data.py source_manifest.json /opt/source/
RUN timeout --kill-after=10s 630s python3 /opt/source/stage_data.py \
      --manifest /opt/source/source_manifest.json --destination /app/data/gradient --work-dir /source_capture

FROM dependencies AS runtime
COPY --from=source /app/data/gradient /app/data/gradient
COPY stage_data.py /opt/source/stage_data.py
COPY source_manifest.json /app/source_manifest.json
COPY method_contract.json /app/method_contract.json
COPY output_schema.json /app/output_schema.json
COPY SOURCE_NOTICE.md /app/SOURCE_NOTICE.md
