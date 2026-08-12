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
# to the repo. Source: ABIDE cpac rois_cc200, band-pass FILTERED, no global-signal regression, NOT
# quality-checked (all 1035 subjects that have a cc200 derivative), fetched from the official nilearn
# mirror and re-packaged into per-subject Fisher-z Craddock-200 connectomes (upper triangle, 19,900
# edges, float16) with AGE_AT_SCAN, SITE_ID and SUB_ID.
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import numpy as np
from nilearn.datasets import fetch_abide_pcp
d = fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                    band_pass_filtering=True, global_signal_regression=False,
                    quality_checked=False, verbose=0)
ph = d.phenotypic
ages = np.asarray(ph["AGE_AT_SCAN"], dtype=float)
sites = [str(s) for s in ph["SITE_ID"]]
subs = np.asarray(ph["SUB_ID"], dtype=np.int64)
iu = np.triu_indices(200, k=1)
X, age, site, subid = [], [], [], []
for arr, a_age, a_site, a_sub in zip(d.rois_cc200, ages, sites, subs):
    ts = np.asarray(arr, dtype=np.float64)
    if ts.ndim != 2 or ts.shape[1] != 200:
        continue
    if not np.isfinite(a_age):
        continue
    with np.errstate(all="ignore"):
        C = np.corrcoef(ts.T)                                 # 200 x 200 Pearson FC
        z = np.arctanh(np.clip(C[iu], -0.999999, 0.999999))   # Fisher-z upper triangle (19,900)
    X.append(z.astype(np.float16))
    age.append(np.float32(a_age)); site.append(a_site); subid.append(int(a_sub))
X = np.asarray(X, dtype=np.float16)
age = np.asarray(age, dtype=np.float32)
site = np.asarray(site)
subid = np.asarray(subid, dtype=np.int64)
assert X.shape[0] >= 300, f"too few subjects built ({X.shape[0]})"
np.savez_compressed("/opt/bundle/cc200_range.npz",
                    X=X, age=age, site=site, subid=subid,
                    atlas="Craddock-200", edges="upper_triangle_of_200_Fisher_z")
print("built cc200_range.npz:", X.shape[0], "subjects x", X.shape[1], "edges")
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
