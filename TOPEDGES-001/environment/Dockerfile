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
# to the repo. Source: ABIDE cpac rois_cc200, UNFILTERED (nofilt_noglobal), fetched from the official
# nilearn mirror and re-packaged into the same subjects x edge Fisher-z connectome bundle this task
# uses (Craddock-200 upper-triangle edges, float16; DX labels 1=ASD/2=TD; first ~400 valid subjects).
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import numpy as np
from nilearn import datasets
abide = datasets.fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                                 band_pass_filtering=False, global_signal_regression=False,
                                 quality_checked=False, n_subjects=400, verbose=0)
dx = np.asarray(abide.phenotypic["DX_GROUP"], float)
sid = np.asarray(abide.phenotypic["SUB_ID"])
iu = np.triu_indices(200, 1)
X, y, ids = [], [], []
for i, arr in enumerate(abide.rois_cc200):
    a = np.asarray(arr, float)
    if a.ndim == 2 and a.shape[0] >= 60 and a.shape[1] >= 200:
        c = np.corrcoef(a[:, :200].T)
        X.append(np.arctanh(np.clip(c[iu], -0.999, 0.999)).astype(np.float16))
        y.append(int(dx[i])); ids.append(int(sid[i]))
X = np.array(X, np.float16); y = np.array(y, np.int8); ids = np.array(ids)
assert X.shape[0] >= 120, f"too few subjects built ({X.shape[0]})"
np.savez_compressed("/opt/bundle/cc200_connectomes.npz", X=X, y=y, subjects=ids,
                    atlas="Craddock-200", edges_upper_triangle_of=200)
print(f"built cc200_connectomes.npz: X={X.shape} y(1=ASD/2=TD)={np.bincount(y)[1:3]}")
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
