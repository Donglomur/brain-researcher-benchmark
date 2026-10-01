FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.2.6 \
      scipy==1.17.0 \
      pooch==1.9.0 \
      mne==1.12.1 pytest==8.4.1 pytest-json-ctrf==0.3.5 && \
    rm -rf /var/lib/apt/lists/*
COPY data_manifest.json fetch_data.py /tmp/eegbci-build/
RUN python3 /tmp/eegbci-build/fetch_data.py --destination /app/data/eegmmidb \
    && chmod -R a-w /app/data/eegmmidb
ENV EEGBCI_DATA_DIR=/app/data/eegmmidb
ENV MPLBACKEND=Agg
WORKDIR /app
