"""Build the packaged connectome bundle for CORTHUBS-001 (route b: offline).

Precomputes each subject's Fisher-z ROI×ROI connectome (upper triangle, 12,720 edges over the
Dosenbach-160 parcellation) from the shared ABIDE timeseries bundle, plus the DX label and the
Dosenbach-160 network/label/coord atlas metadata, so the shipped task needs no network.

The agent gets the FULL per-subject upper-triangle connectome, so it can (a) choose its own
centrality measure (weighted node strength or a thresholded binary degree) consistently, and
(b) compute per-individual hub maps and compare them against the group map (the individual-level
reliability check). Only the DX phenotype is kept (this task uses no other phenotype)."""
import os

import numpy as np
from nilearn import datasets

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.join(HERE, "..", "..", "_shared_bundles", "dos160_ts.npz")
OUT = os.path.join(HERE, "dos160_hubmap.npz")
NROI = 160
iu = np.triu_indices(NROI, 1)

# --- Dosenbach-160 atlas: network + anatomical label + MNI coord per ROI ----------
dos = datasets.fetch_coords_dosenbach_2010()
networks = np.asarray(dos.networks).astype("U24")     # e.g. default, sensorimotor
labels = np.asarray(dos.labels).astype("U40")         # anatomical name
coords = dos.rois[["x", "y", "z"]].to_numpy().astype(np.float32)

# --- per-subject Fisher-z connectome (upper triangle) -----------------------------
d = np.load(BUNDLE, allow_pickle=True)
ts_all, dx = d["ts"], d["dx"].astype(np.int8)
X, dead = [], 0
for a in ts_all:
    a = np.asarray(a, float)[:, :NROI]
    c = np.corrcoef(a.T)
    if not np.all(np.isfinite(c)):
        dead += 1
    c = np.nan_to_num(c, nan=0.0)                      # dead/constant ROI -> no connectivity
    X.append(np.arctanh(np.clip(c[iu], -0.999, 0.999)).astype(np.float16))
X = np.array(X, np.float16)                            # subjects x 12,720 edges

np.savez_compressed(
    OUT, X=X, dx=dx,
    networks=networks, labels=labels, coords=coords,
    atlas="Dosenbach-160", edges_upper_triangle_of=NROI)

sz = os.path.getsize(OUT) / 1e6
print(f"saved X={X.shape} float16 connectomes; dx bincount(1=ASD,2=TD)={np.bincount(dx.astype(int))[1:3]}; "
      f"subjects with a dead ROI={dead}; atlas={NROI} ROIs")
print(f"file: {OUT}  ({sz:.1f} MB)")
