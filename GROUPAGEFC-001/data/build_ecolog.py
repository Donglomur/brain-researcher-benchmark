"""Build the packaged bundle for GROUPAGEFC-001 (route b: offline).

Subsets the shared ABIDE cc200 bundle to the subjects with a valid age and site, and keeps only
the columns this task needs: the subject x edge Fisher-z connectome (X) plus the two phenotypes the
connectivity-age analysis uses (AGE_AT_SCAN, SITE_ID). The shipped task therefore needs no network:
the agent forms each subject's mean connectivity from X and relates it to age at the site-mean
(ecological) and individual levels straight from this file.

Source: _shared_bundles/cc200_full.npz  (X: 1035 x 19,900 Fisher-z edges; phenotypes dx/sex/age/
fiq/site/subid). Only age + site are shipped (dx/sex/fiq/subid are not needed here)."""
import numpy as np

SRC = "_shared_bundles/cc200_full.npz"
DST = "GROUPAGEFC-001/data/cc200_ecolog.npz"

d = np.load(SRC, allow_pickle=True)
X = d["X"].astype(np.float32)               # subjects x 19,900 Fisher-z cc200 edges
age = d["age"].astype(np.float64)           # AGE_AT_SCAN
site = np.asarray(d["site"]).astype(str)    # SITE_ID

# keep subjects with a valid (finite) age and a real site label
keep = np.isfinite(age) & np.array([s not in ("", "nan", "None") for s in site])
X, age, site = X[keep], age[keep].astype(np.float32), site[keep]

np.savez_compressed(DST, X=X, age=age, site=site,
                    atlas="Craddock-200", edges_upper_triangle_of=200)

import os
mb = os.path.getsize(DST) / 1e6
print(f"saved {DST}: X={X.shape} age={age.shape} sites={len(np.unique(site))} "
      f"n_subjects={X.shape[0]}  size={mb:.2f} MB")
