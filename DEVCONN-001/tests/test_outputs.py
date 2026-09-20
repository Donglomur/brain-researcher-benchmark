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


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_subjects_and_values():
    ref = _reference(); st = ref["stats"]
    rows = _submitted()
    pw.check_subjects_and_values(rows, ref, "short", "short", val_tol=st["VAL_TOL"],
                                 corr_min=st["CORR_MIN"], cover=st["COVER"], match=st["MATCH"])
    if any(r.get("long") is not None for r in rows):
        pw.check_subjects_and_values(rows, ref, "long", "long", val_tol=st["VAL_TOL"],
                                     corr_min=st["CORR_MIN"], cover=st["COVER"], match=st["MATCH"])


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
    """Grade the discriminating conclusion AS NUMBERS: the raw age~short effect is negative and
    collapses under a mean-FD partial correlation, and children move far more than adults. An
    agent that never ran the motion control cannot report the partial correlation."""
    ref = _reference(); st = ref["stats"]
    blobs = [b for b in (_load("age_effects.json"), _load("run_metadata.json", required=False))
             if b is not None]

    def find(want, exclude=()):
        for b in blobs:
            v = pw.find_by_path(b, want, exclude=exclude)
            if v is not None:
                return v
        return None

    raw = find(["matur", "short"], exclude=["partial", "fd", "motion"]) \
        or find(["all", "short"], exclude=["partial", "fd", "motion"])
    partial = find(["partial"], exclude=["p/"]) \
        or find(["short", "fd"], exclude=["mwu", "mean"]) \
        or find(["short", "given"], exclude=[])
    child_fd = find(["child", "fd"], exclude=["mwu", "gt", "partial"])
    adult_fd = find(["adult", "fd"], exclude=["mwu", "gt", "partial"])

    assert raw is not None, (
        "no raw maturational age~short-range correlation reported in age_effects.json.")
    assert partial is not None, (
        "no motion-controlled (partial age~short-range | mean FD) correlation reported. The "
        "judgement graded here is that the developmental effect collapses when head motion is "
        "controlled; report the partial correlation (or a motion-matched estimate) as a number.")
    # raw effect is a real negative developmental trend (matches the reference)
    assert raw <= st["RAW_NEG_MAX"] and abs(raw - st["matur_age_short_all_rs"]) <= st["RS_TOL"] + 0.03, (
        f"reported raw age~short r = {raw:+.3f} is not the real negative developmental effect "
        f"(reference {st['matur_age_short_all_rs']:+.3f}).")
    # controlling motion collapses it to ~null
    assert abs(partial) <= st["PARTIAL_ABS_MAX"], (
        f"reported motion-controlled age~short partial r = {partial:+.3f} is not ~null "
        f"(|r| <= {st['PARTIAL_ABS_MAX']}); on the real data it collapses to "
        f"~{st['partial_age_short_given_fd_r']:+.3f} once mean FD is controlled.")
    assert (abs(raw) - abs(partial)) >= st["COLLAPSE_MIN"], (
        f"the effect does not collapse under motion control (raw {raw:+.3f} vs partial "
        f"{partial:+.3f}); the motion-controlled estimate must be markedly closer to zero.")
    # children move far more than adults (the premise of the confound)
    if child_fd is not None and adult_fd is not None:
        assert child_fd > adult_fd, (
            f"reported child mean FD ({child_fd:.3f}) is not greater than adult ({adult_fd:.3f}); "
            f"the motion confound premise (children move ~2x more) is not reproduced.")


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
