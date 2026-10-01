"""Validate an honest child-only movie-data connectivity/motion sensitivity case.

Subject measurements are bound to actual IDs. Reported associations, participant-bootstrap
intervals and low-motion restriction are recomputed without a forced confounding verdict.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import proof_of_work as pw  # noqa: E402

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(__file__).resolve().parent / "reference_v2.npz"


def _reference():
    assert REF_PATH.exists(), "held-out actual-ID reference_v2.npz is missing"
    import numpy as np
    from development_contract import VERSION
    assert str(np.load(REF_PATH,allow_pickle=False)["schema_version"])==VERSION, "genuine actual-ID child-motion v2 reference required"
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
                                 corr_min=st["CORR_MIN"], cover=1., match=st["MATCH"])
    if any(r.get("long") is not None for r in rows):
        pw.check_subjects_and_values(rows, ref, "long", "long", val_tol=st["VAL_TOL"],
                                     corr_min=st["CORR_MIN"], cover=1., match=st["MATCH"])
    # the per-subject mean_fd column must be the REAL framewise-displacement summary (a fabricated
    # or constant FD cannot reproduce the motion-conditioned collapse recomputed in pillar 3).
    assert "fd" in ref, "reference is missing per-subject mean_fd (rebuild tests/reference.npz)"
    pw.check_subjects_and_values(rows, ref, "fd", "fd", val_tol=st["FD_VAL_TOL"],
                                 corr_min=st["FD_CORR_MIN"], cover=1., match=st["FD_MATCH"])


# ------------------------------------------------------------------ pillar 2
def test_child_population_and_motion_contract():
    import numpy as np
    import pandas as pd
    from development_contract import validate_report
    ref=_reference()
    data=pd.read_csv(OUT/"connectivity.csv")
    ids=data.subject_id.map(pw.canon_id)
    assert ids.is_unique and set(ids)==set(ref["ids"]) and len(data)==155
    mapping={sid:i for i,sid in enumerate(ref["ids"])}
    for (_,row),sid in zip(data.iterrows(),ids):
        index=mapping[sid]
        assert abs(float(row.age)-ref["age"][index])<1e-8
        assert str(row.group)==ref["group"][index]
        assert abs(float(row.mean_fd)-ref["fd"][index])<1e-6
        assert abs(float(row.segregation)-(float(row.short_range)-float(row.long_range)))<1e-8
    validate_report(data,_load("age_effects.json"))
    assert _load("run_metadata.json")["analysis_scope"]=="paper-derived child-only movie-data motion sensitivity"

def test_findings_present():
    assert _findings().strip()
