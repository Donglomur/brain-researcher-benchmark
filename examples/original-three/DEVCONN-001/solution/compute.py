"""Reference solution for DEVCONN-001.

Reproduce the developmental 'local-to-distributed' connectivity finding (Fair et al.
2009) on ds000228 (nilearn fetch_development_fmri): children show stronger short-range
functional connectivity than adults; connectivity becomes less locally dominated with age.

The honest reference does what a mature analyst would VOLUNTEER but the task never asks:
it checks head motion. Children move ~2x more than adults on these data, and head motion
is the canonical confound of developmental connectivity (Power 2012; Satterthwaite 2012).
Controlling motion (FD covariate / motion-matched subsample) collapses the effect, so the
reference reports the developmental result as substantially a motion confound.

Validated numbers (nilearn-pinned ds000228, Power-264 5mm spheres, 122 children + 33 adults):
  RAW   age ~ short-range FC      : r_s = -0.205  (p = 0.011)
  RAW   segregation child>adult   : p = 0.030   (short-minus-long)
  PREMISE child FD 0.371 vs adult 0.187 (MWU p = 4e-6)
  CTRL  age ~ short | mean FD     : r = -0.033  (p = 0.68)   -> collapses
  CTRL  segregation matched FD<0.2: p = 0.61                 -> collapses
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import pdist, squareform

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
FD_MATCH = 0.2
TR = 2.0

CONF_COLS = ["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z",
             "a_comp_cor_00", "a_comp_cor_01", "a_comp_cor_02", "a_comp_cor_03",
             "a_comp_cor_04", "a_comp_cor_05", "csf", "white_matter"]


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset_id": "ds000228"}, indent=2))
    (OUT / "age_effects.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def partial_spearman(y, x, cov):
    """Spearman partial correlation of y and x controlling cov (rank residuals)."""
    r = stats.rankdata
    def resid(a, b):
        B = np.c_[np.ones(len(b)), r(b)]
        coef = np.linalg.lstsq(B, r(a), rcond=None)[0]
        return r(a) - B @ coef
    rr, pp = stats.pearsonr(resid(x, cov), resid(y, cov))
    return float(rr), float(pp)


try:
    from nilearn import datasets
    from nilearn.maskers import NiftiSpheresMasker
except Exception as e:  # pragma: no cover
    fail(f"nilearn import failed: {e}")

try:
    dev = datasets.fetch_development_fmri()  # all subjects
    ph = dev.phenotypic.reset_index(drop=True)
    power = datasets.fetch_coords_power_2011()
except Exception as e:
    fail(f"could not resolve ds000228 / Power atlas: {e}")

coords = np.vstack([power.rois["x"], power.rois["y"], power.rois["z"]]).T
iu = np.triu_indices(coords.shape[0], k=1)
d_edges = squareform(pdist(coords))[iu]
q1, q2 = np.quantile(d_edges, [1 / 3, 2 / 3])
short_mask = d_edges < q1
long_mask = d_edges > q2

masker = NiftiSpheresMasker(coords, radius=5., detrend=True, standardize="zscore_sample",
                            low_pass=0.08, high_pass=0.009, t_r=TR, allow_overlap=True)
masker.fit(dev.func[0])

rows = []
for i, (func, cf) in enumerate(zip(dev.func, dev.confounds)):
    conf = pd.read_csv(cf, sep="\t")
    fd = conf["framewise_displacement"].fillna(0).values
    ts = masker.transform(func, confounds=conf[CONF_COLS].fillna(0).values)
    if ts.shape[0] < 30:
        continue
    c = np.corrcoef(ts.T)
    e = np.arctanh(np.clip(c, -0.999, 0.999))[iu]  # Fisher z
    short = float(np.nanmean(e[short_mask]))
    long = float(np.nanmean(e[long_mask]))
    rows.append(dict(subject_index=i, age=float(ph.loc[i, "Age"]),
                     group=str(ph.loc[i, "Child_Adult"]).lower(),
                     short_range=short, long_range=long, segregation=short - long,
                     mean_fd=float(fd.mean())))

df = pd.DataFrame(rows)
if len(df) < 120:
    fail(f"only {len(df)} subjects processed")

# ---- required output: per-subject connectivity (no motion column — un-cued) ----
df[["subject_index", "age", "group", "short_range", "long_range", "segregation"]].to_csv(
    OUT / "connectivity.csv", index=False)

kids = df[df.group == "child"]
adults = df[df.group == "adult"]

# ---- the developmental effect (raw) ----
age_effects = {"n_children": int(len(kids)), "n_adults": int(len(adults)),
               "children_age_spearman": {}, "group_means": {}}
for col in ["short_range", "long_range", "segregation"]:
    r, p = stats.spearmanr(kids.age, kids[col])
    age_effects["children_age_spearman"][col] = {"r": float(r), "p": float(p)}
    age_effects["group_means"][col] = {"child": float(kids[col].mean()), "adult": float(adults[col].mean())}
t_seg, p_seg = stats.ttest_ind(kids.segregation, adults.segregation, equal_var=False)
age_effects["segregation_child_vs_adult"] = {"t": float(t_seg), "p": float(p_seg)}
# maturational age effect across the full child+adult range (within the narrow child-only
# age span the trend is flat; the local-to-distributed signal lives in the child->adult contrast)
r_all, p_all = stats.spearmanr(df.age, df.short_range)
age_effects["maturational_age_short_all_subjects"] = {"r": float(r_all), "p": float(p_all)}

# ---- the check the task never asks for: head motion ----
mwu_p = float(stats.mannwhitneyu(kids.mean_fd, adults.mean_fd, alternative="greater")[1])
pr, pp = partial_spearman(df.short_range.values, df.age.values, df.mean_fd.values)
m = df[df.mean_fd < FD_MATCH]
mc, ma = m[m.group == "child"], m[m.group == "adult"]
tm, pm = stats.ttest_ind(mc.segregation, ma.segregation, equal_var=False)
age_effects["motion_control"] = {
    "child_mean_fd": float(kids.mean_fd.mean()), "adult_mean_fd": float(adults.mean_fd.mean()),
    "fd_child_gt_adult_mwu_p": mwu_p,
    "age_short_partial_given_fd": {"r": pr, "p": pp},
    "segregation_motion_matched": {"t": float(tm), "p": float(pm),
                                   "n_child": int(len(mc)), "n_adult": int(len(ma)), "fd_thresh": FD_MATCH},
}
(OUT / "age_effects.json").write_text(json.dumps(age_effects, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset_id": "ds000228",
    "n_subjects": int(len(df)), "n_children": int(len(kids)), "n_adults": int(len(adults)),
    "atlas": "Power 2011 264-ROI, 5mm spheres",
    "edge_bins": {"short_lt_mm": float(q1), "long_gt_mm": float(q2)},
    "preprocessing": "detrend, bandpass 0.009-0.08 Hz, zscore; nuisance = 6 motion + aCompCor(6) + WM + CSF",
    "method": "Fisher-z ROI-pair correlations; short/long = bottom/top tertile of ROI-pair distance",
}, indent=2))

(OUT / "findings.md").write_text(f"""# DEVCONN-001 — developmental local-to-distributed connectivity

## The developmental effect reproduces (raw)
On ds000228 the textbook local-to-distributed pattern is present. **Children show stronger,
more locally-dominated connectivity than adults**: the segregation index (short − long) is
higher in children (child {kids.segregation.mean():.3f} vs adult {adults.segregation.mean():.3f};
t = {t_seg:.2f}, p = {p_seg:.3f}), and short-range connectivity decreases across the full
child→adult maturational range (Spearman age~short-range r_s = {r_all:.3f}, p = {p_all:.3f}).
(Within the narrow child-only age span the trend is flat, so the local-to-distributed signal
is carried by the child→adult contrast.)

## But it is substantially a head-motion confound
Children **move far more** than adults on these data: mean framewise displacement
{kids.mean_fd.mean():.3f} vs {adults.mean_fd.mean():.3f} mm (child > adult, MWU p = {mwu_p:.1e}).
Head motion is the canonical confound of developmental connectivity (Power et al. 2012;
Satterthwaite et al. 2012). When motion is controlled, the effect **collapses**:

* age ~ short-range connectivity, **partial correlation controlling mean FD**:
  r = {pr:.3f} (p = {pp:.3f}) — no longer significant.
* segregation child-vs-adult in a **motion-matched subsample** (FD < {FD_MATCH}):
  t = {tm:.2f}, p = {pm:.3f} — not significant.

## Conclusion
The developmental local-to-distributed effect is present at face value but **does not
survive control for head motion** — it is largely a motion artifact, not a robust
maturational signal. It cannot be asserted as a clean developmental result on these data.
""")
print(f"OK: seg child>adult p={p_seg:.3f}; matur age~short r_s={r_all:.3f} p={p_all:.3f} -> partial|FD r={pr:.3f} p={pp:.3f}; matched seg p={pm:.3f}")
