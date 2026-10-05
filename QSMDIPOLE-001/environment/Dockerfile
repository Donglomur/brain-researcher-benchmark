FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS dependencies
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl unzip && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.1.3 \
      scipy==1.14.1 \
      nibabel==5.3.2 \
      pytest==8.4.1 \
      pytest-json-ctrf==0.3.5 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
WORKDIR /app

FROM dependencies AS runtime
COPY data/ /app/data/
COPY stage_data.py source_manifest.json /opt/source/
RUN python3 /opt/source/stage_data.py --destination /app/data
COPY method_contract.json /app/method_contract.json
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
