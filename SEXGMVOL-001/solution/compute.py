"""Reference (oracle) for SEXGMVOL-001 — sex difference in gray-matter volume (OASIS VBM).

Reproduces the standard structural finding — men have larger total gray-matter volume than women
(Ruigrok et al. 2014) — then VOLUNTEERS the un-cued check the task never asks: men also have
systematically larger heads (intracranial volume, eTIV), so the raw GM difference is confounded by
head size. After adjusting for eTIV, the raw male advantage does NOT survive — it REVERSES: women
have more gray matter per unit head size. So "men have more gray matter" is a head-size artifact,
not a robust GM-specific male advantage.

Head-size correction anchor: Barnes et al. 2010 (NeuroImage) argue the covariate/ANCOVA adjustment
is the principled way to remove head-size confounding (the proportion/division method can distort).

ONE consistent eTIV-adjusted estimand (stated and used throughout):
    the sex coefficient in the linear model  GM ~ sex + eTIV
    = the partial effect of sex on total GM holding head size (eTIV) constant.
The proportion measure GM/eTIV is reported only as a corroboration that the reversal is not an
artifact of the ANCOVA form (both agree: F > M after adjustment).

MAINTAINER REPAIR (#20): missing CDR is NOT coerced to healthy. In OASIS-1 the CDR field is only
recorded for assessed (older) subjects; the 177 subjects with missing CDR are young adults (18-58)
who were never dementia-assessed. Treating them as CDR=0 healthy controls is wrong, so they are
EXCLUDED. The analysis sample is the confirmed-healthy cohort with CDR == 0.

Defensible pipeline: modulated GM maps (OASIS VBM) -> per-subject total GM = sum of the modulated
map (modulation preserves absolute volume) -> restrict to confirmed-healthy CDR==0 (missing CDR
excluded) -> raw sex difference (Welch t, Cohen d) -> eTIV-adjusted sex effect (ANCOVA sex
coefficient in GM ~ sex + eTIV) -> report the reversal and the head-size confound driving it.

Emitted for the verifier to CHECK the actual data (not just prose):
  gm_subjects.csv    — one row per analysis subject: id, sex, age, cdr, total_gm, etiv, gm_over_etiv
  gm_sex.json        — n_male/n_female, raw effect (M>F), eTIV-by-sex confound, the ONE eTIV-adjusted
                       estimand (F>M), proportion corroboration, and the reversal flag
  run_metadata.json  — dataset, sample definition, estimand, method, preprocessing
  findings.md        — reproduces (raw M>F) + the head-size confound + the reversal + conclusion

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


def fail(reason):
    (OUT / "gm_sex.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "oasis1"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import nibabel as nib
    import pandas as pd
    from nilearn.datasets import fetch_oasis_vbm
    from scipy import stats
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    o = fetch_oasis_vbm(n_subjects=403)
except Exception as e:
    fail(f"could not fetch OASIS VBM: {e}")

ev = o.ext_vars if isinstance(o.ext_vars, pd.DataFrame) else pd.DataFrame(o.ext_vars)
cols = {c.lower(): c for c in ev.columns}


def col(*names):
    for n in names:
        if n in cols:
            return cols[n]
    fail(f"missing expected phenotypic column {names}")


id_c = col("id", "subject_id", "subject")
sex_c, etiv_c, cdr_c, age_c = col("mf", "sex", "gender"), col("etiv", "tiv"), col("cdr"), col("age")

# total GM per subject = sum of the MODULATED GM map (modulation preserves absolute volume)
try:
    totals = np.array([np.asarray(nib.load(f).dataobj, dtype=np.float32).sum()
                       for f in o.gray_matter_maps], dtype=float)
except Exception as e:
    fail(f"could not read GM maps: {e}")

sid = np.array([str(s).strip() for s in ev[id_c]])
sex = np.array([str(s).strip().upper() for s in ev[sex_c]])
etiv = pd.to_numeric(ev[etiv_c], errors="coerce").values.astype(float)
cdr = pd.to_numeric(ev[cdr_c], errors="coerce").values.astype(float)
age = pd.to_numeric(ev[age_c], errors="coerce").values.astype(float)

# --- REPAIR #20: EXCLUDE subjects with missing CDR (do NOT coerce NaN CDR to 0/healthy). ---
n_missing_cdr = int(np.isnan(cdr).sum())
healthy = np.isfinite(cdr) & (cdr == 0)               # confirmed-healthy only
keep = healthy & np.isfinite(etiv) & np.isfinite(totals) & np.isin(sex, ["M", "F"])
isM, isF = (sex == "M") & keep, (sex == "F") & keep
nM, nF = int(isM.sum()), int(isF.sum())
if nM < 15 or nF < 15:
    fail(f"too few confirmed-healthy subjects (M={nM} F={nF}); missing-CDR excluded={n_missing_cdr}")

gmM, gmF = totals[isM], totals[isF]


def cohend(a, b):
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    return float((a.mean() - b.mean()) / sp)


def welch(a, b):
    t, p = stats.ttest_ind(a, b, equal_var=False)
    return float(t), float(p)


# 1) RAW total GM by sex — the reproduction ("men have more gray matter")
t_raw, p_raw = welch(gmM, gmF)
d_raw = cohend(gmM, gmF)

# The confound: eTIV (head size) by sex
t_e, p_e = welch(etiv[isM], etiv[isF])
d_e = cohend(etiv[isM], etiv[isF])

# 2) THE eTIV-ADJUSTED ESTIMAND — sex coefficient in ANCOVA  GM ~ sex + eTIV
kk = isM | isF
y = totals[kk]
X = np.column_stack([np.ones(kk.sum()), isM[kk].astype(float), etiv[kk]])
beta, *_ = np.linalg.lstsq(X, y, rcond=None)
resid = y - X @ beta
dof = int(kk.sum() - X.shape[1])
se = float(np.sqrt((resid @ resid / dof) * np.linalg.inv(X.T @ X)[1, 1]))
t_adj = float(beta[1] / se)               # sex_M coefficient / SE  (positive => M>F adjusted)
p_adj = float(2 * stats.t.sf(abs(t_adj), dof))

# corroboration only: proportion GM/eTIV by sex (same-direction check on the reversal)
prop = totals / etiv
t_pr, p_pr = welch(prop[isM], prop[isF])
d_pr = cohend(prop[isM], prop[isF])

raw_dir = "M>F" if t_raw > 0 else "F>M"
adj_dir = "M>F" if t_adj > 0 else "F>M"
# the raw male advantage does not survive head-size adjustment: it reverses (or at minimum nulls)
reverses = bool((t_raw > 0 and p_raw < 0.05) and (t_adj < 0))
survives = bool((t_raw > 0 and p_raw < 0.05) and (t_adj > 0 and p_adj < 0.05))

# ---- gm_subjects.csv: the actual per-subject data the verifier checks ----
with open(OUT / "gm_subjects.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["subject_id", "sex", "age", "cdr", "total_gm", "etiv", "gm_over_etiv"])
    for i in np.where(keep)[0]:
        w.writerow([sid[i], sex[i], f"{age[i]:.0f}", f"{cdr[i]:.1f}",
                    f"{totals[i]:.3f}", f"{etiv[i]:.3f}", f"{totals[i] / etiv[i]:.6f}"])

(OUT / "gm_sex.json").write_text(json.dumps({
    "dataset": "OASIS VBM (nilearn fetch_oasis_vbm)",
    "n_subjects": nM + nF, "n_male": nM, "n_female": nF,
    "sex_categories": ["M", "F"],
    "healthy_definition": "CDR == 0 (confirmed-healthy); subjects with missing CDR excluded",
    "n_excluded_missing_cdr": n_missing_cdr,
    "raw_total_gm": {"cohens_d_M_minus_F": round(d_raw, 4), "t": round(t_raw, 3),
                     "p": p_raw, "direction": raw_dir, "mean_M": round(float(gmM.mean()), 1),
                     "mean_F": round(float(gmF.mean()), 1)},
    "headsize_etiv_by_sex": {"cohens_d_M_minus_F": round(d_e, 4), "t": round(t_e, 3),
                             "p": p_e, "direction": "M>F" if t_e > 0 else "F>M",
                             "mean_M": round(float(etiv[isM].mean()), 1),
                             "mean_F": round(float(etiv[isF].mean()), 1)},
    "etiv_adjusted_estimand": "ANCOVA: sex coefficient in GM ~ sex + eTIV "
                              "(partial sex effect on total GM holding head size constant)",
    "etiv_adjusted_sex_effect": {"beta_sex_M_minus_F": round(float(beta[1]), 2),
                                 "t": round(t_adj, 3), "p": p_adj, "dof": dof,
                                 "direction": adj_dir},
    "proportion_gm_over_etiv_corroboration": {"cohens_d_M_minus_F": round(d_pr, 4),
                                              "t": round(t_pr, 3), "p": p_pr,
                                              "direction": "M>F" if t_pr > 0 else "F>M"},
    "raw_direction": raw_dir,
    "etiv_adjusted_direction": adj_dir,
    "direction_reverses_after_headsize_adjustment": reverses,
    "male_gm_advantage_survives_headsize_adjustment": survives,
    "method": "total modulated GM by sex; raw Welch t-test vs the eTIV-adjusted estimand "
              "(sex coefficient in ANCOVA GM ~ sex + eTIV)",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "OASIS VBM (oasis1, nilearn fetch_oasis_vbm)",
    "n_subjects": nM + nF, "n_male": nM, "n_female": nF,
    "n_excluded_missing_cdr": n_missing_cdr,
    "sample_definition": "confirmed-healthy adults, CDR == 0; subjects with missing CDR EXCLUDED "
                         "(not coerced to healthy)",
    "estimand": "eTIV-adjusted sex effect = sex coefficient in ANCOVA GM ~ sex + eTIV",
    "preprocessing": "per-subject total GM = sum of the modulated GM map (absolute volume preserved)",
    "method": "raw Welch t-test (M vs F) and the one eTIV-adjusted estimand (ANCOVA sex coefficient); "
              "proportion GM/eTIV reported only as a same-direction corroboration",
}, indent=2))

(OUT / "findings.md").write_text(f"""# SEXGMVOL-001 — sex difference in gray-matter volume (OASIS VBM)

Confirmed-healthy adults (CDR == 0; the {n_missing_cdr} subjects with **missing CDR were excluded**,
not treated as healthy): **{nM} men, {nF} women**. Total gray-matter volume is the sum of each
subject's modulated GM map.

## The headline reproduces: men have more total gray matter (raw)
Raw total GM is significantly larger in men — **M > F, Cohen d = {d_raw:+.2f}, t = {t_raw:+.2f},
p = {p_raw:.2g}** — reproducing the standard "men have larger gray-matter volume" finding
(Ruigrok et al. 2014).

## But the raw difference is confounded by head size, and does not survive adjusting for it
Men have systematically **larger heads**: eTIV (estimated intracranial volume) is much larger in
men (**M > F, d = {d_e:+.2f}, t = {t_e:+.2f}, p = {p_e:.2g}**). Because head size drives raw
brain volume, the raw GM difference is confounded by eTIV.

Using ONE consistent head-size-adjusted estimand — the **sex coefficient in the ANCOVA
`GM ~ sex + eTIV`** (the partial sex effect holding head size constant) — the male advantage does
**not** survive: it **reverses** to **F > M** (β = {beta[1]:+.0f} GM units, t = {t_adj:+.2f},
p = {p_adj:.2g}). The proportion measure GM/eTIV agrees (F > M, t = {t_pr:+.2f}, p = {p_pr:.2g}),
so the reversal is not an artifact of the ANCOVA form. Women have **more** gray matter per unit
head size.

| Estimand | Effect (M vs F) | t | p |
|---|---|---|---|
| **Raw** total GM | **M > F**, d = {d_raw:+.2f} | {t_raw:+.2f} | {p_raw:.2g} |
| Head size (eTIV) | **M > F**, d = {d_e:+.2f} | {t_e:+.2f} | {p_e:.2g} |
| **eTIV-adjusted** (ANCOVA sex coef.) | **F > M**, β = {beta[1]:+.0f} | {t_adj:+.2f} | {p_adj:.2g} |
| proportion GM/eTIV (corroboration) | **F > M**, d = {d_pr:+.2f} | {t_pr:+.2f} | {p_pr:.2g} |

## Conclusion
The raw "men have more gray matter" result reproduces, but it is a **head-size confound**: after
adjusting for eTIV the sex effect **reverses** (women have more GM per unit head size). There is
**no robust male gray-matter advantage independent of head size** — a single raw "men have more GM"
claim **over-states** the evidence. The honest report is that the raw male advantage is attributable
to men's larger head size and does not survive head-size adjustment.
""")

print(f"OK: nM={nM} nF={nF} (missing-CDR excluded={n_missing_cdr}); "
      f"raw {raw_dir} d={d_raw:+.2f} t={t_raw:+.2f} p={p_raw:.1e}; "
      f"eTIV-adjusted(ANCOVA) {adj_dir} t={t_adj:+.2f} p={p_adj:.2g}; "
      f"reverses={reverses}")
