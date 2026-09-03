"""Grading checks for N2PC-001 (N2pc component amplitude, ERP CORE N2pc task).

Ground truth (validated before release on the ERP CORE N2pc task, subjects
1/3/4/5/6/7/8/9/10/11/12/13; electrode pair PO7/PO8; average reference over the 30 scalp
electrodes; 0.1-30 Hz band-pass; -200..0 baseline; mean contralateral-minus-ipsilateral
amplitude in the 200-300 ms window; per subject then mean over the 12):

    N2pc, contralateral-minus-ipsilateral (correct)        : -1.38 uV   <-- EXPECTED
    fixed PO8-PO7 across all trials, pooled (naive)         : +0.34 uV
    fixed PO7-PO8 across all trials, pooled (naive)         : -0.34 uV

The N2pc is a *lateralized* component: a target in the left visual field draws a posterior
negativity over the right scalp (PO8) and a right-field target over the left scalp (PO7).
The contralateral and ipsilateral waveforms must therefore be built by re-mapping the two
electrodes per target side (target side = tens digit of the 3-digit stimulus code). Done
that way the contralateral-minus-ipsilateral difference is a robust ~-1.4 uV negativity
(12/12 subjects negative; -1.374 to -1.378 uV across 0.1-20/30/40 Hz low-pass, average vs no
re-reference, and -150/-200 ms baselines). Taking a *fixed* electrode difference across all
trials pools the two visual fields, on which the negativity sits on opposite electrodes, so
it cancels to |.| ~ 0.3 uV. The verifier matches the reported amplitude magnitude against
1.38 uV; the pooled fixed-electrode values (~0.3 uV) are far outside.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 1.375   # |contra-minus-ipsi N2pc| at PO7/PO8, uV
TOL = 0.75         # accept |amp| in [0.625, 2.125]; pooled fixed-electrode (~0.34 uV) is outside

# keys that do NOT denote the reported (contralateral-minus-ipsilateral) N2pc amplitude
_EXCLUDE = ("fixed", "pooled", "for_reference", "reference", "naive", "contralateral",
            "ipsilateral", "contra", "ipsi", "po7", "po8", "window", "_ms", "bandpass",
            "n_subject", "nsubject", "n_left", "n_right", "n_trial", "ntrial", "count",
            "status", "baseline", "sfreq", "latency", "negative")


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _headline_amp(obj):
    """Reported N2pc amplitude: a numeric leaf under an N2pc/amplitude/negativity-ish key
    with a plausible microvolt magnitude, skipping explicitly-labelled per-condition
    (contralateral/ipsilateral), fixed/pooled reference, and non-value metadata fields."""
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
            if re.search(r"n2pc|amplitude|ampl|negativ|uv|microvolt", k) and 0.2 <= abs(float(cur)) <= 30.0:
                return float(cur)
    return None


def test_n2pc_reported():
    data = _load("n2pc.json")
    amp = _headline_amp(data)
    assert amp is not None, f"no N2pc amplitude found in n2pc.json: {data}"
    n_sub = int(data.get("n_subjects", data.get("nsubjects", 0)))
    assert n_sub >= 8, "expected the N2pc to be grand-averaged over a plausible number of subjects"


def test_n2pc_contra_minus_ipsi():
    # The contralateral-minus-ipsilateral N2pc at PO7/PO8 is ~-1.4 uV. Taking a fixed
    # electrode difference across all trials (pooling the two visual fields, on which the
    # negativity lies over opposite electrodes) cancels it to |.| ~ 0.3 uV.
    data = _load("n2pc.json")
    amp = _headline_amp(data)
    assert amp is not None, f"no N2pc amplitude found in n2pc.json: {data}"
    assert abs(abs(amp) - EXPECTED) < TOL, (
        f"N2pc amplitude {amp:.2f} uV does not match the contralateral-minus-ipsilateral "
        f"value ~-1.4 uV (|amp| within {TOL} of {EXPECTED}). Taking a fixed electrode "
        f"difference across all trials pools the left- and right-field targets, on which the "
        f"lateralized negativity sits over opposite electrodes, and cancels it to ~0.3 uV.")


def test_findings_report():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert ("n2pc" in text or "contralateral" in text or "negativ" in text) and \
        ("uv" in text or "microvolt" in text or "amplitud" in text), \
        "findings.md does not report an N2pc amplitude"
    amp = _headline_amp(_load("n2pc.json"))
    nums = [abs(float(x)) for x in re.findall(r"-?\d+\.?\d*", text)]
    assert any(abs(n - abs(amp)) < 1.0 for n in nums), \
        "findings.md does not report an amplitude consistent with n2pc.json"
