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
# to the repo. Source: ABIDE cpac rois_cc200, band-pass filtered, no global-signal regression, fetched
# from the official nilearn mirror and re-packaged into the SAME cc200 Fisher-z connectome bundle this
# task uses (upper triangle of the 200x200 Pearson-correlation matrix, arctanh-transformed, float16),
# subset to subjects with a valid SEX label (1=male, 2=female).
RUN mkdir -p /opt/bundle && python3 - <<'PY'
import numpy as np
from nilearn import datasets
abide = datasets.fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                                 band_pass_filtering=True, global_signal_regression=False,
                                 quality_checked=False, verbose=0)
ph = abide.phenotypic
iu = np.triu_indices(200, 1)                       # 19,900 upper-triangle edges of a 200-region atlas
X, rows = [], []
for i, arr in enumerate(abide.rois_cc200):
    a = np.asarray(arr, float)
    if a.ndim == 2 and a.shape[0] >= 60 and a.shape[1] >= 200:
        c = np.corrcoef(a[:, :200].T)              # 200x200 Pearson correlation (constant ROI -> NaN)
        X.append(np.arctanh(np.clip(c[iu], -0.999, 0.999)).astype(np.float32))  # Fisher-z edges
        rows.append(i)
X = np.array(X, np.float32)


def col(name, dt=float):
    try:
        return np.asarray(ph[name], dt)[rows]
    except Exception:
        return np.full(len(rows), np.nan)


sex_all = col("SEX", float)
subid_all = col("SUB_ID", float)
valid = np.isin(sex_all, [1.0, 2.0]) & np.isfinite(sex_all)   # keep only valid male(1)/female(2)
Xv = X[valid].astype(np.float16)                    # subjects x 19,900 Fisher-z cc200 edges
sex = sex_all[valid].astype(np.int8)                # SEX: 1 = male, 2 = female
subid = subid_all[valid].astype(np.int64)           # subject IDs
assert Xv.shape[0] >= 200, f"too few subjects built ({Xv.shape[0]})"
assert set(np.unique(sex).tolist()) == {1, 2}, f"unexpected sex labels {np.unique(sex).tolist()}"
np.savez_compressed("/opt/bundle/cc200_baserate.npz", X=Xv, sex=sex, subid=subid,
                    atlas="Craddock-200", edges_upper_triangle_of=200)
print("built cc200_baserate.npz:", Xv.shape, "sex_counts(1=M,2=F)=",
      np.bincount(sex.astype(int))[1:3].tolist())
PY
ENV BUNDLE_DIR=/opt/bundle
WORKDIR /app
