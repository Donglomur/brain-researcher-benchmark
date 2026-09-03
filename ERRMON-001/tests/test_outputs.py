"""Grading checks for ERRMON-001 (error-related frontocentral negativity, ERP CORE Flankers).

Ground truth (validated before release on the ERP CORE Flankers task, subject 001, 400
trials = 54 error / 346 correct; electrode FCz, average reference over the 30 scalp
electrodes, 0.1-30 Hz band-pass, pre-event baseline; mean error-minus-correct amplitude in
the 0-100 ms window):

    ERN, epochs aligned to the RESPONSE (correct) : -5.9 uV   <-- EXPECTED
    error-minus-correct, aligned to the STIMULUS (naive), same 0-100 ms window : -0.6 uV

The error-related frontocentral negativity is generated at the moment of the erroneous
button press, which occurs a variable ~400 ms after the flanker array. Averaging epochs
time-locked to the response reveals the full negativity (~-5.9 uV at FCz); time-locking to
the stimulus smears it across the reaction-time jitter and all but cancels it (~-0.6 uV).
The correct value is robust (-5.5 to -6.2 uV across 0.1-15/20/30/40 Hz low-pass and
pre-event baseline windows, average reference); every stimulus-locked window stays small
(|diff| <= ~3.9 uV). The verifier matches the reported amplitude magnitude against 5.9 uV;
the stimulus-locked values are far outside.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 5.9     # |response-locked ERN| at FCz, uV
TOL = 2.0          # accept |amp| in [3.9, 7.9]; stimulus-locked values (<= ~3.9 uV) are outside

# keys that do NOT denote the reported (response-aligned, error-minus-correct) ERN amplitude
_EXCLUDE = ("stimulus", "stim_", "for_reference", "reference", "naive", "trial_amp",
            "error_trial", "correct_trial", "erroramp", "correctamp", "window", "_ms",
            "bandpass", "n_error", "n_correct", "n_trial", "ntrial", "count", "status",
            "baseline", "sfreq", "latency")


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _headline_amp(obj):
    """Reported ERN amplitude: a numeric leaf under an ERN/amplitude/negativity-ish key with
    a plausible microvolt magnitude, skipping explicitly-labelled stimulus-locked / reference
    / per-condition fields and non-value metadata."""
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
            if re.search(r"ern|amplitude|ampl|negativ|uv|microvolt", k) and 0.3 <= abs(float(cur)) <= 60.0:
                return float(cur)
    return None


def test_ern_reported():
    data = _load("ern.json")
    amp = _headline_amp(data)
    assert amp is not None, f"no ERN amplitude found in ern.json: {data}"
    n_err = int(data.get("n_error_trials", data.get("n_errors", 0)))
    assert n_err >= 20, "expected the ERN to be averaged over a plausible number of error trials"


def test_ern_is_response_aligned():
    # The response-aligned ERN at FCz is ~-5.9 uV. Aligning the same epochs to the stimulus
    # (which precedes the button press by a variable ~400 ms) all but cancels it (~-0.6 uV).
    data = _load("ern.json")
    amp = _headline_amp(data)
    assert amp is not None, f"no ERN amplitude found in ern.json: {data}"
    assert abs(abs(amp) - EXPECTED) < TOL, (
        f"ERN amplitude {amp:.2f} uV does not match the response-aligned value ~-5.9 uV "
        f"(|amp| within {TOL} of {EXPECTED}). Aligning the epochs to the stimulus instead of "
        f"the button press smears the error-related negativity across the reaction-time "
        f"jitter and shrinks the error-minus-correct difference to ~-0.6 uV.")


def test_findings_report():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert ("ern" in text or "error" in text or "negativ" in text) and \
        ("uv" in text or "microvolt" in text or "amplitud" in text), \
        "findings.md does not report an error-related frontocentral negativity amplitude"
    amp = _headline_amp(_load("ern.json"))
    nums = [abs(float(x)) for x in re.findall(r"-?\d+\.?\d*", text)]
    assert any(abs(n - abs(amp)) < 1.0 for n in nums), \
        "findings.md does not report an amplitude consistent with ern.json"
