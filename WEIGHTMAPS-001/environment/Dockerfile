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
# to the repo. Source: ABIDE cpac rois_cc200, band-pass filtered (filt_noglobal), fetched from the
# official nilearn mirror. Per subject: Fisher-z of the upper triangle of the 200x200 Craddock-200 ROI
# correlation matrix (19,900 edges); keep every subject with a valid diagnosis (1=ASD, 2=TD).
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
X = np.array(X, np.float32)
dx = np.asarray(ph["DX_GROUP"], float)[rows]
keep = np.isin(dx, [1.0, 2.0]) & np.isfinite(dx)          # valid diagnosis (1=ASD, 2=TD); drop NaN
X = np.asarray(X[keep], np.float32)
y = np.asarray(dx[keep], np.int8)                          # 1 = ASD, 2 = TD
assert X.shape[0] >= 200, f"too few subjects built ({X.shape[0]})"
np.savez_compressed("/opt/bundle/cc200_interp.npz", X=X, y=y,
                    atlas="Craddock-200", edges_upper_triangle_of=200)
print("built cc200_interp.npz:", X.shape, "y(1=ASD/2=TD)=", np.bincount(y)[1:3])
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
