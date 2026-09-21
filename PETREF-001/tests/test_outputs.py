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

Because the honest per-scan BP_ND is near-degenerate (~1.9 +/- 2%), a table clustered at the
literature value passes the BP_ND checks alone. The TEETH is the now-MANDATORY per-scan R1
(relative delivery): the real R1 is DISPERSED across scans (GM reference ~1.24/1.16/1.12/1.28,
whole-cerebellum reference ~1.09/1.02/1.01/1.16 -- range ~0.15-0.16), so a flat/guessed R1
cannot span it within tolerance on all four scans, and a non-kinetic SUV-ratio produces no R1
at all. Only a real per-scan kinetic fit on the real TACs reproduces it.
  Held-out R1 (GM ref):        1.242 1.163 1.120 1.279
  Held-out R1 (whole-ceb ref): 1.092 1.020 1.010 1.157
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

VAL_TOL_ABS = 0.15     # per-scan BP_ND vs held-out reference: accepts SRTM/Logan/MRTM/MRTM2 (~2%),
VAL_TOL_REL = 0.07     # whole-cerebellum reference (~3-4%) and 2-step estimators; rejects SUVR (0.2-0.8 off)
COVER = 0.9
MATCH = 0.75           # >=3/4 scans within tol (accepts a defensible variant on one scan)
MEAN_TOL_REF = 0.12
MEAN_TOL_JSON = 0.08
# per-scan R1 (relative delivery) is now MANDATORY and matched to the held-out kinetic
# reference (SRTM/SRTM2/whole-cerebellum all land <=0.06 off; a SUVR/flat-BP guess produces
# no R1 and a flat guess cannot span the dispersed real R1 within tol at 4/4).
R1_TOL_ABS = 0.07      # absolute only: dispersed real R1 range (~0.16 GM / ~0.15 whole-ceb)
R1_STD_FLOOR = 0.03    # reject a near-constant (fabricated/flat) R1 column outright


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


# ---------------------------------------------------------------- pillar 4 (mandatory R1 delivery)
def test_r1_relative_delivery_matches_reference():
    """MANDATORY per-scan R1 (relative tracer delivery, target vs reference). Any reference-
    tissue kinetic model (SRTM / SRTM2 / MRTM full) yields R1; a non-kinetic SUV-ratio and a
    flat/near-constant BP guess fundamentally cannot. The submitted per-scan R1 must reproduce
    the DISPERSED real per-scan delivery pattern of the held-out kinetic reference (GM-cortex
    reference R1 ~1.12-1.28, or the whole-cerebellum reference R1 ~1.01-1.16) to within
    R1_TOL_ABS on ALL four scans against ONE consistent reference set. The real R1 spans ~0.16
    (GM) / ~0.15 (whole-ceb) across scans, so no single flat value can cover all four within
    tolerance -- the sub-analysis (a real kinetic fit on the real TACs), not a guess, is forced."""
    import statistics
    ref = _reference()
    assert "R1" in ref, "held-out reference is missing per-scan R1 (rebuild reference.npz)"
    p = OUT / "bp_estimates.csv"
    rows, headers = pw.read_rows(p)
    r1col = pw.pick_col(headers, ("r1", "rone", "relativedelivery", "r1delivery", "deliveryr1"),
                        exclude=("k2", "bp", "logan", "mrtm", "se", "std"))
    assert r1col is not None, (
        f"bp_estimates.csv has no per-scan R1 (relative delivery) column {headers}. R1 is a "
        f"required output: report the relative tracer delivery (target-to-reference) per scan.")
    smap = pw.build_submitted_map(rows, headers, ID_GROUPS, r1col)
    # coverage: R1 for all four real scans, keyed by real id
    cover_gm = pw.match_items(smap, ref["ids"], ref["R1"])
    assert len(cover_gm) >= len(ref["ids"]), (
        f"per-scan R1 covers only {len(cover_gm)}/{len(ref['ids'])} of the four real ds001420 "
        f"scans by id; R1 is required for every scan (fabricated or missing ids).")
    submitted_R1 = [s for _, s, _ in cover_gm]
    assert statistics.pstdev(submitted_R1) >= R1_STD_FLOOR, (
        f"the submitted per-scan R1 is near-constant (std {statistics.pstdev(submitted_R1):.3f} "
        f"< {R1_STD_FLOOR}); the real relative delivery is dispersed across scans (~0.06 std). "
        f"A flat/fabricated R1 does not reflect a per-scan kinetic fit.")
    # 4/4 within tol against ONE consistent accepted delivery set (GM-cortex OR whole-cerebellum)
    n = len(cover_gm)
    close_gm = sum(1 for _, s, r in cover_gm if pw.within(s, r, 0.0, R1_TOL_ABS))
    close_whole = 0
    if "R1_whole" in ref:
        cover_w = pw.match_items(smap, ref["ids"], ref["R1_whole"])
        close_whole = sum(1 for _, s, r in cover_w if pw.within(s, r, 0.0, R1_TOL_ABS))
    best = max(close_gm, close_whole)
    assert best >= n, (
        f"per-scan R1 (relative delivery) matches the held-out kinetic reference on only "
        f"{best}/{n} scans against either accepted reference set (need all {n} within "
        f"{R1_TOL_ABS}). A non-kinetic SUV-ratio has no R1; a flat/guessed R1 cannot reproduce "
        f"the dispersed real per-scan delivery (GM ~1.12-1.28 / whole-ceb ~1.01-1.16).")


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
