"""Build the packaged sex-classification bundle for SEXCLASS-001 (route b: offline).

Subsets the shared cc200 connectome bundle to subjects with a valid SEX label and keeps only
what THIS task needs: the subject x edge connectome matrix (Fisher-z cc200), the SEX phenotype,
and subject IDs. No network is needed at task time — the agent trains the sex classifier from the
packaged .npz alone. (Build-time only; the shared bundle is git-ignored and not shipped.)"""
import numpy as np

SRC = "/Users/nicholas/Desktop/brain-researcher-benchmark/_shared_bundles/cc200_full.npz"
OUT = "/Users/nicholas/Desktop/brain-researcher-benchmark/SEXCLASS-001/data/cc200_baserate.npz"

d = np.load(SRC, allow_pickle=True)
sex = d["sex"].astype(float)
valid = np.isin(sex, [1.0, 2.0]) & np.isfinite(sex)   # keep only valid male(1)/female(2)
X = d["X"][valid].astype(np.float32)                  # subjects x 19,900 Fisher-z cc200 edges
sex = sex[valid].astype(np.int8)                      # SEX: 1 = male, 2 = female
subid = d["subid"][valid].astype(np.int64)            # subject IDs

np.savez_compressed(OUT, X=X, sex=sex, subid=subid,
                    atlas="Craddock-200", edges_upper_triangle_of=200)
import os
mb = os.path.getsize(OUT) / 1e6
print(f"saved X={X.shape} sex_counts(1=M,2=F)={np.bincount(sex)[1:3].tolist()} "
      f"n={len(sex)} -> {OUT} ({mb:.1f} MB)")
