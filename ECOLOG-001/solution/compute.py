"""Reference (oracle) for ECOLOG-001 — the ecological fallacy: a site/group-aggregated connectivity-age
correlation is much larger than the individual-level one and does not license individual inference.

Paper anchor: Robinson 1950, Am Sociol Rev ("Ecological correlations and the behavior of individuals");
the ecological-fallacy critique of aggregated neuroimaging/epidemiological correlations. Correlating
group means (here, per-site means) inflates the correlation relative to the individual level, because
between-group variance is a cleaner (lower-noise) signal than the noisy individual data.

The task (un-cued) asks to examine, ACROSS ABIDE's sites, the relationship between a site's mean
connectivity and its mean age, and report the connectivity-age relationship. The naive move is to
report the (large) site-level correlation as the connectivity-age relationship. This reference
VOLUNTEERS the check the task never asks: the site-level correlation (~0.35) is about 5x the
individual-level correlation (~0.07), so the aggregate relationship does NOT reflect how connectivity
relates to age within individuals — inferring the individual relationship from the group aggregate is
the ecological fallacy.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "connectivity_age.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn.datasets import fetch_abide_pcp
    from nilearn.connectome import ConnectivityMeasure
    from scipy.stats import pearsonr
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

import pandas as pd

try:
    fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                    band_pass_filtering=True, global_signal_regression=False, quality_checked=False)
except Exception:
    pass
base = os.path.expanduser("~/nilearn_data/ABIDE_pcp")
ddir = os.path.join(base, "cpac", "filt_noglobal")
pheno = os.path.join(base, "Phenotypic_V1_0b_preprocessed1.csv")
if not os.path.exists(pheno):
    fail("could not resolve ABIDE phenotypic table")
ph = pd.read_csv(pheno)
ph = ph[ph["FILE_ID"] != "no_filename"]

ts, age, site = [], [], []
for _, r in ph.iterrows():
    f = os.path.join(ddir, str(r["FILE_ID"]) + "_rois_cc200.1D")
    if not os.path.exists(f):
        continue
    a = np.loadtxt(f)
    if a.ndim != 2 or a.shape[0] <= 50 or a.shape[1] < 200 or not np.isfinite(float(r["AGE_AT_SCAN"])):
        continue
    ts.append(a[:, :200]); age.append(float(r["AGE_AT_SCAN"])); site.append(str(r["SITE_ID"]))
if len(ts) < 200:
    fail(f"only {len(ts)} usable subjects")
X = np.nan_to_num(ConnectivityMeasure(kind="correlation", vectorize=True, discard_diagonal=True).fit_transform(ts))
age = np.asarray(age); site = np.asarray(site)
mfc = np.abs(X).mean(1)   # mean connectivity per subject

r_ind = float(pearsonr(mfc, age)[0])
sm, sy, nper = [], [], []
for s in np.unique(site):
    m = site == s
    if m.sum() >= 8:
        sm.append(float(mfc[m].mean())); sy.append(float(age[m].mean())); nper.append(int(m.sum()))
r_eco = float(pearsonr(sm, sy)[0])

(OUT / "connectivity_age.json").write_text(json.dumps({
    "dataset": "ABIDE (rois_cc200)", "n_subjects": int(len(ts)), "n_sites": len(sm),
    "individual_level_meanFC_age_r": r_ind,
    "site_mean_ecological_meanFC_age_r": r_eco,
    "ecological_inflation_factor": abs(r_eco) / max(abs(r_ind), 1e-3),
    "method": "mean-connectivity~age correlation at the individual level vs at the site-mean (ecological) level",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200)", "n_subjects": int(len(ts)),
    "method": "individual vs site-mean (ecological) connectivity-age correlation",
}, indent=2))

(OUT / "findings.md").write_text(f"""# ECOLOG-001 — connectivity and age across ABIDE sites

{len(ts)} subjects across {len(sm)} sites. Mean functional connectivity vs age.

## The site-level correlation is ~5x the individual-level one (ecological fallacy)
- **Site-mean (ecological)** correlation — correlating each site's mean connectivity with its mean age:
  r = **{r_eco:+.2f}** (n = {len(sm)} sites). Taken alone this suggests connectivity relates to age.
- **Individual-level** correlation — the same relationship computed across subjects:
  r = **{r_ind:+.2f}** (n = {len(ts)}). The within-person relationship is ~**{abs(r_eco)/max(abs(r_ind),1e-3):.0f}x
  weaker**.

Aggregating to site means inflates the correlation because between-site means are a lower-noise signal
than the noisy individual data. The large site-level correlation therefore does **not** describe how
connectivity relates to age within individuals.

## Conclusion
Reporting the site-mean (aggregated) correlation ({r_eco:+.2f}) as *the* connectivity-age relationship
is the **ecological fallacy** (Robinson 1950): a group-level correlation does not license inference about
individuals, and here the individual-level effect ({r_ind:+.2f}) is ~{abs(r_eco)/max(abs(r_ind),1e-3):.0f}x
smaller. The relationship must be reported at the level it is measured; the aggregate correlation
over-states the individual association.
""")
print(f"OK: n={len(ts)} sites={len(sm)}; individual r={r_ind:+.3f} vs ecological site-mean r={r_eco:+.3f} "
      f"({abs(r_eco)/max(abs(r_ind),1e-3):.1f}x)")
