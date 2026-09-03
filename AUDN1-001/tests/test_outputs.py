"""Grading checks for AUDN1-001 (auditory N100 GFP amplitude, MNE sample, left auditory).

Ground truth (validated before release on the MNE sample dataset, filtered raw file,
left-auditory trigger 1, 72 epochs; EEG with the marked bad channel excluded, average
reference, -0.2..0.5 s epochs; peak Global Field Power in the 80-120 ms window):

    baseline-corrected N100 GFP peak (correct) : 4.4 uV   <-- EXPECTED
    no baseline correction (naive)             : 9.2 uV   (~2.1x, filtered file)
                                                 ~27 uV    (if the un-filtered raw is used)

An evoked amplitude -- and the GFP, the spatial standard deviation across electrodes --
must be measured against a pre-stimulus baseline. Skipping baseline correction leaves the
residual per-electrode pre-stimulus offsets in the data, which add to the spatial variance
and inflate the GFP peak (to ~9 uV here, more on the un-filtered file). The correct,
baseline-corrected N100 GFP peak is ~4.4 uV and is robust across the filtered/un-filtered
files and reasonable measurement windows. The verifier matches the reported amplitude
against 4.4 uV; the un-baselined values (>=9 uV) are well outside the tolerance.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 4.4     # baseline-corrected N100 GFP peak amplitude, uV
TOL = 2.5          # accept [1.9, 6.9]; the un-baselined values (>=9 uV) are far outside

# keys that do NOT denote the reported (baseline-corrected) N100 amplitude
_EXCLUDE = ("no_baseline", "nobaseline", "reference_uv", "for_reference", "naive",
            "window", "_ms", "n_epoch", "epoch", "count", "status", "latency")


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _headline_amp(obj):
    """Reported N100 amplitude: a numeric leaf under an amplitude/GFP/N1-ish key with a
    plausible microvolt magnitude, skipping explicitly-labelled no-baseline/reference
    fields and non-value metadata."""
    stack = [("", obj)]
    while stack:
        key, cur = stack.pop()
        k = key.lower()
        if isinstance(cur, dict):
            stack.extend(cur.items())
        elif isinstance(cur, (list, tuple)):
            continue
        elif isinstance(cur, (int, float)) and not isinstance(cur, bool):
            if any(x in k for x in _EXCLUDE):
                continue
            if re.search(r"amp|gfp|n1|n100|uv|microvolt", k) and 0.5 <= abs(float(cur)) <= 200.0:
                return float(cur)
    return None


def test_n1_reported():
    data = _load("n1.json")
    amp = _headline_amp(data)
    assert amp is not None, f"no N100 amplitude found in n1.json: {data}"
    assert int(data.get("n_epochs", 0)) >= 30, \
        "expected the N100 to be averaged over the left-auditory epochs"


def test_n1_amplitude_is_baseline_corrected():
    # The baseline-corrected auditory N100 GFP peak is ~4.4 uV. Skipping baseline
    # correction inflates the GFP peak to ~9 uV (filtered file) or ~27 uV (un-filtered),
    # because residual pre-stimulus per-electrode offsets add to the spatial variance.
    data = _load("n1.json")
    amp = _headline_amp(data)
    assert amp is not None, f"no N100 amplitude found in n1.json: {data}"
    assert abs(abs(amp) - EXPECTED) < TOL, (
        f"N100 GFP amplitude {amp:.2f} uV does not match the baseline-corrected value "
        f"~4.4 uV (|.|={EXPECTED}, tol {TOL}). Omitting baseline correction inflates the "
        f"GFP peak to ~9 uV (filtered) or ~27 uV (un-filtered).")


def test_findings_report():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert ("n1" in text or "n100" in text) and ("gfp" in text or "amplitude" in text
                                                  or "field power" in text), \
        "findings.md does not report an auditory N100 amplitude"
    amp = _headline_amp(_load("n1.json"))
    nums = [abs(float(x)) for x in re.findall(r"-?\d+\.?\d*", text)]
    assert any(abs(n - abs(amp)) < 0.5 for n in nums), \
        "findings.md does not report an amplitude consistent with n1.json"
