FROM ubuntu:24.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates python3 python3-venv python3-pip curl && \
    python3 -m pip install --break-system-packages --no-cache-dir \
      numpy==2.1.3 scipy==1.14.1 scikit-learn==1.5.2 pandas==2.2.3 \
      nibabel==5.3.2 nilearn==0.12.1 && \
    rm -rf /var/lib/apt/lists/*
# Build the analysis bundle at IMAGE-BUILD time (internet available here). It is written into the
# image so the agent runs fully OFFLINE (task.toml allow_internet=false); no derived data is fetched
# at run time. Source: ABIDE cpac rois_cc200, band-pass filtered / no global-signal regression,
# fetched from the official nilearn mirror. Each subject's ROIxROI time series is turned into a
# Fisher-z connectome (upper triangle of the 200x200 Pearson-r matrix, 19,900 edges), then the sample
# is subset to the columns this task uses: the subject x edge matrix X, the diagnosis dx (1=ASD,
# 2=TD) and the acquisition site SITE_ID, dropping subjects without a valid dx or site. Stored as
# float16 to keep the bundle compact.
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import numpy as np
from nilearn.datasets import fetch_abide_pcp

abide = fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                        band_pass_filtering=True, global_signal_regression=False,
                        quality_checked=False, verbose=0)
ph = abide.phenotypic
iu = np.triu_indices(200, 1)                          # 19,900 upper-triangle edges
X, rows = [], []
for i, arr in enumerate(abide.rois_cc200):
    a = np.asarray(arr, float)
    if a.ndim == 2 and a.shape[0] >= 60 and a.shape[1] >= 200:
        with np.errstate(all="ignore"):
            c = np.corrcoef(a[:, :200].T)
        X.append(np.arctanh(np.clip(c[iu], -0.999, 0.999)).astype(np.float32))
        rows.append(i)
X = np.array(X, np.float32)
dx = np.asarray(ph["DX_GROUP"], float)[rows]          # 1=ASD, 2=TD
site = np.asarray(ph["SITE_ID"])[rows]                # SITE_ID string


def _bad_site(s):
    return s is None or (isinstance(s, float) and np.isnan(s)) or str(s).strip() in ("", "nan", "NaN")


keep = np.array([(dv in (1.0, 2.0)) and (not _bad_site(sv)) for dv, sv in zip(dx, site)])
X = X[keep].astype(np.float16)
dx = dx[keep].astype(np.int8)
site = np.array([str(s) for s in site])[keep]
assert X.shape[0] >= 800 and len(np.unique(site)) >= 10, (
    f"too few subjects/sites built ({X.shape[0]} subjects, {len(np.unique(site))} sites)")

np.savez_compressed("/opt/bundle/cc200_deeplin.npz", X=X, dx=dx, site=site,
                    atlas="Craddock-200 (cc200)",
                    edges="upper triangle of 200x200, Pearson r, Fisher-z",
                    dx_coding="1=ASD, 2=TD (control)")
print(f"built cc200_deeplin.npz: X={X.shape} dx(1=ASD,2=TD)={np.bincount(dx.astype(int))[1:3].tolist()} "
      f"sites={len(np.unique(site))}")
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
