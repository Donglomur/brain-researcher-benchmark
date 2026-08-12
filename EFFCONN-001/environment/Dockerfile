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
# to the repo. Source: ABIDE cpac rois_dosenbach160, band-pass filtered, no GSR (filt_noglobal),
# fetched from the official nilearn mirror and re-packaged exactly as the shipped bundle: per-subject
# Dosenbach-160 ROI time series (the .1D files have 161 cols -> keep the first 160), keep subjects
# with >= 150 time points, deterministic first 250 in fetch order, float16; dx retained (1=ASD,2=TD).
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import numpy as np
from nilearn.datasets import fetch_abide_pcp
NROI, MIN_T, N_KEEP = 160, 150, 250
d = fetch_abide_pcp(derivatives=["rois_dosenbach160"], pipeline="cpac",
                    band_pass_filtering=True, global_signal_regression=False,
                    quality_checked=False, verbose=0)
ph = d.phenotypic
# stage 1 — build the shared per-subject timeseries list (same filter as the shared dos160 bundle)
ts_all, dx_all = [], []
for i, arr in enumerate(d.rois_dosenbach160):
    a = np.asarray(arr, float)
    if a.ndim == 2 and a.shape[0] >= 76 and a.shape[1] >= NROI:   # dos160 .1D has 161 cols
        ts_all.append(a[:, :NROI].astype(np.float16))            # T x 160, float16
        dx_all.append(float(np.asarray(ph["DX_GROUP"])[i]))
dx_all = np.array(dx_all)
# stage 2 — task subset: subjects with >= 150 TRs (so each split-half keeps >= 75), first 250 in order
T = np.array([t.shape[0] for t in ts_all])
keep = np.where(T >= MIN_T)[0][:N_KEEP]
assert len(keep) >= 100, f"too few subjects built ({len(keep)})"
ts = np.empty(len(keep), object)
for k, i in enumerate(keep):
    ts[k] = np.asarray(ts_all[i], np.float16)[:, :NROI]
dx = dx_all[keep].astype(np.int8)                                 # 1 = ASD, 2 = TD
np.savez_compressed("/opt/bundle/dos160_causal.npz",
                    ts=ts, dx=dx, atlas="Dosenbach-160", n_roi=NROI)
Ts = [ts[k].shape[0] for k in range(len(ts))]
print(f"built dos160_causal.npz: {len(ts)} subjects  T min/median/max = "
      f"{min(Ts)}/{int(np.median(Ts))}/{max(Ts)}  asd/td = {np.bincount(dx)[1:3]}")
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
