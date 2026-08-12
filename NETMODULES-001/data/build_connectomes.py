"""Build the packaged connectome bundle for NETMODULES-001 (route b: offline).

Precomputes each subject's Fisher-z connectome (upper triangle of the 160x160 Dosenbach-160 ROI
correlation matrix -> 12,720 edges) from the shared ABIDE dosenbach160 timeseries bundle, so the
shipped task needs no network. Keeps only the phenotype the task uses: dx (1=ASD, 2=TD). The
community-detection analysis reconstructs the group-mean 160x160 connectome from these edges, so
the full weighted graph is recoverable offline.

Build-only (reads _shared_bundles/, which is git-ignored and not shipped). Not run in-container.
"""
import os

import numpy as np

SRC = "_shared_bundles/dos160_ts.npz"
OUT = "NETMODULES-001/data/dos160_modular.npz"
NROI = 160

d = np.load(SRC, allow_pickle=True)
ts, dx, sub = d["ts"], d["dx"].astype(np.int8), d["subid"]
iu = np.triu_indices(NROI, 1)
X, y, ids = [], [], []
for i, arr in enumerate(ts):
    a = np.asarray(arr, float)
    if a.ndim != 2 or a.shape[0] < 76 or a.shape[1] < NROI:
        continue
    c = np.corrcoef(a[:, :NROI].T)
    z = np.nan_to_num(np.arctanh(np.clip(c[iu], -0.999, 0.999)), nan=0.0).astype(np.float16)
    X.append(z)
    y.append(int(dx[i]))
    ids.append(int(sub[i]))
X = np.array(X, np.float16)
y = np.array(y, np.int8)
ids = np.array(ids)
np.savez_compressed(OUT, X=X, dx=y, subid=ids, atlas="Dosenbach-160",
                    n_roi=NROI, edges_upper_triangle_of=NROI)
print(f"saved X={X.shape} dtype={X.dtype} ({os.path.getsize(OUT)/1e6:.2f}MB) "
      f"dx(1=ASD/2=TD)={np.bincount(y.astype(int))[1:3]}")
