"""Proof-of-work grader for NETSEG-001 -- system segregation of the cortical connectome in a
developmental cohort, an un-cued edge-sign (anti-correlation handling) judgement.

The previous verifier checked a per-participant non-constant guard, a cohort-mean band, and a
prose edge-sign disclosure. This grader adds full proof-of-work: it validates the exact
developmental participants and their per-participant POSITIVE-EDGE segregation against a
reference (tests/reference.npz, built from the oracle run; held out of the agent CONTAINER but
PUBLIC in this repo (burned) -- a real eval needs fresh tasks / a server-side reference),
recomputes the cohort mean FROM the submitted rows, and grades the developmental
child<adult contrast as numbers. An all-edges run (which keeps the anti-correlations and
inflates segregation to ~0.55) has the wrong per-subject values and the wrong recomputed mean,
so it fails; the positive-edge cohort mean is ~0.37.
"""
import json
import os
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_of_work as pw  # noqa: E402

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).resolve().parent / "reference.npz"


def _reference():
    assert REF_PATH.exists(), (
        "held-out reference tests/reference.npz is missing (build it from the oracle run)")
    return pw.load_reference(REF_PATH)


def _meta():
    p = OUT / "run_metadata.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _submitted():
    p = OUT / "segregation.csv"
    assert p.exists(), "missing required output segregation.csv"
    # Positive-edge is the intended quantity (Chan et al.): prefer an explicitly positive-edge
    # column when the submission provides one alongside a signed primary, then fall back to a
    # single segregation column (the reference solution's own column IS the positive-edge one).
    return pw.load_submitted(
        p,
        id_cols=("participant", "subject", "participantid", "subid", "id"),
        seg_cols=("systemsegregationposonly", "segregationposonly", "posonly", "segpos",
                  "spos", "positiveedgesegregation", "segregationpositive",
                  "segregation", "systemsegregation", "seg", "sseg", "s"),
        group_cols=("group", "childadult", "cohort", "agegroup"))


def _text():
    blob = ""
    for name in ("findings.md", "run_metadata.json"):
        p = OUT / name
        if p.exists():
            blob += "\n" + p.read_text(encoding="utf-8")
    return blob.lower()


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    seg, _ = _submitted()
    vals = list(seg.values())
    assert len(vals) >= 30, (
        f"segregation.csv must carry per-participant system segregation for the ~40-participant "
        f"cohort; parsed {len(vals)} rows")
    assert all(-0.5 <= v <= 1.0 for v in vals), "segregation values outside a plausible range"
    assert statistics.pstdev(vals) > 1e-3, (
        "segregation is identical across participants -- not computed per subject")


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_subjects_and_values():
    ref = _reference(); st = ref["stats"]
    seg, _ = _submitted()
    pw.check_subjects_and_values(seg, ref, val_tol=st["VAL_TOL"], corr_min=st["CORR_MIN"],
                                 cover=st["COVER"], match=st["MATCH"], eps=st["EPS"])


# ------------------------------------------------------------------ pillar 2
def test_recompute_cohort_mean_from_rows():
    """Recompute the cohort-mean segregation FROM the submitted rows and require it to sit in
    the positive-edge band (admits both the negatives-excluded ~0.37 and negatives-clipped-to-0
    ~0.47 conventions). An all-edges run recomputes ~0.55 and fails the band. If a cohort mean
    is reported, the one consistent with the positive-edge rows must exist (a submission may
    also report a signed primary; we grade the positive-edge one)."""
    ref = _reference(); st = ref["stats"]
    seg, _ = _submitted()
    matched = [i for i in seg if i in set(ref["ids"])]
    mean_rows = statistics.fmean([seg[i] for i in matched])
    lo, hi = st["POS_BAND"]
    assert lo <= mean_rows <= hi, (
        f"cohort-mean segregation recomputed from the submitted rows ({mean_rows:.3f}) is "
        f"outside the positive-edge band [{lo}, {hi}]. System segregation is defined on the "
        f"positive edges (Chan et al. 2014); keeping the anti-correlations inflates the cohort "
        f"mean toward ~{st['all_edge_mean']:.2f}.")
    cands = pw.collect_numbers(_meta(),
                               [r"segregationmean", r"cohortmean", r"meansegregation",
                                r"segregationcohort"],
                               exclude=[r"child", r"adult", r"std", r"\bsd\b", r"group"])
    if cands:
        best = min(cands, key=lambda v: abs(v - mean_rows))
        assert abs(best - mean_rows) <= st["REPORT_TOL"], (
            f"no reported cohort-mean segregation is consistent with the submitted rows "
            f"(closest reported {best:.3f} vs rows {mean_rows:.3f}).")


# ------------------------------------------------------------------ pillar 3 (judgement as numbers)
def test_developmental_contrast_and_edge_sign():
    """The reported cohort mean is the positive-edge quantity, and the child-vs-adult
    developmental contrast matches the reference direction (segregation is higher in adults).
    Plus an explicit edge-sign disclosure (the over-claim axis)."""
    ref = _reference(); st = ref["stats"]
    seg, grp = _submitted()
    # child vs adult from the submitted rows, if a group column is present. Grade the DIRECTION
    # (adults more segregated than children) robustly -- the per-group magnitude is convention
    # dependent (negatives-excluded vs negatives-clipped-to-0 shift it by ~0.10), so it is not
    # pinned.
    child = [seg[i] for i in seg if grp.get(i, "").startswith("child")]
    adult = [seg[i] for i in seg if grp.get(i, "").startswith("adult")]
    if len(child) >= 5 and len(adult) >= 5:
        cm, am = statistics.fmean(child), statistics.fmean(adult)
        assert am > cm, (
            f"the reference has adults MORE segregated than children (a developmental increase "
            f"in system segregation); the submitted contrast is reversed (child {cm:.3f}, "
            f"adult {am:.3f}).")

    # explicit edge-sign disclosure (the over-claim this task targets)
    text = _text()
    has_result = re.search(r"segregation[^.\n]{0,40}[-+]?\d?\.\d|[-+]?\d?\.\d\d[^.\n]{0,40}"
                           r"segregation|segregation_mean", text)
    edge_sign = re.search(
        r"positive[- ]?edge|positive[- ]?(correlation|weight|connection|tie|value|fc)|"
        r"anti[- ]?correlation|negative[- ]?(edge|correlation|weight|connection|tie|value|fc)|"
        r"positive edges only|set aside|"
        r"(thresh\w*|clip\w*|floor\w*|rectif\w*)[^.\n]{0,25}(zero|0|negativ)|"
        r"(exclud\w*|remov\w*|discard\w*|drop\w*|ignor\w*|zero\w*|set|keep only|only the|retain\w*)"
        r"[^.\n]{0,20}(negativ|anti[- ]?correl|positive)|"
        r"(negativ\w*|anti[- ]?correl\w*)[^.\n]{0,25}"
        r"(exclud|remov|discard|drop|ignor|set aside|zero|thresh|clip)|"
        r"absolute value|\|r\|", text)
    assert has_result and edge_sign, (
        "findings/run_metadata do not DISCLOSE how the anti-correlations (negative edges) were "
        "handled. System segregation is defined on the positive edges (Chan et al. 2014); "
        "silently keeping the negatives inflates it by ~half. State the edge-sign handling "
        "alongside the reported segregation value.")
