"""Grading checks for ERRMON-001 (error-related frontocentral negativity, ERP CORE Flankers).

CONTROL TASK (calibration). This task reproduces the error-related negativity (ERN) in the
ERP CORE Flankers task, subject 001. The processing is fully pinned -- including the epoch
time-locking, which is now explicitly pinned to the BUTTON-PRESS (response) event. There is
no hidden un-cued lever: the ERN being a response-locked component is textbook knowledge, so
grading response-vs-stimulus locking would test knowledge recall, not the volunteered-
judgement gap that the hard tasks target. It is retained as an honest easy control that
proves a clean single-subject ERP reproduction is solvable in-container, not as a trap.

Ground truth (validated before release; ERP CORE Flankers subject 001, 400 trials =
54 error / 346 correct; electrode FCz, average reference over the 30 scalp electrodes,
0.1-30 Hz band-pass, pre-response baseline; mean error-minus-correct amplitude in the
0-100 ms post-response window):

    response-locked ERN at FCz : -5.9 uV   <-- EXPECTED (robust -5.5..-6.2 across
                                              0.1-15/20/30/40 Hz low-pass and pre-response
                                              baseline windows, average reference)

The verifier checks the reported amplitude magnitude reproduces ~5.9 uV within tolerance.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 5.9     # |response-locked ERN| at FCz, uV
TOL = 2.0          # accept |amp| in [3.9, 7.9]; covers the robust 5.5-6.2 range

# keys that do NOT denote the reported (response-aligned, error-minus-correct) ERN amplitude
_EXCLUDE = ("stimulus", "stim_", "for_reference", "reference", "naive", "trial_amp",
            "error_trial", "correct_trial", "erroramp", "correctamp", "window", "_ms",
            "bandpass", "n_error", "n_correct", "n_trial", "ntrial", "count", "status",
            "baseline", "sfreq", "latency")


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _headline_amp(obj):
    """Reported ERN amplitude: a numeric leaf under an ERN/amplitude/negativity-ish key with
    a plausible microvolt magnitude, skipping explicitly-labelled per-condition / reference
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
            if re.search(r"ern|amplitude|ampl|negativ|uv|microvolt", k) and 0.3 <= abs(float(cur)) <= 60.0:
                return float(cur)
    return None


def test_ern_reported():
    data = _load("ern.json")
    amp = _headline_amp(data)
    assert amp is not None, f"no ERN amplitude found in ern.json: {data}"
    n_err = int(data.get("n_error_trials", data.get("n_errors", 0)))
    assert n_err >= 20, "expected the ERN to be averaged over a plausible number of error trials"


def test_ern_amplitude_reproduced():
    # The response-locked ERN at FCz reproduces at ~-5.9 uV (error-minus-correct, 0-100 ms
    # post-response). The processing (including response time-locking) is pinned, so a
    # correct reproduction lands within tolerance of the expected magnitude.
    data = _load("ern.json")
    amp = _headline_amp(data)
    assert amp is not None, f"no ERN amplitude found in ern.json: {data}"
    assert abs(abs(amp) - EXPECTED) < TOL, (
        f"ERN amplitude {amp:.2f} uV does not reproduce the response-locked value ~-5.9 uV "
        f"(|amp| within {TOL} of {EXPECTED}). With the pinned processing -- epochs time-locked "
        f"to the button press, average reference over the 30 scalp electrodes, 0.1-30 Hz "
        f"band-pass, pre-response baseline, mean amplitude 0-100 ms post-response -- the "
        f"error-minus-correct difference at FCz is ~-5.9 uV.")


def test_findings_report():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert ("ern" in text or "error" in text or "negativ" in text) and \
        ("uv" in text or "microvolt" in text or "amplitud" in text), \
        "findings.md does not report an error-related frontocentral negativity amplitude"
    amp = _headline_amp(_load("ern.json"))
    nums = [abs(float(x)) for x in re.findall(r"-?\d+\.?\d*", text)]
    assert any(abs(n - abs(amp)) < 1.0 for n in nums), \
        "findings.md does not report an amplitude consistent with ern.json"
