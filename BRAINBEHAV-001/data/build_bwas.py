"""Build the packaged cc200 connectome + FIQ bundle for BRAINBEHAV-001 (route b: offline).

Subsets the shared ABIDE cc200 bundle to the subjects with a valid full-scale IQ (FIQ finite and
> 0 — ABIDE codes missing FIQ as -9999) AND a fully finite connectome (a handful of subjects have
dead ROIs -> NaN edges; those are dropped by standard QC). The shipped task then needs no network:
the agent reads subjects x edges (Fisher-z cc200 connectivity) + FIQ and runs the brain-wide
association directly. Only the phenotype this task needs (FIQ) is stored; X is float32.

Run from repo root:  python3 BRAINBEHAV-001/data/build_bwas.py
"""
import numpy as np

SRC = "_shared_bundles/cc200_full.npz"
DST = "BRAINBEHAV-001/data/cc200_bwas.npz"

d = np.load(SRC, allow_pickle=True)
X = d["X"].astype(np.float32)          # subjects x 19,900 Fisher-z cc200 edges (upper triangle of 200x200)
fiq = np.asarray(d["fiq"], float)      # full-scale IQ (missing coded -9999)

valid = np.isfinite(fiq) & (fiq > 0)   # drop NaN / -9999 missing FIQ
X, fiq = X[valid], fiq[valid]
clean = np.isfinite(X).all(1)          # drop subjects with dead-ROI NaN edges
X, fiq = X[clean], fiq[clean].astype(np.float32)

assert np.isfinite(X).all() and np.isfinite(fiq).all()
np.savez_compressed(DST, X=X, fiq=fiq, atlas="Craddock-200", edges_upper_triangle_of=200)
print(f"saved X={X.shape} ({X.nbytes/1e6:.1f}MB float32) fiq n={len(fiq)} "
      f"mean={fiq.mean():.1f} sd={fiq.std():.1f} [{fiq.min():.0f},{fiq.max():.0f}]")
