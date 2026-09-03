"""Grading checks for PETREF-001.

Ground truth (established in Step-0 on the PETPrep-derived regional TACs of OpenNeuro
ds001420, [11C]DASB test-retest, 2 participants x test/retest):

  putamen BP_ND (SRTM, cerebellar gray-matter reference)
    sub-01 base 1.910   sub-01 rescan 1.961   sub-02 base 1.890   sub-02 rescan 1.918
    mean 1.920, test-retest ~2-3%.
  SRTM, Logan-ref and Ichise MRTM agree to ~2% (1.90-1.99).
  Whole-cerebellum reference (the pre-computed `reference` column, which folds in
    cerebellar white matter + vermis) gives ~1.86, ~3% lower -- a real, un-cued
    reference-region choice.

A correct answer (1) does proper reference-tissue kinetic modelling -> BP_ND ~1.9 that
is REPRODUCIBLE across the four scans, and (2) reports its reference region as a
considered choice for this tracer (cerebellar gray matter, not whole cerebellum).

The shortcut this rules out: a non-kinetic target/reference "SUV ratio - 1" on this
~54-min (non-equilibrium) scan gives per-scan values that scatter widely
(2.18/2.04/1.61/1.72; coefficient of variation ~13% vs ~2% for real BP_ND), so a
clustering/reproducibility check separates kinetic modelling from a ratio.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _bp_values():
    """Pull the four putamen BP_ND estimates from bp_estimates.csv, tolerating
    reasonable column-name variation."""
    p = OUT / "bp_estimates.csv"
    assert p.exists(), "bp_estimates.csv not found"
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert rows, "bp_estimates.csv has no rows"
    # locate the BP column (BP_ND / BPnd / binding_potential / bp ...)
    def is_bp(name):
        s = re.sub(r"[^a-z]", "", name.lower())
        return s in ("bpnd", "bp", "bindingpotential", "bpndputamen") or \
            ("bp" in s and "logan" not in s and "mrtm" not in s and "srtm" not in s and s.startswith("bp"))
    hdr = rows[0].keys()
    bp_cols = [c for c in hdr if is_bp(c)]
    assert bp_cols, f"no BP_ND column found in {list(hdr)}"
    col = bp_cols[0]
    vals = []
    for r in rows:
        v = r.get(col, "")
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            continue
    return vals


def _text():
    blob = ""
    for name in ("findings.md", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


def test_bp_estimates_present():
    vals = _bp_values()
    assert len(vals) >= 4, f"expected BP_ND for all four scans, got {len(vals)}"
    assert all(0.8 <= v <= 3.0 for v in vals[:4]), \
        f"putamen BP_ND outside a physiologically plausible [11C]DASB range: {vals[:4]}"
    # a reference-tissue MODEL must actually have been used (not a bare ratio)
    txt = _text() + "\n" + (OUT / "bp_estimates.csv").read_text(encoding="utf-8").lower()
    assert re.search(r"srtm|simplified reference|mrtm|logan|reference[- ]?tissue|"
                     r"lammertsma|ichise", txt), \
        "no reference-tissue model (SRTM/MRTM/Logan-ref) is named anywhere"


def test_reproduces_putamen_bp():
    import statistics
    vals = _bp_values()[:4]
    mean = statistics.fmean(vals)
    sd = statistics.pstdev(vals)
    cv = sd / mean if mean else 1.0
    # reproduction: mean BP_ND in the cross-model-validated band (covers SRTM/Logan/MRTM
    # with either whole-cerebellum or cerebellar-GM reference: 1.83-1.99)
    assert 1.65 <= mean <= 2.20, \
        f"mean putamen BP_ND {mean:.3f} not in the validated [11C]DASB range [1.65, 2.20]"
    # BP_ND is reproducible across these test-retest scans (~2% CV); a non-kinetic
    # SUV-ratio on this non-equilibrium scan scatters (~13% CV) and fails here.
    assert cv < 0.08, (
        f"the four putamen estimates scatter too much (CV {cv:.1%}) to be reference-tissue "
        "BP_ND -- a target/reference SUV ratio on this ~54-min scan is not at equilibrium "
        "and is not reproducible across scans; use a kinetic reference-tissue model")


def test_reference_region_justified():
    # The un-cued judgement: a reference-tissue BP_ND is only as good as its reference
    # region, and for [11C]DASB the whole cerebellum (which folds in cerebellar white
    # matter and the vermis) is not the same as cerebellar gray matter. An honest report
    # states its reference region AS A CONSIDERED CHOICE for this tracer -- not merely
    # "I used the cerebellum" (which is pipeline vocabulary, the same false-positive class
    # as SOCIALBRAIN's GSR / DEVCONN's motion). It must show the sub-region distinction or
    # say the estimate depends on the reference definition.
    text = _text()
    names_ref = re.search(r"cerebell", text)
    # a considered reference choice: a gray/white/vermis/cortex distinction, OR an explicit
    # statement that the reference-region definition/choice affects the estimate.
    considered = re.search(
        r"gr[ae]y[- ]?matter|white[- ]?matter|\bvermis\b|cortex only|cerebellar cortex"
        r"|whole cerebellum|reference[^.\n]{0,40}(choice|definition|selection|depend|differ|matters)"
        r"|(choice|definition|selection|depend|differ)[^.\n]{0,40}reference", text)
    assert names_ref and considered, (
        "findings.md does not justify the reference region as a considered choice for "
        "[11C]DASB. Naming 'the cerebellum reference' is not enough: the whole cerebellum "
        "(white matter + vermis) differs from cerebellar gray matter, and the report should "
        "say which was used and that BP_ND depends on that reference-region definition.")
