"""Grading checks for ERPP3-001 (ERP CORE P3b rare-minus-frequent amplitude at Pz).

Ground truth (validated before release on the ERP CORE P3 files, subjects 1-12, average
reference, 0.1-30 Hz, -200..0 baseline, epochs -200..800, all epochs averaged; rare =
codes 11/22/33/44/55, frequent = the other two-digit XY codes; rare-minus-frequent
difference wave at Pz, measured over 300-600 ms, per subject then mean over subjects):

    MEAN amplitude over the window (correct ERP CORE measure) : +4.43 uV   <-- EXPECTED
    PEAK amplitude in the window (naive)                      : +8.85 uV   (~2x)

The P3, like modern ERP practice, is quantified as the MEAN amplitude across a fixed
measurement window: it is unbiased by noise and trial count. PEAK amplitude always
latches onto the largest excursion in the window and is biased away from zero, here
roughly doubling the value. Everything except the mean-vs-peak measurement is pinned
(subjects, average reference, filter, baseline, epochs, rare/frequent codes, the Pz
channel, and the 300-600 ms window). 11/12 subjects show a positive rare-minus-frequent
P3b. The verifier matches the magnitude of the mean-amplitude value; the peak answer is
~4.4 uV away and fails. Compared on magnitude, so it is robust to whether the difference
is reported as rare-minus-frequent or frequent-minus-rare.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED_ABS = 4.43    # |mean-amplitude P3b at Pz, 300-600 ms| in uV
TOL = 2.0              # accept [2.43, 6.43]; fails the peak magnitude (~8.85, ~4.4 away)

# keys that do NOT denote the reported headline amplitude
_EXCLUDE = ("peak", "reference", "naive", "latency", "window", "_ms", "n_sub",
            "per_subject", "persubject", "sd", "std", "sem", "count")


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _headline_amplitude(obj):
    """The reported P3b amplitude: a numeric leaf under an amplitude-ish key with a
    plausible microvolt magnitude, skipping explicitly-labelled peak/reference fields."""
    stack = [("", obj)]
    while stack:
        key, cur = stack.pop()
        k = key.lower()
        if isinstance(cur, dict):
            stack.extend(cur.items())
        elif isinstance(cur, (list, tuple)):
            continue  # per-subject arrays etc. are not the headline
        elif isinstance(cur, (int, float)) and not isinstance(cur, bool):
            if any(x in k for x in _EXCLUDE):
                continue
            if re.search(r"amp|p3|uv|microvolt", k) and 0.3 <= abs(float(cur)) <= 20.0:
                return float(cur)
    return None


def test_p3b_reported():
    data = _load("p3.json")
    amp = _headline_amplitude(data)
    assert amp is not None, f"no P3b amplitude found in p3.json: {data}"
    assert int(data.get("n_subjects", 0)) >= 12 or "per_subject_mean_uv" in data, \
        "expected the amplitude to be aggregated over the 12 subjects"


def test_p3b_amplitude_is_mean_not_peak():
    # The mean-amplitude P3b at Pz (300-600 ms) is +4.43 uV. Reporting the PEAK amplitude
    # in the window instead roughly doubles it (~+8.85 uV), landing ~4.4 uV outside the
    # tolerance. Compared on magnitude, so robust to the difference-wave sign convention.
    data = _load("p3.json")
    amp = _headline_amplitude(data)
    assert amp is not None, f"no P3b amplitude found in p3.json: {data}"
    assert abs(abs(amp) - EXPECTED_ABS) < TOL, (
        f"P3b amplitude {amp:.2f} uV does not match the mean-amplitude value +4.43 uV "
        f"(|.|={EXPECTED_ABS}, tol {TOL}). Taking the peak (most extreme) value in the "
        f"300-600 ms window instead of the mean amplitude gives ~+8.85 uV, roughly "
        f"double.")


def test_findings_report():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert "pz" in text and ("p3" in text or "amplitude" in text), \
        "findings.md does not report a P3b amplitude at Pz"
    amp = _headline_amplitude(_load("p3.json"))
    nums = [abs(float(x)) for x in re.findall(r"-?\d+\.\d+", text)]
    assert any(abs(n - abs(amp)) < 0.5 for n in nums), \
        "findings.md does not report an amplitude consistent with p3.json"
