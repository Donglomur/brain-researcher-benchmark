"""Build the packaged fsLR-32k bundle for CORTMAPS-001 (route b: offline).

Precomputes the two cortical annotation maps (HCP S1200 cortical thickness; Margulies-2016
functional-connectivity gradient 2), the fsLR-32k spherical vertex coordinates, the hemisphere
ids, and the cortical (no-medial-wall) mask — everything needed to (a) correlate the two maps on
the cortex and (b) generate an Alexander-Bloch spin-test null offline — so the shipped task needs
no network. Source: the neuromaps data cache (~/neuromaps-data or $NEUROMAPS_DATA), fetched with
neuromaps.datasets.fetch_annotation / fetch_atlas.

The agent receives the FULL per-vertex maps + sphere geometry + cortical mask, so it can reproduce
the parametric correlation AND generate a spatial-autocorrelation-preserving spin null itself —
nothing needed for the hidden check is stripped.
"""
import os
from pathlib import Path

import numpy as np
import nibabel as nib

BASE = Path(os.environ.get("NEUROMAPS_DATA", str(Path.home() / "neuromaps-data")))
OUT = Path(__file__).resolve().parent / "mapcorr_fslr32k.npz"

ANN = BASE / "annotations"
ATL = BASE / "atlases" / "fsLR"
THICK = ANN / "hcps1200" / "thickness" / "fsLR"
GRAD = ANN / "margulies2016" / "fcgradient02" / "fsLR"


def _feat(p):
    return nib.load(str(p)).darrays[0].data.astype(np.float32)


def _coords(p):
    return np.asarray(nib.load(str(p)).agg_data()[0], dtype=np.float32)


def _label(p):
    return nib.load(str(p)).darrays[0].data.astype(np.int32)


# --- the two cortical maps (L then R), fsLR 32k ---
thickness = np.concatenate([
    _feat(THICK / "source-hcps1200_desc-thickness_space-fsLR_den-32k_hemi-L_feature.func.gii"),
    _feat(THICK / "source-hcps1200_desc-thickness_space-fsLR_den-32k_hemi-R_feature.func.gii"),
])
gradient2 = np.concatenate([
    _feat(GRAD / "source-margulies2016_desc-fcgradient02_space-fsLR_den-32k_hemi-L_feature.func.gii"),
    _feat(GRAD / "source-margulies2016_desc-fcgradient02_space-fsLR_den-32k_hemi-R_feature.func.gii"),
])

# --- spherical vertex coordinates (for the spin) + hemisphere ids ---
cL = _coords(ATL / "tpl-fsLR_den-32k_hemi-L_sphere.surf.gii")
cR = _coords(ATL / "tpl-fsLR_den-32k_hemi-R_sphere.surf.gii")
sphere_coords = np.vstack([cL, cR]).astype(np.float32)
hemi = np.concatenate([np.zeros(len(cL), np.int8), np.ones(len(cR), np.int8)])

# --- cortical mask (fsLR no-medial-wall label; 1 = cortex) ---
mwL = _label(ATL / "tpl-fsLR_den-32k_hemi-L_desc-nomedialwall_dparc.label.gii")
mwR = _label(ATL / "tpl-fsLR_den-32k_hemi-R_desc-nomedialwall_dparc.label.gii")
cortex_mask = (np.concatenate([mwL, mwR]) == 1)

assert thickness.shape == gradient2.shape == hemi.shape == cortex_mask.shape
assert sphere_coords.shape == (thickness.shape[0], 3)

np.savez_compressed(
    OUT,
    thickness=thickness,
    gradient2=gradient2,
    sphere_coords=sphere_coords,
    hemi=hemi,
    cortex_mask=cortex_mask,
    map_a="cortical thickness (HCP S1200), fsLR den-32k",
    map_b="2nd functional-connectivity gradient (Margulies 2016), fsLR den-32k",
    space="fsLR",
    density="32k",
    mask="fsLR no-medial-wall label (desc-nomedialwall)",
    vertex_order="left hemisphere then right hemisphere",
)
print(f"saved {OUT.name}: n_grid={thickness.shape[0]} n_cortex={int(cortex_mask.sum())} "
      f"({OUT.stat().st_size/1e6:.2f}MB)")
