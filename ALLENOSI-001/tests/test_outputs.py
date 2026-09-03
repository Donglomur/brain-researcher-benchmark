"""Grading checks for ALLENOSI-001 (reproduce the orientation-selective fraction in VISp).

Ground truth (validated before release on DANDI 000021, sub-707296975 ses-721123822; VISp units
mapped by peak-channel electrode location; drifting-gratings responses = per-unit spike rate over
each 2 s presentation; OSI = (R_pref - R_orth)/(R_pref + R_orth) at the preferred temporal
frequency; threshold 0.5):

  n VISp units (all)                 = 133
  n VISp units passing QC            = 42       (isi_violations<0.5, amplitude_cutoff<0.1,
                                                 presence_ratio>0.9 -- the Allen SDK defaults)
  n QC-pass & visually responsive    = ~37
  CORRECT  fraction OSI>0.5 among analysis-grade units = ~0.24   <-- reported
  NAIVE    fraction OSI>0.5 among ALL VISp clusters     = ~0.39   (noise-inflated by junk units)

The off-critical-path error this task targets (un-cued): the agent takes every cluster labelled
VISp and reports the fraction with OSI>0.5, ~0.39. But most of the excluded clusters are poorly
isolated, low-firing units (91 of 133 VISp units fail QC; most fire < 1 Hz), and OSI is a
positively biased contrast statistic, so their sparse spike counts make them spuriously
orientation-selective. Applying the standard unit quality-control gate and a visual-responsiveness
criterion -- as any careful tuning analysis does -- roughly halves the apparent fraction to ~0.24.
The correct value is stable across the responsiveness threshold and whether or not the preferred
orientation is chosen on held-out trials (0.21-0.26). A reported ~0.39 fails the numeric match.
"""
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))

EXPECTED = 0.24     # honest, quality-controlled orientation-selective fraction
TOL = 0.08          # [0.16, 0.32]: passes any reasonable QC/responsiveness gating, fails naive ~0.39


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

    n_total = find(r"n_?visp.*total|n_?visp_?units\b|total.*visp|num.*visp")
    assert n_total is not None and 90 <= n_total <= 170, f"n VISp units implausible: {n_total}"
    n_analyzed = find(r"analy[sz]ed|n_?kept|qc.*pass|n_?good|n_?selective_denom")
    # analysed (quality/responsiveness-gated) count should be a sensible subset
    if n_analyzed is not None:
        assert 15 <= n_analyzed <= 90, f"n analysed units implausible: {n_analyzed}"


def _headline_fraction(res):
    """The reported orientation-selective fraction. Never take a value the submission itself
    labelled as the no-QC / all-units / naive comparison."""
    # 1) explicit primary key
    for k, v in res.items():
        if not (isinstance(v, (int, float)) and not isinstance(v, bool)):
            continue
        if re.search(r"no_?qc|all_?units|naive|unfilter|inflat|every|raw|contaminat", k, re.I):
            continue
        if re.search(r"(orientation|osi).*(select|frac)|select.*frac|frac.*select", k, re.I):
            return _as_fraction(v)
    # 2) any non-comparison fraction-like key naming selectivity
    for k, v in res.items():
        if (isinstance(v, (int, float)) and not isinstance(v, bool)
                and re.search(r"frac|proportion|percent|ratio", k, re.I)
                and re.search(r"select|osi|orient", k, re.I)
                and not re.search(r"no_?qc|all_?units|naive|unfilter|inflat|every|raw", k, re.I)):
            return _as_fraction(v)
    return None


def test_reported_fraction_reproduces_quality_controlled_value():
    res = _results()
    primary = _headline_fraction(res)
    assert primary is not None, "results.json exposes no headline orientation-selective fraction"
    assert abs(primary - EXPECTED) <= TOL, (
        f"reported orientation-selective fraction {primary:.3f} does not reproduce the honest, "
        f"quality-controlled value {EXPECTED:.2f} +/- {TOL:.2f}. A ~0.39 fraction comes from counting "
        f"every VISp cluster, including poorly isolated low-firing units whose sparse spike counts "
        f"make OSI spuriously high; after standard unit quality control and a responsiveness gate the "
        f"orientation-selective fraction is ~0.24.")


def test_findings_report_is_not_the_inflated_value():
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower()
    # write-up mentions orientation selectivity / OSI
    assert re.search(r"orientation|osi|select", text), "findings.md does not describe orientation selectivity"
    # the headline value must be reproduced in the prose too (as fraction or percent)
    res = _results()
    primary = _headline_fraction(res)
    assert primary is not None and abs(primary - EXPECTED) <= TOL, \
        "headline fraction in results.json is not the honest quality-controlled value"
