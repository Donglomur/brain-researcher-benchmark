"""Proof-of-work grader for MOVIESYNC-001 (inter-subject correlation of the movie-evoked
visual-cortex response in the development_fmri cohort).

A clean REPRODUCTION task: measure the ISC of the movie-driven BOLD response in visual cortex
on the pinned dataset/atlas/preprocessing and report it. Either standard estimator is accepted
(pairwise ~0.152, leave-one-out ~0.365; Nastase et al. 2019). Because a single headline scalar
is guessable, the grader validates the finest intermediate the analysis produces -- the
per-subject ISC (both estimators) -- against a held-out reference (tests/reference.npz, built
from the oracle run, never shipped to the agent), recomputes the headline as the mean of the
per-subject column, and requires the reported value to match the reference for the DECLARED
estimator.

Ground truth (nilearn 0.13.1, fetch_development_fmri n=40, MSDL visual regions
["Vis","Striate","Occ post"], confound-cleaned, band-pass 0.01-0.1 Hz):
  per-subject pairwise ISC (mean r with the other 39)  -> isc_pairwise; mean = 0.152
  per-subject leave-one-out ISC (vs mean of others)    -> isc_loo;      mean = 0.365

Three pillars:
  1. per-subject ISC (pairwise + leave-one-out) ARE the real values (track the held-out ref)
  2. recompute the headline as the mean of the per-subject column == reference == reported
  3. the reported headline matches the reference for the declared estimator (and is one of the
     two legitimate estimator values, not a fabricated number)
"""
import json
import math
import os
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


def _submitted():
    p = OUT / "isc_per_subject.csv"
    assert p.exists(), (
        "missing required output isc_per_subject.csv -- the per-subject inter-subject correlation "
        "(the finest intermediate the ISC is built from). The single headline value cannot be "
        "validated without it.")
    return pw.load_submitted(p)


def _results():
    p = OUT / "isc_results.json"
    assert p.exists(), "missing required output isc_results.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _metadata():
    p = OUT / "run_metadata.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _reported_headline(res):
    return pw.find_number(res, [r"visualisc", r"^isc$", r"iscvisual", r"intersubjectcorrel",
                                r"headlineisc", r"iscmean", r"meanisc"],
                          exclude=[r"chance", r"perregion", r"nsub", r"ntime", r"std", r"sem",
                                   r"ci", r"lower", r"upper", r"loo", r"leaveoneout", r"inflated"])


# ------------------------------------------------------------------ well-formedness
def test_outputs_present_and_wellformed():
    ref = _reference()
    sub, has_pw, has_loo = _submitted()
    assert len(sub) >= 35, f"isc_per_subject.csv covers only {len(sub)} subjects (expected ~40)"
    assert has_pw or has_loo, (
        "isc_per_subject.csv has no per-subject ISC column (isc_pairwise / isc_loo)")
    res = _results()
    h = _reported_headline(res)
    assert h is not None, f"isc_results.json has no visual_isc headline value: {res}"
    assert -1.0 <= h <= 1.0, f"reported visual_isc {h} is not a valid correlation"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_per_subject_isc():
    ref = _reference()
    st = ref["stats"]
    sub, has_pw, has_loo = _submitted()
    cov = pw.coverage(sub, ref["ids"])
    assert cov >= st["COVER"], (
        f"isc_per_subject.csv covers only {cov:.0%} of the {len(ref['ids'])} pinned participants "
        f"(need >= {st['COVER']:.0%})")
    checked = 0
    for idx, has, name, ref_map in ((0, has_pw, "pairwise", ref["pairwise"]),
                                    (1, has_loo, "leave-one-out", ref["loo"])):
        if not has:
            continue
        assert pw.nonconstant(sub, idx, st["EPS"]), (
            f"per-subject {name} ISC is constant across participants -- fabricated")
        rc, n = pw.cross_corr(sub, ref_map, ref["ids"], idx)
        assert math.isfinite(rc) and rc >= st["CORR_MIN"], (
            f"per-subject {name} ISC does not track the held-out reference (cross-subject "
            f"r={rc:.3f} < {st['CORR_MIN']}); it was not computed from the real time series")
        frac, n = pw.per_subject_match(sub, ref_map, ref["ids"], idx, st["VAL_TOL"])
        assert frac >= st["MATCH"], (
            f"only {frac:.0%} of {n} matched participants have {name} ISC within {st['VAL_TOL']} "
            f"of the reference (need >= {st['MATCH']:.0%})")
        checked += 1
    assert checked >= 1, "no per-subject ISC column could be validated against the reference"


# ------------------------------------------------------------------ pillar 2
def test_headline_recomputes_from_rows():
    ref = _reference()
    st = ref["stats"]
    sub, has_pw, has_loo = _submitted()
    res = _results()
    reported = _reported_headline(res)

    means = {}
    if has_pw:
        means["pairwise"] = pw.mean_of(sub, ref["ids"], 0)
    if has_loo:
        means["loo"] = pw.mean_of(sub, ref["ids"], 1)
    # the mean of the per-subject pairwise column IS the pairwise headline; check vs reference.
    if "pairwise" in means:
        assert abs(means["pairwise"] - st["pairwise"]) <= 0.03, (
            f"mean of the per-subject pairwise ISC ({means['pairwise']:.3f}) != reference "
            f"({st['pairwise']:.3f})")
    if "loo" in means:
        assert abs(means["loo"] - st["loo"]) <= 0.04, (
            f"mean of the per-subject leave-one-out ISC ({means['loo']:.3f}) != reference "
            f"({st['loo']:.3f})")
    # the reported headline must equal the mean of ONE of the per-subject columns (CSV<->JSON).
    assert any(abs(reported - m) <= 0.03 for m in means.values()), (
        f"reported visual_isc ({reported:.3f}) is not the mean of any submitted per-subject ISC "
        f"column ({', '.join(f'{k}={v:.3f}' for k, v in means.items())}); the headline is not "
        f"consistent with the per-subject rows")


# ------------------------------------------------------------------ pillar 3 (headline vs declared estimator)
def test_headline_matches_declared_estimator():
    ref = _reference()
    st = ref["stats"]
    res = _results()
    meta = _metadata()
    reported = _reported_headline(res)
    tol = st["ISC_TOL"]

    matches_pw = abs(reported - st["pairwise"]) <= tol
    matches_loo = abs(reported - st["loo"]) <= tol
    assert matches_pw or matches_loo, (
        f"reported visual_isc ({reported:.3f}) matches neither legitimate estimator on these data "
        f"(pairwise {st['pairwise']:.3f} / leave-one-out {st['loo']:.3f}); it is not a real ISC "
        f"of the pinned analysis")

    est = pw.declared_estimator({**meta, **{k: v for k, v in res.items() if isinstance(v, str)}})
    if est == "pairwise":
        assert matches_pw, (
            f"run_metadata declares the PAIRWISE estimator but the reported visual_isc "
            f"({reported:.3f}) is not the pairwise value ({st['pairwise']:.3f}); it looks like the "
            f"leave-one-out value reported under the wrong estimator")
    elif est == "loo":
        assert matches_loo, (
            f"run_metadata declares the LEAVE-ONE-OUT estimator but the reported visual_isc "
            f"({reported:.3f}) is not the leave-one-out value ({st['loo']:.3f})")

    # above chance (a movie-driven response was actually recovered)
    assert reported > float(st.get("chance", 0.0)) + 0.03, (
        f"reported ISC ({reported:.3f}) is at/below chance -- the movie response was not recovered")
