"""Proof-of-work grader for SOCIALBRAIN-001 -- reproduce Richardson's increasing ToM-pain
anti-correlation, an un-cued global-signal-regression (GSR) dependence.

The previous verifier NEVER opened age_effects.json (which holds the headline r/p): it checked
only that network_connectivity.csv had in-range columns and that findings.md contained a
GSR-dependence sentence -- so fabricated per-subject rows + a keyword sentence passed. This
grader closes that. It validates the exact ds000228 subjects and their per-subject ToM/pain
connectivity against a held-out reference (tests/reference.npz, built from the oracle and never
shipped to the agent), recomputes the children's Spearman(age, across-network) FROM the
submitted rows, cross-checks it against the reported JSON and the reference, and grades the
GSR-dependence AS NUMBERS: across-network vs age is ~null without GSR (~-0.07) and clearly
negative with GSR (~-0.34). An agent that ran only one pipeline cannot report both.
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
    p = OUT / "network_connectivity.csv"
    assert p.exists(), "missing required output network_connectivity.csv"
    return pw.load_submitted(p)


def _findings():
    return (OUT / "findings.md").read_text(encoding="utf-8").lower()


# ------------------------------------------------------------------ well-formedness
def test_connectivity_computed():
    rows = _submitted()
    assert len(rows) >= 120, f"expected ~155 subjects, got {len(rows)}"
    across = [r["across"] for r in rows if r.get("across") is not None]
    assert len(across) >= 120 and all(-1.01 <= v <= 1.01 for v in across), "across_network invalid"


# ------------------------------------------------------------------ pillar 1
def test_proof_of_work_subjects_and_values():
    ref = _reference(); st = ref["stats"]
    rows = _submitted()
    # standard-clean across-network per subject must be the real ones
    pw.check_subjects_and_values(rows, ref, "across", "across", val_tol=st["VAL_TOL"],
                                 corr_min=st["CORR_MIN"], cover=st["COVER"], match=st["MATCH"])
    # within-ToM is pipeline-robust; require it too (a real ROI extraction, not a fake table)
    if any(r.get("within_tom") is not None for r in rows):
        pw.check_subjects_and_values(rows, ref, "within_tom", "within_tom", val_tol=st["VAL_TOL"],
                                     corr_min=st["CORR_MIN"], cover=st["COVER"], match=st["MATCH"])


# ------------------------------------------------------------------ pillar 2
def test_recompute_children_spearman_from_rows():
    """Recompute the children's Spearman(age, across-network) FROM the submitted rows; it must
    match the standard-clean (no-GSR) reference (~-0.07) AND the reported age_effects.json
    across-network r."""
    ref = _reference(); st = ref["stats"]
    rows = _submitted()
    r_rows, n = pw.children_spearman(rows, ref, "across")
    assert n >= 20, f"too few child rows to recompute the age correlation ({n})"
    ref_ng = float(st["across_nogsr_rs"])
    assert abs(r_rows - ref_ng) <= st["RS_TOL"], (
        f"children Spearman(age, across-network) recomputed from the submitted rows ({r_rows:+.3f}) "
        f"does not match the standard-clean reference ({ref_ng:+.3f}, tol {st['RS_TOL']}). The "
        f"per-subject across-network column is not the real no-GSR quantity.")
    eff = _load("age_effects.json")
    reported_ng = pw.find_across_r(eff, gsr=False)
    assert reported_ng is not None, (
        "age_effects.json does not report the across-network vs age Spearman r (standard clean).")
    assert abs(reported_ng - r_rows) <= st["RS_TOL"], (
        f"age_effects.json across-network r ({reported_ng:+.3f}) disagrees with the value the "
        f"submitted rows produce ({r_rows:+.3f}); CSV and JSON are inconsistent.")


# ------------------------------------------------------------------ pillar 3 (judgement as numbers)
def test_gsr_dependence_is_numeric():
    """Grade the discriminating conclusion AS NUMBERS: across-network vs age is ~null without
    GSR and clearly negative with GSR (the GSR-dependence). An agent that ran only one pipeline
    has only one of the two numbers and fails."""
    ref = _reference(); st = ref["stats"]
    blobs = [_load("age_effects.json"), _load("run_metadata.json", required=False)]
    def _first(gsr):
        for b in blobs:
            if b is not None:
                v = pw.find_across_r(b, gsr=gsr)
                if v is not None:
                    return v
        return None
    r_ng = _first(gsr=False)
    r_gsr = _first(gsr=True)
    assert r_ng is not None, (
        "no across-network vs age correlation under STANDARD cleaning (no GSR) reported in "
        "age_effects.json.")
    assert r_gsr is not None, (
        "no across-network vs age correlation WITH global-signal regression (GSR) reported. The "
        "judgement graded here is that the anti-correlation reproduces only under GSR; report the "
        "across-network vs age Spearman under GSR as a number (e.g. across_network_gsr).")
    # standard clean is ~null (matches reference)
    assert abs(r_ng) <= st["NOGSR_ABS_MAX"] and abs(r_ng - st["across_nogsr_rs"]) <= st["RS_TOL"], (
        f"reported no-GSR across-network r = {r_ng:+.3f} is not the ~null standard-clean value "
        f"(reference {st['across_nogsr_rs']:+.3f}); without GSR the increasing anti-correlation "
        f"does not reproduce.")
    # GSR is clearly negative (matches reference)
    assert r_gsr <= st["GSR_NEG_MAX"] and abs(r_gsr - st["across_gsr_rs"]) <= st["RS_TOL"], (
        f"reported GSR across-network r = {r_gsr:+.3f} is not the clearly-negative GSR value "
        f"(reference {st['across_gsr_rs']:+.3f}); with GSR the anti-correlation reproduces "
        f"(~Richardson's -0.35).")
    # the dependence itself: GSR pulls the correlation meaningfully more negative
    assert (r_ng - r_gsr) >= st["DEPEND_MIN"], (
        f"the with/without-GSR contrast (no-GSR {r_ng:+.3f} vs GSR {r_gsr:+.3f}) does not show the "
        f"GSR-dependence; GSR must pull the across-network correlation markedly more negative.")


# ------------------------------------------------------------------ secondary prose signal
def test_findings_recognise_gsr_dependence():
    """SECONDARY (not the sole gate). findings.md must report the GSR-dependence in prose."""
    text = _findings()
    mentions_gsr = re.search(r"global[- ]signal|\bgsr\b", text)
    recognises = re.search(
        r"(only|solely)[^.\n]{0,30}(gsr|global[- ]signal)"
        r"|gsr[- ]?dependen|depend\w*[^.\n]{0,20}(gsr|global[- ]signal)"
        r"|(with|under|adding|applying|appl\w*|introduc\w*|includ\w*)\s+(global[- ]signal regression|gsr)"
        r"[^.\n]{0,90}(reproduc|recover|appear|emerg|becomes?|negativ|anti[- ]?correlat|significan|strengthen|-?0?\.[1-9]|driv)"
        r"|(reproduc|recover|appear|emerg|becomes?|negativ|significan|null|absent|vanish|driv)"
        r"[^.\n]{0,90}(with|under|after|by|adding|applying|appl\w*)\s+(global[- ]signal regression|gsr)"
        r"|(spurious|artif|inflat|induce\w*|introduc\w*|strengthen)[^.\n]{0,40}(anti|negativ|correlat)"
        r"|spurious|contested|cannot be asserted|not (a )?robust|not robustly", text)
    assert mentions_gsr and recognises, (
        "findings.md does not report that the anti-correlation result is dependent on global-signal "
        "regression (reproduces with GSR, not without / GSR induces it).")
