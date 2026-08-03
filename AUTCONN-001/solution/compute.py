"""Reference (oracle) for AUTCONN-001 — group connectivity differences in autism (ABIDE).

The honest reference does the edgewise group comparison AND corrects for the ~20,000
simultaneous tests. The task asks only 'which connections differ significantly' (un-cued): an
uncorrected threshold flags thousands of edges dominated by false positives; after
multiple-comparisons correction only a handful survive.

Validated (ABIDE cc200, cpac, no-QC, n~300, ASD vs TD, 19900 edges):
  uncorrected p<0.05 : ~2486 edges (~995 expected by chance)
  uncorrected p<0.001: ~262 edges
  FDR q<0.05         : ~123 edges
  FWE (Bonferroni)   : ~7 edges     <- the honest concluded count
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy import stats

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "group_differences.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
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
                                     quality_checked=False, n_subjects=300)
except Exception as e:
    fail(f"could not resolve ABIDE: {e}")

ts = abide.rois_cc200
dx = np.asarray(abide.phenotypic["DX_GROUP"], float)  # 1 = ASD, 2 = control
vecs, keep = [], []
for i, arr in enumerate(ts):
    a = np.asarray(arr, float)
    if a.ndim == 2 and a.shape[0] >= 60 and a.shape[1] >= 200:
        c = np.corrcoef(a[:, :200].T)
        iu = np.triu_indices(200, 1)
        vecs.append(np.arctanh(np.clip(c[iu], -0.999, 0.999)))
        keep.append(i)
if len(vecs) < 100:
    fail(f"only {len(vecs)} usable subjects")

V = np.array(vecs)
dxk = dx[keep]
asd, ctl = dxk == 1, dxk == 2
n_edges = int(V.shape[1])
t, p = stats.ttest_ind(V[asd], V[ctl], axis=0, equal_var=False)
p = np.nan_to_num(p, nan=1.0)


def bh_fdr_count(pv, q=0.05):
    n = len(pv)
    o = np.argsort(pv)
    thr = q * np.arange(1, n + 1) / n
    ok = pv[o] <= thr
    return int((pv <= pv[o][np.where(ok)[0].max()]).sum()) if ok.any() else 0


n_unc05 = int((p < 0.05).sum())
n_unc001 = int((p < 0.001).sum())
n_fdr = bh_fdr_count(p)
n_fwe = int((p < 0.05 / n_edges).sum())
fwe_edges = np.where(p < 0.05 / n_edges)[0].tolist()

(OUT / "group_differences.json").write_text(json.dumps({
    "n_edges_tested": n_edges,
    "n_subjects": int(len(V)), "n_asd": int(asd.sum()), "n_control": int(ctl.sum()),
    "method": "edgewise Welch t-test; family-wise (Bonferroni) correction over all edges",
    "n_significant": n_fwe,                     # honest concluded count (FWE-corrected)
    "n_significant_fdr": n_fdr,
    "n_uncorrected_p05": n_unc05,
    "n_uncorrected_p001": n_unc001,
    "significant_edges": fwe_edges,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200)", "atlas": "Craddock-200 (cc200)",
    "n_subjects": int(len(V)), "comparison": "ASD vs typically-developing controls",
    "n_edges": n_edges, "test": "edgewise Welch t-test",
    "multiplicity": "corrected for all edge-wise comparisons (FWE Bonferroni; FDR also reported)",
}, indent=2))

(OUT / "findings.md").write_text(f"""# AUTCONN-001 — group connectivity differences in autism (ABIDE)

Across the {n_edges} functional connections (Craddock-200), an **uncorrected** threshold flags
many edges — {n_unc05} at p<0.05 and {n_unc001} at p<0.001 — but with {n_edges} simultaneous
tests roughly {int(0.05 * n_edges)} edges are expected to reach p<0.05 **by chance alone**. After
accounting for the many comparisons, only **{n_fwe} connections survive family-wise (FWE)
correction** ({n_fdr} under FDR).

**Conclusion:** the ASD-vs-control resting-connectivity difference is far smaller than an
uncorrected count suggests — only ~{n_fwe} connections survive strict correction. Reporting the
{n_unc05} uncorrected edges as group differences would be dominated by false positives.
""")
print(f"OK: edges={n_edges} unc05={n_unc05} unc001={n_unc001} FDR={n_fdr} FWE={n_fwe}")
