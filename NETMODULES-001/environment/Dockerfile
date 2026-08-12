FROM ubuntu:24.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.1.3 scipy==1.14.1 scikit-learn==1.5.2 networkx==3.4.2 \
      pandas==2.2.3 nibabel==5.3.2 nilearn==0.12.1 && \
    rm -rf /var/lib/apt/lists/*
# Build the analysis bundle at IMAGE-BUILD time (internet available here). It is written into the
# image so the agent runs fully OFFLINE (task.toml allow_internet=false); no derived data is committed
# to the repo. Source: ABIDE cpac rois_dosenbach160, band-pass filtered / no GSR (filt_noglobal),
# fetched from the official nilearn mirror and re-packaged into the SAME connectome bundle this task
# uses: each usable subject's Fisher-z connectome (upper triangle of the 160x160 Dosenbach-160 ROI
# correlation matrix -> 12,720 float16 edges) plus dx (1=ASD, 2=TD) and subject id.
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import numpy as np
from nilearn import datasets
NROI = 160
ab = datasets.fetch_abide_pcp(derivatives=["rois_dosenbach160"], pipeline="cpac",
                              band_pass_filtering=True, global_signal_regression=False,
                              quality_checked=False, verbose=0)
ph = ab.phenotypic
iu = np.triu_indices(NROI, 1)
X, y, ids = [], [], []
for i, arr in enumerate(ab.rois_dosenbach160):
    a = np.asarray(arr, float)                       # dosenbach160 .1D has 161 columns; keep first 160
    if a.ndim != 2 or a.shape[0] < 76 or a.shape[1] < NROI:
        continue
    ts16 = a[:, :NROI].astype(np.float16)            # shared-bundle timeseries precision (float16)
    a2 = np.asarray(ts16, float)                      # connectome derived from that float16 series
    c = np.corrcoef(a2.T)
    z = np.nan_to_num(np.arctanh(np.clip(c[iu], -0.999, 0.999)), nan=0.0).astype(np.float16)
    X.append(z)
    y.append(int(np.asarray(ph["DX_GROUP"])[i]))
    ids.append(int(np.asarray(ph["SUB_ID"])[i]))
assert len(X) >= 200, f"too few subjects built ({len(X)})"
X = np.array(X, np.float16)
y = np.array(y, np.int8)
ids = np.array(ids)
np.savez_compressed("/opt/bundle/dos160_modular.npz", X=X, dx=y, subid=ids,
                    atlas="Dosenbach-160", n_roi=NROI, edges_upper_triangle_of=NROI)
print(f"built dos160_modular.npz: X={X.shape} dtype={X.dtype} "
      f"dx(1=ASD/2=TD)={np.bincount(y.astype(int))[1:3]}")
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
