"""Grading checks for HIPPOTHETA-001 (reproduce the locomotion theta peak frequency).

Ground truth (validated before release on DANDI 000552, sub-e15-13f1 ses-e15-13f1-220117; LFP
processing/ecephys/LFP/ElectricalSeriesLFP at 1250 Hz; running speed from
processing/behavior/SubjectPosition; best theta-power channel; Welch 4 s windows; 6-10 Hz band):

  CORRECT  during locomotion (speed > ~5 units/s) : 8.99 Hz  (>3 -> 8.86 Hz; stable to channel)
  NAIVE    whole recording, no movement gating     : 7.92 Hz
  (context) REM theta 7.42 Hz ; awake immobility theta 7.50 Hz

Theta frequency is state-dependent: running theta is fast (~9 Hz) whereas theta during REM sleep
and awake immobility is ~1.5 Hz slower (~7.4-7.5 Hz). This session is ~7 h, mostly home-cage
rest/sleep with a single ~31 min maze epoch, so the theta-band spectral peak taken over the WHOLE
recording (or without conditioning on movement) is dragged down to ~7.9 Hz by the dominant
slow-theta (REM / immobility) periods. Only restricting to locomotion recovers ~9 Hz. The
locomotion value is stable across the theta channel (48/63/78 -> 8.99 Hz) and running-speed
cutoff (~8.9 +/- 0.1 Hz).

The failure mode this task targets (un-cued): the agent estimates the theta peak over the whole
LFP (or does not condition on movement) and reports ~7.9 Hz -- the rest/REM-contaminated value --
rather than the ~9 Hz movement-related theta. A reported ~7.9 Hz fails the numeric match.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 8.9      # locomotion theta peak frequency (Hz)
TOL = 0.5           # passes the ~8.9-9.0 locomotion peak; fails the ~7.9 whole-recording value
THETA_LO, THETA_HI = 6.0, 10.0

# keys/labels that denote a NON-reported contrast quantity (never grade these as the headline)
EXCLUDE = re.compile(r"whole|recording|session|rem|immobil|rest|sleep|slow|naive|"
                     r"contaminat|contrast|context|delta|non.?theta", re.I)
# keys that denote the theta peak frequency we DO grade
PEAK_KEY = re.compile(r"(theta.*(peak|freq))|((peak|dominant).*(theta|freq))|theta_peak", re.I)


def _load(name):
    return (OUT / name).read_text(encoding="utf-8")


def _results():
    return json.loads(_load("results.json"))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _walk(obj, prefix=""):
    """Yield (dotted_key, value) for every scalar in a nested dict/list."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def _headline_peak(res):
    """The reported locomotion theta peak: a theta-peak-frequency value that is NOT tagged as one
    of the contrast quantities (whole-recording / REM / immobility / ...)."""
    # 1) prefer an explicit theta-peak key that is not an excluded contrast key
    for k, v in _walk(res):
        leaf = k.split(".")[-1].split("[")[0]
        if _num(v) and PEAK_KEY.search(leaf) and not EXCLUDE.search(k):
            if THETA_LO - 1.5 <= float(v) <= THETA_HI + 1.5:
                return float(v)
    # 2) fall back to any in-band frequency-like value not on an excluded key
    for k, v in _walk(res):
        if _num(v) and re.search(r"freq|hz|peak", k, re.I) and not EXCLUDE.search(k):
            if THETA_LO <= float(v) <= THETA_HI:
                return float(v)
    return None


def test_analysis_ran():
    res = _results()
    # a real run: some locomotion time was analysed and a channel/rate is recorded somewhere
    vals = dict(_walk(res))
    run_time = next((float(v) for k, v in vals.items()
                     if _num(v) and re.search(r"locomot|run", k, re.I) and re.search(r"time|dur|sec", k, re.I)), None)
    # locomotion time is expected but be lenient: accept its presence OR a stated running criterion
    crit = any(re.search(r"run|locomot|speed", str(k), re.I) for k in vals)
    assert crit, "no running/locomotion criterion recorded in results.json"
    if run_time is not None:
        assert 60 <= run_time <= 2000, f"locomotion time implausible for a ~31 min maze epoch: {run_time}"


def test_reported_theta_peak_reproduces_locomotion_value():
    res = _results()
    peak = _headline_peak(res)
    assert peak is not None, "results.json exposes no theta peak frequency (Hz) headline value"
    assert THETA_LO - 1.0 <= peak <= THETA_HI + 1.0, f"peak {peak} not a plausible theta frequency"
    assert abs(peak - EXPECTED) <= TOL, (
        f"reported theta peak frequency {peak:.2f} Hz does not reproduce the locomotion value "
        f"{EXPECTED:.1f} +/- {TOL:.1f} Hz. Running (movement) theta is ~9 Hz; a ~7.9 Hz estimate "
        f"comes from a spectrum taken over the whole recording, which is dominated by rest/REM/"
        f"immobility where theta is ~1.5 Hz slower. Only conditioning on locomotion recovers ~9 Hz.")


def test_findings_reports_locomotion_theta_not_slow_value():
    text = _load("findings.md").lower()
    assert "theta" in text, "findings.md does not mention theta"
    # the reported locomotion value must appear in the prose too, and match the headline
    res = _results()
    peak = _headline_peak(res)
    assert peak is not None and abs(peak - EXPECTED) <= TOL, \
        "headline theta peak in results.json is not the locomotion value"
    nums = [float(x) for x in re.findall(r"(\d+\.?\d*)\s*hz", text)]
    assert any(abs(n - EXPECTED) <= TOL for n in nums), \
        "findings.md does not state a theta peak frequency (Hz) consistent with the locomotion value"
