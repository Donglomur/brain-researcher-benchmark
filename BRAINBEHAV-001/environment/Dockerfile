FROM ubuntu:24.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.1.3 \
      scipy==1.14.1 \
      pandas==2.2.3 \
      nibabel==5.3.2 \
      nilearn==0.12.1 && \
    rm -rf /var/lib/apt/lists/*
# Build the analysis bundle at IMAGE-BUILD time (internet available here). It is written into the
# image so the agent runs fully OFFLINE (task.toml allow_internet=false); no derived data is relied on
# from the repo at runtime. Source: ABIDE cpac rois_cc200, band-pass FILTERED (filt_noglobal, no GSR),
# fetched from the official nilearn mirror and re-packaged into edgewise Fisher-z connectomes + FIQ.
# Reproduces the shared cc200 connectome build then subsets to subjects with a valid full-scale IQ and
# a fully finite connectome (float16 edges), matching the packaged cc200_bwas.npz (n~925, 19,900 edges).
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import numpy as np
from nilearn.datasets import fetch_abide_pcp
d = fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                    band_pass_filtering=True, global_signal_regression=False,
                    quality_checked=False, verbose=0)
ph = d.phenotypic
fiq_all = np.asarray(ph["FIQ"], float)          # full-scale IQ (ABIDE codes missing as -9999)
iu = np.triu_indices(200, 1)                     # upper triangle of the 200x200 cc200 matrix
X, rows = [], []
for i, arr in enumerate(d.rois_cc200):
    a = np.asarray(arr, float)
    if a.ndim == 2 and a.shape[0] >= 60 and a.shape[1] >= 200:
        with np.errstate(all="ignore"):
            c = np.corrcoef(a[:, :200].T)        # 200x200 ROI-ROI correlation
        X.append(np.arctanh(np.clip(c[iu], -0.999, 0.999)).astype(np.float32))  # Fisher-z edges
        rows.append(i)
X = np.array(X, np.float32)
fiq = fiq_all[rows]
# Subset exactly as the offline build: valid FIQ (finite, >0) AND a fully finite connectome.
valid = np.isfinite(fiq) & (fiq > 0)
X, fiq = X[valid], fiq[valid]
clean = np.isfinite(X).all(1)
X, fiq = X[clean], fiq[clean]
assert np.isfinite(X).all() and np.isfinite(fiq).all(), "non-finite values survived filtering"
assert X.shape[0] >= 100 and X.shape[1] == 19900, f"unexpected bundle shape {X.shape}"
np.savez_compressed("/opt/bundle/cc200_bwas.npz",
                    X=X.astype(np.float16), fiq=fiq.astype(np.float32),
                    atlas="Craddock-200", edges_upper_triangle_of=200)
print("built cc200_bwas.npz:", X.shape, "subjects", len(fiq),
      "FIQ mean %.1f sd %.1f" % (fiq.mean(), fiq.std()))
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
