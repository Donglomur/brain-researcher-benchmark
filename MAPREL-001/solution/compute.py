#!/usr/bin/env python3
"""Reference solution for MAPREL-001.

Question: are the second macroscale functional-connectivity gradient (Margulies
et al. 2016) and the group-average cortical-thickness map (HCP S1200) spatially
correlated across the cortex?

The reference does the honest thing an experienced analyst does when correlating
two smooth cortical maps: it does not stop at the parcel-wise Pearson r and its
parametric p-value (which treats the ~400 parcels as independent observations —
they are not, both maps are strongly spatially autocorrelated). It compares the
observed r against a spatial null that preserves each map's spatial
autocorrelation (a spin / rotation-based permutation of the parcels on the
spherical surface). Under that null the correlation is well within chance, so the
maps are NOT significantly spatially correlated once autocorrelation is accounted
for — the tiny parametric p is anti-conservative.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

import numpy as np
import nibabel as nib
from scipy import stats

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

N_PARCELS = 400
N_PERM = 1000
SEED = 0

SCHAEFER_URL = (
    "https://raw.githubusercontent.com/ThomasYeoLab/CBIG/master/stable_projects/"
    "brain_parcellation/Schaefer2018_LocalGlobal/Parcellations/HCP/fslr32k/cifti/"
    "Schaefer2018_400Parcels_7Networks_order.dlabel.nii"
)


def fail(reason):
    meta = {"status": "failed_precondition", "reason": reason}
    (OUT / "run_metadata.json").write_text(json.dumps(meta, indent=2))
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition",
                                                  "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# MAPREL-001 — failed precondition\n\n{reason}\n")
    print("FAILED_PRECONDITION:", reason, file=sys.stderr)
    sys.exit(1)


def main():
    try:
        from neuromaps import datasets, images
        from neuromaps.nulls.spins import gen_spinsamples
    except Exception as e:  # pragma: no cover
        fail(f"neuromaps import failed: {e!r}")

    # --- fetch the two cortical maps (fsLR 32k, native space, no resampling) ---
    try:
        map_a = datasets.fetch_annotation(source="margulies2016", desc="fcgradient02",
                                          space="fsLR", den="32k")
        map_b = datasets.fetch_annotation(source="hcps1200", desc="thickness",
                                          space="fsLR", den="32k")
        va = np.asarray(images.load_data(map_a), dtype=float)
        vb = np.asarray(images.load_data(map_b), dtype=float)
    except Exception as e:
        fail(f"could not fetch neuromaps annotations: {e!r}")

    # --- Schaefer-400 (7-network) parcellation, dense fsLR 32k (label 0 = medial wall) ---
    dlabel = OUT / "Schaefer2018_400Parcels_7Networks_fsLR32k.dlabel.nii"
    if not dlabel.exists():
        try:
            urllib.request.urlretrieve(SCHAEFER_URL, dlabel)
        except Exception as e:
            fail(f"could not download Schaefer parcellation: {e!r}")
    try:
        limg = nib.load(str(dlabel))
        lab = limg.get_fdata().ravel().astype(int)
        label_axis = limg.header.get_axis(0)
        names = label_axis.label[0]  # {int_key: (name, (r,g,b,a))}
    except Exception as e:
        fail(f"could not read Schaefer parcellation: {e!r}")

    if lab.shape[0] != va.shape[0]:
        fail(f"parcellation ({lab.shape[0]}) and maps ({va.shape[0]}) are not aligned")

    parcels = np.arange(1, N_PARCELS + 1)

    def network_of(key):
        nm = names.get(int(key), (str(key),))[0]
        for net in ("Vis", "SomMot", "DorsAttn", "SalVentAttn", "Limbic", "Cont", "Default"):
            if net.lower() in str(nm).lower():
                return net
        return "NA"

    # --- parcellate (parcel means, medial wall excluded) ---
    pa = np.array([va[lab == p].mean() for p in parcels])
    pb = np.array([vb[lab == p].mean() for p in parcels])

    # --- parcel centroids on the fsLR spherical surface (for the spatial null) ---
    atlas = datasets.fetch_atlas("fsLR", "32k")
    sph = np.vstack([nib.load(str(atlas["sphere"].L)).darrays[0].data,
                     nib.load(str(atlas["sphere"].R)).darrays[0].data])
    cent = np.zeros((N_PARCELS, 3))
    hemiid = np.zeros(N_PARCELS, dtype=int)
    nverts_per_hemi = va.shape[0] // 2
    for i, p in enumerate(parcels):
        idx = np.where(lab == p)[0]
        c = sph[idx].mean(0)
        cent[i] = c / np.linalg.norm(c) * 100.0
        hemiid[i] = 0 if idx.mean() < nverts_per_hemi else 1

    # --- observed correlation + the naive p-values (parametric & label-shuffle) ---
    r_obs, p_param = stats.pearsonr(pa, pb)
    rng = np.random.default_rng(SEED)
    shuf = np.array([stats.pearsonr(rng.permutation(pa), pb)[0] for _ in range(N_PERM)])
    p_shuffle = (np.sum(np.abs(shuf) >= abs(r_obs)) + 1) / (N_PERM + 1)

    # --- the honest test: spatial-autocorrelation-preserving spin null ---
    spins = gen_spinsamples(cent, hemiid, n_rotate=N_PERM, seed=SEED, method="original")
    spin_null = np.array([stats.pearsonr(pa[spins[:, i]], pb)[0]
                          for i in range(spins.shape[1])])
    p_spin = (np.sum(np.abs(spin_null) >= abs(r_obs)) + 1) / (spins.shape[1] + 1)
    np.savez_compressed(OUT / "spin_evidence.npz", centroids=cent, hemisphere=hemiid,
                        spin_indices=spins, schema_version="spatial-geometry-v2")

    # --- write the natural deliverables ---
    with open(OUT / "parcels.csv", "w") as f:
        f.write("parcel_id,network,gradient2,thickness\n")
        for i, p in enumerate(parcels):
            f.write(f"{p},{network_of(p)},{pa[i]:.6f},{pb[i]:.6f}\n")

    results = {
        "null_family": "centroid_spin", "spin_method": "original", "seed": SEED,
        "n_parcels": int(N_PARCELS),
        "pearson_r": float(r_obs),
        "p_parametric": float(p_param),
        "p_label_shuffle": float(p_shuffle),
        "p_spin": float(p_spin),
        "spin_null_mean": float(spin_null.mean()),
        "spin_null_sd": float(spin_null.std()),
        "n_permutations": int(N_PERM),
        "significant_after_spatial_null": bool(p_spin < 0.05),
        # the full sampling distribution of the correlation under the spatial null: the array the
        # p-value is derived from (the grader recomputes the p-value from this and validates its
        # spread, so the significance judgement cannot be a guessed scalar).
        "null_distribution": [float(x) for x in spin_null],
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=2))

    (OUT / "run_metadata.json").write_text(json.dumps({
        "status": "ok",
        "map_a": "margulies2016 fcgradient02 (2nd functional connectivity gradient)",
        "map_b": "hcps1200 thickness (group-average cortical thickness)",
        "space": "fsLR 32k",
        "parcellation": "Schaefer2018 400Parcels 7Networks (fsLR 32k)",
        "n_parcels": int(N_PARCELS),
        "correlation": "Pearson across parcels",
        "spatial_null": "spin permutation (Alexander-Bloch/Vazquez-Rodriguez centroid variant)",
        "n_permutations": int(N_PERM),
    }, indent=2))

    verdict_sig = "a significant" if p_spin < 0.05 else "no significant"
    (OUT / "findings.md").write_text(
        f"# Published-map spatial-null application\n\n"
        f"Across-parcel Pearson r={r_obs:+.4f}; independent-parcel p={p_param:.5g}; "
        f"declared centroid-spin p={p_spin:.5g}. Significant under this null: {p_spin<.05}. "
        "This inference is conditional on map/geometry preprocessing and the selected spatial "
        "null, which approximately preserves spherical spatial structure; it does not prove "
        "absence of a relationship or that every parametric association is spurious.\n")
    print(f"r={r_obs:+.3f} p_param={p_param:.2e} p_shuffle={p_shuffle:.4f} p_spin={p_spin:.3f}")


if __name__ == "__main__":
    main()
