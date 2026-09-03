"""Grading checks for PETCOX-001.

Ground truth (established in Step-0 on the petfit-extracted regional TACs + arterial blood of
OpenNeuro ds004869, [11C]MC1 COX-2, 27 human participants at their baseline scan; reproduces
the dataset's petfit reference):

  cerebral-cortex V_T (metabolite-corrected arterial-plasma input), cohort mean, by estimator
    Logan graphical (t* = 20 min)      2.174
    Ichise MA1 (cross-check)           2.156
    2-tissue compartment (petfit ref)  ~2.14
  Per-participant cortical V_T spans ~1.6 - 2.9 (max/min ~2.0). Logan and MA1 agree to ~1%,
  i.e. once a model adequate to the tracer's kinetics is used, V_T is estimator-invariant.

The un-cued judgement is the MODEL ORDER. [11C]MC1 cortical TACs have an early peak and a
slow tail that a single tissue compartment cannot follow. A 1-tissue-compartment (1TCM) fit
still converges and looks reasonable, but it under-estimates cortical V_T by roughly a third:

    1TCM cohort-mean cortical V_T  ~1.45   (~ -33 %)

Two tissue compartments -- or, equivalently, the model-order-independent graphical estimators
(Logan / MA1) -- are required, and they agree with the 2TCM reference at ~2.15. A secondary
wrong choice, fitting the Logan plot over all frames including the early curved phase, biases
V_T to ~1.86. A magnitude band therefore separates a model adequate to the tracer (~2.15)
from the under-fitting 1TCM (~1.45) and the all-frames graphical error (~1.86) mechanically,
not by keyword.
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
    """Cortical V_T estimates, tolerating column-name variation and restricting to cortical
    rows when a target/region column is present. Never the MA1 cross-check column."""
    rows = _rows()
    hdr = list(rows[0].keys())

    def norm(s):
        return re.sub(r"[^a-z0-9]", "", s.lower())

    def is_vt(name):
        s = norm(name)
        if s in ("vt", "vtlogan", "vtmlcm3", "distributionvolume", "totaldistributionvolume"):
            return True
        return s.startswith("vt") and "ma1" not in s and "ref" not in s and "1tcm" not in s
    vt_cols = [c for c in hdr if is_vt(c)]
    if not vt_cols:
        vt_cols = [c for c in hdr if norm(c).startswith("vt")]
    assert vt_cols, f"no V_T column found in {hdr}"
    col = vt_cols[0]

    tgt_col = next((c for c in hdr if norm(c) in ("target", "region", "targetregion", "roi")), None)
    use = rows
    if tgt_col is not None:
        cort = [r for r in rows if re.search(r"cort", (r.get(tgt_col) or ""), re.I)]
        if len(cort) >= 10:
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
    assert len(vals) >= 20, \
        f"expected cortical V_T for the ~27-participant cohort, got {len(vals)}"
    assert all(0.5 <= v <= 6.0 for v in vals), \
        f"cortical V_T outside a plausible [11C]MC1 range: {vals}"
    # an arterial-input kinetic V_T estimator must actually be named (not a bare SUV / ratio)
    txt = _text()
    assert re.search(r"logan|ichise|\bma1\b|multilinear|distribution volume|\bv_?t\b|"
                     r"two[- ]?tissue|2[- ]?tcm|compartment|graphical|kinetic", txt), \
        "no arterial-input kinetic V_T estimator (Logan / MA1 / 2TCM) is named anywhere"


def test_reproduces_cortical_vt():
    import statistics
    vals = _vt_values()
    mean = statistics.fmean(vals)
    ratio = max(vals) / min(vals) if min(vals) > 0 else 1.0
    # Reproduction: with a kinetic model adequate to [11C]MC1 (two tissue compartments, or a
    # model-order-independent graphical estimator), the cohort-mean cortical V_T is ~2.15
    # (Logan 2.17 / MA1 2.16 / 2TCM ~2.14). A 1-tissue-compartment fit under-estimates it to
    # ~1.45, and regressing the whole Logan plot from t=0 biases it to ~1.86 -- both below the
    # band; a grossly over-estimating input error lands above it.
    assert 1.90 <= mean <= 2.60, (
        f"cohort-mean cortical V_T {mean:.3f} is outside the validated band [1.90, 2.60] "
        "mL.cm-3. A value near ~1.45 means a single-tissue-compartment (1TCM) fit was used, "
        "which cannot follow the tracer's two-phase kinetics and under-estimates V_T by ~a "
        "third; a value near ~1.86 means the Logan plot was regressed over all frames "
        "including the early, pre-equilibrium phase. Use a two-tissue-compartment model, or "
        "the model-order-independent graphical estimators (Logan/MA1), which agree at ~2.15.")
    # a real, per-participant estimate varies across the cohort (not a constant / fill)
    assert ratio >= 1.4, (
        f"per-participant cortical V_T spread (max/min {ratio:.2f}) is too small to be the "
        "real 27-participant cohort (the dataset spans an ~2x range).")


def test_kinetic_analysis_reported():
    # A genuine arterial-input kinetic analysis must be reported (the estimator/model named,
    # co-occurring with an actual V_T result) -- not a bare number, an SUV, or a tissue ratio.
    # This is the false-positive class the shipped PET/rs-fMRI tasks guard against: naming a
    # pipeline step is not enough; the kinetic estimator must accompany a reported V_T.
    text = _text()
    estimator = re.search(r"logan|ichise|\bma1\b|multilinear|two[- ]?tissue|2[- ]?tcm|"
                          r"compartment|graphical|distribution volume|\bv_?t\b", text)
    has_result = re.search(r"v_?t\s*[=:]?\s*\d|distribution volume[^.\n]{0,40}\d\.\d|"
                           r"cohort[^.\n]{0,30}\d\.\d|mean[^.\n]{0,30}\d\.\d|\d\.\d+\s*ml", text)
    assert estimator and has_result, (
        "findings/run_metadata do not report an arterial-input kinetic V_T analysis with a "
        "result. Name the kinetic estimator/model used (Logan / MA1 / two-tissue "
        "compartment) and report the cortical V_T it produced.")
