"""Build the packaged connectome bundle for the top-differences task (route b: offline).
Precomputes subject x edge Fisher-z cc200 connectivity + DX labels from ABIDE, so the shipped
task needs no network. The agent still has the full subject x edge matrix + labels, so it can
split the sample and estimate held-out shrinkage (nothing needed for the robustness check removed)."""
import numpy as np
from nilearn import datasets
abide = datasets.fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                                 quality_checked=False, n_subjects=400)
dx = np.asarray(abide.phenotypic["DX_GROUP"], float)
sid = np.asarray(abide.phenotypic["SUB_ID"])
iu = np.triu_indices(200, 1)
X, y, ids = [], [], []
for i, arr in enumerate(abide.rois_cc200):
    a = np.asarray(arr, float)
    if a.ndim == 2 and a.shape[0] >= 60 and a.shape[1] >= 200:
        c = np.corrcoef(a[:, :200].T)
        X.append(np.arctanh(np.clip(c[iu], -0.999, 0.999)).astype(np.float32))
        y.append(int(dx[i])); ids.append(int(sid[i]))
X = np.array(X, np.float32); y = np.array(y, np.int8); ids = np.array(ids)
np.savez_compressed("TOPEDGES-001/data/cc200_connectomes.npz", X=X, y=y, subjects=ids,
                    atlas="Craddock-200", edges_upper_triangle_of=200)
print(f"saved X={X.shape} ({X.nbytes/1e6:.1f}MB) y(1=ASD/2=TD)={np.bincount(y)[1:3]}")
