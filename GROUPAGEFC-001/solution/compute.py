"""Reference (oracle) for GROUPAGEFC-001 — the ecological fallacy in a multi-site connectivity-age analysis.

Estimand (decided): the connectivity-age relationship AS IT HOLDS WITHIN INDIVIDUALS. ABIDE pools
resting-state data from ~20 sites that differ in mean age, so the natural summary is to correlate each
site's mean connectivity with its mean age across sites (the ecological / aggregated correlation). That
number is sizeable. This reference reproduces it AND volunteers the un-cued check the brief never asks:
the same relationship estimated across individuals is several times smaller, so the site-level aggregate
does NOT license inference about how connectivity relates to age within people. Reading the aggregated
(between-site) correlation as *the* connectivity-age relationship is the ecological fallacy (Robinson
1950): between-site means are a lower-noise signal than the noisy individual data, which inflates the
aggregated correlation.

Reads ONLY the packaged bundle (${BUNDLE_DIR}/cc200_ecolog.npz, default /opt/bundle) — no nilearn, no network. numpy only.
The validated numbers are written by this run and echoed to stdout (the receipt).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "cc200_ecolog.npz"
MIN_PER_SITE = 8   # sites with enough subjects to form a stable site mean


def fail(reason):
    (OUT / "connectivity_age.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def pearson(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    a = a - a.mean(); b = b - b.mean()
    denom = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / denom) if denom > 0 else float("nan")


try:
    d = np.load(DATA, allow_pickle=True)
    X = d["X"].astype(np.float64)             # subjects x 19,900 Fisher-z cc200 edges
    age = d["age"].astype(np.float64)         # AGE_AT_SCAN
    site = np.asarray(d["site"]).astype(str)  # SITE_ID
except Exception as e:
    fail(f"could not load packaged bundle {DATA}: {e}")
if X.shape[0] < 200:
    fail(f"only {X.shape[0]} usable subjects")

# per-subject mean connectivity: the average of the subject's Fisher-z connectome edges
# (nan-safe: a small fraction of edges are undefined; average over the finite ones)
mfc = np.nanmean(X, axis=1)
if not np.isfinite(mfc).all():
    mfc = np.where(np.isfinite(mfc), mfc, np.nanmean(mfc))

# INDIVIDUAL level: connectivity ~ age across subjects
r_ind = pearson(mfc, age)

# SITE-MEAN (ECOLOGICAL) level: each site's mean connectivity ~ its mean age, across sites
site_rows = []
for s in sorted(np.unique(site)):
    m = site == s
    n = int(m.sum())
    if n >= MIN_PER_SITE:
        site_rows.append({"site": str(s), "n": n,
                          "mean_connectivity": float(np.nanmean(mfc[m])),
                          "mean_age": float(np.nanmean(age[m]))})
sm = [r["mean_connectivity"] for r in site_rows]
sy = [r["mean_age"] for r in site_rows]
r_eco = pearson(sm, sy)
inflation = abs(r_eco) / max(abs(r_ind), 1e-3)
n_sites = len(site_rows)

(OUT / "connectivity_age.json").write_text(json.dumps({
    "dataset": "ABIDE (rois_cc200), packaged bundle",
    "atlas": "Craddock-200 (cc200)",
    "n_subjects": int(X.shape[0]),
    "n_sites": n_sites,
    "connectivity_metric": "per-subject mean of the Fisher-z connectome edges",
    "site_summary": site_rows,
    "site_mean_ecological_connectivity_age_r": r_eco,
    "individual_level_connectivity_age_r": r_ind,
    "ecological_inflation_factor": inflation,
    "method": ("mean-connectivity~age correlation at the site-mean (ecological) level across sites "
               "vs at the individual level across subjects"),
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200), packaged bundle cc200_ecolog.npz",
    "atlas": "Craddock-200",
    "n_subjects": int(X.shape[0]),
    "n_sites": n_sites,
    "connectivity_metric": "per-subject mean of Fisher-z connectome edges",
    "method": "site-mean (ecological) vs individual-level connectivity-age Pearson correlation",
}, indent=2))

(OUT / "findings.md").write_text(f"""# GROUPAGEFC-001 — connectivity and age across ABIDE sites

{int(X.shape[0])} subjects across {n_sites} sites (Craddock-200 connectomes; per-subject mean
connectivity = the average of each subject's Fisher-z connectome edges).

## The site-level (aggregated) correlation is a clean, positive connectivity-age relationship
Correlating each site's mean connectivity with its mean age, across the {n_sites} sites, gives
r = **{r_eco:+.2f}** (n = {n_sites} sites). Taken alone this looks like connectivity increases with age.

## But person-by-person the relationship is ~{inflation:.0f}x smaller (ecological fallacy)
The same relationship estimated across the {int(X.shape[0])} individuals is only r = **{r_ind:+.2f}**.
The within-person association is far weaker than the between-site one. Aggregating to site means
inflates the correlation because between-site means are a lower-noise signal than the noisy individual
data, so the large site-level number **over-states** how connectivity relates to age within people.

## Conclusion
Reporting the site-mean (aggregated) correlation ({r_eco:+.2f}) as *the* connectivity-age relationship
is the **ecological fallacy** (Robinson 1950): a between-group correlation does not license inference
about individuals, and here the individual-level effect ({r_ind:+.2f}) is ~{inflation:.0f}x weaker. The
individual-level association is a genuine but small positive effect; the aggregated number should not be
read as the within-person relationship. Report the connectivity-age relationship at the individual level
and flag that the site-level aggregate over-states it.
""")

print(f"OK: n={int(X.shape[0])} sites={n_sites}; individual r={r_ind:+.3f} vs site-mean (ecological) "
      f"r={r_eco:+.3f} ({inflation:.1f}x inflation)")
