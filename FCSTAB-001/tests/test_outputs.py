"""Proof-of-work grading for FCSTAB-001 (within-run change of the strongest FC edges).

Templates: QSMDIPOLE-001 (held-out reference, tight tolerance) + NETINTEG-001 (grade the
reported result against PINNED real subject ids + a non-constant guard). See
PROOF_OF_WORK_SPEC.md. A passing submission is impossible without running the real
four-selection analysis on the pinned, baked cohort.

Held-out reference (tests/reference.npz), built by running solution/compute.py on the baked
CC200 time series of the exact 40 quality-checked ABIDE cpac subjects (all PITT, eyes closed,
196 TRs / ~4.9 min). Per-subject signed Fisher-z change (second - first) of the top-decile
edges under four selection schemes; group discriminating means:

  forward (top by 1st half)  = -0.212   <- the naive, SELECTION-CONTAMINATED decline
  reverse (top by 2nd half)  = +0.235   <- opposite sign: the "effect" follows the selection
  independent (LOSO strong)  = -0.000   <- selection-free estimate, ~0 (CI [-0.042, +0.042])
  random  (size-matched)     = +0.005   <- selection-free control, ~0

The graded scientific conclusion is NUMERIC, not keyword-based: the naive top-decile decline
cannot by itself establish weakening because selection on the first half biases second-first
downward -- shown by the sign flip under reverse selection and by the selection-free
(independent/random) estimates being ~0 within the prespecified +/-0.05 z equivalence margin.
An agent that only ran the naive forward analysis cannot produce the reverse per-subject
column or the near-zero independent mean, so it fails.

Three pillars (all required):
  1. exact pinned subjects + real per-subject forward/reverse values (kills fabricated/dup rows)
  2. recompute the group means FROM the submitted rows == reported summary == reference
  3. grade the discriminating scheme means as numbers (sign flip + selection-free ~0)
"""
import json
import re

from proof_of_work import (
    OUT, load_reference, load_submitted, resolve_columns, submitted_map, coverage,
    real_id_fraction, nonconstant, per_subject_match, group_mean, reported_scheme_means,
)

REF = load_reference()
ST = REF["stats"]
VAL_TOL = ST["VAL_TOL"]          # per-subject |submitted - ref| for forward/reverse
GROUP_TOL = ST["GROUP_TOL"]      # group-mean recompute vs reference (pinned schemes)
CONSIST = ST["CONSIST_TOL"]      # rows-recompute vs reported-in-summary consistency
NEAR = ST["NEARZERO_MARGIN"]     # |selection-free group mean| upper bound
COVER = ST["COVER"]
MATCH = ST["MATCH"]
EPS = ST["EPS"]


def _summary():
    for name in ("summary.json", "run_metadata.json", "results.json"):
        p = OUT / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def _find_numbers(obj, key_re):
    out = []

    def walk(o, key=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, str(k))
        elif isinstance(o, list):
            for v in o:
                walk(v, key)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            if re.search(key_re, key, re.I):
                out.append(float(o))
    walk(obj)
    return out


def _findings():
    p = OUT / "findings.md"
    return p.read_text(encoding="utf-8").lower() if p.exists() else ""


# =============================================================================================
# Pillar 1 -- exact subjects + real per-subject values
# =============================================================================================
def test_csv_covers_exact_pinned_subjects():
    header, rows = load_submitted()
    cols = resolve_columns(header)
    assert cols["id"], f"stability.csv has no subject-id column (columns: {header})"
    idmap = submitted_map(rows, resolve_columns(header)["forward_delta"] or header[-1])
    # need the id column populated; build a bare id set
    ids = {re.sub(r"\D", "", str(r[cols['id']])).lstrip('0') for r in rows if r.get(cols['id'])}
    cov = sum(1 for i in REF["ids"] if i in ids) / len(REF["ids"])
    assert cov >= COVER, (
        f"stability.csv covers only {cov:.0%} of the {len(REF['ids'])} pinned ABIDE subjects "
        f"(need >= {COVER:.0%}); the exact quality-checked cohort must be analysed, not a "
        f"different or fabricated subject list")
    real = sum(1 for i in ids if i in set(REF["ids"])) / max(1, len(ids))
    assert real >= 0.85, (
        f"only {real:.0%} of the submitted subject ids are the real pinned ids -- the table "
        f"appears padded with fabricated subjects")


def test_forward_per_subject_matches_reference():
    """PILLAR 1: the per-subject forward top-decile numbers must be the REAL values for the
    pinned subjects (non-constant, and within tolerance) -- fabricated / constant / duplicated
    rows fail even if the group headline is right."""
    header, rows = load_submitted()
    cols = resolve_columns(header)
    for key, ref_vals in (("forward_first", REF["forward_first"]),
                          ("forward_second", REF["forward_second"]),
                          ("forward_delta", REF["forward_delta"])):
        col = cols[key]
        assert col, f"stability.csv is missing the {key} column (columns: {header})"
        smap = submitted_map(rows, col)
        assert coverage(smap, REF["ids"]) >= COVER, f"{key}: too few pinned subjects present"
        assert nonconstant(smap, EPS), (
            f"{key} is constant across subjects (pstdev <= {EPS}); a real per-subject "
            f"computation is not constant -- looks fabricated/duplicated")
        frac, n = per_subject_match(smap, REF["ids"], ref_vals, VAL_TOL)
        assert frac >= MATCH, (
            f"{key}: only {frac:.0%} of {n} matched subjects are within {VAL_TOL} of the real "
            f"per-subject value (need >= {MATCH:.0%}); the submitted rows are not the real "
            f"first-half-selected top-decile numbers for these subjects")


def test_reverse_per_subject_matches_reference():
    """PILLAR 1 (discriminating): reverse-half selection is not on the naive path. Its
    per-subject signed change must be the REAL values -- an agent that only ran forward
    selection cannot produce this column."""
    header, rows = load_submitted()
    col = resolve_columns(header)["reverse_delta"]
    assert col, (
        "stability.csv has no reverse-half-selection delta column. The task requires the "
        "per-subject signed change of the top-decile edges selected on the SECOND half "
        "(reverse_delta) -- this is what exposes the selection contamination.")
    smap = submitted_map(rows, col)
    assert coverage(smap, REF["ids"]) >= COVER, "reverse_delta: too few pinned subjects present"
    assert nonconstant(smap, EPS), "reverse_delta is constant across subjects -- looks fabricated"
    frac, n = per_subject_match(smap, REF["ids"], REF["reverse_delta"], VAL_TOL)
    assert frac >= MATCH, (
        f"reverse_delta: only {frac:.0%} of {n} matched subjects are within {VAL_TOL} of the "
        f"real reverse-selection value (need >= {MATCH:.0%}). Select the top decile on the "
        f"SECOND half and re-measure the same edges' change; the group mean should be POSITIVE "
        f"(~+0.235), the opposite sign of the forward decline.")


def test_all_selection_evidence_and_uncertainty():
    import csv
    import numpy as np
    from pathlib import Path
    from selection_contract import check_source,check_selections
    path=Path("/app/data/abide_cc200_pitt40.npz")
    if not path.exists():
        path=Path(__file__).resolve().parents[1]/"environment/data/abide_cc200_pitt40.npz"
    z1,z2,zf,ids=check_source(path)
    rows=list(csv.DictReader((OUT/"stability.csv").open()))
    evidence=json.loads((OUT/"selection_evidence.json").read_text())
    report=_summary()
    expected,p,equivalent,reliability=check_selections(z1,z2,zf,ids,evidence,rows,
                                                    seed=report["preprocessing"]["seed"])
    for scheme,values in expected.items():
        for key,value in values.items():
            assert np.isclose(report["selection_schemes"][scheme][key],value,atol=1e-5,rtol=1e-5)
    assert report["equivalence"]["margin_z"]==.05
    assert np.isclose(report["equivalence"]["tost_p"],p,atol=1e-6)
    assert report["equivalence"]["equivalent_within_margin"] is equivalent
    for key,value in reliability.items():
        assert np.isclose(report["reliability"][key],value,atol=1e-6)

def test_findings_present():
    assert _findings().strip()
