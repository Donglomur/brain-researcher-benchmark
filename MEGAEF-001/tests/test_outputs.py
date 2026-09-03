"""Grading checks for MEGAEF-001 (auditory M100 latency, bst_auditory, standard tones).

Ground truth (validated before release on the Brainstorm ``bst_auditory`` MEG recording,
run 1, standard-tone trigger code 1, 200 trials; MEG magnetometers, -0.1..0.4 s epochs
with a pre-stimulus baseline, 40 Hz low-pass; peak Global Field Power latency in the
60-160 ms window):

    M100 GFP-peak latency, acoustic-onset aligned (correct) : 93.3 ms   <-- EXPECTED
    M100 GFP-peak latency, raw digital-trigger timing (naive): 107.5 ms  (~+14 ms)

The digital stimulus trigger on ``UPPT001`` precedes the actual acoustic delivery of the
tone by a fixed ~14 ms (recoverable from the analog audio channel ``UADC001``), so the
physiological M100 latency must be measured relative to the true acoustic onset. Timing the
epochs to the raw trigger inflates the apparent latency by that fixed delay. The correct,
acoustic-onset-aligned M100 latency is ~93 ms and is robust (92-94 ms across 30/40 Hz / no
low-pass, several measurement windows, and audio-detection thresholds 1.5-3.0 x sigma); the
raw-trigger value is ~107-109 ms, well outside the tolerance. The verifier matches the
reported latency against 93.3 ms; the raw-trigger value (>=107 ms) fails.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 93.3    # acoustic-onset-aligned M100 GFP-peak latency, ms
TOL = 8.0          # accept [85.3, 101.3]; the raw-trigger value (~107.5 ms) is far outside

# keys that do NOT denote the reported (acoustic-onset-aligned) M100 latency
_EXCLUDE = ("trigger", "reference", "delay", "naive", "raw_", "amplitude", "_ft", "gfp_amp",
            "window", "_win", "n_trial", "ntrial", "count", "status", "baseline", "epoch",
            "lowpass", "sfreq")


def _load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def _headline_latency(obj):
    """Reported M100 latency: a numeric leaf under a latency/M100-ish key with a plausible
    millisecond magnitude, skipping explicitly-labelled trigger/reference/delay fields and
    non-latency metadata."""
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
            if re.search(r"latenc|m100|n100|peak_time|lat_ms|_lat", k) and 40.0 <= abs(float(cur)) <= 200.0:
                return float(cur)
    return None


def test_m100_reported():
    data = _load("m100.json")
    lat = _headline_latency(data)
    assert lat is not None, f"no M100 latency found in m100.json: {data}"
    assert int(data.get("n_trials", data.get("n_epochs", 0))) >= 100, \
        "expected the M100 to be averaged over the standard-tone trials"


def test_m100_latency_is_acoustic_onset_aligned():
    # The acoustic-onset-aligned M100 GFP-peak latency is ~93 ms. Timing the epochs to the
    # raw digital trigger (which precedes the sound by ~14 ms) inflates it to ~107.5 ms.
    data = _load("m100.json")
    lat = _headline_latency(data)
    assert lat is not None, f"no M100 latency found in m100.json: {data}"
    assert abs(lat - EXPECTED) < TOL, (
        f"M100 latency {lat:.1f} ms does not match the acoustic-onset-aligned value "
        f"~93.3 ms (tol {TOL}). Timing the epochs to the raw ``UPPT001`` trigger, which "
        f"leads the acoustic onset by ~14 ms, inflates the apparent latency to ~107.5 ms.")


def test_findings_report():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert ("m100" in text or "n100m" in text or "n100" in text) and \
        ("latenc" in text or "ms" in text or "millisecond" in text), \
        "findings.md does not report an auditory M100 latency"
    lat = _headline_latency(_load("m100.json"))
    nums = [abs(float(x)) for x in re.findall(r"-?\d+\.?\d*", text)]
    assert any(abs(n - abs(lat)) < 1.0 for n in nums), \
        "findings.md does not report a latency consistent with m100.json"
