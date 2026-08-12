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
# nilearn mirror and re-packaged (deterministic first 150 valid subjects, float16 ROI time series).
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import numpy as np
from nilearn.datasets import fetch_abide_pcp
d = fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                    band_pass_filtering=False, global_signal_regression=False,
                    quality_checked=False, verbose=0)
fids = list(d.phenotypic["FILE_ID"])
ts, sub = [], []
for arr, fid in zip(d.rois_cc200, fids):
    a = np.asarray(arr)
    if a.ndim != 2 or a.shape[0] < 80 or a.shape[1] != 200:
        continue
    ts.append(a.astype(np.float16)); sub.append(str(fid))
    if len(ts) >= 150:
        break
assert len(ts) >= 100, f"too few subjects built ({len(ts)})"
np.savez_compressed("/opt/bundle/cc200_nofilt_ts.npz",
                    ts=np.array(ts, dtype=object), subid=np.array(sub),
                    pipeline="cpac nofilt_noglobal", atlas="cc200")
print("built cc200_nofilt_ts.npz:", len(ts), "subjects")
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
