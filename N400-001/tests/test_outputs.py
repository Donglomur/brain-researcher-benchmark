"""Grading checks for N400-001 (ERP CORE N400 unrelated-minus-related amplitude at CPz).

Ground truth (validated before release on the ERP CORE N400 files, subjects 1-12, P9/P10
mastoid reference, 0.1-30 Hz, -200..0 baseline, epochs -200..800, all epochs of each
condition averaged; unrelated-minus-related difference wave at CPz, mean amplitude over
300-500 ms, per subject then mean over subjects):

    TARGET WORDS ONLY (correct)                 : -8.70 uV   <-- EXPECTED
    PRIME + TARGET pooled by relatedness (naive): -4.20 uV   (~half)

The N400 relatedness effect is elicited by the TARGET word, so the contrast must use
target words only (unrelated targets 221/222 minus related targets 211/212). Pooling the
prime words (codes 1XY) into the contrast dilutes the effect with ~zero-difference prime
trials of equal number and roughly halves the amplitude; the prime-only difference is
~0. 12/12 subjects show a negative unrelated-minus-related N400 with the target-only
contrast. The verifier matches the magnitude of the target-only value; the pooled answer
is ~4.5 uV away and fails. Compared on magnitude, so it is robust to whether the
difference is reported as unrelated-minus-related or related-minus-unrelated.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED_ABS = 8.70    # |mean-amplitude N400 at CPz, 300-500 ms| in uV
TOL = 2.0              # accept [6.70, 10.70]; fails the pooled magnitude (~4.20, ~4.5 away)

# keys that do NOT denote the reported headline amplitude
_EXCLUDE = ("pooled", "prime", "reference", "naive", "latency", "window", "_ms", "n_sub",
            "per_subject", "persubject", "sd", "std", "sem", "count")


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _headline_amplitude(obj):
    """The reported N400 amplitude: a numeric leaf under an amplitude-ish key with a
    plausible microvolt magnitude, skipping explicitly-labelled pooled/reference fields."""
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
            if re.search(r"amp|n400|uv|microvolt", k) and 0.3 <= abs(float(cur)) <= 20.0:
                return float(cur)
    return None


def test_n400_reported():
    data = _load("n400.json")
    amp = _headline_amplitude(data)
    assert amp is not None, f"no N400 amplitude found in n400.json: {data}"
    assert int(data.get("n_subjects", 0)) >= 12 or "per_subject_uv" in data, \
        "expected the amplitude to be aggregated over the 12 subjects"


def test_n400_amplitude_is_target_only():
    # The target-only N400 at CPz (300-500 ms) is -8.70 uV. Pooling the prime words into
    # the unrelated/related contrast roughly halves it (~-4.20 uV), landing ~4.5 uV
    # outside the tolerance. Compared on magnitude, so robust to the difference-wave sign.
    data = _load("n400.json")
    amp = _headline_amplitude(data)
    assert amp is not None, f"no N400 amplitude found in n400.json: {data}"
    assert abs(abs(amp) - EXPECTED_ABS) < TOL, (
        f"N400 amplitude {amp:.2f} uV does not match the target-only value -8.70 uV "
        f"(|.|={EXPECTED_ABS}, tol {TOL}). Pooling the prime words (codes 1XY) into the "
        f"unrelated/related contrast instead of using target words only (2XY) roughly "
        f"halves it (~-4.20 uV).")


def test_findings_report():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert "cpz" in text and ("n400" in text or "amplitude" in text), \
        "findings.md does not report an N400 amplitude at CPz"
    amp = _headline_amplitude(_load("n400.json"))
    nums = [abs(float(x)) for x in re.findall(r"-?\d+\.\d+", text)]
    assert any(abs(n - abs(amp)) < 0.5 for n in nums), \
        "findings.md does not report an amplitude consistent with n400.json"
