FROM ubuntu:24.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl git && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.2.6 \
      scipy==1.17.0 \
      scikit-learn==1.8.0 \
      pandas==2.3.3 \
      matplotlib==3.10.8 \
      nibabel==5.4.2 \
      nilearn==0.13.1 \
      neuromaps==0.0.7 \
      brainsmash==0.11.0 && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
