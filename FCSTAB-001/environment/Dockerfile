FROM ubuntu:24.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.1.3 \
      scipy==1.14.1 \
      scikit-learn==1.5.2 \
      pandas==2.2.3 \
      nibabel==5.3.2 \
      nilearn==0.12.1 \
      pytest==8.4.1 \
      pytest-json-ctrf==0.3.5 && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Bake the exact CC200 ROI time series (40 quality-checked ABIDE cpac PITT subjects) into the
# image so the task runs fully OFFLINE (task.toml sets allow_internet=false). MANIFEST.json
# pins the subject/file ids and content hashes.
COPY data /app/data
