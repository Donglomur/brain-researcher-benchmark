"""Proof-of-work grader for ALLENCONN-001 (self-strongest fraction in the mouse mesoscale connectome).

The deliverable is one fraction, but the analysis naturally produces a per-source-region indicator
(is the strongest projection target the source's own structure?). The grader validates that NEUTRAL
per-source table (source_strongest.csv -- produced by both the injection-included and the
projection-only analyses) against a held-out reference (tests/reference.npz, built from the oracle
run, never shipped to the agent), recomputes the fraction from the submitted rows, and requires the
headline to lie in the honest band that only the projection-only analysis reaches.

Ground truth (Allen Mouse Connectivity Atlas, 498 wild-type experiments, 316 summary structures,
whole-structure projection_density, source = primary injection structure -> summary ancestor):
  n source regions = 157
  CORRECT  projection signal only (is_injection=False)  fraction = 0.36   <-- reported
  NAIVE    injection-site compartments left in           fraction = 0.62   (saturated bolus artifact)

Off-critical-path error (un-cued): the structure-unionize records carry an is_injection flag; the
is_injection=True rows are saturated tracer signal INSIDE the injection site (median
projection_density ~0.82), not a projection to a target. Because the injection sits in the source's
own structure, leaving them in makes the self cell the row's largest entry for most sources -- an
artifact. The honest self-strongest fraction is ~0.36, not ~0.62.

Pillars:
  1. per-source self-strongest table covers the real sources, non-constant, matches the held-out
     projection-only reference (a matrix with injection compartments left in disagrees on ~26%)
  2. recompute the fraction from the submitted rows == reference == reported JSON
  3. headline in the honest band (fails the naive ~0.62)
  4. discriminating recognition (fail if absent): the honest analysis recognises that the
     injection-site compartments inflate the fraction (a volunteered ~0.62 OR prose)
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_of_work as pw  # noqa: E402

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).resolve().parent / "reference.npz"

FRAC_BAND = (0.27, 0.46)      # honest projection-only fraction ~0.36; fails the naive ~0.62
REF_TOL = 0.06
JSON_TOL = 0.05


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _self_projection():
    p = OUT / "self_projection.json"
    assert p.exists(), "missing required output self_projection.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _source_table():
    p = OUT / "source_strongest.csv"
    assert p.exists(), (
        "missing required output source_strongest.csv -- for each source region, its strongest "
        "target and whether that target is the source's own structure. The single fraction cannot "
        "be validated without the per-source table it is computed from.")
    return pw.load_submitted_source_table(p)


def _headline(sj):
    return pw.find_number(
        sj, [r"selfstrongestfraction", r"selffraction", r"fractionself", r"selfstrongest",
             r"selfreferential", r"fraction"],
        exclude=[r"injection", r"included", r"naive", r"inflat", r"nsource", r"nself", r"nexp",
                 r"ntarget", r"count", r"hemisphere"])


def test_outputs_present_and_wellformed():
    _reference()
    sj = _self_projection()
    hl = _headline(sj)
    assert hl is not None, f"self_projection.json exposes no self_strongest_fraction: {sj}"
    assert 0.0 <= hl <= 1.0, f"self-strongest fraction {hl} out of range"
    tab = _source_table()
    assert len(tab) >= 80, f"source_strongest.csv covers too few source regions ({len(tab)})"
    # the directed source x target matrix is a required deliverable
    mpath = OUT / "connectivity_matrix.csv"
    assert mpath.exists(), (
        "missing required output connectivity_matrix.csv -- the directed source-region x "
        "target-structure projection-strength matrix")
    import csv as _csv
    with open(mpath, encoding="utf-8") as fh:
        reader = _csv.reader(fh)
        header = next(reader, [])
        n_rows = sum(1 for _ in reader)
    assert len(header) >= 300, (
        f"connectivity_matrix.csv has {len(header)} columns; expected the 316 target summary "
        f"structures (plus an index column)")
    assert n_rows >= 80, (
        f"connectivity_matrix.csv has {n_rows} source rows; expected one per injected source region")


def test_proof_of_work_per_source_indicators_match_reference():
    ref = _reference()
    tab = _source_table()
    recomputed, matched = pw.check_per_source_indicators(tab, ref)
    # recompute the fraction FROM the submitted per-source rows == held-out reference
    ref_correct = float(ref["stats"]["frac_correct"])
    assert abs(recomputed - ref_correct) <= REF_TOL, (
        f"self-strongest fraction recomputed from the submitted per-source rows ({recomputed:.3f}) "
        f"does not match the held-out reference ({ref_correct:.3f}); the per-source indicators are "
        f"not the real projection-only result")
    # ... and == the reported JSON fraction (CSV <-> JSON consistency)
    sj = _self_projection()
    hl = _headline(sj)
    assert hl is not None and abs(hl - recomputed) <= JSON_TOL, (
        f"reported self_strongest_fraction ({hl}) does not equal the fraction recomputed from the "
        f"submitted per-source table ({recomputed:.3f}); self_projection.json and "
        f"source_strongest.csv disagree")


def test_headline_in_honest_band():
    ref = _reference()
    sj = _self_projection()
    hl = _headline(sj)
    lo, hi = FRAC_BAND
    assert hl is not None and lo <= hl <= hi, (
        f"reported self-strongest fraction {hl} is not the honest projection-only value "
        f"(~{ref['stats']['frac_correct']:.2f}, band [{lo},{hi}]). Leaving the saturated "
        f"injection-site compartments in inflates it to ~{ref['stats']['frac_naive']:.2f}.")


def test_injection_artifact_recognised():
    """Discriminating recognition, fail if absent (DEVCONN way): the honest analysis recognises
    that the saturated injection-site compartments inflate the self-strongest fraction -- by
    reporting the injection-included value as a contrast, or by stating it in the write-up."""
    ref = _reference()
    sj = _self_projection()
    ref_naive = float(ref["stats"]["frac_naive"])
    naive_num = pw.find_number(
        sj, [r"injection", r"included", r"naive", r"inflat", r"withinjection", r"uncorrected",
             r"allcompartment"],
        exclude=[r"nsource", r"nself", r"count", r"hemisphere", r"ntarget", r"nexp"])
    has_number = naive_num is not None and abs(naive_num - ref_naive) <= 0.08
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower() if (OUT / "findings.md").exists() else ""
    INJ = (r"injection[- ]?site|injection[- ]?compartment|injection bolus|is[_ ]?injection|"
           r"saturat\w*|self[- ]?injection|tracer (?:signal )?(?:inside|at|in) the injection|"
           r"source (?:site|region) (?:signal|itself)|primary injection|inside the injection")
    EFFECT = (r"inflat|overestimat|over-?estimat|spurious|artifact|artefact|bias|exclud\w*|"
              r"remov\w*|not a projection|self cell|self[- ]?strongest|drop\w*|filter\w*|"
              r"larg\w* (?:entry|value)|too high|higher")
    prose = bool(re.search(INJ + r"[^\n]{0,140}(?:" + EFFECT + ")", text) or
                 re.search("(?:" + EFFECT + r")[^\n]{0,140}(?:" + INJ + ")", text))
    assert has_number or prose, (
        "the submission does not recognise that the saturated injection-site compartments "
        "(is_injection=True; tracer signal inside the injection site, not a projection to a target) "
        f"inflate the self-strongest fraction. Leaving them in gives ~{ref_naive:.2f} vs the honest "
        f"projection-only ~{ref['stats']['frac_correct']:.2f}. A flat fraction with no recognition "
        "of the injection-site artifact misses the issue this result has.")
