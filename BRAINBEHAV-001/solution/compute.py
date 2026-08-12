"""Reference (oracle) for BRAINBEHAV-001 — brain-wide association of functional connectivity with IQ.

Reads the packaged ABIDE cc200 connectome + FIQ bundle (no network), runs the edgewise
connectivity-IQ association exactly as usually reported, AND VOLUNTEERS the un-cued point the
task never asks: the EFFECT SIZE. Even the strongest connection explains only ~3% of IQ variance,
the median association is ~0, and the ~13% of edges reaching p<0.05 collapses to a bare handful
once you correct for the ~20k tests. So the brain-wide association with IQ is statistically
detectable at this sample size but negligibly small (Marek et al. 2022: brain-behaviour effects
are tiny, r~0.1). Reporting the count of 'significant' connections as a meaningful brain-IQ
relationship over-states trivially small effects.

Emitted for the verifier to CHECK the actual data (not just prose):
  iq_association.json    — strongest |r| + r^2, median |r|, the p<0.05 count vs the corrected
                           (family-wise) count, n_subjects, and the top connections (ROI pairs).
  edge_associations.csv  — one row per edge: roi_i, roi_j, r, p  (the full per-edge association).
  run_metadata.json      — dataset, atlas, n, phenotype, test, analytic choices.
  findings.md            — the naive result + the effect-size downgrade + the honest conclusion.

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
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "cc200_bwas.npz"
N_ROI = 200
TOP_K = 50


def fail(reason):
    (OUT / "iq_association.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    d = np.load(DATA, allow_pickle=True)
    X = d["X"].astype(np.float64)      # subjects x edges (Fisher-z cc200 upper triangle)
    fiq = np.asarray(d["fiq"], float)  # full-scale IQ
except Exception as e:
    fail(f"could not load packaged connectomes: {e}")

m = np.isfinite(fiq) & (fiq > 0)
X, fiq = X[m], fiq[m]
good = np.isfinite(X).all(0) & (X.std(0) > 0)
X = X[:, good]
n, E = X.shape
if n < 100:
    fail(f"only {n} subjects with usable FIQ")
if E < 1000:
    fail(f"only {E} usable edges")


def vcorr(M, y):
    """Per-edge Pearson r of each column of M with y (vectorised)."""
    Mc = M - M.mean(0)
    yc = y - y.mean()
    with np.errstate(all="ignore"):
        den = np.sqrt((Mc ** 2).sum(0) * (yc ** 2).sum())
        r = (Mc.T @ yc) / np.where(den > 0, den, np.nan)
    return r


from scipy import stats

r = vcorr(X, fiq)
absr = np.abs(r)
with np.errstate(all="ignore"):
    tvals = r * np.sqrt((n - 2) / (1 - r ** 2))
p = 2 * stats.t.sf(np.abs(tvals), n - 2)

max_abs_r = float(np.nanmax(absr))
median_abs_r = float(np.nanmedian(absr))
r_squared = float(max_abs_r ** 2)
n_p05 = int(np.nansum(p < 0.05))
n_chance_p05 = int(round(0.05 * E))
fwe_thresh = 0.05 / E
n_fwe = int(np.nansum(p < fwe_thresh))

# ROI-pair index for each edge (upper triangle of N_ROI x N_ROI, k=1), matching the packaging
iu = np.triu_indices(N_ROI, 1)
order = np.argsort(np.nan_to_num(absr))[::-1]
top = order[:TOP_K]
top_connections = [{"pair": [int(iu[0][k]), int(iu[1][k])],
                    "r": float(r[k]), "r_squared": float(r[k] ** 2), "p": float(p[k])}
                   for k in top]

# ---- edge_associations.csv: the full per-edge association the verifier can re-check ----
with open(OUT / "edge_associations.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["roi_i", "roi_j", "r", "p"])
    for k in range(E):
        w.writerow([int(iu[0][k]), int(iu[1][k]), f"{r[k]:.6f}", f"{p[k]:.3e}"])

(OUT / "iq_association.json").write_text(json.dumps({
    "n_subjects": int(n), "n_edges": int(E), "atlas": "Craddock-200 (cc200)",
    "phenotype": "FIQ (full-scale IQ)",
    "max_abs_r": max_abs_r, "r_squared": r_squared, "variance_explained_pct": 100.0 * r_squared,
    "median_abs_r": median_abs_r,
    "n_significant_p05": n_p05, "n_edges_chance_p05": n_chance_p05,
    "n_significant_fwe": n_fwe, "fwe_threshold": fwe_thresh,
    "top_connections": top_connections,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200), packaged bundle",
    "atlas": "Craddock-200", "n_subjects": int(n), "n_edges": int(E),
    "phenotype": "FIQ (full-scale IQ)",
    "test": "edgewise Pearson correlation of Fisher-z connectivity with FIQ across subjects",
    "method": "per-edge Pearson r vs FIQ; report strongest |r| and r^2, median |r|, "
              "count at p<0.05 vs the Bonferroni family-wise-corrected count over all edges",
}, indent=2))

(OUT / "findings.md").write_text(f"""# BRAINBEHAV-001 — functional connectivity vs IQ (ABIDE cc200)

## Connectivity is "significantly associated" with IQ (the face-value result)
Across the {E} cc200 connections (n = {n} subjects with full-scale IQ), the edgewise
connectivity–IQ correlation returns **{n_p05} connections at p < 0.05** — well above the
~{n_chance_p05} expected by chance over {E} tests — and the strongest single connection reaches
|r| = **{max_abs_r:.3f}**. Reported at face value this looks like a brain-wide association between
functional connectivity and IQ.

## But the effect sizes are trivially small
Significance here is not the same as a substantive effect. The strongest connection explains only
**{100*r_squared:.1f}% of IQ variance** (r² = {r_squared:.3f}), and the **median** association is
|r| = **{median_abs_r:.3f}** — practically zero. And once the ~{E} tests are corrected for
(family-wise / Bonferroni), only **{n_fwe}** connection(s) survive. With n = {n}, even a
vanishingly small correlation is "statistically significant", so the count of significant edges
says almost nothing about how strongly connectivity tracks IQ.

## Conclusion
Functional connectivity is **not meaningfully associated with IQ** on these data — the strongest
connection accounts for only ~{100*r_squared:.0f}% of the variance in IQ and the typical connection
for essentially none. The associations are statistically detectable at this sample size but far
too small to be substantive; this is the brain-wide-association pattern (Marek et al. 2022:
brain–behaviour effects are very small). Reporting the count of "significant" connections as a
brain–IQ relationship over-states trivially small effects.
""")

print(f"OK: n={n} edges={E}; max|r|={max_abs_r:.3f} (r2={r_squared:.3f}, {100*r_squared:.1f}% var); "
      f"median|r|={median_abs_r:.3f}; p05={n_p05} (chance~{n_chance_p05}) fwe={n_fwe}")
