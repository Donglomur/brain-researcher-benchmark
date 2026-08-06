"""Reference (oracle) for CIRCROI-001 — circular analysis / double dipping in a structural VBM contrast.

Paper anchor: Kriegeskorte et al. 2009, Nature Neuroscience (10.1038/nn.2303, "Circular analysis in
systems neuroscience: the dangers of double dipping"); Vul et al. 2009 (non-independence). Localizing a
region by the very contrast you then test — on the SAME subjects — is non-independent ("circular"): the
selection guarantees an inflated, often "significant" effect even when there is none.

The task (un-cued) asks whether there are localized sex differences in gray matter beyond overall head
size: localize the region with the largest sex difference (after controlling for eTIV) and report its
significance. The naive move is to test the selected region on the same subjects. This reference
VOLUNTEERS the check the task never asks: that test is circular. After head-size control the overall
sex difference is ~null, yet the circular region is "significant" (p ~ 4e-4); under a permuted/random
grouping the circular procedure returns p<0.05 ~89% of the time (nominal 5%) — pure selection bias. An
honest split-half (select on one half, test on the other) shows no reliable localized sex difference.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "roi.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
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
sex = np.array([str(s).strip().upper() for s in ev[cols.get("mf")]])
etiv = pd.to_numeric(ev[cols.get("etiv", cols.get("tiv"))], errors="coerce").values.astype(float)

masker = NiftiMasker(mask_strategy="epi", standardize=False, detrend=False)
X = masker.fit_transform(o.gray_matter_maps)
v = X.var(0)
X = X[:, v > np.percentile(v, 50)]
ok = np.isfinite(etiv) & ((sex == "M") | (sex == "F"))
X, male, etiv = X[ok], (sex[ok] == "M").astype(int), etiv[ok]
n, V = X.shape
if n < 80:
    fail(f"too few subjects ({n})")

# remove head size (eTIV) from every voxel, then look for localized sex differences
d = etiv - etiv.mean()
Xr = X - np.outer(d, (d @ X) / (d @ d))
rng = np.random.default_rng(0)
K = 200


def circular_p(g):
    t, _ = stats.ttest_ind(Xr[g == 1], Xr[g == 0], axis=0)
    top = np.argsort(np.abs(np.nan_to_num(t)))[-K:]           # SELECT peak-difference region (all subjects)
    return float(stats.ttest_ind(Xr[g == 1][:, top].mean(1), Xr[g == 0][:, top].mean(1))[1])  # TEST same subjects


def honest_p(g):
    idx = rng.permutation(n); h1, h2 = idx[:n // 2], idx[n // 2:]
    t, _ = stats.ttest_ind(Xr[h1][g[h1] == 1], Xr[h1][g[h1] == 0], axis=0)   # select on half 1
    top = np.argsort(np.abs(np.nan_to_num(t)))[-K:]
    a, b = Xr[h2][g[h2] == 1][:, top].mean(1), Xr[h2][g[h2] == 0][:, top].mean(1)  # test on half 2
    if len(a) < 3 or len(b) < 3:
        return 1.0
    return float(stats.ttest_ind(a, b)[1])


p_circular = circular_p(male)
p_honest = float(np.median([honest_p(male) for _ in range(20)]))

# NULL: permuted/random grouping -> false-positive rate of the circular procedure
null_sig = sum(circular_p(rng.integers(0, 2, n)) < 0.05 for _ in range(150))
null_fpr = float(null_sig / 150)

(OUT / "roi.json").write_text(json.dumps({
    "dataset": "OASIS VBM (gray-matter maps)", "n_subjects": int(n), "n_voxels": int(V), "roi_size_voxels": K,
    "circular_region_sex_pvalue": p_circular,
    "honest_splithalf_sex_pvalue_median": p_honest,
    "circular_null_false_positive_rate": null_fpr,
    "method": "GM residualized on eTIV; peak sex-difference ROI tested on same subjects (circular) vs "
              "split-half (honest) vs permuted-grouping null",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "OASIS VBM (oasis1)", "n_subjects": int(n),
    "method": "circular vs split-half vs permuted-null localized sex-difference test (eTIV-controlled)",
}, indent=2))

(OUT / "findings.md").write_text(f"""# CIRCROI-001 — localized sex differences in gray matter (OASIS VBM)

{n} subjects; gray matter residualized on eTIV (head size). We localize the {K}-voxel region with the
largest sex difference and test it.

## The "significant" localized sex difference is circular
- **Circular** test (localize the peak sex-difference region and test it on the **same** subjects):
  **p = {p_circular:.1e}** — apparently a significant localized sex difference.
- **Honest** split-half test (localize on one half, test on the other): median **p = {p_honest:.2f}** —
  no reliable difference.
- **Permuted-grouping null** (labels shuffled, no true difference): the circular procedure returns
  p < 0.05 in **{null_fpr*100:.0f}%** of runs — nominal should be 5%.

After controlling for head size the overall sex difference is ~null, yet the circular procedure
manufactures a "significant" regional effect, because the region was chosen *because* it differed and
then tested on the same data.

## Conclusion
Localizing a region by a contrast and testing that contrast in the **same** subjects is **circular /
double dipping** (Kriegeskorte 2009; Vul 2009): it fabricates significance ({null_fpr*100:.0f}% of the
time under the null). There is **no reliable localized sex difference** here — the honest split-half is
non-significant. Region strength must be estimated on **independent** data (split-half / cross-
validation) or with a permutation null; the circular p-value over-states the evidence.
""")
print(f"OK: n={n}; circular p={p_circular:.1e} vs honest split-half p={p_honest:.2f}; null FPR={null_fpr:.2f}")
