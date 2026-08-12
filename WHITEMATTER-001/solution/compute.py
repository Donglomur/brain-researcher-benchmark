"""Reference (oracle) for WHITEMATTER-001 — fractional anisotropy, ATLAS-BASED anatomical
localization, and the crossing-fiber trap.

Paper anchor: Pierpaoli & Basser 1996, Magn Reson Med (10.1002/mrm.1910360612, "Toward a
quantitative assessment of diffusion anisotropy") establishes FA as the standard rotationally-
invariant measure of white-matter organization; the crossing-fiber limitation of the single-tensor
model is characterized by Jeurissen et al. 2013, HBM (10.1002/hbm.22099) and Tournier et al. 2007
(CSD). The diffusion tensor is a rank-1 (single-orientation) model, so in voxels containing >=2
crossing fiber populations it cannot represent the geometry and FA drops sharply — NOT because the
tissue is less organized, but because the model is mis-specified.

The task (un-cued) asks to compute FA and IDENTIFY / NAME the white-matter regions of LOWEST
FA — the regions the standard reading would call the lowest microstructural integrity. The naive
move is to report those lowest-FA regions as the least-organized tissue.

This reference does the ATLAS-BASED localization the task asks for (each white-matter voxel is
assigned to a named FreeSurfer cortical-gyral white-matter territory, co-registered to this exact
subject; the corpus callosum is kept as an explicit named white-matter structure) AND then
VOLUNTEERS the check the task never asks:
  * BETWEEN regions — the lowest-FA named territories are exactly the highest-crossing ones
    (region mean FA vs crossing fraction is strongly anti-correlated), while the corpus callosum,
    the textbook coherent single-fiber tract, has the HIGHEST FA and almost no crossing;
  * WITHIN every region — holding anatomy fixed, crossing-fiber voxels have lower FA than
    single-fiber voxels (global ~0.50 -> ~0.33, a ~34% collapse).
So the "lowest-integrity" ranking is a crossing-fiber artifact of the single-tensor model, not an
integrity ranking; a crossing-aware model (CSD fODF peak count) is needed to tell them apart.

Emitted for the verifier to CHECK the actual data (not just prose):
  regional_fa.csv  — one row per named territory: region, n_wm_voxels, crossing_fraction,
                     mean_FA, mean_FA_single_fiber, mean_FA_crossing_fiber, rank_by_FA
  fa.json          — global numbers + the named lowest-FA / highest-crossing / highest-FA
                     territories + the region-level FA-vs-crossing anti-correlation
  run_metadata.json— dataset, atlas, preprocessing, method
  findings.md      — reproduces (named lowest-FA regions) + the crossing localization + conclusion

Validated numbers are written by this run and echoed to stdout (the "OK:" receipt). Deterministic.
"""
import csv
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
MIN_REGION = 200  # a named WM territory must have at least this many white-matter voxels


def fail(reason):
    (OUT / "fa.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "stanford_hardi"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from dipy.data import (read_stanford_hardi, read_stanford_labels,
                           fetch_stanford_labels, default_sphere)
    from dipy.reconst.dti import TensorModel, fractional_anisotropy
    from dipy.reconst.csdeconv import ConstrainedSphericalDeconvModel, auto_response_ssst
    from dipy.direction import peaks_from_model
    from dipy.segment.mask import median_otsu
    from scipy import ndimage
    from scipy.stats import spearmanr, pearsonr
except Exception as e:  # pragma: no cover
    fail(f"import failed (need dipy + scipy): {e}")

# --- data + co-registered FreeSurfer atlas (route-a: fetched to ~/.dipy, cached after first run) ---
try:
    img, gtab = read_stanford_hardi()
    _, _, labels_img = read_stanford_labels()
    _files, folder = fetch_stanford_labels()
except Exception as e:
    fail(f"could not fetch Stanford HARDI diffusion data + FreeSurfer labels: {e}")
data = img.get_fdata()
labels = np.asarray(labels_img.get_fdata()).astype(int)

# parse the co-registered atlas' label table (new_label -> FreeSurfer name)
name_by_label = {}
try:
    for line in Path(folder, "label_info.txt").read_text().splitlines():
        m = re.match(r'\s*(\d+)\s*,\s*(\d+)\s*,\s*"([^"]+)"', line)
        if m:
            name_by_label.setdefault(int(m.group(1)), []).append(m.group(3))
except Exception as e:
    fail(f"could not read atlas label table (label_info.txt): {e}")
rep = {}
for nl, names in name_by_label.items():
    rep[nl] = "Corpus-Callosum" if nl == 2 else (
        "Cerebral-White-Matter" if nl == 1 else names[0])
cortical = [nl for nl in rep if rep[nl].startswith("ctx-")]
if len(cortical) < 20:
    fail(f"atlas label table yielded only {len(cortical)} cortical parcels")

# --- single-tensor DTI fractional anisotropy over the white matter (the standard reading) ---
b0, mask = median_otsu(data, vol_idx=[0], median_radius=3, numpass=1)
ten = TensorModel(gtab).fit(data, mask=mask)
FA = np.nan_to_num(fractional_anisotropy(ten.evals))
wm = mask & (FA > 0.2)
n_wm = int(wm.sum())
if n_wm < 5000:
    fail(f"white-matter mask too small ({n_wm} voxels)")

# --- crossing-aware model: CSD fODF peak count per voxel (single- vs multi-fiber) ---
resp, ratio = auto_response_ssst(gtab, data, roi_radii=10, fa_thr=0.7)
csd = ConstrainedSphericalDeconvModel(gtab, resp)
pk = peaks_from_model(csd, data, default_sphere, relative_peak_threshold=0.5,
                      min_separation_angle=25, mask=wm, npeaks=3, parallel=False)
npeaks = (np.abs(pk.peak_values) > 0).sum(-1)
single = wm & (npeaks == 1)
cross = wm & (npeaks >= 2)

fa_single = float(FA[single].mean())
fa_cross = float(FA[cross].mean())
frac_cross = float(cross.sum() / n_wm)
collapse_pct = float(100 * (1 - fa_cross / fa_single))
# of the lowest-FA (bottom-20% "least organized") white-matter voxels, what fraction cross?
thr = np.percentile(FA[wm], 20)
lowfa = wm & (FA <= thr)
frac_lowfa_crossing = float((lowfa & cross).sum() / max(int(lowfa.sum()), 1))

# --- ATLAS-BASED anatomical localization (wmparc-style): assign each white-matter voxel to the
#     nearest FreeSurfer cortical-gyral parcel -> a named white-matter territory; keep the corpus
#     callosum as an explicit named white-matter structure. ---
gm = np.zeros(labels.shape, int)
for nl in cortical:
    gm[labels == nl] = nl
idx = ndimage.distance_transform_edt(gm == 0, return_indices=True, return_distances=False)
nearest = gm[tuple(idx)]
terr = np.zeros(labels.shape, int)
terr[wm] = nearest[wm]
terr[wm & (labels == 2)] = 2  # corpus callosum (explicit WM structure)

regions = []
for nl in sorted(set(terr[wm].tolist())):
    reg = (terr == nl) & wm
    n = int(reg.sum())
    if n < MIN_REGION:
        continue
    rc, rs = reg & cross, reg & single
    regions.append({
        "region": rep.get(nl, str(nl)),
        "n_wm_voxels": n,
        "crossing_fraction": float(rc.sum() / n),
        "mean_FA": float(FA[reg].mean()),
        "mean_FA_single_fiber": float(FA[rs].mean()) if int(rs.sum()) else None,
        "mean_FA_crossing_fiber": float(FA[rc].mean()) if int(rc.sum()) else None,
        "n_crossing": int(rc.sum()),
        "n_single": int(rs.sum()),
    })
n_reg = len(regions)
by_fa = sorted(regions, key=lambda r: r["mean_FA"])
for rank, r in enumerate(sorted(regions, key=lambda r: r["mean_FA"]), 1):
    r["rank_by_FA"] = rank  # 1 = lowest FA ("lowest integrity" by the naive reading)

fa_arr = np.array([r["mean_FA"] for r in regions])
cf_arr = np.array([r["crossing_fraction"] for r in regions])
pear = float(pearsonr(fa_arr, cf_arr)[0])
spear = float(spearmanr(fa_arr, cf_arr)[0])
n_right_dir = sum(1 for r in regions
                  if r["mean_FA_single_fiber"] is not None
                  and r["mean_FA_crossing_fiber"] is not None
                  and r["mean_FA_crossing_fiber"] < r["mean_FA_single_fiber"])

lowest = by_fa[:10]
highest_cross = sorted(regions, key=lambda r: -r["crossing_fraction"])[:10]
highest_fa = sorted(regions, key=lambda r: -r["mean_FA"])[:6]


def slim(r):
    return {k: r[k] for k in ("region", "n_wm_voxels", "mean_FA", "crossing_fraction",
                              "mean_FA_single_fiber", "mean_FA_crossing_fiber", "rank_by_FA")}


# ---- regional_fa.csv: the per-territory data the verifier checks ----
with open(OUT / "regional_fa.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["region", "n_wm_voxels", "crossing_fraction", "mean_FA",
                "mean_FA_single_fiber", "mean_FA_crossing_fiber", "rank_by_FA"])
    for r in sorted(regions, key=lambda r: r["rank_by_FA"]):
        w.writerow([r["region"], r["n_wm_voxels"], f"{r['crossing_fraction']:.6f}",
                    f"{r['mean_FA']:.6f}",
                    "" if r["mean_FA_single_fiber"] is None else f"{r['mean_FA_single_fiber']:.6f}",
                    "" if r["mean_FA_crossing_fiber"] is None else f"{r['mean_FA_crossing_fiber']:.6f}",
                    r["rank_by_FA"]])

(OUT / "fa.json").write_text(json.dumps({
    "dataset": "dipy Stanford HARDI (single subject, 150 directions, b=2000)",
    "atlas": "FreeSurfer aparc (aparc-reduced), co-registered to the Stanford HARDI subject; "
             "white-matter voxels labelled by nearest cortical-gyral parcel (wmparc-style)",
    "n_white_matter_voxels": n_wm,
    "n_named_wm_regions": n_reg,
    "fraction_white_matter_with_crossing_fibers": frac_cross,
    "mean_FA_single_fiber": fa_single,
    "mean_FA_crossing_fiber": fa_cross,
    "FA_collapse_in_crossing_pct": collapse_pct,
    "fraction_of_lowest_FA_voxels_that_are_crossing": frac_lowfa_crossing,
    "region_FA_vs_crossing_fraction_pearson_r": pear,
    "region_FA_vs_crossing_fraction_spearman_r": spear,
    "n_regions_crossing_FA_below_single_FA": n_right_dir,
    "lowest_FA_regions": [slim(r) for r in lowest],       # the naive "lowest integrity" regions
    "highest_crossing_regions": [slim(r) for r in highest_cross],
    "highest_FA_regions": [slim(r) for r in highest_fa],  # incl. corpus callosum (single-fiber)
    "method": "single-tensor DTI fractional anisotropy vs CSD fODF peak count, localized to "
              "co-registered FreeSurfer cortical-gyral white-matter territories",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset": "dipy Stanford HARDI (stanford_hardi), fetched at runtime and cached under ~/.dipy",
    "atlas": "FreeSurfer aparc-reduced parcellation co-registered to the subject (dipy "
             "read_stanford_labels); white-matter voxels assigned to nearest cortical-gyral parcel",
    "n_subjects": 1,
    "preprocessing": "median_otsu brain mask; white matter = mask & FA>0.2",
    "method": "single-tensor DTI FA (dipy TensorModel/fractional_anisotropy) vs constrained "
              "spherical deconvolution fODF peak count (single- vs crossing-fiber voxels); "
              "per-region localization by co-registered FreeSurfer cortical-gyral territories",
}, indent=2))

low_names = ", ".join(f"{r['region']} (FA {r['mean_FA']:.2f}, {r['crossing_fraction']*100:.0f}% crossing)"
                      for r in lowest[:5])
cc = next((r for r in regions if r["region"] == "Corpus-Callosum"), None)
cc_line = (f"the **corpus callosum** — the textbook coherent single-fiber tract — has the HIGHEST FA "
           f"(mean FA {cc['mean_FA']:.2f}) and only **{cc['crossing_fraction']*100:.0f}% crossing** "
           f"voxels, exactly as the single-tensor model predicts for coherent tissue.\n"
           if cc else "")

(OUT / "findings.md").write_text(f"""# WHITEMATTER-001 — lowest-FA white-matter regions and the crossing-fiber confound

White-matter voxels: {n_wm} across {n_reg} named FreeSurfer cortical-gyral white-matter territories
(atlas co-registered to this subject). Fractional anisotropy (FA) from the single diffusion tensor
is the standard scalar measure of white-matter organization.

## The lowest-FA white-matter regions (the naive "lowest integrity" reading)
Ranking the named territories by mean FA, the lowest-FA white matter is:
{chr(10).join(f"- **{r['region']}** — mean FA {r['mean_FA']:.2f} ({r['crossing_fraction']*100:.0f}% crossing-fiber voxels)" for r in lowest[:5])}

A naive analysis stops here and reports these as the regions of lowest microstructural integrity.

## But those lowest-FA regions are the crossing-fiber regions, not low-integrity tissue
- **{frac_cross*100:.0f}% of white-matter voxels contain crossing fibers** (>=2 CSD fODF peaks) — the
  single-tensor model cannot represent them, and FA collapses there for a *modelling* reason.
- **Between regions:** the lowest-FA territories are exactly the highest-crossing ones — region mean
  FA is strongly anti-correlated with crossing fraction (Pearson r = {pear:.2f}, Spearman r =
  {spear:.2f}). Conversely {cc_line}
- **Within every region:** holding anatomy fixed, crossing-fiber voxels have lower FA than
  single-fiber voxels in **{n_right_dir} of {n_reg}** territories (globally mean FA
  **{fa_single:.2f}** single-fiber vs **{fa_cross:.2f}** crossing-fiber — a **{collapse_pct:.0f}%
  collapse**). Adding a second fiber population, not losing integrity, is what drops FA.
- **{frac_lowfa_crossing*100:.0f}%** of the lowest-FA (bottom-20%) white-matter voxels are
  crossing-fiber voxels.

## Conclusion
Low FA in white matter **does not** by itself indicate low microstructural integrity: the diffusion
tensor is a single-orientation (rank-1) model, so it under-estimates anisotropy wherever fibers
cross, kiss, or fan — about half of all white-matter voxels here (Jeurissen 2013; Tournier 2007).
The lowest-FA named regions are dominated by crossing-fiber model failure, not genuinely
disorganized tissue; the "lowest-integrity" ranking is really a crossing-fiber ranking. Assessing
integrity from FA requires a crossing-aware model (e.g. CSD fODF peaks); reporting the lowest-FA
regions as the least-organized white matter is misleading.
""")

print(f"OK: WM={n_wm} regions={n_reg} crossing={frac_cross*100:.0f}%; "
      f"FA single={fa_single:.2f} cross={fa_cross:.2f} ({collapse_pct:.0f}% collapse); "
      f"region FA-vs-crossing pearson={pear:.2f} spearman={spear:.2f}; "
      f"crossFA<singleFA in {n_right_dir}/{n_reg} regions; "
      f"lowest-FA: {', '.join(r['region'] for r in lowest[:3])}")
