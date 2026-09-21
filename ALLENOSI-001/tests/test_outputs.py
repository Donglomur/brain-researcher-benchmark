"""Proof-of-work grader for ALLENOSI-001 (orientation-selective fraction of VISp).

The deliverable is one fraction, but the analysis naturally produces a per-unit OSI. The grader
validates that NEUTRAL per-unit table (units.csv: unit_id, osi -- produced by both a naive and an
honest run) against a held-out reference (tests/reference.npz, built from the oracle run, never
shipped to the agent), then RECOMPUTES the honest quality-controlled selective fraction from the
submitted OSI using the held-out QC/responsiveness flags.

Ground truth (DANDI 000021, sub-707296975 ses-721123822, VISp, drifting gratings, OSI at the
preferred temporal frequency, threshold 0.5):
  n VISp units = 133 ; QC-pass & responsive = 37
  CORRECT  (QC + responsive)             fraction OSI>0.5 = 0.24   <-- reported
  NAIVE    (all VISp clusters, no gate)  fraction OSI>0.5 = 0.39   (noise-inflated by junk units)

Off-critical-path error (un-cued): Neuropixels recordings contain many poorly isolated, low-firing
clusters; OSI is a positively biased contrast statistic, so sparse-spike clusters get spuriously
high OSI. Counting every VISp cluster roughly doubles the apparent selective fraction. The honest
fraction (quality-controlled, visually responsive) is ~0.24, not ~0.39.

Pillars:
  1. per-unit OSI table covers the real VISp units, non-constant, matches the held-out reference
     (cross-unit r>=0.95 and per-unit agreement) -- proof the OSI were really computed
  2. recompute the honest QC-gated fraction FROM the submitted OSI with the held-out QC flags ==
     reference == reported headline; the naive all-units recompute reproduces ~0.39
  3. discriminating recognition (fail if absent): the honest analysis recognises that unfiltered
     low-quality clusters inflate the fraction (a volunteered all-units ~0.39 OR prose)
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

FRAC_BAND = (0.12, 0.33)      # honest QC-gated fraction ~0.24; fails the naive all-units ~0.39
REF_TOL = 0.05               # recompute-from-submitted-OSI vs held-out reference
JSON_TOL = 0.05              # honest recompute vs reported headline


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _results():
    p = OUT / "results.json"
    assert p.exists(), "missing required output results.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _submitted_units():
    p = OUT / "units.csv"
    assert p.exists(), (
        "missing required output units.csv -- the per-unit orientation selectivity index (unit_id, "
        "osi) for the VISp units. The single fraction cannot be validated without the per-unit "
        "table it is computed from.")
    return pw.load_submitted_units(p)


def _headline(res):
    return pw.find_number(
        res, [r"orientationselectivefraction", r"selectivefraction", r"fractionselective",
              r"osifraction", r"fraction", r"selective"],
        exclude=[r"allunits", r"noqc", r"nogate", r"naive", r"inflat", r"threshold", r"osidef",
                 r"total", r"nvisp", r"count"])


def test_outputs_present_and_wellformed():
    _reference()
    res = _results()
    hl = _headline(res)
    assert hl is not None, f"results.json exposes no orientation_selective_fraction: {res}"
    assert 0.0 <= hl <= 1.0, f"selective fraction {hl} out of range"
    units = _submitted_units()
    assert len(units) >= 20, f"units.csv covers too few VISp units ({len(units)})"


def test_proof_of_work_per_unit_osi_matches_reference():
    ref = _reference()
    units = _submitted_units()
    pw.check_units_and_osi(units, ref)


def test_recompute_qc_gated_fraction_from_submitted_osi():
    ref = _reference()
    units = _submitted_units()
    res = _results()
    honest, naive = pw.recompute_fractions(units, ref, thr=float(ref["stats"]["osi_threshold"]))
    ref_correct = float(ref["stats"]["frac_correct"])
    ref_naive = float(ref["stats"]["frac_naive"])
    # recompute from the submitted OSI + held-out QC flags reproduces the honest reference fraction
    assert abs(honest - ref_correct) <= REF_TOL, (
        f"the quality-controlled selective fraction recomputed from the submitted per-unit OSI "
        f"({honest:.3f}) does not match the held-out reference ({ref_correct:.3f}); the OSI values "
        f"are not the real per-unit results.")
    # sanity: the all-units recompute reproduces the (inflated) naive fraction
    assert abs(naive - ref_naive) <= REF_TOL + 0.03, (
        f"the all-units selective fraction recomputed from the submitted OSI ({naive:.3f}) does "
        f"not match the reference all-units value ({ref_naive:.3f})")
    # the reported headline must be the honest QC-gated fraction (recomputed), not the inflated one
    hl = _headline(res)
    assert hl is not None and abs(hl - honest) <= JSON_TOL, (
        f"reported orientation_selective_fraction ({hl}) does not equal the quality-controlled "
        f"fraction recomputed from the submitted OSI ({honest:.3f}); results.json disagrees with "
        f"the per-unit table (or reports the inflated all-clusters value ~{ref_naive:.2f}).")


def test_headline_in_honest_band():
    ref = _reference()
    res = _results()
    hl = _headline(res)
    lo, hi = FRAC_BAND
    assert hl is not None and lo <= hl <= hi, (
        f"reported orientation-selective fraction {hl} is not the honest quality-controlled value "
        f"(~{ref['stats']['frac_correct']:.2f}, band [{lo},{hi}]). Counting every VISp cluster with "
        f"no quality-control / responsiveness gate roughly doubles it to ~{ref['stats']['frac_naive']:.2f}.")


def test_quality_control_recognised():
    """Discriminating recognition, fail if absent (DEVCONN way): the honest analysis recognises
    that unfiltered, poorly isolated / low-firing clusters spuriously inflate the OSI fraction --
    by reporting the inflated all-units value as a contrast, or by stating it in the write-up."""
    ref = _reference()
    res = _results()
    ref_naive = float(ref["stats"]["frac_naive"])
    naive_num = pw.find_number(
        res, [r"allunits", r"noqc", r"nogate", r"naive", r"inflat", r"unfiltered", r"allcluster",
              r"beforeqc", r"withoutqc"],
        exclude=[r"threshold", r"total", r"count", r"nvisp"])
    has_number = naive_num is not None and abs(naive_num - ref_naive) <= 0.08
    text = (OUT / "findings.md").read_text(encoding="utf-8").lower() if (OUT / "findings.md").exists() else ""
    QC = (r"quality[- ]?control|\bqc\b|isi[_ ]?violation|amplitude[_ ]?cutoff|presence[_ ]?ratio|"
          r"well[- ]?isolated|poorly[- ]?isolated|spike[- ]?sort|unit quality|low[- ]?firing|"
          r"low firing|few spikes|sparse spik|responsiv|analysis-?grade|junk|noise")
    EFFECT = (r"inflat|overestimat|over-?estimat|spurious|bias|doubl\w*|too high|higher|"
              r"artifact|artefact|exclud\w*|filter\w*|gate|remov\w*|drop\w*|reduc\w*")
    prose = bool(re.search(QC + r"[^\n]{0,120}(?:" + EFFECT + ")", text) or
                 re.search("(?:" + EFFECT + r")[^\n]{0,120}(?:" + QC + ")", text))
    assert has_number or prose, (
        "the submission does not recognise that unfiltered, poorly isolated / low-firing clusters "
        "inflate the orientation-selective fraction (OSI is positively biased for sparse-spike "
        f"units). Counting every VISp cluster gives ~{ref_naive:.2f} vs the quality-controlled "
        f"~{ref['stats']['frac_correct']:.2f}. A flat fraction with no quality-control recognition "
        "misses the issue this result has.")
