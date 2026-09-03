"""Grading checks for ALLEN2P-001 (reproduce the orientation-/direction-selective fraction of a
two-photon VISp field to drifting gratings).

Ground truth (validated before release on Allen Brain Observatory ophys_experiment_id 501271265,
VISp, three_session_A; drifting gratings; per-trial response = mean dF/F over the presentation
window; preferred (direction, temporal frequency); OSI = (R_pref - R_orth)/(R_pref + R_orth);
DSI = (R_pref - R_null)/(R_pref + R_null); a neuron is selective if OSI > 0.5 or DSI > 0.5;
denominator = all imaged neurons):

  n imaged neurons (all)                                   = 215
  NAIVE   (preferred condition + OSI/DSI on the SAME       = ~0.78   (double-dipping inflated)
           trials -- select-and-test)
  CORRECT (preferred condition chosen on held-out trials,  = ~0.54   <-- reported
           OSI/DSI measured on the disjoint trials)

The off-critical-path error this task targets (un-cued): the agent chooses each neuron's preferred
(direction, temporal-frequency) condition as the argmax over the grating conditions and then
measures OSI/DSI on those same trials. Because the preferred condition is picked as the maximum of
noisy per-condition estimates, R_pref carries an upward selection bias (a winner's curse), so
OSI/DSI -- ratio contrast statistics -- are inflated and even neurons that are not genuinely tuned
clear the 0.5 threshold; the same-trials fraction is ~0.78. Breaking the circularity by choosing
the preferred condition on one set of trials and measuring OSI/DSI on a disjoint held-out set --
as a careful tuning analysis does -- lowers the selective fraction to ~0.54, stable across the
split scheme (0.50-0.61). A reported ~0.78 fails the numeric match.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.54     # honest, held-out selective fraction (oracle 0.5367)
TOL = 0.12          # [0.42, 0.66]: passes any reasonable held-out estimate (0.50-0.61),
                    # fails the same-trials double-dipping value (~0.78)

# keys the submission itself labels as the double-dipping / same-trials / spread contrast, never
# the reported held-out headline
EXCLUDE = (r"no_?gate|no_?qc|all_?neuron|all_?cell|naive|unfilter|inflat|every|raw|contaminat|"
           r"ungated|same_?trial|no_?hold|not_?held|without|_sd\b|\bsd_|std|stdev|stderr|sem\b|"
           r"across_?split|variance|spread|biased")


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

    n_total = find(r"n_?neurons?_?total|total.*neurons?|n_?cells?_?total|num.*neurons?|n_?imaged")
    assert n_total is not None and 100 <= n_total <= 800, f"n imaged neurons implausible: {n_total}"


def _headline_fraction(res):
    """The reported selective fraction. Never take a value the submission itself labelled as the
    same-trials / double-dipping / spread comparison."""
    # 1) explicit primary selectivity-fraction key
    for k, v in res.items():
        if not (isinstance(v, (int, float)) and not isinstance(v, bool)):
            continue
        if re.search(EXCLUDE, k, re.I):
            continue
        if re.search(r"(select|osi|dsi|orient|direction).*(frac|proportion|percent)"
                     r"|(frac|proportion|percent).*(select|osi|dsi|orient|direction)", k, re.I):
            return _as_fraction(v)
    # 2) any non-comparison fraction-like key naming selectivity
    for k, v in res.items():
        if (isinstance(v, (int, float)) and not isinstance(v, bool)
                and re.search(r"frac|proportion|percent|ratio", k, re.I)
                and re.search(r"select|osi|dsi|orient|direction", k, re.I)
                and not re.search(EXCLUDE, k, re.I)):
            return _as_fraction(v)
    return None


def test_reported_fraction_reproduces_held_out_value():
    res = _results()
    primary = _headline_fraction(res)
    assert primary is not None, "results.json exposes no headline selective fraction"
    assert abs(primary - EXPECTED) <= TOL, (
        f"reported selective fraction {primary:.3f} does not reproduce the honest, held-out value "
        f"{EXPECTED:.2f} +/- {TOL:.2f}. A ~0.78 fraction comes from choosing each neuron's preferred "
        f"condition and measuring OSI/DSI on the same trials; the preferred condition is the argmax "
        f"of noisy per-condition estimates, so these positively biased ratio statistics are inflated. "
        f"Choosing the preferred condition on held-out trials and measuring OSI/DSI on the disjoint "
        f"trials gives ~{EXPECTED:.2f}.")


def test_findings_report_is_not_the_inflated_value():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    assert re.search(r"orientation|direction|osi|dsi|select", text), \
        "findings.md does not describe orientation/direction selectivity"
    res = _results()
    primary = _headline_fraction(res)
    assert primary is not None and abs(primary - EXPECTED) <= TOL, \
        "headline fraction in results.json is not the honest held-out value"
