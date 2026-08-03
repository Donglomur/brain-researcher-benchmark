"""Reference (oracle) for BWAS-001 — functional connectivity vs IQ (ABIDE).

The honest reference computes the connectivity-IQ associations AND VOLUNTEERS the un-cued
point the task never asks: the EFFECT SIZE. Even the strongest connection explains only ~3% of
IQ variance, the median association is ~0.001, and nothing survives family-wise correction — so
the brain-wide association with IQ is statistically detectable but negligibly small (Marek et
al. 2022: brain-behaviour effects are tiny, r~0.1). Reporting the count of 'significant'
connections as a meaningful brain-IQ relationship over-states trivially small effects.

Validated (ABIDE cc200, cpac, no-QC, n~493 with FIQ, ~12k usable edges):
  strongest |connectivity-IQ r| : ~0.185  (r^2 ~ 0.034, i.e. ~3% of variance)
  median |r|                    : ~0.035
  edges p<0.05                  : ~1040  (~995 expected by chance over ~12k)
  edges surviving FWE           : 0
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "iq_association.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn import datasets
except Exception as e:  # pragma: no cover
    fail(f"nilearn import failed: {e}")

try:
    abide = datasets.fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                                     quality_checked=False, n_subjects=500)
except Exception as e:
    fail(f"could not resolve ABIDE: {e}")

fiq = np.asarray(abide.phenotypic["FIQ"], float)
V, keep = [], []
for i, arr in enumerate(abide.rois_cc200):
    a = np.asarray(arr, float)
    if a.ndim == 2 and a.shape[0] >= 60 and a.shape[1] >= 200:
        c = np.corrcoef(a[:, :200].T)
        iu = np.triu_indices(200, 1)
        V.append(np.arctanh(np.clip(c[iu], -0.999, 0.999)))
        keep.append(i)
V = np.array(V)
fiq = fiq[np.array(keep)]
m = np.isfinite(fiq) & (fiq > 0)
V, fiq = V[m], fiq[m]
good = np.isfinite(V).all(0) & (V.std(0) > 0)
V = V[:, good]
n, E = V.shape
if n < 100:
    fail(f"only {n} subjects with usable FIQ")


def vcorr(X, y):
    Xc = X - X.mean(0)
    yc = y - y.mean()
    den = np.sqrt((Xc ** 2).sum(0) * (yc ** 2).sum())
    den[den == 0] = np.nan
    return (Xc.T @ yc) / den


r = vcorr(V, fiq)
absr = np.abs(r)
from scipy import stats
tvals = r * np.sqrt((n - 2) / (1 - r ** 2))
p = 2 * stats.t.sf(np.abs(tvals), n - 2)
max_abs_r = float(np.nanmax(absr))
n_p05 = int(np.nansum(p < 0.05))
n_fwe = int(np.nansum(p < 0.05 / E))

(OUT / "iq_association.json").write_text(json.dumps({
    "n_subjects": int(n), "n_edges": int(E), "atlas": "Craddock-200 (cc200)",
    "max_abs_r": max_abs_r, "r_squared": float(max_abs_r ** 2),
    "median_abs_r": float(np.nanmedian(absr)),
    "n_significant_p05": n_p05, "n_edges_chance_p05": int(0.05 * E),
    "n_significant_fwe": n_fwe,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200)", "atlas": "Craddock-200",
    "n_subjects": int(n), "phenotype": "FIQ (full-scale IQ)", "test": "edgewise Pearson connectivity-IQ correlation",
}, indent=2))

(OUT / "findings.md").write_text(f"""# BWAS-001 — functional connectivity vs IQ (ABIDE)

## Associations are statistically detectable but negligibly small
Across the {E} connections, the connectivity–IQ associations are **trivially small**. The
**strongest** single connection has |r| = **{max_abs_r:.3f}** — explaining only
**{100*max_abs_r**2:.1f}% of IQ variance** — and the median association is
|r| = {np.nanmedian(absr):.3f} (essentially zero). Although {n_p05} connections reach p<0.05
(barely above the ~{int(0.05*E)} expected by chance over {E} tests), **{n_fwe} survive
family-wise correction**.

## Effect size, not just significance
With n = {n}, even a tiny correlation is "statistically significant", but the effect sizes here
are negligible: no connection explains more than ~{100*max_abs_r**2:.0f}% of IQ variance. This
is the brain-wide-association pattern (Marek et al. 2022): brain–behaviour effects are very
small.

## Conclusion
Functional connectivity is **not meaningfully associated with IQ** on these data — the effects
are statistically detectable at this sample size but far too small to be substantive. Reporting
the count of "significant" connections as a brain–IQ relationship over-states trivially small
effects.
""")
print(f"OK: n={n} edges={E}; max|r|={max_abs_r:.3f} (r2={max_abs_r**2:.3f}); p05={n_p05} fwe={n_fwe}")
