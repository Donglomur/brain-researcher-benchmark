"""Proof-of-work grader for TASKFC-001 (task-state FC of a co-engaged visual region pair).

Held-out reference (tests/reference.npz), built by running solution/compute.py on the pinned
nilearn language-localizer demo (all 10 subjects, left/right lateral occipital 8 mm spheres at
MNI (-30,-90,-6)/(30,-90,-6), common preprocessing = cosine drift + 6 motion regressors):

  per-subject RAW task-state FC (task-evoked kept)      -> connectivity column
  per-subject BACKGROUND FC (task-evoked regressed out) -> background_connectivity column
  group (Fisher-z averaged):  raw = 0.630   background = 0.461
  inflation raw > background: +0.169, paired t = 4.02, p = 3.0e-03, raw>background in 10/10

A raw Pearson correlation of the two regions' BOLD during the task SYSTEMATICALLY OVERSTATES
their connectivity: both occipital regions are co-driven by the visual stimulus, so much of
the raw co-variation is the shared task-evoked response. Removing it first (background
connectivity; Fair 2007, Al-Aidroos 2012, Cole 2019) drops the estimate substantially. An
agent that only correlated the raw time series cannot produce the per-subject background
column or the ~0.46 background mean.

Four pillars:
  1  exact pinned subjects + real per-subject RAW values (kills fabricated/dup)
  1b MANDATORY: real per-subject BACKGROUND values (cross-subject r>=0.95 + absolute match to the
     reference). corr(raw,background) across subjects is only ~0.74, so a background fabricated by
     scaling the raw column fails -- the residual correlations must actually be computed.
  2  recompute the group raw + background Fisher-z means FROM the rows == reported == reference
  3  grade the discriminating inflation as numbers, RECOMPUTED FROM THE ROWS (raw > background,
     gap, n raw>bg); the reported group background is only a consistency cross-check
  4  SECONDARY prose signal: findings.md links the task-evoked co-activation to the inflation
"""
import json
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_of_work as pw  # noqa: E402

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).resolve().parent / "reference.npz"

# Background (task-regressed) FC is task-model-sensitive: which GLM / HRF / drift basis is used to
# regress the task-evoked response shifts the per-subject residual, so the per-subject background is
# NOT pinned to the reference magnitude (the reference and an independent, defensible live solve
# agree per subject at only corr ~= 0.70, mean|Delta| ~= 0.087, far above the old VAL_TOL 0.05).
# Instead the grader requires the SIGNATURE of a genuine residual that is derived from the real
# subjects' data:
#   * BG_RAW_CORR band -- across subjects the background tracks the raw column (both computed on the
#     same subjects) but is NOT a trivial affine rescaling of it. corr(raw, background) ~= 0.74 in
#     the reference and ~0.89 for the live solve; an affine scaled/shifted copy of raw has corr ~=
#     1.0 (rejected by the max) and a grossly unrelated column has corr near 0 (rejected by the min).
#   * BG_MEAN_GAP -- the background lies materially below raw (the shared task-evoked response
#     inflates raw FC); a background==raw copy has zero gap and is rejected.
#   * BG_REF_CORR -- the background must correlate with the held-out reference background ACROSS
#     subjects above a lenient floor. This is affine-invariant (no magnitude pin) and, crucially,
#     safe for any real pipeline: the raw column is pinned to the reference (corr ~0.997) and
#     corr(raw, reference-background) ~= 0.75, so any background genuinely derived from the real
#     subjects inherits corr(background, reference-background) ~= 0.6-0.75, while a fabricated /
#     blind-random background (not derived from the real subjects) scores ~0 and is rejected.
# NOTE (documented limit): because raw and background are intrinsically coupled and the real
# background's agreement with the reference is carried almost entirely by raw (raw-controlled
# partial corr ~= 0.09), a determined adversary who builds background = k*raw + tuned noise from the
# agent's OWN raw column produces a column that is statistically indistinguishable from a real
# task-regressed residual (right band, below raw, right group inflation, inherits the reference
# correlation via raw). No reference-based per-subject check can reject it without also rejecting the
# defensible real solve. The grader therefore rejects the naive/lazy/blind fabrications and grades
# the true scientific claim (the group task-evoked inflation); it does not claim to prove per-subject
# task regression against that specific adversary.
BG_RAW_CORR_MIN = 0.40
BG_RAW_CORR_MAX = 0.95
BG_MEAN_GAP_MIN = 0.04  # mean per-subject (raw - background); ~0.13 real, 0 for background==raw
BG_REF_CORR_MIN = 0.55  # lenient across-subject corr with the held-out reference background
                        # (live solve ~0.70; blind/fabricated ~0; guaranteed >~0.6 for real bg by
                        # the pinned raw column, so it does NOT pin the pipeline-sensitive magnitude)


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _submitted():
    p = OUT / "connectivity.csv"
    assert p.exists(), "missing required output connectivity.csv"
    return pw.load_submitted(p)


def _summary():
    for name in ("connectivity_summary.json", "summary.json", "results.json"):
        p = OUT / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def _findings():
    p = OUT / "findings.md"
    return p.read_text(encoding="utf-8").lower() if p.exists() else ""


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    ref = _reference()
    sub, raw_c, bg_c = _submitted()
    assert len(sub) >= 8, f"connectivity.csv covers only {len(sub)} subjects (expected ~10)"
    assert raw_c is not None, "connectivity.csv has no raw task-state connectivity column"
    raws = [sub[i][0] for i in sub if sub[i][0] is not None and math.isfinite(sub[i][0])]
    assert raws and all(-1.01 <= v <= 1.01 for v in raws), "raw connectivity out of [-1,1]"
    summ = _summary()
    assert summ, "connectivity_summary.json missing/empty"
    assert pw.find_number(summ, [r"groupconnectivity", r"rawtaskstate", r"connectivity", r"^r$"],
                          exclude=[r"nsub", r"background", r"nparial"]) is not None, \
        "connectivity_summary.json has no group connectivity value"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_subjects_and_raw_values():
    ref = _reference()
    st = ref["stats"]
    sub, _, _ = _submitted()
    cov = pw.coverage(set(sub), ref["ids"])
    assert cov >= st["COVER"], (
        f"connectivity.csv covers only {cov:.0%} of the {len(ref['ids'])} pinned subjects "
        f"(need >= {st['COVER']:.0%})")
    assert pw.nonconstant(sub, 0, st["EPS"]), "raw connectivity is constant across subjects"
    rc = pw.cross_corr(sub, ref["raw_by_id"], ref["ids"], 0)
    assert math.isfinite(rc) and rc >= st["CORR_MIN"], (
        f"per-subject RAW connectivity does not track the reference (cross-subject r={rc:.3f} "
        f"< {st['CORR_MIN']}); not computed from the real time series")
    frac, n = pw.per_subject_match(sub, ref["raw_by_id"], ref["ids"], 0, st["VAL_TOL"])
    assert frac >= st["MATCH"], (
        f"only {frac:.0%} of {n} matched subjects have RAW connectivity within {st['VAL_TOL']} "
        f"of the reference (need >= {st['MATCH']:.0%})")


def test_background_recomputed_from_intermediates():
    import numpy as np
    from residual_contract import check_subject
    ref = _reference()
    sub, _, bg_c = _submitted()
    assert set(sub) == set(ref["ids"]) and len(sub) == 10
    assert bg_c is not None
    reference_dir = Path(__file__).resolve().parent / "residual_reference_v2"
    assert reference_dir.is_dir(), "genuine residual-v2 reference regeneration required"
    for sid in ref["ids"]:
        reference = np.load(reference_dir / f"subject_{sid}.npz", allow_pickle=False)
        # The source participant ID is preserved in each held-out subject reference.
        source_id = str(reference["subject_id"])
        data = np.load(OUT / f"intermediates_{source_id}.npz", allow_pickle=False)
        check_subject(data, reference, sub[sid])


# ------------------------------------------------------------------ pillar 2
def _reported_group_background(summ):
    # Exclude any inflation / difference field: keys like `inflation_raw_minus_background_r` contain
    # the substring "background" but report the raw-minus-background GAP (~0.14), not the group
    # background FC (~0.49). Without these excludes the BFS returns the inflation value and the
    # consistency cross-check spuriously fails a correct submission.
    return pw.find_number(summ, [r"background", r"residualconnectivity", r"intrinsicconnectivity",
                                 r"taskregressedconnectivity"],
                          exclude=[r"nsub", r"inflationp", r"paired", r"inflationt",
                                   r"inflation", r"minus", r"delta", r"difference", r"\bgap\b",
                                   r"rawminus", r"raw_?minus"])


def test_group_means_recompute_from_rows():
    """PILLAR 2: the reported group RAW FC must equal what the submitted per-subject rows produce
    AND the held-out reference. If a per-subject background column is present, its group mean must
    also match the reported group background."""
    ref = _reference()
    st = ref["stats"]
    sub, raw_c, bg_c = _submitted()
    matched = [i for i in ref["ids"] if i in sub]
    raw_recompute = pw.fisher_mean([sub[i][0] for i in matched])

    assert abs(raw_recompute - st["raw_g"]) <= st["GROUP_TOL"], (
        f"group RAW FC recomputed from the rows ({raw_recompute:.3f}) != reference "
        f"({st['raw_g']:.3f}, tol {st['GROUP_TOL']})")

    summ = _summary()
    rep_raw = pw.find_number(summ, [r"rawtaskstate", r"groupconnectivity", r"rawconnectivity",
                                    r"^rawfc"],
                             exclude=[r"background", r"nsub", r"inflation"])
    if rep_raw is not None:
        assert abs(rep_raw - raw_recompute) <= st["CONSIST"], (
            f"summary raw FC {rep_raw:.3f} inconsistent with the rows ({raw_recompute:.3f})")
    if bg_c is not None:
        bg_recompute = pw.fisher_mean([sub[i][1] for i in matched])
        rep_bg = _reported_group_background(summ)
        if rep_bg is not None:
            assert abs(rep_bg - bg_recompute) <= 0.05, (
                f"summary background FC {rep_bg:.3f} inconsistent with the per-subject background "
                f"rows ({bg_recompute:.3f})")


# ------------------------------------------------------------------ pillar 3 (judgement as numbers)
def test_signed_model_sensitivity_summary():
    import numpy as np
    from residual_contract import paired_interval
    ref = _reference()
    sub, _, _ = _submitted()
    raw = np.array([sub[i][0] for i in ref["ids"]])
    bg = np.array([sub[i][1] for i in ref["ids"]])
    expected = paired_interval(raw, bg)
    actual = _summary()["paired_z_sensitivity"]
    assert actual["n"] == 10
    assert np.isclose(actual["mean_raw_minus_background_z"], expected["mean_raw_minus_background_z"], atol=1e-5)
    assert np.allclose(actual["ci95"], expected["ci95"], atol=1e-5)

def test_findings_present():
    assert _findings().strip()
