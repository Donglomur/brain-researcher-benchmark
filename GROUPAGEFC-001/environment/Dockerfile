FROM ubuntu:24.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.1.3 scipy==1.14.1 scikit-learn==1.5.2 pandas==2.2.3 \
      nibabel==5.3.2 nilearn==0.12.1 && \
    rm -rf /var/lib/apt/lists/*
# Build the analysis bundle at IMAGE-BUILD time (internet available here). It is written into the
# image so the agent runs fully OFFLINE (task.toml allow_internet=false); no derived data is committed
# to the repo. Source: ABIDE cpac rois_cc200 (band-pass filtered, no GSR), fetched from the official
# nilearn mirror. Each subject's ROI time series -> Craddock-200 Pearson connectome -> Fisher-z
# upper triangle (19,900 edges); then restricted to subjects with a valid age and site (the ecological
# connectivity-age task needs only X + AGE_AT_SCAN + SITE_ID).
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import numpy as np
from nilearn import datasets
abide = datasets.fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                                 band_pass_filtering=True, global_signal_regression=False,
                                 quality_checked=False, verbose=0)
ph = abide.phenotypic
iu = np.triu_indices(200, 1)
X, rows = [], []
for i, arr in enumerate(abide.rois_cc200):
    a = np.asarray(arr, float)
    if a.ndim == 2 and a.shape[0] >= 60 and a.shape[1] >= 200:
        c = np.corrcoef(a[:, :200].T)
        X.append(np.arctanh(np.clip(c[iu], -0.999, 0.999)).astype(np.float32))
        rows.append(i)
X = np.array(X, np.float32)                        # subjects x 19,900 Fisher-z cc200 edges
age = np.asarray(ph["AGE_AT_SCAN"], float)[rows]   # AGE_AT_SCAN
site = np.asarray(ph["SITE_ID"])[rows].astype(str) # SITE_ID
# keep subjects with a valid (finite) age and a real site label
keep = np.isfinite(age) & np.array([s not in ("", "nan", "None") for s in site])
X, age, site = X[keep], age[keep].astype(np.float32), site[keep]
np.savez_compressed("/opt/bundle/cc200_ecolog.npz", X=X, age=age, site=site,
                    atlas="Craddock-200", edges_upper_triangle_of=200)
print("built cc200_ecolog.npz:", X.shape, "sites", len(np.unique(site)))
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
