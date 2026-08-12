"""Reference (oracle) for REGIONALGM-001 — circular analysis / double dipping in a structural VBM contrast.

Paper anchor: Kriegeskorte et al. 2009, Nature Neuroscience (10.1038/nn.2303, "Circular analysis in
systems neuroscience: the dangers of double dipping"); Vul et al. 2009 (non-independence / "voodoo
correlations"). Localizing a region by the very contrast you then test — on the SAME subjects — is
non-independent ("circular"): the selection guarantees an inflated, often "significant" effect even
when there is none.

The task (un-cued) asks whether there are localized sex differences in gray matter beyond overall head
size: residualize the gray-matter maps on eTIV (head size), localize the region with the largest
male-female difference, and report its significance. The NAIVE move is to test the selected region on
the SAME subjects — that is circular. This reference reproduces that naive "significant" result AND
VOLUNTEERS the check the task never asks:

  * circular  (select peak sex-difference ROI on all subjects, test on the SAME subjects) -> p ~ 4e-4
  * honest    (split-half: select the ROI on one half, test on the other half)            -> median p ~ 0.5-0.6 (n.s.)
  * null      (permuted / shuffled sex labels, no true difference): the circular procedure still
              returns p<0.05 in ~85-92% of runs (nominal 5%) -- pure selection bias.

After head-size control the overall sex difference is ~null, yet the circular procedure manufactures a
"significant" regional effect because the region was chosen *because* it differed and then tested on the
same data. The honest split-half shows no reliable localized sex difference.

Emitted for the verifier to CHECK the actual data (not just prose):
  subjects.csv     — one row per subject: subject_id, sex (M/F), eTIV (head size) — the real labels/values
  splithalf.csv    — one row per honest split: split_id, heldout_p, heldout_cohens_d — the honest distribution
  roi.json         — n_subjects, circular (naive) p + Cohen's d, honest split-half median p, null false-
                     positive rate of the circular procedure
  run_metadata.json — dataset, n_subjects, preprocessing, method
  findings.md      — reproduces the naive "significant" result + volunteers the circularity + conclusion

Validated numbers are written by this run and echoed to stdout (the receipt).
"""
import csv
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

K = 200            # ROI = the K peak sex-difference voxels
N_SPLITS = 25      # honest split-half repeats
N_NULL = 120       # permuted-grouping repeats for the null false-positive rate


def fail(reason):
    (OUT / "roi.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "oasis1"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn.datasets import fetch_oasis_vbm
    from nilearn.maskers import NiftiMasker
    from scipy import stats
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

import pandas as pd

try:
    o = fetch_oasis_vbm(n_subjects=150)
except Exception as e:
    fail(f"could not fetch OASIS VBM: {e}")

ev = o.ext_vars if isinstance(o.ext_vars, pd.DataFrame) else pd.DataFrame(o.ext_vars)
cols = {c.lower(): c for c in ev.columns}
if "mf" not in cols or not (set(cols) & {"etiv", "tiv"}):
    fail(f"OASIS ext_vars missing sex (mf) / eTIV columns: have {list(ev.columns)}")

sid = np.array([str(s).strip() for s in ev[cols.get("id", cols["mf"])]])
sex = np.array([str(s).strip().upper() for s in ev[cols["mf"]]])
etiv = pd.to_numeric(ev[cols.get("etiv", cols.get("tiv"))], errors="coerce").values.astype(float)

masker = NiftiMasker(mask_strategy="epi", standardize=False, detrend=False)
X = masker.fit_transform(o.gray_matter_maps).astype(np.float64)
# keep finite, higher-variance (brain) voxels; drop background / degenerate columns
X[~np.isfinite(X)] = 0.0
v = X.var(0)
X = X[:, np.isfinite(v) & (v > 0) & (v > np.percentile(v, 50))]

ok = np.isfinite(etiv) & ((sex == "M") | (sex == "F"))
X, sid, sex_ok, etiv = X[ok], sid[ok], sex[ok], etiv[ok]
male = (sex_ok == "M").astype(int)
n, V = X.shape
n_m, n_f = int(male.sum()), int((male == 0).sum())
if n < 80 or n_m < 10 or n_f < 10:
    fail(f"too few usable subjects (n={n}, M={n_m}, F={n_f})")

# ---- remove head size (eTIV): regress intercept + eTIV out of every voxel ----
# z-score eTIV for a well-conditioned design (residuals are invariant to regressor scaling)
etiv_z = (etiv - etiv.mean()) / etiv.std(ddof=0)
Z = np.column_stack([np.ones(n), etiv_z])                # (n, 2) design: intercept + head size
beta, *_ = np.linalg.lstsq(Z, X, rcond=None)             # (2, V)
with np.errstate(all="ignore"):                          # silence spurious matmul FP-flag warning
    Xr = X - Z @ beta                                    # eTIV-residualized GM per voxel
if not np.isfinite(Xr).all():
    fail("eTIV residualization produced non-finite values")

rng = np.random.default_rng(0)


def roi_test(train_g, train_mask, test_g, test_mask):
    """Select the K peak |male-female| voxels on the TRAIN subjects, then test the ROI-mean sex
    difference on the TEST subjects. Returns (p_value, cohens_d) or (nan, nan) if degenerate."""
    Xtr, gtr = Xr[train_mask], train_g[train_mask]
    if gtr.sum() < 3 or (gtr == 0).sum() < 3:
        return np.nan, np.nan
    t, _ = stats.ttest_ind(Xtr[gtr == 1], Xtr[gtr == 0], axis=0)
    top = np.argsort(np.abs(np.nan_to_num(t)))[-K:]
    Xte, gte = Xr[test_mask][:, top], test_g[test_mask]
    a, b = Xte[gte == 1].mean(1), Xte[gte == 0].mean(1)
    if len(a) < 3 or len(b) < 3:
        return np.nan, np.nan
    p = float(stats.ttest_ind(a, b)[1])
    sp = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    d = float((a.mean() - b.mean()) / sp) if sp > 0 else 0.0
    return p, d


allmask = np.ones(n, bool)

# NAIVE / circular: select AND test on the SAME (all) subjects
p_circular, d_circular = roi_test(male, allmask, male, allmask)

# HONEST: split-half — select the ROI on one half, test it on the other half
sh_rows = []
for s in range(N_SPLITS):
    idx = rng.permutation(n)
    h1 = np.zeros(n, bool); h1[idx[:n // 2]] = True
    h2 = ~h1
    p, d = roi_test(male, h1, male, h2)
    if np.isfinite(p):
        sh_rows.append((s, p, d))
p_honest = float(np.median([p for _, p, _ in sh_rows])) if sh_rows else float("nan")
d_honest = float(np.median([d for _, _, d in sh_rows])) if sh_rows else float("nan")
frac_sig_honest = float(np.mean([p < 0.05 for _, p, _ in sh_rows])) if sh_rows else float("nan")

# NULL: permuted / shuffled sex labels (no true difference) -> false-positive rate of the circular test
null_hits = 0
for _ in range(N_NULL):
    g = rng.integers(0, 2, n)
    p, _ = roi_test(g, allmask, g, allmask)
    if np.isfinite(p) and p < 0.05:
        null_hits += 1
null_fpr = float(null_hits / N_NULL)

# ---- subjects.csv: the real per-subject labels/values the verifier checks ----
with open(OUT / "subjects.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["subject_id", "sex", "eTIV"])
    for i in range(n):
        w.writerow([sid[i], sex_ok[i], f"{etiv[i]:.1f}"])

# ---- splithalf.csv: the honest out-of-sample distribution the verifier checks ----
with open(OUT / "splithalf.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["split_id", "heldout_p", "heldout_cohens_d"])
    for s, p, d in sh_rows:
        w.writerow([s, f"{p:.6f}", f"{d:.6f}"])

(OUT / "roi.json").write_text(json.dumps({
    "dataset": "OASIS VBM (gray-matter maps)",
    "n_subjects": int(n), "n_male": n_m, "n_female": n_f, "n_voxels": int(V), "roi_size_voxels": K,
    "circular_region_sex_pvalue": p_circular,
    "circular_region_sex_cohens_d": d_circular,
    "honest_splithalf_sex_pvalue_median": p_honest,
    "honest_splithalf_sex_cohens_d_median": d_honest,
    "honest_splithalf_fraction_significant": frac_sig_honest,
    "circular_null_false_positive_rate": null_fpr,
    "method": ("GM residualized on intercept+eTIV; ROI = K peak |male-female| voxels. Circular: select "
               "AND test on the SAME subjects. Honest: split-half (select on one half, test on the other). "
               "Null: permuted sex labels -> false-positive rate of the circular procedure."),
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "OASIS VBM (oasis1)", "n_subjects": int(n),
    "n_male": n_m, "n_female": n_f, "n_voxels": int(V), "roi_size_voxels": K,
    "preprocessing": "modulated GM maps; EPI brain mask; intercept+eTIV regressed out of every voxel; "
                     "high-variance voxels kept",
    "method": "circular (select+test same subjects) vs split-half (honest) vs permuted-label null; "
              "localized sex-difference test, eTIV-controlled",
}, indent=2))

verdict = ("no reliable localized sex difference" if p_honest >= 0.05
           else "a localized sex difference that survives split-half")
(OUT / "findings.md").write_text(f"""# REGIONALGM-001 — localized sex differences in gray matter (OASIS VBM)

{n} subjects ({n_m} M / {n_f} F); gray matter residualized on eTIV (head size). We localize the
{K}-voxel region with the largest male-female difference and test the sex difference there.

## The "significant" localized sex difference is circular
- **Circular** test — localize the peak sex-difference ROI and test it on the **same** subjects:
  **p = {p_circular:.1e}** (Cohen's d = {d_circular:.2f}) — apparently a significant localized sex
  difference beyond head size.
- **Honest** split-half — localize the ROI on one half of the subjects, test it on the **other** half:
  median **p = {p_honest:.2f}** (median d = {d_honest:.2f}); significant in only
  {frac_sig_honest*100:.0f}% of splits — **no reliable difference** out of sample.
- **Permuted-label null** — sex labels shuffled, so there is no true difference: the circular procedure
  still returns p < 0.05 in **{null_fpr*100:.0f}%** of runs (nominal should be 5%).

After controlling for head size the overall sex difference is ~null, yet the circular procedure
manufactures a "significant" regional effect: the region was selected *because* it differed and then
tested on the **same** data, so the selection bias is baked into the test.

## Conclusion
Selecting a region by a contrast and testing that contrast in the **same** subjects is **circular /
double dipping** (Kriegeskorte 2009; Vul 2009): it is **non-independent** and inflates the estimate. Here
it fabricates significance in {null_fpr*100:.0f}% of shuffled-label runs (nominal 5%), and the honest
split-half estimate **collapses** (p = {p_circular:.1e} -> {p_honest:.2f}). The correct conclusion is
**{verdict}**: the circular p-value over-states the evidence. A localized sex difference must be
estimated on **independent** data (split-half / cross-validation) or against a **permutation null**, not
on the same subjects used to select the region.
""")
print(f"OK: n={n} ({n_m}M/{n_f}F); circular p={p_circular:.1e} (d={d_circular:.2f}) vs honest split-half "
      f"median p={p_honest:.2f}; null FPR={null_fpr:.2f}")
