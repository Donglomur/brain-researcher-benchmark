FROM ubuntu:24.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.1.3 scipy==1.14.1 scikit-learn==1.5.2 pandas==2.2.3 \
      nibabel==5.3.2 nilearn==0.13.1 && \
    rm -rf /var/lib/apt/lists/*
# Build the analysis bundle at IMAGE-BUILD time (internet available here). It is written into the
# image so the agent runs fully OFFLINE (task.toml allow_internet=false); no derived data is committed
# to the repo. Source: NKI Enhanced resting-state surface data (TR=645 ms, fsaverage5), fetched with
# nilearn.datasets.fetch_surf_nki_enhanced (first 60 subjects, ages 18-78). Each subject's left+right
# fsaverage5 time series is parcellated into the 148-region Destrieux atlas (region-mean time series);
# the bundle holds the (n_subjects, 895, 148) region time series plus age and sex. The download is
# ~5 GB from the NKI/NITRC mirror and can be slow; the fetch is retried until it completes, then the
# raw surface files are removed to keep the image small.
COPY build_bundle.py cohort_manifest.json /opt/build/
RUN mkdir -p /opt/bundle && python3 /opt/build/build_bundle.py
# drop the raw ~5 GB surface download; keep only the compact bundle
RUN rm -rf /root/nilearn_data
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
