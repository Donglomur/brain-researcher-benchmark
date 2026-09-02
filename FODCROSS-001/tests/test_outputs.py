"""Grading checks for FODCROSS-001 (crossing-fibre fraction in the centrum semiovale).

Ground truth (validated before release on dipy's multi-shell sherbrooke_3shell, ROI box
[45:83, 45:90, 31:36] & brain-mask & 0.30<FA<0.90 = 5060 voxels; peaks_from_model
relative_peak_threshold=0.5, min_separation_angle=25 deg, npeaks=3, sh_order_max=8):

    MSMT-CSD  (correct multi-shell estimator)  : crossing_fraction = 0.349   <-- EXPECTED
    single-shell CSD, all mixed shells         : crossing_fraction = 0.484
    single-shell CSD, b=1000 only              : crossing_fraction = 0.457
    single-shell CSD, b=3500 only              : crossing_fraction = 0.696

The acquisition is genuinely multi-shell, so the correct fODF estimator is multi-shell
multi-tissue CSD, which models WM/GM/CSF jointly and suppresses the spurious fODF lobes
that single-tissue single-shell CSD produces from grey-matter / CSF partial volume.
Single-shell CSD OVER-detects crossings (0.46-0.70 depending on which shell), so any
single-shell answer lands >= 0.10 above the MSMT value. The verifier matches the MSMT
crossing fraction within tolerance; every single-shell answer falls outside it.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.349    # MSMT-CSD crossing fraction
TOL = 0.08          # fails every single-shell value (nearest is 0.457, i.e. 0.108 away)


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _find_fraction(obj):
    """Recursively find the reported crossing fraction: the numeric leaf whose key names
    a crossing fraction, else any float in [0, 1] under a 'cross'-ish key."""
    best = None
    stack = [("", obj)]
    while stack:
        key, cur = stack.pop()
        if isinstance(cur, dict):
            stack.extend(cur.items())
        elif isinstance(cur, (list, tuple)):
            stack.extend(("", x) for x in cur)
        elif isinstance(cur, (int, float)) and not isinstance(cur, bool):
            k = key.lower()
            if ("cross" in k or "fod" in k) and ("frac" in k or "prop" in k or "ratio" in k):
                if 0.0 <= float(cur) <= 1.0:
                    return float(cur)          # exact-intent match wins
            if "frac" in k and 0.0 <= float(cur) <= 1.0 and best is None:
                best = float(cur)
    return best


def test_crossing_fraction_reproduced():
    # The centrum-semiovale crossing fraction, estimated with the correct multi-shell
    # (MSMT) fODF model, is 0.349. A single-shell CSD answer is inflated by partial
    # volume and lands >= 0.10 higher, so it falls outside the tolerance.
    data = _load("crossing.json")
    frac = _find_fraction(data)
    assert frac is not None, f"no crossing fraction found in crossing.json: {data}"
    assert abs(frac - EXPECTED) < TOL, (
        f"crossing fraction {frac:.3f} does not match the MSMT value {EXPECTED:.3f} "
        f"(tol {TOL}). Single-shell CSD over-detects crossings from GM/CSF partial "
        f"volume (0.46-0.70); the multi-shell MSMT estimate is ~0.35.")


def test_findings_report():
    # light honesty check: the write-up reports a crossing fraction for the centrum
    # semiovale, and it is consistent with the number in crossing.json.
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert "crossing" in text or "cross" in text, "findings.md does not discuss crossings"
    frac = _find_fraction(_load("crossing.json"))
    nums = [float(x) for x in re.findall(r"0?\.\d+", text)]
    assert any(abs(n - frac) < 0.02 for n in nums), (
        "findings.md does not report a crossing fraction consistent with crossing.json")
