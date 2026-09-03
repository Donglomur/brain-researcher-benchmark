"""Grading checks for MMN-001 (ERP CORE mismatch-negativity amplitude at FCz).

Ground truth (validated before release on the ERP CORE MMN files, subjects 1-12, P9/P10
mastoid reference, 0.1-30 Hz, -200..0 baseline, epochs -200..800, all epochs of each
condition averaged; standard = code 80, deviant = code 70; deviant-minus-standard
difference wave at FCz, measured over 125-225 ms, per subject then mean over subjects):

    MEAN amplitude over the window (correct ERP CORE measure) : -1.82 uV   <-- EXPECTED
    PEAK amplitude in the window (naive, most-negative)       : -3.53 uV   (~2x)

The MMN, like modern ERP practice, is quantified as the MEAN amplitude across a fixed
measurement window: it is unbiased by noise and trial count. PEAK amplitude always latches
onto the largest excursion in the window and is biased away from zero, here roughly
doubling the value. Everything except the mean-vs-peak measurement is pinned (subjects,
P9/P10 reference, filter, baseline, epochs, standard/deviant codes, the FCz channel, and
the 125-225 ms window). 11/12 subjects show a negative deviant-minus-standard MMN. The
verifier matches the magnitude of the mean-amplitude value; the peak answer is ~1.7 uV
away and fails. Compared on magnitude, so it is robust to whether the difference is
reported as deviant-minus-standard or standard-minus-deviant.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED_ABS = 1.82    # |mean-amplitude MMN at FCz, 125-225 ms| in uV
TOL = 0.8              # accept [1.02, 2.62]; fails the peak magnitude (~3.53, ~1.7 away)

# keys that do NOT denote the reported headline amplitude
_EXCLUDE = ("peak", "reference", "naive", "latency", "window", "_ms", "n_sub",
            "per_subject", "persubject", "sd", "std", "sem", "count")


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _headline_amplitude(obj):
    """The reported MMN amplitude: a numeric leaf under an amplitude-ish key with a
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
            if re.search(r"amp|mmn|uv|microvolt", k) and 0.3 <= abs(float(cur)) <= 12.0:
                return float(cur)
    return None


def test_mmn_reported():
    data = _load("mmn.json")
    amp = _headline_amplitude(data)
    assert amp is not None, f"no MMN amplitude found in mmn.json: {data}"
    assert int(data.get("n_subjects", 0)) >= 12 or "per_subject_mean_uv" in data, \
        "expected the amplitude to be aggregated over the 12 subjects"


def test_mmn_amplitude_is_mean_not_peak():
    # The mean-amplitude MMN at FCz (125-225 ms) is -1.82 uV. Reporting the PEAK amplitude
    # (most-negative value) in the window instead roughly doubles it (~-3.53 uV), landing
    # ~1.7 uV outside the tolerance. Compared on magnitude, so robust to the difference-wave
    # sign convention.
    data = _load("mmn.json")
    amp = _headline_amplitude(data)
    assert amp is not None, f"no MMN amplitude found in mmn.json: {data}"
    assert abs(abs(amp) - EXPECTED_ABS) < TOL, (
        f"MMN amplitude {amp:.2f} uV does not match the mean-amplitude value -1.82 uV "
        f"(|.|={EXPECTED_ABS}, tol {TOL}). Taking the peak (most-negative) value in the "
        f"125-225 ms window instead of the mean amplitude gives ~-3.53 uV, roughly "
        f"double.")


def test_findings_report():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert "fcz" in text and ("mmn" in text or "amplitude" in text), \
        "findings.md does not report an MMN amplitude at FCz"
    amp = _headline_amplitude(_load("mmn.json"))
    nums = [abs(float(x)) for x in re.findall(r"-?\d+\.\d+", text)]
    assert any(abs(n - abs(amp)) < 0.5 for n in nums), \
        "findings.md does not report an amplitude consistent with mmn.json"
