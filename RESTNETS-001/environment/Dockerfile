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
# to the repo. Source: ABIDE cpac rois_dosenbach160, band-pass FILTERED (filt_noglobal), fetched from
# the official nilearn mirror and re-packaged: the first 80 CONTROL subjects (DX_GROUP==2) with a
# usable time series, sorted by subject id, stored as float16 ROI time series (each T x 160). Note the
# Dosenbach-160 .1D files carry 161 columns, so the leading extra column is dropped ([:, :160]).
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import numpy as np
from nilearn.datasets import fetch_abide_pcp
d = fetch_abide_pcp(derivatives=["rois_dosenbach160"], pipeline="cpac",
                    band_pass_filtering=True, global_signal_regression=False,
                    quality_checked=False, verbose=0)
ph = d.phenotypic
# Per-subject ROI time series, mirroring the shared dos160 bundle: keep 2D series with enough time
# points and >=160 ROIs; Dosenbach-160 .1D has 161 columns, so keep the first 160.
ts_all, dx_all, sub_all = [], [], []
for i, arr in enumerate(d.rois_dosenbach160):
    a = np.asarray(arr, float)
    if a.ndim == 2 and a.shape[0] >= 76 and a.shape[1] >= 160:
        ts_all.append(a[:, :160].astype(np.float16))
        dx_all.append(float(np.asarray(ph["DX_GROUP"])[i]))
        sub_all.append(int(np.asarray(ph["SUB_ID"])[i]))
subid = np.array(sub_all)
dx = np.array(dx_all, float)
# RESTNETS selection: CONTROL subjects (DX_GROUP==2) with a usable series (T>=100, >=160 ROIs),
# deterministic order sorted by subject id, first 80.
N_SUBJECTS, MIN_T = 80, 100
ctrl = [i for i in np.argsort(subid)
        if dx[i] == 2
        and np.asarray(ts_all[i]).ndim == 2
        and np.asarray(ts_all[i]).shape[0] >= MIN_T
        and np.asarray(ts_all[i]).shape[1] >= 160]
keep = ctrl[:N_SUBJECTS]
assert len(keep) >= 40, f"too few control subjects built ({len(keep)})"
out_ts = np.empty(len(keep), dtype=object)
for j, i in enumerate(keep):
    out_ts[j] = np.asarray(ts_all[i], dtype=np.float16)[:, :160]
out_dx = dx[keep].astype(np.int8)
np.savez_compressed("/opt/bundle/dos160_ica.npz",
                    ts=out_ts, dx=out_dx, atlas="Dosenbach-160", n_rois=160,
                    note="ABIDE control-subject resting-state ROI time series (float16)")
Ts = [a.shape[0] for a in out_ts]
print(f"built dos160_ica.npz: {len(keep)} control subjects, T in [{min(Ts)},{max(Ts)}] x 160")
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
