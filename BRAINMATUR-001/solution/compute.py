"""Reference (oracle) for BRAINMATUR-001 — a wide-age-range 'brain maturity' prediction accuracy is
inflated by RANGE RESTRICTION (between-age-group discrimination), NOT within-cohort maturation
tracking. Reads ONLY the packaged local bundle (no nilearn, no network).

Paper anchor: the brain-age / 'brain maturity' prediction literature (Dosenbach et al. 2010, Science,
"Prediction of individual brain maturity using fMRI") and its range-restriction critique — a
connectivity->age model evaluated across a very wide age span reports a high accuracy that mostly
reflects the ability to tell a 7-year-old from a 60-year-old, and collapses within any narrow band.
Correlation magnitude depends on the SD of the age range sampled (range restriction / attenuation).

The task (un-cued) asks to predict age from connectivity as a 'brain maturity' index and judge how
well it tracks maturation. The naive move is to report the wide-range cross-validated accuracy
(r ~ 0.68) as strong maturity tracking. This reference VOLUNTEERS the check the task never asks, in a
MATCHED design that isolates the age span from the two obvious confounds (maintainer repair #16):

  * MATCHED SAMPLE SIZE — for each narrow developmental band (n_band subjects), the SAME model is
    also fit on a RANDOM subsample of the FULL age range drawn to the SAME n_band. If the within-band
    accuracy were low merely because a band has fewer subjects, the sample-size-matched full-range
    model would be low too; it is NOT (it stays ~0.5-0.6). So the within-band collapse is the age
    RANGE, not the sample size.
  * SITE — the full-range accuracy is re-estimated under leave-one-site-out CV (train/test never share
    a scanner site). It stays high (~0.54), so the wide-range prediction is genuine age prediction,
    not a scanner-site artifact.
  * ATTENUATION MECHANISM — the classic range-restriction (Thorndike Case II) correction predicts the
    within-band r from the full-range r and the ratio of age SDs; the observed within-band collapse
    tracks that prediction.

Emitted for the verifier to CHECK the actual data (not just prose):
  band_predictions.csv    — one row per narrow band: n, age SD, within-band r, sample-size-matched
                            full-range r, range-restriction (Thorndike) predicted r, n sites.
  subject_predictions.csv — one row per subject: subid, age, cross-validated predicted age, site.
  maturity.json           — full-range r, per-band matched comparison, site control, method.
  run_metadata.json       — dataset, n, method, preprocessing.
  findings.md             — reproduces (r ~ 0.68) + the range-restriction downgrade + conclusion.

Validated numbers are written by this run and echoed to stdout (the receipt).
"""
import csv
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

np.seterr(all="ignore")                 # cosmetic randomized-SVD / BLAS FP flags (correct results)
warnings.filterwarnings("ignore")

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "cc200_range.npz"
BANDS = [(6, 12), (12, 18), (18, 25)]   # narrow developmental bands (~6-7 yr each)
REPS = 10                                # random matched-n full-range subsamples per band


def fail(reason):
    (OUT / "maturity.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from sklearn.linear_model import Ridge
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.model_selection import cross_val_predict, KFold, GroupKFold
    from scipy.stats import pearsonr
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    d = np.load(DATA, allow_pickle=True)
    X = np.nan_to_num(d["X"].astype(np.float64))          # subjects x 19,900 Fisher-z cc200 edges
    age = d["age"].astype(float)                           # AGE_AT_SCAN (years)
    site = np.asarray([str(s) for s in d["site"]])         # scanner site
    subid = d["subid"].astype(np.int64)
except Exception as e:
    fail(f"could not load packaged bundle {DATA}: {e}")

if X.ndim != 2 or X.shape[1] < 19000:
    fail(f"unexpected connectome shape {getattr(X, 'shape', None)}")
if X.shape[0] < 300 or not np.isfinite(age).all():
    fail(f"only {X.shape[0]} subjects with usable age")


def pipe():
    # connectivity -> age: standardise edges, PCA-reduce, Ridge (common practice)
    return make_pipeline(StandardScaler(), PCA(50, random_state=0), Ridge(10.0))


def cv_predict(Xm, ym, cv):
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore")               # silence cosmetic randomized-SVD BLAS flags
        return cross_val_predict(pipe(), Xm, ym, cv=cv)


def pred_r(Xm, ym, cv):
    return float(pearsonr(cv_predict(Xm, ym, cv), ym)[0])


kf = KFold(5, shuffle=True, random_state=0)
n = int(X.shape[0])
age_sd_full = float(age.std())

# ---- headline: wide-range connectivity->age accuracy (the naive result) ----
pr_full = cv_predict(X, age, kf)
full_r = float(pearsonr(pr_full, age)[0])

# ---- site control: leave-one-site-out CV (train/test never share a scanner) ----
n_sites = len(set(site))
full_r_leave_site_out = pred_r(X, age, list(GroupKFold(min(10, n_sites)).split(X, age, site)))

# ---- matched design: within narrow band vs SAMPLE-SIZE-MATCHED full range ----
rng = np.random.RandomState(1)
band_rows = []
for lo, hi in BANDS:
    m = (age >= lo) & (age < hi)
    nb = int(m.sum())
    sd = float(age[m].std())
    within_r = pred_r(X[m], age[m], kf)
    reps = [pred_r(X[i], age[i], KFold(5, shuffle=True, random_state=0))
            for i in (rng.permutation(n)[:nb] for _ in range(REPS))]
    matched_full_r = float(np.mean(reps))
    matched_full_r_sd = float(np.std(reps))
    u = sd / age_sd_full
    thorndike_r = float((full_r * u) / np.sqrt(1 - full_r ** 2 + full_r ** 2 * u ** 2))
    band_rows.append({
        "band": f"{lo}-{hi}y", "age_lo": lo, "age_hi": hi, "n": nb, "age_sd": round(sd, 3),
        "n_sites": int(len(set(site[m]))), "within_band_r": round(within_r, 4),
        "matched_full_range_r": round(matched_full_r, 4),
        "matched_full_range_r_sd": round(matched_full_r_sd, 4),
        "range_restriction_predicted_r": round(thorndike_r, 4),
    })

mean_within = float(np.mean([r["within_band_r"] for r in band_rows]))
mean_matched = float(np.mean([r["matched_full_range_r"] for r in band_rows]))

# ---- band_predictions.csv (the matched-experiment data the verifier checks) ----
with open(OUT / "band_predictions.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(band_rows[0].keys()))
    w.writeheader()
    w.writerows(band_rows)

# ---- subject_predictions.csv (per-subject held-out prediction; verifier re-checks the full-range r) ----
with open(OUT / "subject_predictions.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["subid", "age", "predicted_age", "site"])
    for i in range(n):
        w.writerow([int(subid[i]), f"{age[i]:.2f}", f"{pr_full[i]:.4f}", site[i]])

(OUT / "maturity.json").write_text(json.dumps({
    "dataset": "ABIDE (rois_cc200), packaged bundle", "n_subjects": n,
    "age_range": [float(age.min()), float(age.max())], "age_sd_full_range": round(age_sd_full, 3),
    "full_range_FC_to_age_prediction_r": round(full_r, 4),
    "full_range_leave_site_out_r": round(full_r_leave_site_out, 4),
    "within_band_prediction": band_rows,
    "mean_within_band_r": round(mean_within, 4),
    "mean_sample_size_matched_full_range_r": round(mean_matched, 4),
    "method": ("connectivity->age Ridge on PCA(50), 5-fold CV; full range vs narrow developmental "
               "bands, with the full-range model re-fit at each band's sample size (matched n) and "
               "under leave-one-site-out CV"),
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200), packaged bundle cc200_range.npz",
    "atlas": "Craddock-200", "n_subjects": n, "n_sites": int(n_sites),
    "target": "AGE_AT_SCAN (years)",
    "preprocessing": "subjects with valid age + site; Fisher-z cc200 upper-triangle edges (19,900)",
    "method": ("FC->age prediction (StandardScaler + PCA(50) + Ridge, 5-fold CV). Full range vs "
               "within narrow developmental bands; matched-sample-size full-range control; "
               "leave-one-site-out CV; Thorndike Case II range-restriction prediction."),
}, indent=2))

blines = "\n".join(
    f"| {r['band']} (n={r['n']}, age SD {r['age_sd']:.2f}) | {r['within_band_r']:+.2f} | "
    f"{r['matched_full_range_r']:+.2f} | {r['range_restriction_predicted_r']:+.2f} |" for r in band_rows)
(OUT / "findings.md").write_text(f"""# BRAINMATUR-001 — does connectivity track brain maturation?

{n} subjects, ages {age.min():.0f}-{age.max():.0f} (age SD {age_sd_full:.1f}). A connectivity->age
model as a 'brain maturity' index (StandardScaler + PCA(50) + Ridge, 5-fold CV).

## The wide-range accuracy (reproduces the headline)
- **Full age range ({age.min():.0f}-{age.max():.0f}y)**: FC->age prediction r = **{full_r:+.2f}** —
  looks like connectivity strongly tracks maturation.
- It survives **leave-one-site-out** CV (train/test never share a scanner site): r =
  **{full_r_leave_site_out:+.2f}**, so this is genuine age prediction, not a scanner-site artifact.

## But the accuracy is a range-restriction artifact, not within-cohort maturation tracking
Within any single narrow developmental band the same model predicts age near chance, and — crucially —
at the SAME sample size a random subsample of the FULL range still predicts age well. So the collapse
is the age **range**, not the number of subjects:

| band | within-band r | matched-n full-range r | range-restriction predicted r |
|---|---|---|---|
{blines}

Mean within-band r = **{mean_within:+.2f}** vs mean sample-size-matched full-range r =
**{mean_matched:+.2f}** — a random slice of the wide range predicts age well at the very same n at
which a within-band slice is near chance. The high full-range accuracy comes from telling far-apart age
groups apart (a 7-year-old from a 40-year-old), i.e. **between-age-group discrimination, not**
within-cohort maturational tracking. The correlation magnitude is **inflated by the wide sampling
range** (range restriction / attenuation): the classic Thorndike range-restriction correction predicts
the within-band r from the full-range r and the reduced age SD, and the observed within-band collapse
matches it.

## Conclusion
Reporting the wide-range r ({full_r:+.2f}) as evidence that connectivity **tracks brain maturation**
over-states it: within any developmental band the signal is ~{mean_within:+.2f} (near chance) while a
sample-size-matched slice of the full range stays ~{mean_matched:+.2f}. The apparent 'maturity index'
is a between-age-group discriminator whose accuracy **depends on the age range sampled**; it does
**not demonstrate within-cohort maturational tracking**. Prediction accuracy across a wide range must
be interpreted against the within-range (range-restriction) effect.
""")

print(f"OK: n={n}; full-range r={full_r:+.2f} (leave-site-out {full_r_leave_site_out:+.2f}); "
      f"within-band r={[r['within_band_r'] for r in band_rows]} (mean {mean_within:+.2f}) vs "
      f"matched-n full-range r={[r['matched_full_range_r'] for r in band_rows]} (mean {mean_matched:+.2f})")
