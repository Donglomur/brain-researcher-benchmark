"""Grading checks for HIPPORIPPLE-001 (reproduce the non-REM SWR incidence rate).

Ground truth (validated before release on DANDI 000552, sub-e15-13f1 ses-e15-13f1-220117; the
provided processing/ecephys/Ripples detections and processing/behavior/SleepStates annotations;
ripple assigned to a state by its peak time):

  CORRECT  non-REM ripples / non-REM duration = 6772 / 9016 s = 0.751 /s   <-- reported
  NAIVE-1  all ripples / whole recording       = 9135 / 25502 s = 0.358 /s
  NAIVE-2  non-REM ripples / whole recording    = 6772 / 25502 s = 0.266 /s
  (context) awake 0.148 /s ; REM 0.046 /s

Sharp-wave ripples are state-specific -- abundant in non-REM sleep, rare in locomotion/REM. The
incidence rate DURING non-REM sleep is (ripples in non-REM) / (time in non-REM) ~ 0.75 /s. A
pipeline that normalises by the WHOLE recording instead of by the non-REM duration (state
contamination of the denominator), or counts all ripples over the whole session, reports ~0.27-
0.36 /s -- about half. The correct value is identical whether ripples are assigned by peak or by
onset time.

The failure mode this task targets (un-cued): the agent divides ripples by the whole-recording
duration rather than by the non-REM sleep duration, and reports ~0.36 /s instead of the ~0.75 /s
non-REM incidence rate. A reported ~0.27-0.36 /s fails the numeric match.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.75     # non-REM SWR incidence rate (events/s)
TOL = 0.15          # passes ~0.60-0.90; fails the ~0.27-0.36 whole-recording normalisations

# keys/labels that denote a NON-reported contrast quantity (never grade these as the headline)
EXCLUDE = re.compile(r"whole|recording|session|total|overall|awake|\brem\b|naive|contrast|"
                     r"context|duration|count|n_?ripple|number", re.I)
# keys that denote a rate we DO grade
RATE_KEY = re.compile(r"rate|incidence|per.?sec|/s|events?_per|freq|hz", re.I)


def _load(name):
    return (OUT / name).read_text(encoding="utf-8")


def _results():
    return json.loads(_load("results.json"))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _walk(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def _canon_rate(v):
    """Return events/second. Accept a per-minute report (~20-90/min) by dividing by 60."""
    v = float(v)
    if 15.0 <= v <= 120.0:      # clearly a per-minute figure (0.27/s=16/min .. 0.9/s=54/min)
        return v / 60.0
    return v


def _headline_rate(res):
    # 1) prefer a non-REM-tagged rate key that is not a contrast key
    for k, v in _walk(res):
        if _num(v) and RATE_KEY.search(k) and re.search(r"non.?rem|nrem|sws|slow.?wave", k, re.I) \
                and not EXCLUDE.search(re.sub(r"non.?rem|nrem", "", k, flags=re.I)):
            r = _canon_rate(v)
            if 0.02 <= r <= 5.0:
                return r
    # 2) any rate key not tagged as a contrast quantity
    for k, v in _walk(res):
        if _num(v) and RATE_KEY.search(k) and not EXCLUDE.search(k):
            r = _canon_rate(v)
            if 0.02 <= r <= 5.0:
                return r
    return None


def test_analysis_ran():
    res = _results()
    vals = dict(_walk(res))
    n_total = next((float(v) for k, v in vals.items()
                    if _num(v) and re.search(r"(n_?ripple|ripple.*count|number.*ripple)", k, re.I)
                    and re.search(r"total|all|detect", k, re.I)), None)
    if n_total is None:  # accept any ripple count
        n_total = next((float(v) for k, v in vals.items()
                        if _num(v) and re.search(r"n_?ripple|ripple.*count", k, re.I)), None)
    assert n_total is not None and 500 <= n_total <= 30000, f"ripple count implausible: {n_total}"
    nrem = next((float(v) for k, v in vals.items()
                 if _num(v) and re.search(r"non.?rem|nrem", k, re.I) and re.search(r"dur|time|sec", k, re.I)), None)
    assert nrem is not None and 1000 <= nrem <= 20000, f"non-REM duration implausible: {nrem}"


def test_reported_rate_reproduces_nonrem_value():
    res = _results()
    rate = _headline_rate(res)
    assert rate is not None, "results.json exposes no non-REM ripple incidence rate (events/s)"
    assert abs(rate - EXPECTED) <= TOL, (
        f"reported ripple incidence rate {rate:.3f}/s does not reproduce the non-REM value "
        f"{EXPECTED:.2f} +/- {TOL:.2f} /s. Sharp-wave ripples are a non-REM phenomenon; the rate "
        f"DURING non-REM sleep is (ripples in non-REM) / (time in non-REM) ~ 0.75/s. A ~0.27-0.36/s "
        f"value comes from dividing by the whole recording rather than by the non-REM duration.")


def test_findings_reports_nonrem_rate():
    text = _load("findings.md").lower()
    assert re.search(r"rippl|swr|sharp.?wave", text), "findings.md does not mention ripples"
    assert re.search(r"non.?rem|nrem|slow.?wave|sws", text), "findings.md does not mention non-REM sleep"
    res = _results()
    rate = _headline_rate(res)
    assert rate is not None and abs(rate - EXPECTED) <= TOL, \
        "headline ripple rate in results.json is not the non-REM value"
    nums = [_canon_rate(x) for x in re.findall(r"(\d+\.?\d*)\s*(?:events?\s*)?(?:/|per)\s*s", text)]
    nums += [float(x) for x in re.findall(r"=\s*(\d+\.?\d*)\b", text)]
    assert any(abs(n - EXPECTED) <= TOL for n in nums), \
        "findings.md does not state a non-REM ripple incidence rate consistent with the headline"
