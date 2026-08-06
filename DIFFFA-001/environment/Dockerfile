FROM ubuntu:24.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.1.3 scipy==1.14.1 nibabel==5.3.2 h5py==3.12.1 tqdm==4.67.1 \
      dipy==1.12.1 && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
