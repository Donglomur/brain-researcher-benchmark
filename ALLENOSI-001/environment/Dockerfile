FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates python3 python3-venv python3-pip && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.1.3 scipy==1.14.1 h5py==3.12.1 \
      pytest==8.4.1 pytest-json-ctrf==0.3.5 && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1

FROM dependencies AS source
COPY fetch_data.py data_manifest.json /opt/source/
RUN python3 /opt/source/fetch_data.py --destination /app/data/allenosi

FROM source AS runtime
COPY method_contract.json /app/method_contract.json
