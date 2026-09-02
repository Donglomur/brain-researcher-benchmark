FROM ubuntu:24.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.2.6 \
      scipy==1.17.0 \
      pooch==1.9.0 \
      mne==1.12.1 && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
