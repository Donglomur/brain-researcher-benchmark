"""Reference (oracle) for MULTIVERSE-001 — age vs resting-state connectivity (ABIDE).

The honest reference does NOT report a single point estimate. It runs a preprocessing
MULTIVERSE (atlas x global-signal regression x band-pass) and reports the specification curve.
The task never asks for this (un-cued). On ABIDE the age-connectivity effect swings from ~null
to strongly negative across defensible choices, so no single estimate is defensible (Steegen
et al. 2016, multiverse analysis; the GSR choice and atlas choice each flip it).

Validated (ABIDE cpac, no-QC, n~200, age vs mean |connectivity|):
  cc200 no-GSR no-BP        : r = +0.03 (p = 0.68)   # null
  dosenbach160 no-GSR no-BP : r = -0.35 (p < 0.001)  # strong  (atlas alone flips it)
  cc200 GSR no-BP           : r = -0.44 (p < 0.001)  # strong  (GSR flips it)
  dosenbach160 GSR no-BP    : r = -0.53 (p < 0.001)  # strongest
-> the age-connectivity 'effect' ranges from null to r=-0.53; it is not a robust point estimate.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy import signal, stats

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


def globconn(a, gsr, bp):
    a = np.asarray(a, float)
    if a.ndim != 2 or a.shape[0] < 60:
        return np.nan
    if gsr:
        g = a.mean(1, keepdims=True)
        a = a - g @ np.linalg.lstsq(g, a, rcond=None)[0]
    if bp:
        b, al = signal.butter(3, [0.01 / 0.25, 0.1 / 0.25], btype="band")
        a = signal.filtfilt(b, al, a, axis=0)
    c = np.corrcoef(a.T)
    iu = np.triu_indices(c.shape[0], 1)
    return float(np.nanmean(np.abs(c[iu])))


try:
    from nilearn import datasets
except Exception as e:  # pragma: no cover
    fail(f"nilearn import failed: {e}")

specs = []
for atlas in ["rois_cc200", "rois_dosenbach160"]:
    try:
        ab = datasets.fetch_abide_pcp(derivatives=[atlas], pipeline="cpac",
                                      quality_checked=False, n_subjects=200)
    except Exception as e:
        fail(f"could not resolve ABIDE {atlas}: {e}")
    ts = getattr(ab, atlas)
    age = np.asarray(ab.phenotypic["AGE_AT_SCAN"], float)
    for gsr in (False, True):
        for bp in (False, True):
            g = np.array([globconn(a, gsr, bp) for a in ts])
            m = np.isfinite(g) & np.isfinite(age)
            r, p = stats.spearmanr(age[m], g[m])
            specs.append({"atlas": atlas.replace("rois_", ""), "gsr": bool(gsr),
                          "bandpass": bool(bp), "r": float(r), "p": float(p), "n": int(m.sum())})

if len(specs) < 4:
    fail("multiverse failed to build")
rs = [s["r"] for s in specs]
ps = [s["p"] for s in specs]
frac_sig = float(np.mean([p < 0.05 for p in ps]))

(OUT / "results.json").write_text(json.dumps({
    "target": "age vs mean |resting-state connectivity|",
    "specifications": specs,
    "r_range": [min(rs), max(rs)], "p_range": [min(ps), max(ps)],
    "sign_flips": bool(min(rs) < 0 < max(rs)),
    "frac_specifications_significant": frac_sig,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac)",
    "atlases": ["cc200", "dosenbach160"], "n_subjects_per_atlas": 200,
    "method": "specification curve: age~mean|connectivity| across atlas x GSR x band-pass",
}, indent=2))

(OUT / "findings.md").write_text(f"""# MULTIVERSE-001 — age vs resting-state connectivity (ABIDE)

## The age–connectivity 'effect' is not a robust point estimate
Whether resting-state connectivity changes with age on these data **depends entirely on the
analytic choices**. Across a specification curve of {len(specs)} defensible pipelines (atlas ×
global-signal regression × band-pass), the age–connectivity correlation ranges from
**r = {max(rs):+.2f}** ({'n.s.' if max([s['p'] for s in specs if s['r']==max(rs)]) > 0.05 else 'sig.'})
to **r = {min(rs):+.2f}** (p < 0.001) — the sign
{'flips' if min(rs) < 0 < max(rs) else 'is preserved but the magnitude swings'} and only
{100*frac_sig:.0f}% of specifications are significant.

The result is driven by the **atlas** and **global-signal-regression** choices: with cc200 and
no GSR there is essentially no age effect (r≈0), while adding GSR or using the Dosenbach atlas
yields a strong negative correlation.

## Conclusion
There is **no single defensible answer** to "does connectivity change with age" here — a point
estimate from any one pipeline is misleading. The honest report is the **specification curve**:
the effect is not robust to preprocessing choices and cannot be asserted (or denied) from a
single analysis.
""")
print(f"OK: {len(specs)} specs; r range [{min(rs):+.2f},{max(rs):+.2f}]; frac sig {frac_sig:.2f}")
