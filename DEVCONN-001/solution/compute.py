"""Paper-derived child-only movie-data motion-sensitivity case, not Fair reproduction."""
import json
import os
import re
import hashlib
from development_contract import estimate, validate_input_identity
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import pdist, squareform

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
FD_THRESHOLD = 0.2
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


from development_contract import partial_spearman


try:
    from nilearn import datasets
    from nilearn.maskers import NiftiSpheresMasker
except Exception as e:  # pragma: no cover
    fail(f"nilearn import failed: {e}")

try:
    dev = datasets.fetch_development_fmri(n_subjects=155)
    ph = dev.phenotypic
    ph = ph.reset_index(drop=True) if hasattr(ph,"reset_index") else pd.DataFrame(ph)
    assert ph.participant_id.is_unique
    ph=ph.set_index("participant_id")
    validate_input_identity(dev.func,dev.confounds,ph.index)
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
source_receipt={}
for i, (func, cf) in enumerate(zip(dev.func, dev.confounds)):
    sid=re.search(r"(sub-[A-Za-z0-9]+)",Path(func).name).group(1)
    if sid not in ph.index:
        fail(f"missing phenotype for {sid}")
    source_receipt[sid]={"image_sha256":hashlib.sha256(Path(func).read_bytes()).hexdigest(),
                         "confounds_sha256":hashlib.sha256(Path(cf).read_bytes()).hexdigest()}
    conf = pd.read_csv(cf, sep="\t")
    fd = conf["framewise_displacement"].fillna(0).values
    ts = masker.transform(func, confounds=conf[CONF_COLS].fillna(0).values)
    if ts.shape[0] < 30:
        fail(f"insufficient timepoints for {sid}")
    c = np.corrcoef(ts.T)
    e = np.arctanh(np.clip(c, -0.999, 0.999))[iu]  # Fisher z
    short = float(np.nanmean(e[short_mask]))
    long = float(np.nanmean(e[long_mask]))
    rows.append(dict(subject_id=sid, age=float(ph.loc[sid, "Age"]),
                     group=str(ph.loc[sid, "Child_Adult"]).lower(),
                     short_range=short, long_range=long, segregation=short - long,
                     mean_fd=float(fd.mean())))

df = pd.DataFrame(rows)
if len(df) != 155 or not df.subject_id.is_unique:
    fail(f"only {len(df)} subjects processed")

# ---- required output: per-subject connectivity + mean framewise displacement (standard QC) ----
df[["subject_id", "age", "group", "short_range", "long_range", "segregation", "mean_fd"]].to_csv(
    OUT / "connectivity.csv", index=False)

kids = df[df.group == "child"].sort_values("subject_id")
adults = df[df.group == "adult"]

# ---- the developmental effect (raw) ----
age_effects = {"population": "children_only", "n_children": int(len(kids)), "n_adults": int(len(adults)),
               "children_age_spearman": {}, "group_means": {}}
for col in ["short_range", "long_range", "segregation"]:
    r, p = stats.spearmanr(kids.age, kids[col])
    age_effects["children_age_spearman"][col] = estimate(kids.age.to_numpy(),kids[col].to_numpy(),kids.mean_fd.to_numpy())
    age_effects["group_means"][col] = {"child": float(kids[col].mean()), "adult": float(adults[col].mean())}
t_seg, p_seg = stats.ttest_ind(kids.segregation, adults.segregation, equal_var=False)
age_effects["segregation_child_vs_adult"] = {"t": float(t_seg), "p": float(p_seg)}
# Optional pooled association: exploratory, not the primary developmental estimand.
r_all, p_all = stats.spearmanr(df.age, df.short_range)
age_effects["maturational_age_short_all_subjects"] = {"r": float(r_all), "p": float(p_all)}

# ---- public motion sensitivity and low-motion restriction ----
mwu_p = float(stats.mannwhitneyu(kids.mean_fd, adults.mean_fd, alternative="greater")[1])
pr, pp = partial_spearman(kids.short_range.values, kids.age.values, kids.mean_fd.values)
m = df[df.mean_fd < FD_THRESHOLD]
mc, ma = m[m.group == "child"], m[m.group == "adult"]
tm, pm = stats.ttest_ind(mc.segregation, ma.segregation, equal_var=False)
age_effects["motion_control"] = {
    "child_mean_fd": float(kids.mean_fd.mean()), "adult_mean_fd": float(adults.mean_fd.mean()),
    "fd_child_gt_adult_mwu_p": mwu_p,
    "age_short_partial_given_fd": {"r": pr, "p": pp},
    "segregation_low_motion_restriction": {"t": float(tm), "p": float(pm),
                                   "n_child": int(len(mc)), "n_adult": int(len(ma)), "fd_thresh": FD_THRESHOLD},
}
(OUT / "age_effects.json").write_text(json.dumps(age_effects, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset_id": "ds000228",
    "analysis_scope": "paper-derived child-only movie-data motion sensitivity",
    "source_sha256_by_subject": source_receipt,
    "n_subjects": int(len(df)), "n_children": int(len(kids)), "n_adults": int(len(adults)),
    "atlas": "Power 2011 264-ROI, 5mm spheres",
    "edge_bins": {"short_lt_mm": float(q1), "long_gt_mm": float(q2)},
    "preprocessing": "detrend, bandpass 0.009-0.08 Hz, zscore; nuisance = 6 motion + aCompCor(6) + WM + CSF",
    "method": "Fisher-z ROI-pair correlations; short/long = bottom/top tertile of ROI-pair distance",
}, indent=2))

(OUT / "findings.md").write_text(
    "# Fair/Power-motivated child-only movie-data motion sensitivity\n\n"
    f"Child-only short-range age r={age_effects['children_age_spearman']['short_range']['r']:+.4f}; "
    f"motion-adjusted rank r={pr:+.4f}, p={pp:.5g}. "
    "Participant-bootstrap95% intervals are reported for all child age estimands. "
    f"FD<0.2 child/adult segregation comparison p={pm:.5g}; this is low-motion restriction, "
    "not motion matching. The data are movie-watching, with Power264/distance-tertile "
    "summaries; this is not Fair's original resting/four-network reproduction. Covariate "
    "sensitivity and non-significance do not establish a motion-caused artifact or no developmental effect.\n")

print(f"OK: child-only age~short r_s={age_effects['children_age_spearman']['short_range']['r']:.3f}; partial|FD r={pr:.3f} p={pp:.3f}; low-motion restricted segregation p={pm:.3f}")
