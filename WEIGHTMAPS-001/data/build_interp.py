"""Build the packaged connectome bundle for WEIGHTMAPS-001 (route b: offline).

Precomputes the subject x edge Fisher-z cc200 connectivity matrix + diagnosis labels from the
shared ABIDE bundle, so the shipped task needs no network. The agent gets the full subject x edge
matrix + labels — enough to train a classifier, read out its weights (backward), transform them to
the Haufe forward/activation pattern A = Cov(X)*w, and compare against the univariate per-edge group
difference. Only the phenotype this task needs (diagnosis) is kept; X is float32."""
import numpy as np

d = np.load("_shared_bundles/cc200_full.npz", allow_pickle=True)
X, dx = d["X"], d["dx"]
keep = np.isin(dx, [1.0, 2.0]) & np.isfinite(dx)   # valid diagnosis (1=ASD, 2=TD); drop NaN
X = np.asarray(X[keep], np.float32)
y = np.asarray(dx[keep], np.int8)                   # 1 = ASD, 2 = TD
np.savez_compressed("WEIGHTMAPS-001/data/cc200_interp.npz", X=X, y=y,
                    atlas="Craddock-200", edges_upper_triangle_of=200)
print(f"saved X={X.shape} ({X.nbytes/1e6:.1f}MB float32) y(1=ASD/2=TD)={np.bincount(y)[1:3]}")
