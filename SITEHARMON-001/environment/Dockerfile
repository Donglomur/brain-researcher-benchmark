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
# to the repo. Source: ABIDE cpac rois_cc200 (band-pass filtered, no GSR, not quality-checked),
# fetched from the official nilearn mirror. Fisher-z cc200 connectomes (upper triangle, 19,900 edges)
# for every usable subject + the phenotypes this task uses (AGE_AT_SCAN, SITE_ID, SUB_ID); subjects
# with valid age AND site kept; ROI edges stored float16.
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import numpy as np
from nilearn.datasets import fetch_abide_pcp
d = fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                    band_pass_filtering=True, global_signal_regression=False,
                    quality_checked=False, verbose=0)
ph = d.phenotypic
age_all = np.asarray(ph["AGE_AT_SCAN"], float)
site_all = np.asarray(ph["SITE_ID"]).astype(str)
subid_all = np.asarray(ph["SUB_ID"], float)
iu = np.triu_indices(200, 1)
X, rows = [], []
for i, arr in enumerate(d.rois_cc200):
    a = np.asarray(arr, float)
    if a.ndim == 2 and a.shape[0] >= 60 and a.shape[1] >= 200:
        with np.errstate(all="ignore"):
            c = np.corrcoef(a[:, :200].T)
        X.append(np.arctanh(np.clip(c[iu], -0.999, 0.999)).astype(np.float32))
        rows.append(i)
X = np.array(X, np.float32)
age = age_all[rows]; site = site_all[rows]; subid = subid_all[rows]
valid = np.isfinite(age) & np.array([s not in ("", "nan", "NaN", "None") for s in site])
X, age, site, subid = X[valid], age[valid], site[valid], subid[valid]
assert X.shape[0] >= 800, f"too few subjects built ({X.shape[0]})"
np.savez_compressed("/opt/bundle/cc200_harmon.npz",
                    X=X.astype(np.float16), age=age.astype(np.float32),
                    site=site.astype(object), subid=subid.astype(np.int64),
                    atlas="Craddock-200 (cc200)", edges_upper_triangle_of=200)
print("built cc200_harmon.npz:", X.shape[0], "subjects,", len(np.unique(site)), "sites")
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
