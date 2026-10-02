FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS dependencies
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates coreutils && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    numpy==2.2.6 scipy==1.17.0 pandas==2.3.3 pytest==8.4.1 pytest-json-ctrf==0.3.5

FROM dependencies AS source
COPY stage_data.py source_manifest.json /opt/source/
# One conditional GET per frozen member, no redirects/retries; bounded build only.
RUN timeout --kill-after=10s 1830s python3 /opt/source/stage_data.py \
    --manifest /opt/source/source_manifest.json --destination /app/data/fcmatur --work-dir /source_capture

FROM dependencies AS runtime
COPY --from=source /app/data/fcmatur /app/data/fcmatur
COPY stage_data.py /opt/source/stage_data.py
COPY source_manifest.json method_contract.json output_schema.json SOURCE_NOTICE.md subject_ids.txt /app/
# Public arithmetic contract only: no I/O, original loader, outcomes or answers.
COPY statistics_kernel.py /app/statistics_kernel.py
WORKDIR /app
