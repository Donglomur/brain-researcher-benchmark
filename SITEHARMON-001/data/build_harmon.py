"""Build the packaged phenotype+connectome bundle for SITEHARMON-001 (route b: offline).

Subsets the shared ABIDE cc200 bundle to the columns THIS task needs — the subject x edge
Fisher-z connectivity `X` plus the two phenotypes the harmonization/age analysis uses (`age` =
AGE_AT_SCAN, `site` = SITE_ID) and a subject id for per-row identity — so the shipped task needs
no network. Subjects are kept where age and site are both valid (drop NaN). The agent still has the
full subject x edge matrix + site labels + ages, so it can fit the harmonization WITHIN training
folds and protect (or not protect) the covariate.

Run from the repo root:  python3 SITEHARMON-001/data/build_harmon.py
"""
import numpy as np

SRC = "_shared_bundles/cc200_full.npz"
OUT = "SITEHARMON-001/data/cc200_harmon.npz"

d = np.load(SRC, allow_pickle=True)
X = d["X"].astype(np.float32)          # subjects x 19,900 Fisher-z cc200 edges
age = d["age"].astype(float)           # AGE_AT_SCAN (years)
site = np.asarray(d["site"]).astype(str)   # SITE_ID
subid = d["subid"].astype(float)

# keep subjects with valid age AND valid site (drop NaN / missing)
valid = np.isfinite(age) & np.array([s not in ("", "nan", "NaN", "None") for s in site])
X, age, site, subid = X[valid], age[valid], site[valid], subid[valid]

np.savez_compressed(
    OUT,
    X=X.astype(np.float32),
    age=age.astype(np.float32),
    site=site.astype(object),
    subid=subid.astype(np.int64),
    atlas="Craddock-200 (cc200)",
    edges_upper_triangle_of=200,
)
import os
mb = os.path.getsize(OUT) / 1e6
print(f"saved {OUT}: X={X.shape} n={X.shape[0]} sites={len(np.unique(site))} "
      f"age[{age.min():.1f},{age.max():.1f}] size={mb:.1f}MB")
