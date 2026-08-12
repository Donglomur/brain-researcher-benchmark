"""Build the packaged connectome bundle for DEEPCLASS-001 (route b: offline).

Subsets the shared ABIDE cc200 bundle to the columns THIS task needs — the subject x edge
Fisher-z connectome (X), the diagnosis label (dx: 1=ASD, 2=TD) and the acquisition site
(SITE_ID) — dropping subjects without a valid dx or site. No phenotype the classifier does not
use (sex/age/fiq/subid) is shipped. The shipped task therefore needs NO network: the agent has
the full subject x edge matrix + labels + site, enough to run a seeded, nested, leave-one-site-
out comparison of a deep/nonlinear model against a linear baseline.

Run from the repo root:  python3 DEEPCLASS-001/data/build_data.py
"""
import numpy as np

SRC = "_shared_bundles/cc200_full.npz"
DST = "DEEPCLASS-001/data/cc200_deeplin.npz"

d = np.load(SRC, allow_pickle=True)
X = d["X"].astype(np.float32)                 # subjects x 19,900 Fisher-z cc200 edges
dx = np.asarray(d["dx"], float)               # 1=ASD, 2=TD
site = np.asarray(d["site"], dtype=object)    # SITE_ID string


def _bad_site(s):
    return s is None or (isinstance(s, float) and np.isnan(s)) or str(s).strip() in ("", "nan", "NaN")


keep = np.array([(dv in (1.0, 2.0)) and (not _bad_site(sv)) for dv, sv in zip(dx, site)])
X, dx, site = X[keep], dx[keep].astype(np.int8), np.array([str(s) for s in site])[keep]

np.savez_compressed(
    DST, X=X, dx=dx, site=site,
    atlas="Craddock-200 (cc200)", edges="upper triangle of 200x200, Pearson r, Fisher-z",
    dx_coding="1=ASD, 2=TD (control)",
)
print(f"saved {DST}: X={X.shape} ({X.nbytes/1e6:.1f}MB raw float32) "
      f"dx counts (1=ASD,2=TD)={np.bincount(dx)[1:3].tolist()} sites={len(np.unique(site))}")
