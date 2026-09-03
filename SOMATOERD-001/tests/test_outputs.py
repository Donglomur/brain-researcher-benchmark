"""Grading checks for SOMATOERD-001 (contralateral sensorimotor beta ERD, MNE somato).

Ground truth (validated before release on MNE somato sub-01, 111 median-nerve trials;
gradiometers MEG 1342/1343/1332/1333; Morlet 15-30 Hz, n_cycles = freq/2; percent
baseline over -1.0..-0.25 s; beta 15-30 Hz averaged over the 0.10-0.35 s window):

    induced / total power (per-trial time-frequency, then averaged) : -17.7 %  <-- EXPECTED
    evoked power (time-frequency of the trial-average)              : +443.6 % (naive)

Beta ERD/ERS are INDUCED (non-phase-locked) effects, so the power must be computed on
single trials and then averaged (the MNE ``compute_tfr(..., average=True)`` default).
Computing the time-frequency power of the trial-AVERAGE (the evoked response) keeps only
phase-locked power; here the early somatosensory evoked field dominates and its
pre-stimulus baseline is averaged toward zero, so the evoked-power "ERD" comes out large
and POSITIVE (~+444 %) -- the wrong sign and off by an order of magnitude. The correct
induced-power value is a modest negative percentage (a decrease). The verifier matches the
MAGNITUDE of the reported percent, so it is robust to whether the change is reported as
-17.7 % or as a +17.7 % decrease, and it comfortably rejects the evoked-power value.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED_ABS = 17.7    # |induced beta ERD| in percent
TOL = 8.0              # accept |.| in [9.7, 25.7]; the evoked value (~444%) is far outside

# keys that do NOT denote the reported induced-ERD percentage
_EXCLUDE = ("evoked", "reference", "naive", "baseline", "window", "_ms", "trial",
            "band", "hz", "channel", "freq", "cycle", "sd", "std", "sem", "count", "status")


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _headline_erd(obj):
    """Reported beta-ERD percentage: a numeric leaf under an ERD/beta/percent-ish key,
    skipping explicitly-labelled evoked/reference fields and non-value metadata."""
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
            if re.search(r"erd|beta|percent|desync|power", k) and 3.0 <= abs(float(cur)) <= 2000.0:
                return float(cur)
    return None


def test_erd_reported():
    data = _load("erd.json")
    amp = _headline_erd(data)
    assert amp is not None, f"no beta-ERD percentage found in erd.json: {data}"
    assert int(data.get("n_trials", 0)) >= 50, \
        "expected the ERD to be aggregated over the median-nerve trials"


def test_erd_is_induced_not_evoked():
    # Induced (single-trial then averaged) beta power gives an ERD of about -17.7 %.
    # Computing time-frequency power on the trial-average (evoked power) instead gives a
    # large POSITIVE percentage (~+444 %), off by an order of magnitude and the wrong sign.
    # Compared on magnitude, so robust to the sign convention used for the decrease.
    data = _load("erd.json")
    amp = _headline_erd(data)
    assert amp is not None, f"no beta-ERD percentage found in erd.json: {data}"
    assert abs(abs(amp) - EXPECTED_ABS) < TOL, (
        f"beta ERD {amp:.1f}% does not match the induced-power value ~-17.7% "
        f"(|.|={EXPECTED_ABS}, tol {TOL}). Computing the time-frequency power of the "
        f"trial-average (evoked power) instead of per-trial power gives ~+444%, the "
        f"wrong sign and off by an order of magnitude.")


def test_findings_report():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert ("beta" in text) and ("erd" in text or "desync" in text), \
        "findings.md does not report a beta ERD"
    amp = _headline_erd(_load("erd.json"))
    nums = [abs(float(x)) for x in re.findall(r"-?\d+\.?\d*", text)]
    assert any(abs(n - abs(amp)) < 2.0 for n in nums), \
        "findings.md does not report an ERD magnitude consistent with erd.json"
