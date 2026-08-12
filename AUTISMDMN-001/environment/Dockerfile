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
# image so the agent runs fully OFFLINE (task.toml allow_internet=false); no derived data is committed
# to the repo. Source: ABIDE cpac rois_dosenbach160, band-pass FILTERED, no global-signal regression
# (filt_noglobal), fetched from the official nilearn mirror and re-packaged EXACTLY as this task's
# build pipeline: per-subject Fisher-z functional connectome (upper triangle of the 160x160 Pearson
# matrix -> 12,720 float16 edges, degenerate-ROI edges kept as NaN) + the phenotypes the task uses
# (dx 1=ASD/2=TD, site, age, sex, motion=func_mean_fd) + Dosenbach-160 network labels.
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import os
import numpy as np
from nilearn import datasets

NROI = 160

# 1) Fetch the SAME ABIDE derivative + preprocessing this task's bundle was built from.
ab = datasets.fetch_abide_pcp(derivatives=["rois_dosenbach160"], pipeline="cpac",
                              band_pass_filtering=True, global_signal_regression=False,
                              quality_checked=False, verbose=0)
ph = ab.phenotypic

# 2) Per-subject ROI timeseries (dosenbach160 .1D has 161 columns -> keep the first 160 ROI columns),
#    float16, with the phenotypes this task uses. Same selection/order as the shared build.
ts, dx, age, sex, site, motion = [], [], [], [], [], []
for i, arr in enumerate(ab.rois_dosenbach160):
    a = np.asarray(arr, float)
    if a.ndim == 2 and a.shape[0] >= 76 and a.shape[1] >= NROI:
        r = ph.iloc[i]                      # positional row (phenotypic aligned with derivative order)
        ts.append(a[:, :NROI].astype(np.float16))
        dx.append(float(r["DX_GROUP"]))
        age.append(float(r["AGE_AT_SCAN"]))
        sex.append(float(r["SEX"]))
        site.append(str(r["SITE_ID"]))
        motion.append(float(r["func_mean_fd"]))
dx = np.array(dx); age = np.array(age); sex = np.array(sex)
site = np.array(site); motion = np.array(motion)

# 3) Fisher-z functional connectome: upper triangle of the 160x160 Pearson matrix (12,720 edges),
#    degenerate (flat) ROI edges kept as NaN (not fabricated).
networks = np.asarray(datasets.fetch_coords_dosenbach_2010().networks).astype("U24")
assert len(networks) == NROI, f"expected {NROI} network labels, got {len(networks)}"

iu = np.triu_indices(NROI, 1)
X, keep = [], []
for a16 in ts:
    a = np.asarray(a16, float)
    if a.ndim != 2 or a.shape[0] < 76 or a.shape[1] < NROI:
        keep.append(False)
        continue
    c = np.corrcoef(a[:, :NROI].T)
    z = np.arctanh(np.clip(c[iu], -0.999, 0.999))
    X.append(z.astype(np.float16))
    keep.append(True)

keep = np.array(keep, bool)
X = np.asarray(X, dtype=np.float16)                       # subjects x 12,720 edges
dx = dx[keep].astype(np.int8)                             # 1=ASD, 2=TD
site = site[keep].astype("U16")
age = age[keep].astype(np.float32)
sex = sex[keep].astype(np.int8)
motion = motion[keep].astype(np.float32)

np.savez_compressed("/opt/bundle/dos160_autconn.npz", X=X, dx=dx, site=site, age=age, sex=sex,
                    motion=motion, networks=networks, atlas="Dosenbach-160",
                    edges_upper_triangle_of=NROI)
print(f"built dos160_autconn.npz: X={X.shape} asd/td={np.bincount(dx.astype(int))[1:3]} "
      f"sites={len(set(site.tolist()))}")
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
