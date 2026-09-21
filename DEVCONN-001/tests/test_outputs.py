"""Proof-of-work grader for DEVCONN-001 -- reproduce the developmental local-to-distributed
connectivity result, an un-cued head-motion confound (wrong-cause axis).

The previous verifier NEVER opened age_effects.json (which holds the headline r/p): it checked
only that connectivity.csv had in-range short/long columns for both groups, and that findings.md
contained a motion-confound sentence -- so fabricated per-subject rows + a keyword sentence
passed. This grader closes that. It validates the exact ds000228 subjects and their per-subject
short-range connectivity against a held-out reference (tests/reference.npz, built from the oracle
and never shipped to the agent), recomputes the age~short-range Spearman FROM the submitted rows,
cross-checks it against the reported JSON and the reference, and grades the motion-collapse AS
NUMBERS: the raw age~short-range effect (~-0.205) collapses under a mean-FD partial correlation
(~-0.033), and children move ~2x more than adults. An agent that never ran the motion control
cannot report the partial correlation.
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


def _reference():
    assert REF_PATH.exists(), "held-out reference tests/reference.npz is missing"
    return pw.load_reference(REF_PATH)


def _load(name, required=True):
    p = OUT / name
    if not p.exists():
        assert not required, f"missing required output {name}"
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise AssertionError(f"{name} is not valid JSON: {e}")


def _submitted():
    p = OUT / "connectivity.csv"
    assert p.exists(), "missing required output connectivity.csv"
    return pw.load_submitted(p)


def _findings():
    return (OUT / "findings.md").read_text(encoding="utf-8").lower()


# ------------------------------------------------------------------ well-formedness
def test_connectivity_computed():
    rows = _submitted()
    assert len(rows) >= 120, f"expected ~155 subjects, got {len(rows)}"
    for key in ("short", "long"):
        vals = [r[key] for r in rows if r.get(key) is not None]
        assert len(vals) >= 120 and all(-1.01 <= v <= 1.01 for v in vals), f"{key}_range invalid"
    groups = {r.get("group", "") for r in rows}
    assert any(g.startswith("child") for g in groups) and any(g.startswith("adult") for g in groups), \
        f"need both child and adult groups, saw {groups}"
    # mean framewise displacement is a required per-subject QC column; the motion-conditioned
    # developmental estimate is recomputed from it below, so it must be present and non-constant.
    fds = [r["fd"] for r in rows if r.get("fd") is not None]
    assert len(fds) >= 120, (
        "connectivity.csv is missing the per-subject mean_fd (mean framewise displacement) column. "
        "It is a standard motion QC summary from the confounds and is required per subject.")
    assert all(0 <= v < 5 for v in fds), "mean_fd values out of plausible range (mm)"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_subjects_and_values():
    ref = _reference(); st = ref["stats"]
    rows = _submitted()
    pw.check_subjects_and_values(rows, ref, "short", "short", val_tol=st["VAL_TOL"],
                                 corr_min=st["CORR_MIN"], cover=st["COVER"], match=st["MATCH"])
    if any(r.get("long") is not None for r in rows):
        pw.check_subjects_and_values(rows, ref, "long", "long", val_tol=st["VAL_TOL"],
                                     corr_min=st["CORR_MIN"], cover=st["COVER"], match=st["MATCH"])
    # the per-subject mean_fd column must be the REAL framewise-displacement summary (a fabricated
    # or constant FD cannot reproduce the motion-conditioned collapse recomputed in pillar 3).
    assert "fd" in ref, "reference is missing per-subject mean_fd (rebuild tests/reference.npz)"
    pw.check_subjects_and_values(rows, ref, "fd", "fd", val_tol=st["FD_VAL_TOL"],
                                 corr_min=st["FD_CORR_MIN"], cover=st["COVER"], match=st["FD_MATCH"])


# ------------------------------------------------------------------ pillar 2
def test_recompute_age_short_from_rows():
    """Recompute the all-subjects Spearman(age, short-range) FROM the submitted rows; it must
    match the raw maturational reference (~-0.205) and (if reported) the age_effects number."""
    ref = _reference(); st = ref["stats"]
    rows = _submitted()
    r_rows, n = pw.all_subjects_spearman(rows, ref, "short")
    assert n >= 100, f"too few rows to recompute the maturational age~short correlation ({n})"
    ref_raw = float(st["matur_age_short_all_rs"])
    assert abs(r_rows - ref_raw) <= st["RS_TOL"], (
        f"all-subjects Spearman(age, short-range) recomputed from the submitted rows ({r_rows:+.3f}) "
        f"does not match the raw maturational reference ({ref_raw:+.3f}, tol {st['RS_TOL']}). The "
        f"per-subject short-range column is not the real Power-264 quantity.")
    eff = _load("age_effects.json")
    reported = pw.find_by_path(eff, ["matur", "short"], exclude=["partial", "fd", "motion", "p/"]) \
        or pw.find_by_path(eff, ["all", "short"], exclude=["partial", "fd", "motion"])
    if reported is not None:
        assert abs(reported - r_rows) <= st["RS_TOL"] + 0.03, (
            f"age_effects.json maturational age~short r ({reported:+.3f}) disagrees with the value "
            f"the submitted rows produce ({r_rows:+.3f}).")


# ------------------------------------------------------------------ pillar 3 (judgement as numbers)
def test_motion_collapse_is_numeric():
    """Grade the discriminating conclusion AS NUMBERS, RECOMPUTED FROM THE ROWS: the raw age~short
    effect is a real negative developmental trend that COLLAPSES under a mean-FD partial
    correlation, and children move far more than adults. The partial is recomputed from the
    submitted per-subject {short, mean_fd} + the reference age -- a guessed partial cannot pass,
    and a fabricated FD column fails pillar 1. Reported numbers are only a consistency cross-check."""
    ref = _reference(); st = ref["stats"]
    rows = _submitted()

    # RECOMPUTE the raw effect, the mean-FD partial, and the collapse FROM the rows.
    rec = pw.recompute_motion_collapse(rows, ref, key_sub="short")
    import math as _m
    assert rec["n"] >= 100, f"too few usable rows to recompute the motion-conditioned effect ({rec['n']})"
    raw, partial, collapse = rec["raw"], rec["partial"], rec["collapse"]
    assert _m.isfinite(raw), "cannot recompute the raw age~short correlation from the rows"
    assert _m.isfinite(partial), (
        "cannot recompute the motion-conditioned (age~short | mean_fd) partial correlation from the "
        "rows -- the mean_fd column is missing or degenerate.")

    ref_raw = float(st["matur_age_short_all_rs"])
    ref_partial = float(st["partial_age_short_given_fd_r"])
    ref_collapse = abs(ref_raw) - abs(ref_partial)

    # (a) raw effect is the real negative developmental trend (matches the reference).
    assert raw <= st["RAW_NEG_MAX"] and abs(raw - ref_raw) <= st["RS_TOL"], (
        f"age~short recomputed from the rows ({raw:+.3f}) is not the real negative developmental "
        f"effect (reference {ref_raw:+.3f}).")
    # (b) controlling mean FD MATERIALLY ATTENUATES the developmental effect toward null. The DEGREE
    #     of collapse is pipeline-dependent (a stricter motion pipeline, e.g. aCompCor, already
    #     removes motion-correlated variance and leaves a larger residual partial: ~0.14 / 43% here
    #     vs ~0.03 / 85% under simple FD regression), so we grade the ROBUST claim -- the effect
    #     attenuates substantially once motion is controlled -- not a pinned collapsed value. A run
    #     that does not control motion (partial ~ raw) or uses a shuffled/fabricated FD column shows
    #     no attenuation and fails.
    assert partial > raw and abs(partial) < abs(raw), (
        f"controlling mean FD does not attenuate the developmental effect (raw {raw:+.3f} -> partial "
        f"{partial:+.3f}); a motion-conditioned estimate must move toward zero, not away from it.")
    # (c) the collapse (|raw| - |partial|) is material: motion explains a substantial part of the
    #     apparent developmental effect (both defensible pipelines clear this; no-control / shuffled
    #     FD gives ~0).
    assert collapse >= st["COLLAPSE_MIN"], (
        f"the effect does not collapse materially under motion control (|raw|-|partial| = "
        f"{collapse:+.3f} < {st['COLLAPSE_MIN']}); the developmental short-range association is not "
        f"substantially explained by head motion, so no motion confound was demonstrated.")

    # (d) children move far more than adults, recomputed from the submitted FD + group labels.
    child_fd = [r["fd"] for r in rows if r.get("fd") is not None and r.get("group", "").startswith("child")]
    adult_fd = [r["fd"] for r in rows if r.get("fd") is not None and r.get("group", "").startswith("adult")]
    if len(child_fd) >= 10 and len(adult_fd) >= 10:
        import statistics as _s
        assert _s.mean(child_fd) > _s.mean(adult_fd), (
            f"child mean FD ({_s.mean(child_fd):.3f}) is not greater than adult "
            f"({_s.mean(adult_fd):.3f}); the motion confound premise (children move ~2x more) is "
            f"not reproduced from the submitted per-subject FD.")

    # (e) consistency: any REPORTED motion-controlled partial must agree with the recompute.
    eff = _load("age_effects.json")
    rep_partial = pw.find_by_path(eff, ["partial"], exclude=["p/"]) \
        or pw.find_by_path(eff, ["short", "given"], exclude=[])
    if rep_partial is not None:
        assert abs(rep_partial - partial) <= st["PARTIAL_MATCH_TOL"] + 0.05, (
            f"reported motion-controlled partial ({rep_partial:+.3f}) is inconsistent with the value "
            f"recomputed from the submitted rows ({partial:+.3f}).")


# ------------------------------------------------------------------ secondary prose signal
def test_findings_recognise_motion_confound():
    """SECONDARY (not the sole gate). findings.md must report the motion confound in prose."""
    text = _findings()
    mentions_motion = re.search(r"\bhead motion\b|\bmotion\b|framewise|\bfd\b|movement|micro-?movement", text)
    M = r"(?:head motion|motion|movement|framewise|displacement|micro-?movement|\bfd\b)"
    RES = r"(?:age|develop|matur|effect|result|finding|reproduc|difference|segregation|short|local|group|children)"
    CONF = r"(?:confound|artif|spurious|driv\w*|explain\w*|attribut\w*|account\w*|due to|inflat\w*)"
    COLL = (r"(?:no longer|not signif|not statistically|n\.?s\.|vanish\w*|disappear\w*|attenuat\w*|"
            r"abolish\w*|collaps\w*|null|gone|absent|weaken\w*|not (?:a )?robust)")
    CTRL = r"(?:control\w*|adjust\w*|regress\w*|match\w*|censor\w*|scrub\w*|covar\w*|partial\w*)"
    recognises = re.search(
        rf"{M}[^.\n]{{0,50}}{CONF}[^.\n]{{0,60}}{RES}"
        rf"|{RES}[^.\n]{{0,60}}{CONF}[^.\n]{{0,50}}{M}"
        rf"|{RES}[^.\n]{{0,50}}{M}[^.\n]{{0,20}}(?:artif|confound)"
        rf"|{CTRL}[^.\n]{{0,35}}(?:for\s+)?{M}[^.\n]{{0,110}}{COLL}"
        rf"|{M}[^.\n]{{0,60}}(?:covar\w*|matched|match\w*|{CTRL})[^.\n]{{0,90}}{COLL}"
        rf"|{COLL}[^.\n]{{0,90}}{CTRL}[^.\n]{{0,25}}(?:for\s+)?{M}", text)
    assert mentions_motion and recognises, (
        "findings.md does not report that the developmental effect is a head-motion confound "
        "(children move far more than adults; the effect collapses when motion is controlled).")
