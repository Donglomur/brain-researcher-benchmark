"""Grading checks for ALLEN2P-001 (orientation-/direction-selective fraction of a two-photon VISp
field to drifting gratings) -- graded as a VOLUNTEERED-judgement task, not a point-match.

Ground truth (validated before release on Allen Brain Observatory ophys_experiment_id 501271265,
VISp, three_session_A; drifting gratings; per-trial response = mean dF/F over the presentation
window; preferred (direction, temporal frequency); OSI = (R_pref - R_orth)/(R_pref + R_orth);
DSI = (R_pref - R_null)/(R_pref + R_null); a neuron is selective if OSI > 0.5 or DSI > 0.5;
denominator = all imaged neurons):

  n imaged neurons (all)                                   = 215
  SAME-TRIALS (preferred condition + OSI/DSI on the SAME   = ~0.78   (winner's-curse inflated)
               trials -- the standard AllenSDK select-and-test procedure the brief pins)
  HELD-OUT    (preferred condition chosen on one set of    = ~0.54   (bias-free)
               trials, OSI/DSI measured on the disjoint set)

The pinned procedure IS the field-standard same-trials computation, so an agent that faithfully
follows it and reports ~0.78 has NOT done anything the brief forbade -- punishing that number
outright would be unfair (it is exactly what the AllenSDK DriftingGratings analysis yields on this
session). What a careful analyst volunteers, un-cued, is the metacognition: the preferred (direction,
temporal-frequency) condition is chosen as the argmax of noisy per-condition estimates, so measuring
the ratio contrast statistics OSI/DSI on those same trials is circular (double dipping) and biases
R_pref upward -- a winner's curse -- inflating the fraction; the honest, held-out fraction is much
lower (~0.54, stable 0.50-0.61 across the split scheme).

So this task grades JUDGEMENT, DEVCONN-style. A submission passes if EITHER
  (A) its reported headline selective fraction reproduces the bias-corrected held-out value ~0.54
      (it broke the circularity and reports the honest number -- the AllenSDK-standard-but-
      cross-validated answer), OR
  (B) it reports the same-trials value but VOLUNTEERS the winner's-curse / double-dipping caveat,
      linked to the result (the same-trials fraction is inflated / the held-out value is lower).
An un-caveated same-trials ~0.78 -- select-and-test with no skepticism -- fails.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

HELDOUT = 0.54      # honest, held-out selective fraction (oracle 0.5367)
TOL = 0.12          # [0.42, 0.66]: any reasonable held-out estimate (0.50-0.61); excludes ~0.78

# keys the submission itself labels as the same-trials / double-dipping / spread contrast, never the
# reported honest headline
EXCLUDE = (r"no_?gate|no_?qc|all_?neuron|all_?cell|naive|unfilter|inflat|every|raw|contaminat|"
           r"ungated|same_?trial|no_?hold|not_?held|without|_sd\b|\bsd_|std|stdev|stderr|sem\b|"
           r"across_?split|variance|spread|biased|circular|double|winner")


def _results():
    return json.loads((OUT / "results.json").read_text(encoding="utf-8"))


def _as_fraction(v):
    """Accept a fraction (0..1) or a percentage (0..100)."""
    v = float(v)
    return v / 100.0 if v > 1.5 else v


def test_analysis_ran():
    res = _results()
    assert isinstance(res, dict)

    def find(keypat, obj=res):
        for k, v in (obj.items() if isinstance(obj, dict) else []):
            if re.search(keypat, k, re.I) and isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
        return None

    n_total = find(r"n_?neurons?\b|n_?cells?\b|neurons?_?total|total.*neurons?|"
                   r"n_?cells?_?total|num.*neurons?|n_?imaged")
    assert n_total is not None and 100 <= n_total <= 800, f"n imaged neurons implausible: {n_total}"
    # a headline selective fraction must exist and be in a plausible range (accepts both the
    # same-trials ~0.78 and the held-out ~0.54 -- the science is judged in the next test)
    primary = _headline_fraction(res)
    assert primary is not None, "results.json exposes no headline selective fraction"
    assert 0.2 <= primary <= 0.98, f"selective fraction implausible: {primary}"


def _headline_fraction(res):
    """The reported selective fraction. Never take a value the submission itself labelled as the
    same-trials / double-dipping / spread comparison."""
    for k, v in res.items():
        if not (isinstance(v, (int, float)) and not isinstance(v, bool)):
            continue
        if re.search(EXCLUDE, k, re.I):
            continue
        if re.search(r"(select|osi|dsi|orient|direction).*(frac|proportion|percent)"
                     r"|(frac|proportion|percent).*(select|osi|dsi|orient|direction)", k, re.I):
            return _as_fraction(v)
    for k, v in res.items():
        if (isinstance(v, (int, float)) and not isinstance(v, bool)
                and re.search(r"frac|proportion|percent|ratio", k, re.I)
                and re.search(r"select|osi|dsi|orient|direction", k, re.I)
                and not re.search(EXCLUDE, k, re.I)):
            return _as_fraction(v)
    return None


# --- the volunteered-judgement detector -------------------------------------------------------
# The insight = "choosing the preferred condition as the argmax and measuring OSI/DSI on the SAME
# trials is circular / a winner's curse, so the fraction is inflated; the held-out value is lower."
# Guard against pipeline-vocabulary false positives: the concept token must CO-OCCUR (same
# neighbourhood) with a RESULT token. A bare "we selected the preferred condition" (pipeline
# description) has no bias/result token and must NOT pass.
_LEVER = re.compile(
    r"held[\s-]?out|cross[\s-]?validat|double[\s-]?dipp|winner'?s?[\s-]?curse|circular|"
    r"selection[\s-]?bias|select\w*[\s-]?bias|same[\s-]?(set of )?trials|same[\s-]?data|"
    r"same set of trials|non[\s-]?independent|independent (set of )?trials|disjoint trials|"
    r"re[\s-]?used the same|regression to the mean", re.I)
# result/collapse tokens. The numeric token requires TWO decimals in the held-out range
# (0.45-0.66) so it matches a bias-corrected value like 0.54 but NOT the bare "0.5" OSI/DSI
# threshold that appears in every write-up.
_RESULT = re.compile(
    r"inflat|over[\s-]?estimat|overestimat|exagger|artificially|spurious|too high|"
    r"bias\w* (high|up|upward|toward)|upward|winner|lower|drops?|fall|reduc|shrink|"
    r"honest\w*|unbiased|\b0\.(4[5-9]|5[0-9]|6[0-6])\b", re.I)


def _volunteers_selection_bias(text):
    """True iff a lever/circularity concept co-occurs (within ~200 chars) with a result/collapse
    token -- i.e. the write-up links the same-trials selection to the inflation, not merely names a
    pipeline step."""
    levers = [m.start() for m in _LEVER.finditer(text)]
    results = [m.start() for m in _RESULT.finditer(text)]
    for li in levers:
        for ri in results:
            if abs(li - ri) <= 200:
                return True
    return False


def test_findings_describe_selectivity():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert re.search(r"orientation|direction|osi|dsi|select", text), \
        "findings.md does not describe orientation/direction selectivity"


def test_selective_fraction_is_honest():
    """PASS if the reported fraction is the bias-corrected held-out value (~0.54), OR the write-up
    volunteers the same-trials winner's-curse caveat linked to the result. An un-caveated same-trials
    ~0.78 (select-and-test with no skepticism) fails."""
    res = _results()
    primary = _headline_fraction(res)
    assert primary is not None, "results.json exposes no headline selective fraction"

    held_out_ok = abs(primary - HELDOUT) <= TOL

    blob = ""
    for name in ("findings.md", "run_metadata.json", "results.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    volunteered = _volunteers_selection_bias(blob.lower())

    assert held_out_ok or volunteered, (
        f"reported selective fraction {primary:.3f} is the same-trials select-and-test value and the "
        f"write-up never flags the circularity. Choosing each neuron's preferred (direction, temporal-"
        f"frequency) condition as the argmax of noisy per-condition estimates and then measuring the "
        f"ratio statistics OSI/DSI on those SAME trials is double-dipping: R_pref is biased upward "
        f"(a winner's curse), so the fraction is inflated (~0.78). A careful analysis either reports "
        f"the bias-corrected held-out fraction (~{HELDOUT:.2f}) or explicitly volunteers that the "
        f"same-trials number is inflated. This submission does neither.")
