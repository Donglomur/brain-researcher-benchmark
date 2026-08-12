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
# (filt_noglobal), fetched from the official nilearn mirror, plus the Dosenbach-160 coordinate atlas.
# Each subject's Fisher-z upper-triangle connectome (12,720 edges over 160 ROIs) is re-derived exactly
# as the committed bundle was (float16), and re-packaged to /opt/bundle/dos160_hubmap.npz.
# Note: the dosenbach160 .1D files carry 161 columns, so the ROI axis is sliced to the first 160.
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import numpy as np
from nilearn import datasets

NROI = 160
iu = np.triu_indices(NROI, 1)

# --- per-subject ROI timeseries: ABIDE cpac dosenbach160, band-pass filtered, no GSR --------------
ab = datasets.fetch_abide_pcp(derivatives=["rois_dosenbach160"], pipeline="cpac",
                              band_pass_filtering=True, global_signal_regression=False,
                              quality_checked=False, verbose=0)
ph = ab.phenotypic
ts, dxl = [], []
for i, arr in enumerate(ab.rois_dosenbach160):
    a = np.asarray(arr, float)                       # dosenbach160 .1D has 161 cols -> slice to 160
    if a.ndim == 2 and a.shape[0] >= 76 and a.shape[1] >= 160:
        ts.append(a[:, :NROI].astype(np.float16))    # float16 quantization matches the shared bundle
        dxl.append(float(np.asarray(ph["DX_GROUP"])[i]))
assert len(ts) >= 100, f"too few subjects built ({len(ts)})"
dx = np.array(dxl).astype(np.int8)                   # 1 = ASD, 2 = control (TD)

# --- Dosenbach-160 atlas: network + anatomical label + MNI coord per ROI --------------------------
dos = datasets.fetch_coords_dosenbach_2010()
networks = np.asarray(dos.networks).astype("U24")
labels = np.asarray(dos.labels).astype("U40")
coords = dos.rois[["x", "y", "z"]].to_numpy().astype(np.float32)

# --- per-subject Fisher-z connectome (upper triangle, 12,720 edges) -------------------------------
X = []
for a in ts:
    a = np.asarray(a, float)[:, :NROI]               # float16 -> float, exactly as build_hubmap.py
    c = np.corrcoef(a.T)
    c = np.nan_to_num(c, nan=0.0)                     # dead/constant ROI -> no connectivity
    X.append(np.arctanh(np.clip(c[iu], -0.999, 0.999)).astype(np.float16))
X = np.array(X, np.float16)                           # subjects x 12,720 edges

np.savez_compressed("/opt/bundle/dos160_hubmap.npz", X=X, dx=dx,
                    networks=networks, labels=labels, coords=coords,
                    atlas="Dosenbach-160", edges_upper_triangle_of=NROI)
print(f"built dos160_hubmap.npz: X={X.shape} float16; "
      f"bincount(1=ASD,2=TD)={np.bincount(dx.astype(int))[1:3]}; atlas={NROI} ROIs")
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
