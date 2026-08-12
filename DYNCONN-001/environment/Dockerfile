FROM ubuntu:24.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.1.3 scipy==1.14.1 pandas==2.2.3 \
      nibabel==5.3.2 nilearn==0.12.1 && \
    rm -rf /var/lib/apt/lists/*
# Build the analysis bundle at IMAGE-BUILD time (internet available here). It is written into the
# image so the agent runs fully OFFLINE (task.toml allow_internet=false); no derived data is committed
# to the repo. Source: ABIDE cpac rois_dosenbach160, BAND-PASS FILTERED, no global-signal regression
# (filt_noglobal), fetched from the official nilearn mirror and re-packaged (deterministic first 60
# valid subjects, T x 160 float16 ROI time series). NOTE: the dosenbach160 .1D files carry 161 columns
# (nilearn loads them verbatim via np.loadtxt), so keep the first 160 ROI columns.
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import numpy as np
from nilearn.datasets import fetch_abide_pcp
d = fetch_abide_pcp(derivatives=["rois_dosenbach160"], pipeline="cpac",
                    band_pass_filtering=True, global_signal_regression=False,
                    quality_checked=False, verbose=0)
ts = []
for arr in d.rois_dosenbach160:
    a = np.asarray(arr, float)
    if a.ndim != 2 or a.shape[0] < 76 or a.shape[1] < 160:   # dosenbach160 .1D has 161 columns
        continue
    ts.append(a[:, :160].astype(np.float16))                 # keep the first 160 ROI columns
    if len(ts) >= 60:
        break
assert len(ts) >= 30, f"too few subjects built ({len(ts)})"
out = np.empty(len(ts), dtype=object)
out[:] = ts
np.savez_compressed("/opt/bundle/dos160_dynfc.npz", ts=out, atlas="Dosenbach-160",
                    preprocessing="ABIDE cpac filt_noglobal (band-pass filtered, no GSR)")
print("built dos160_dynfc.npz:", len(ts), "subjects")
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
