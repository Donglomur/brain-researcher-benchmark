"""Proof-of-work grader for PETREF-001 (putamen BP_ND from [11C]DASB, reference-tissue kinetics).

Reproduction task: the deliverable is a per-scan putamen BP_ND table and the test-retest
summary. The un-cued shortcut is a non-kinetic SUV-ratio ("SUVR - 1") in place of a proper
reference-tissue kinetic model. A SUVR on this ~54-min (non-equilibrium) scan gets the
COHORT MEAN roughly right (1.98 vs 1.92) but its PER-SCAN values scatter wildly (1.12 / 2.51
/ 2.11 / 2.20 vs the kinetic 1.91 / 1.96 / 1.89 / 1.92). So the grader validates the
submitted per-scan BP_ND against a held-out kinetic reference (tests/reference.npz, built
from the oracle SRTM fit on the real ds001420 TACs, never shipped to the agent), recomputes
the cohort mean from the submitted rows, and grades the cohort BP_ND -- without naming
"kinetic, not SUVR" in the instruction (the QSMDIPOLE held-out-reference model).

Held-out ground truth (SRTM, cerebellar gray-matter reference):
  sub-01 base 1.910  sub-01 rescan 1.961  sub-02 base 1.890  sub-02 rescan 1.918
  mean 1.920, test-retest ~2%.  SRTM / Logan-ref / MRTM agree ~2%; whole-cerebellum
  reference ~3% lower (~1.86) -- both accepted as valid reference-tissue kinetics.
  A late-window SUVR-1 scatters 15-50% off per scan -> rejected per-item.
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

VAL_TOL_ABS = 0.17     # per-scan BP_ND vs held-out reference: accepts SRTM/Logan/MRTM/whole-ceb
VAL_TOL_REL = 0.09     # (within ~3%); rejects SUVR (>=0.18 off)
COVER = 0.9
MATCH = 0.75           # >=3/4 scans within tol (accepts a defensible variant on one scan)
MEAN_TOL_REF = 0.12
MEAN_TOL_JSON = 0.08


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _load_json(name):
    p = OUT / name
    assert p.exists(), f"missing required output {name}"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"{name} is not valid JSON: {e}")


ID_GROUPS = [(("subject", "subid", "participant", "sub"), ("session", "ses")),
             (("session", "ses"), ("subject",))]


def _submitted_map(val_cands=("bpnd", "bp", "bindingpotential", "bpputamen"),
                   val_exclude=("logan", "mrtm", "srtm", "r1", "k2", "se", "std", "sd", "suvr")):
    p = OUT / "bp_estimates.csv"
    assert p.exists(), "missing required output bp_estimates.csv (one row per scan)"
    rows, headers = pw.read_rows(p)
    assert rows, "bp_estimates.csv has no rows"
    val = pw.pick_col(headers, val_cands, exclude=val_exclude)
    if val is None and val_cands[0] == "bpnd":
        val = pw.pick_col(headers, ("bp",), exclude=("logan", "mrtm", "srtm", "r1", "k2"))
    assert val is not None, f"no {val_cands[0]} column in bp_estimates.csv: {headers}"
    return pw.build_submitted_map(rows, headers, ID_GROUPS, val)


def _test_retest_from_map(smap):
    """Recompute mean absolute test-retest % from the submitted per-scan rows."""
    import statistics
    pcts = []
    for sub in ("sub-01", "sub-02"):
        b = smap.get(pw.norm(sub) + pw.norm("ses-baseline"))
        r = smap.get(pw.norm(sub) + pw.norm("ses-rescan"))
        if b is not None and r is not None and (b + r) != 0:
            pcts.append(abs(b - r) / ((b + r) / 2.0) * 100.0)
    return statistics.fmean(pcts) if pcts else None


def test_outputs_present_and_wellformed():
    _reference()
    smap = _submitted_map()
    assert len(smap) >= 4, f"expected putamen BP_ND for all four scans, got {len(smap)}"
    assert all(0.8 <= v <= 3.0 for v in smap.values()), \
        f"putamen [11C]DASB BP_ND outside a physiological range: {list(smap.values())}"


# ---------------------------------------------------------------- pillar 1
def test_proof_of_work_per_scan_matches_reference():
    ref = _reference()
    smap = _submitted_map()
    matched = pw.match_items(smap, ref["ids"], ref["values"])
    coverage = len(matched) / len(ref["ids"])
    assert coverage >= COVER, (
        f"bp_estimates.csv covers only {coverage:.0%} of the four real ds001420 scans by id "
        f"(need >= {COVER:.0%}); fabricated or missing subject/session ids.")
    import statistics
    subvals = [s for _, s, _ in matched]
    assert statistics.pstdev(subvals) >= 0.0  # (near-constant across scans is expected here)
    close = sum(1 for _, s, r in matched if pw.within(s, r, VAL_TOL_REL, VAL_TOL_ABS))
    frac = close / len(matched)
    assert frac >= MATCH, (
        f"only {frac:.0%} of matched scans are within tolerance of the held-out kinetic "
        f"reference BP_ND (need >= {MATCH:.0%}). The per-scan values do not match a reference-"
        f"tissue kinetic model -- a non-kinetic SUV-ratio scatters 15-50% off per scan.")


# ---------------------------------------------------------------- pillar 2
def test_recompute_cohort_mean():
    import statistics
    ref = _reference()
    smap = _submitted_map()
    matched = pw.match_items(smap, ref["ids"], ref["values"])
    mean_rows = statistics.fmean([s for _, s, _ in matched])
    mean_ref = float(ref["stats"]["mean_srtm"])
    assert abs(mean_rows - mean_ref) <= MEAN_TOL_REF, (
        f"mean putamen BP_ND recomputed from the submitted rows ({mean_rows:.3f}) does not "
        f"match the held-out kinetic reference ({mean_ref:.3f}, tol {MEAN_TOL_REF})")
    reported = pw.find_number(_load_json("run_metadata.json"),
                              [r"bpndmean", r"meanbp", r"putamenbpndmean", r"bp.*mean", r"mean.*bp"],
                              exclude=[r"logan", r"mrtm", r"perscan", r"testretest", r"pct"])
    if reported is None:
        reported = pw.find_number(_load_json("run_metadata.json"), [r"mean"],
                                  exclude=[r"logan", r"mrtm", r"pct", r"retest"])
    assert reported is not None and abs(mean_rows - reported) <= MEAN_TOL_JSON, (
        f"mean BP_ND recomputed from the rows ({mean_rows:.3f}) does not match the reported "
        f"mean ({reported}); the table and reported summary disagree.")


# ---------------------------------------------------------------- pillar 2b (reproducibility from rows)
def test_test_retest_reproducible_from_rows():
    """The per-scan rows must show the real (small but non-zero) test-retest variability of a
    kinetic BP_ND (~2%). A constant/duplicated table (0%) or a non-equilibrium SUV-ratio
    (per-scan scatter tens of %) is rejected -- both are recomputed FROM the submitted rows."""
    smap = _submitted_map()
    trt = _test_retest_from_map(smap)
    assert trt is not None, (
        "could not pair baseline/rescan scans by subject in bp_estimates.csv to recompute "
        "test-retest variability")
    assert 0.4 <= trt <= 9.0, (
        f"test-retest variability recomputed from the submitted rows is {trt:.1f}% -- outside "
        f"the reproducible reference-tissue band [0.4, 9]%. A value ~0% is a constant/duplicated "
        f"table (no real per-scan estimate); tens of % is a non-equilibrium SUV-ratio, not a "
        f"kinetic BP_ND.")


# ---------------------------------------------------------------- pillar 3 (discriminating: kinetic not SUVR)
def test_bp_is_kinetic_not_suvr():
    import statistics
    ref = _reference()
    smap = _submitted_map()
    matched = pw.match_items(smap, ref["ids"], ref["values"])
    st = ref["stats"]
    # per-scan closeness: honest kinetic (nearly flat 1.89-1.96) vs SUVR (widely scattered).
    # require each matched scan to be much closer to its kinetic reference than the SUVR value.
    suvr = {f"{a}|{b}": v for (a, b), v in zip(
        [("sub-01", "ses-baseline"), ("sub-01", "ses-rescan"),
         ("sub-02", "ses-baseline"), ("sub-02", "ses-rescan")], st["bp_per_scan_suvr_gm"])}
    n_kinetic = 0
    for rid, s, r in matched:
        sv = suvr.get(rid)
        if sv is None or abs(s - r) < abs(s - sv):
            n_kinetic += 1
    assert n_kinetic >= 0.75 * len(matched), (
        f"the per-scan BP_ND pattern matches a non-kinetic SUV-ratio more closely than the "
        f"reference-tissue kinetic model on {len(matched) - n_kinetic}/{len(matched)} scans.")
    # cohort mean sits at the kinetic level (test-retest reproducible band)
    mean_rows = statistics.fmean([s for _, s, _ in matched])
    assert 1.70 <= mean_rows <= 2.10, (
        f"mean putamen BP_ND {mean_rows:.3f} is outside the reproducible reference-tissue band "
        f"[1.70, 2.10].")


def test_kinetic_params_if_volunteered():
    """If the submission volunteers the kinetic delivery parameter R1 (as SRTM/MRTM do -- a
    non-kinetic SUV-ratio fundamentally cannot), it must be the real per-scan R1 from the
    held-out reference. Graded only when an R1 column is present (a defensible graphical-only
    submission may omit it)."""
    ref = _reference()
    if "R1" not in ref:
        return
    p = OUT / "bp_estimates.csv"
    rows, headers = pw.read_rows(p)
    r1col = pw.pick_col(headers, ("r1", "rone", "relativedelivery", "r1delivery"),
                        exclude=("k2", "bp", "logan", "mrtm"))
    if r1col is None:
        return  # not volunteered -> not graded (grade-if-present)
    smap = pw.build_submitted_map(rows, headers, ID_GROUPS, r1col)
    matched = pw.match_items(smap, ref["ids"], ref["R1"])
    if len(matched) < 3:
        return
    close = sum(1 for _, s, r in matched if pw.within(s, r, 0.15, 0.15))
    assert close >= 0.75 * len(matched), (
        f"the volunteered per-scan R1 (relative delivery) does not match the held-out kinetic "
        f"reference on {len(matched) - close}/{len(matched)} scans -- a fabricated or non-"
        f"kinetic table cannot reproduce the real per-scan R1 (~1.12-1.28).")


# ---------------------------------------------------------------- secondary prose signal
def test_findings_reference_tissue_model_secondary():
    """SECONDARY: a reference-tissue kinetic model (not a bare SUV ratio) should be named."""
    blob = ""
    for name in ("findings.md", "run_metadata.json", "bp_estimates.csv"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    blob = blob.lower()
    assert blob.strip(), "no findings.md / run_metadata.json produced"
    assert re.search(r"srtm|simplified reference|mrtm|logan|reference[- ]?tissue|lammertsma|ichise",
                     blob), \
        "no reference-tissue kinetic model (SRTM / MRTM / Logan-ref) is named anywhere"
