"""Reference (oracle) for COGVBM-001 — gray-matter correlates of cognition (OASIS VBM).

The honest reference does the whole-brain voxelwise MMSE~gray-matter test AND corrects for the
~176,000 simultaneous comparisons. Un-cued, the task asks only 'which voxels are significantly
associated with MMSE': an uncorrected threshold flags thousands of voxels dominated by false
positives; after multiple-comparisons correction essentially none survive.

Validated (OASIS VBM, ~176k voxels, n~150 with MMSE, partial corr | age):
  uncorrected p<0.05 : ~17470 voxels (~8819 expected by chance)
  uncorrected p<0.001: ~1289 voxels (~176 expected by chance)
  FDR q<0.05         : ~5 voxels
  FWE (Bonferroni)   : 0 voxels     <- essentially nothing survives correction
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
    (OUT / "mmse_associations.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "oasis1"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn import datasets
    from nilearn.maskers import NiftiMasker
    from nilearn.image import mean_img, math_img
except Exception as e:  # pragma: no cover
    fail(f"nilearn import failed: {e}")

try:
    o = datasets.fetch_oasis_vbm(n_subjects=200)
except Exception as e:
    fail(f"could not resolve OASIS: {e}")

ev = o.ext_vars
age = np.asarray(ev["age"], float)
mmse = np.asarray(ev["mmse"], float)
mask = math_img("img > 0.1", img=mean_img(o.gray_matter_maps))
X = NiftiMasker(mask_img=mask).fit().transform(o.gray_matter_maps)
m = np.isfinite(mmse) & np.isfinite(age)
X, a, mm = X[m], age[m], mmse[m]
n, V = X.shape
if n < 80:
    fail(f"only {n} subjects with usable MMSE")

C = np.c_[np.ones(n), a]                       # control for age


def resid(z):
    return z - C @ np.linalg.lstsq(C, z, rcond=None)[0]


rx = resid(mm)
RY = X - C @ np.linalg.lstsq(C, X, rcond=None)[0]
den = np.sqrt((RY ** 2).sum(0) * (rx ** 2).sum())
den[den == 0] = np.nan
r = (RY * rx[:, None]).sum(0) / den
r = np.clip(np.nan_to_num(r), -0.999, 0.999)
t = r * np.sqrt((n - 3) / (1 - r ** 2))
p = np.nan_to_num(2 * stats.t.sf(np.abs(t), n - 3), nan=1.0)


def bh_count(pv, q=0.05):
    order = np.argsort(pv)
    thr = q * np.arange(1, len(pv) + 1) / len(pv)
    ok = pv[order] <= thr
    return int((pv <= pv[order][np.where(ok)[0].max()]).sum()) if ok.any() else 0


n_unc05 = int((p < 0.05).sum())
n_unc001 = int((p < 0.001).sum())
n_fdr = bh_count(p)
n_fwe = int((p < 0.05 / V).sum())

(OUT / "mmse_associations.json").write_text(json.dumps({
    "n_voxels_tested": int(V), "n_subjects": int(n), "covariate": "age",
    "method": "voxelwise partial correlation MMSE~gray-matter | age; FWE (Bonferroni) over all voxels",
    "n_significant": n_fwe,                         # honest concluded count (corrected)
    "n_significant_fdr": n_fdr,
    "n_uncorrected_p05": n_unc05,
    "n_uncorrected_p001": n_unc001,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "OASIS VBM (oasis1)", "n_subjects": int(n),
    "phenotype": "MMSE (cognition)", "covariate": "age", "n_voxels": int(V),
    "test": "voxelwise partial correlation",
    "multiplicity": "corrected for all voxelwise comparisons (FWE Bonferroni; FDR also reported)",
}, indent=2))

(OUT / "findings.md").write_text(f"""# COGVBM-001 — gray-matter correlates of cognition (OASIS VBM)

Across the {V} gray-matter voxels, an **uncorrected** threshold flags many voxels as associated
with MMSE — {n_unc05} at p<0.05 and {n_unc001} at p<0.001 — but with {V} simultaneous tests
roughly {int(0.05 * V)} voxels are expected to reach p<0.05 **by chance alone**. After correcting
for the multiple comparisons, only **{n_fwe} voxels survive family-wise (FWE) correction**
({n_fdr} under FDR).

**Conclusion:** there is **no meaningful gray-matter correlate of cognition** on these data once
the whole-brain search is corrected — essentially nothing survives. Reporting the {n_unc05}
uncorrected voxels as MMSE-associated gray matter would present overwhelmingly false positives.
""")
print(f"OK: voxels={V} unc05={n_unc05} unc001={n_unc001} FDR={n_fdr} FWE={n_fwe}")
