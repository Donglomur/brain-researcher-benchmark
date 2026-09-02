"""Grading checks for FACEERP-001 (ERP CORE N170 face-minus-car peak amplitude at PO8).

Ground truth (validated before release on the ERP CORE N170 files, subjects 1-12, filter
0.1-30 Hz, epochs -200..400 ms, -200..0 baseline, 150 uV rejection; per-subject peak =
most negative PO8 face-minus-car value in 110-150 ms, then mean over subjects):

    average-reference (correct ERP CORE convention) : -6.17 uV   <-- EXPECTED (|.| = 6.17)
    P9/P10 linked-mastoid reference (naive)          : -3.15 uV   (|.| = 3.15)

The ERP CORE N170 dataset is referenced to the average of the scalp electrodes, which
preserves the occipito-temporal N170 as a genuine negativity at PO8. A linked-mastoid
reference sits beside the N170 generators and roughly halves the measured amplitude
(and inverts the absolute face N170), giving a materially smaller number. 12/12 subjects
show the same direction (paired t = -6.6, p = 4e-5). The verifier matches the magnitude
of the average-reference amplitude; the linked-mastoid answer is ~3 uV away and fails.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED_ABS = 6.17    # |average-reference N170 peak amplitude| in uV
TOL = 1.5              # fails the linked-mastoid magnitude (3.15, i.e. ~3.0 away)


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _find_amplitude(obj):
    """Recursively find the reported N170 amplitude: a numeric leaf under an
    amplitude/N170/peak-ish key with a plausible microvolt magnitude."""
    stack = [("", obj)]
    while stack:
        key, cur = stack.pop()
        if isinstance(cur, dict):
            stack.extend(cur.items())
        elif isinstance(cur, (list, tuple)):
            stack.extend(("", x) for x in cur)
        elif isinstance(cur, (int, float)) and not isinstance(cur, bool):
            k = key.lower()
            if re.search(r"amp|n170|peak|uv|microvolt", k) and 0.3 <= abs(float(cur)) <= 20.0:
                return float(cur)
    return None


def test_n170_amplitude_reproduced():
    # The average-reference N170 peak amplitude at PO8 is -6.17 uV. A linked-mastoid
    # reference roughly halves it (-3.15 uV), landing ~3 uV outside the tolerance.
    # Compared on magnitude, so it is robust to whether the sign is reported.
    data = _load("n170.json")
    amp = _find_amplitude(data)
    assert amp is not None, f"no N170 amplitude found in n170.json: {data}"
    assert abs(abs(amp) - EXPECTED_ABS) < TOL, (
        f"N170 peak amplitude {amp:.2f} uV does not match the average-reference value "
        f"-6.17 uV (|.|={EXPECTED_ABS}, tol {TOL}). A linked-mastoid reference gives "
        f"~-3.2 uV, roughly half the amplitude.")


def test_findings_report():
    # light honesty check: the write-up reports an N170 amplitude for PO8 consistent
    # with the number in n170.json.
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert "po8" in text and ("n170" in text or "amplitude" in text), \
        "findings.md does not report an N170 amplitude at PO8"
    amp = _find_amplitude(_load("n170.json"))
    nums = [abs(float(x)) for x in re.findall(r"-?\d+\.\d+", text)]
    assert any(abs(n - abs(amp)) < 0.5 for n in nums), \
        "findings.md does not report an amplitude consistent with n170.json"
