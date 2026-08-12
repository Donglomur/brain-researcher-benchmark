"""Build the packaged connectome bundle for AUTISMDMN-001 (route b: offline).

Reads the shared build-only Dosenbach-160 timeseries bundle (`_shared_bundles/dos160_ts.npz`,
git-ignored, never shipped) and precomputes each subject's Fisher-z functional connectome
(upper triangle of the 160x160 Pearson matrix -> 12,720 edges), then packages the connectomes
plus ONLY the phenotypes this task uses: dx (1=ASD, 2=TD), site, age, sex, motion (func_mean_fd).

The shipped task reads ONLY `AUTISMDMN-001/data/dos160_autconn.npz` (no network, no nilearn). The
agent has the full subject x edge matrix + confounds, so it can run the edgewise ASD-vs-TD
comparison controlling site/age/sex/motion and correct for multiplicity over all 12,720 edges.

NaN edges from a degenerate (flat) ROI are kept as NaN (not fabricated to 0), so the analysis
can exclude them rather than invent a value.
"""
import os
import numpy as np
from nilearn import datasets

SRC = os.path.expanduser(
    os.environ.get("AUTCONN_SRC",
                   "/Users/nicholas/Desktop/brain-researcher-benchmark/_shared_bundles/dos160_ts.npz"))
OUT = "AUTISMDMN-001/data/dos160_autconn.npz"
NROI = 160

d = np.load(SRC, allow_pickle=True)
ts = d["ts"]
dx, age, sex, site, motion = d["dx"], d["age"], d["sex"], d["site"], d["motion"]

# Dosenbach-160 network labels (public atlas property, not subject data) — lets the task keep the
# within-DMN (Assaf 2010) context. Same ROI order as the rois_dosenbach160 timeseries.
networks = np.asarray(datasets.fetch_coords_dosenbach_2010().networks).astype("U24")
assert len(networks) == NROI, f"expected {NROI} network labels, got {len(networks)}"

iu = np.triu_indices(NROI, 1)          # 12,720 upper-triangle edges
X, keep = [], []
for i, arr in enumerate(ts):
    a = np.asarray(arr, float)
    if a.ndim != 2 or a.shape[0] < 76 or a.shape[1] < NROI:
        keep.append(False)
        continue
    c = np.corrcoef(a[:, :NROI].T)                       # 160x160 Pearson
    z = np.arctanh(np.clip(c[iu], -0.999, 0.999))        # Fisher-z, keep NaN (degenerate ROI) as NaN
    X.append(z.astype(np.float16))
    keep.append(True)

keep = np.array(keep, bool)
X = np.asarray(X, dtype=np.float16)                       # subjects x 12,720 edges
dx = dx[keep].astype(np.int8)                             # 1=ASD, 2=TD
site = site[keep].astype("U16")
age = age[keep].astype(np.float32)
sex = sex[keep].astype(np.int8)
motion = motion[keep].astype(np.float32)

np.savez_compressed(OUT, X=X, dx=dx, site=site, age=age, sex=sex, motion=motion,
                    networks=networks, atlas="Dosenbach-160", edges_upper_triangle_of=NROI)
sz = os.path.getsize(OUT) / 1e6
print(f"saved X={X.shape} ({X.nbytes/1e6:.1f}MB raw) -> {OUT} ({sz:.1f}MB on disk)")
print(f"asd/td={np.bincount(dx.astype(int))[1:3]} sites={len(set(site.tolist()))} "
      f"age[{age.min():.1f},{age.max():.1f}] motion[{motion.min():.3f},{motion.max():.3f}]")
