"""Grading checks for PETVT-001.

Ground truth (established in Step-0 on the PETPrep-extracted regional TACs + arterial blood
of OpenNeuro ds005619, [18F]SF51 TSPO, 7 human participants; reproduces the ds005619 source
study, Yan et al.):

  cerebral-cortex V_T (Logan, metabolite-corrected decay-referenced arterial plasma input)
    sf02 1.067  sf05 0.628  sf06 0.999  sf07 0.781  sf08 0.456  sf09 0.523  sf10 1.127
    cohort mean 0.797 mL.cm-3, max/min 2.47x.
  Ichise MA1 agrees to ~1% (mean 0.793); V_T is stable across the graphical linear-phase
  start t* (20-60 min mean 0.782-0.820), i.e. estimator- and window-invariant once the
  input is correct.

The published headline this reproduces: [18F]SF51 has NOTABLY LOW brain V_T (< 1) while
remaining sensitive to the TSPO rs6971 polymorphism (~2x V_T range across affinity
genotypes).

The un-cued judgement is how the model input is built from the blood recording. V_T is
defined against the metabolite-corrected arterial PLASMA of the intact parent radioligand,
placed on the same decay footing as the (decay-corrected) tissue TACs. Naive inputs that
"look reasonable" give the WRONG cohort V_T -- and, revealingly, an even more "< 1"-looking
number that seems to confirm the paper:
    whole-blood input                -> cohort mean 0.448  (~-44%)
    plasma without parent-fraction   -> cohort mean 0.514  (~-35%)
    plasma not decay-corrected       -> cohort mean 1.011  (~+27%, and Logan fails to plateau)
Only the metabolite-corrected, decay-referenced arterial plasma reproduces V_T ~ 0.80 with
Logan/MA1 agreement. A magnitude band therefore separates the correct input construction
from the naive ones mechanically, not by keyword.
"""
import csv
import json
import os
import re
from pathlib import Path

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _rows():
    p = OUT / "vt_estimates.csv"
    assert p.exists(), "vt_estimates.csv not found"
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert rows, "vt_estimates.csv has no rows"
    return rows


def _vt_values():
    """Pull the cortical V_T estimates, tolerating column-name variation and, when a
    target/region column is present, restricting to the cortical rows."""
    rows = _rows()
    hdr = list(rows[0].keys())

    def norm(s):
        return re.sub(r"[^a-z0-9]", "", s.lower())

    # locate the V_T column (VT / V_T / vt / distribution_volume / VT_logan ...),
    # never the MA1 cross-check column when a primary VT column exists.
    def is_vt(name):
        s = norm(name)
        if s in ("vt", "vtlogan", "vtmlcm3", "distributionvolume", "totaldistributionvolume"):
            return True
        return s.startswith("vt") and "ma1" not in s and "ref" not in s
    vt_cols = [c for c in hdr if is_vt(c)]
    if not vt_cols:
        vt_cols = [c for c in hdr if norm(c).startswith("vt")]
    assert vt_cols, f"no V_T column found in {hdr}"
    col = vt_cols[0]

    # if a target/region column exists, keep the cortical rows
    tgt_col = next((c for c in hdr if norm(c) in ("target", "region", "targetregion", "roi")), None)
    use = rows
    if tgt_col is not None:
        cort = [r for r in rows if re.search(r"cort", (r.get(tgt_col) or ""), re.I)]
        if len(cort) >= 6:
            use = cort

    vals = []
    for r in use:
        try:
            vals.append(float(r.get(col, "")))
        except (TypeError, ValueError):
            continue
    return vals


def _text():
    blob = ""
    for name in ("findings.md", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    p = OUT / "vt_estimates.csv"
    if p.exists():
        blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


def test_vt_estimates_present():
    vals = _vt_values()
    assert len(vals) >= 6, f"expected cortical V_T for the ~7-participant cohort, got {len(vals)}"
    assert all(0.2 <= v <= 1.6 for v in vals), \
        f"cortical V_T outside a physiologically plausible [18F]SF51 range: {vals}"
    # an invasive V_T estimator must actually be named (not a bare SUV / ratio)
    txt = _text()
    assert re.search(r"logan|ichise|\bma1\b|multilinear|distribution volume|\bv_?t\b|"
                     r"two[- ]?tissue|2[- ]?tcm|compartment|graphical", txt), \
        "no invasive V_T estimator (Logan / MA1 / 2TCM) is named anywhere"


def test_reproduces_cortical_vt():
    import statistics
    vals = _vt_values()
    mean = statistics.fmean(vals)
    ratio = max(vals) / min(vals) if min(vals) > 0 else 1.0
    # reproduction: the cohort-average cortical V_T is low, in the band that only the
    # metabolite-corrected, decay-referenced arterial-plasma input yields (Logan/MA1,
    # full acquisition). Whole-blood (0.45), no-metabolite (0.51) and no-decay (1.01)
    # inputs fall outside this band.
    assert 0.68 <= mean <= 0.92, (
        f"cohort-mean cortical V_T {mean:.3f} not in the validated [18F]SF51 band "
        "[0.68, 0.92] mL.cm-3. Values well below indicate a whole-blood input or a missing "
        "parent-fraction (metabolite) correction; values above indicate an arterial input "
        "left on a different decay footing than the tissue TACs. Only the metabolite-"
        "corrected, decay-referenced arterial PLASMA reproduces the published low V_T.")
    # per-participant V_T spans the ~2x genotype range (a real, varying per-subject estimate,
    # not a constant or a bogus fill).
    assert ratio >= 1.6, (
        f"per-participant V_T spread (max/min {ratio:.2f}) too small to be the real cohort; "
        "the source study shows an ~2x V_T range across TSPO rs6971 genotypes.")


def test_input_construction_justified():
    # The un-cued judgement: V_T from an invasive model is only as good as its input
    # function, and for a TSPO ligand the input is the metabolite-corrected arterial PLASMA
    # of the intact parent -- NOT whole blood, and NOT total plasma. An honest report states
    # its input AS A CONSIDERED CHOICE (the parent/metabolite correction, or that V_T depends
    # on the input definition) -- not merely "we used the arterial input" (pipeline
    # vocabulary, the same false-positive class guarded against in SOCIALBRAIN / DEVCONN).
    text = _text()
    names_input = re.search(r"plasma|arterial|input function|blood", text)
    considered = re.search(
        # the parent / metabolite correction, explicitly
        r"metabolit|parent[- ]?fraction|parent fraction|intact (?:parent|tracer|radio)|"
        r"radiometabolit|hplc|free[- ]?fraction"
        # or linking plasma/input to being metabolite/parent-corrected
        r"|(?:plasma|input)[^.\n]{0,40}(?:parent|metabolit|corrected|intact)"
        r"|(?:parent|metabolit|corrected|intact)[^.\n]{0,40}(?:plasma|input)"
        # or explicitly reasoning that whole-blood / uncorrected is NOT the input / biases V_T
        r"|(?:whole[- ]?blood|uncorrected|total plasma)[^.\n]{0,50}"
        r"(?:not the input|differ|bias|wrong|instead|lower|higher|overestimat|underestimat)"
        # or that V_T depends on the input definition / construction
        r"|(?:input|plasma)[^.\n]{0,40}(?:choice|definition|construction|depend|differ|matters)",
        text)
    assert names_input and considered, (
        "findings.md does not justify the model input as a considered choice. For [18F]SF51 "
        "the invasive V_T is defined against the METABOLITE-CORRECTED arterial PLASMA of the "
        "intact parent (whole blood and uncorrected total plasma give different, biased V_T); "
        "the report should state the parent-fraction (metabolite) correction it applied and "
        "that V_T depends on that input definition, not merely that 'the arterial input' was "
        "used.")
