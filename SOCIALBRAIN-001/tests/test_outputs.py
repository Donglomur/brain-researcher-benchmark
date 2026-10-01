"""Validate real subject values under two publicly declared GSR sensitivity pipelines.

Fisher-z aggregation and actual subject-ID references require genuine version2
regeneration. Child age and motion-adjusted statistics are recomputed from submitted
measurements; no fixed sign, non-significance or causal/artifact conclusion is graded.
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
    assert REF_PATH.exists(), "held-out Fisher/subject-ID reference_v2.npz is missing"
    import numpy as np
    from social_contract import VERSION
    assert str(np.load(REF_PATH,allow_pickle=False)["schema_version"])==VERSION, "genuine Fisher/ID v2 reference required"
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


def _bound():
    """Bind the two public pipeline names to their declared estimands."""
    ref = _reference(); st = ref["stats"]
    rows, across_cols = _submitted()
    std_col, alt_col, diag = pw.assign_across_columns(rows, ref, cover=st["COVER"])
    pw.bind_column(rows, std_col, "across_std")
    pw.bind_column(rows, alt_col, "across_alt")
    return ref, st, rows, std_col, alt_col, diag


# ------------------------------------------------------------------ well-formedness
def test_connectivity_computed():
    rows, across_cols = _submitted()
    assert len(rows) >= 120, f"expected ~155 subjects, got {len(rows)}"
    assert across_cols, "network_connectivity.csv has no across-network column"
    # at least one across-network column present and in-range per subject
    ok = False
    for c in across_cols:
        vals = [r["across_by_col"].get(c) for r in rows if r["across_by_col"].get(c) is not None]
        if len(vals) >= 120 and all(-1.01 <= v <= 1.01 for v in vals):
            ok = True
    assert ok, "no across-network column has >=120 valid per-subject values in [-1,1]"


# ------------------------------------------------------------------ pillar 1 (real per-subject data, BOTH pipelines)
def test_proof_of_work_subjects_and_values():
    """Authenticate all public per-subject network measurements under their named pipelines."""
    ref, st, rows, std_col, alt_col, diag = _bound()
    assert std_col is not None, (
        "network_connectivity.csv has no across-network column that tracks the real per-subject "
        f"connectivity of the ds000228 subjects (candidate diagnostics: {diag}).")
    # standard-clean across-network per subject must be the real ones
    pw.check_subjects_and_values(rows, ref, "across", "across_std", val_tol=st["VAL_TOL"],
                                 corr_min=st["CORR_MIN"], cover=1., match=st["MATCH"])
    for column in ("within_tom","within_pain"):
        pw.check_subjects_and_values(rows,ref,column,column,val_tol=st["VAL_TOL"],
                                     corr_min=st["CORR_MIN"],cover=1.,match=st["MATCH"])
    # a genuine SECOND across-network column under the alternative preprocessing must be present
    assert alt_col is not None and alt_col != std_col, (
        "network_connectivity.csv reports the across-network correlation under only ONE "
        "preprocessing choice. The task asks you to report it per subject under EACH preprocessing "
        "choice you consider; a single pipeline cannot establish whether the anti-correlation is "
        "robust to the analyst's preprocessing decisions.")
    pw.check_subjects_and_values(rows, ref, "across_gsr", "across_alt", val_tol=st["VAL_TOL"],
                                 corr_min=st["CORR_MIN"], cover=1., match=st["MATCH"])


# ------------------------------------------------------------------ pillar 2 (recompute both correlations from rows)
def test_recompute_children_spearman_from_rows():
    """Recompute the children's Spearman(age, across-network) FROM the submitted rows, for BOTH the
    standard-clean and the alternative-preprocessing columns. The standard-clean value must match
    the ~null reference and the reported age_effects.json value; the alternative value is checked
    in the discrimination pillar below."""
    ref, st, rows, std_col, alt_col, diag = _bound()
    r_std, n = pw.children_spearman(rows, ref, "across_std")
    assert n >= 20, f"too few child rows to recompute the age correlation ({n})"
    ref_ng = float(st["across_nogsr_rs"])
    assert abs(r_std - ref_ng) <= st["RS_TOL"], (
        f"children Spearman(age, across-network) recomputed from the submitted standard-clean rows "
        f"({r_std:+.3f}) does not match the standard-clean reference ({ref_ng:+.3f}, tol "
        f"{st['RS_TOL']}). The per-subject across-network column is not the real quantity.")
    eff = _load("age_effects.json")
    reported = pw.find_across_r(eff, gsr=False)
    if reported is not None:
        assert abs(reported - r_std) <= st["RS_TOL"], (
            f"age_effects.json across-network r ({reported:+.3f}) disagrees with the value the "
            f"submitted standard-clean rows produce ({r_std:+.3f}); CSV and JSON are inconsistent.")


# ------------------------------------------------------------------ measured GSR/motion sensitivity, without a fixed verdict
def test_measured_preprocessing_and_motion_sensitivity():
    import numpy as np
    import pandas as pd
    from scipy.stats import spearmanr
    from social_contract import partial_rank_corr
    ref=_reference()
    data=pd.read_csv(OUT/"network_connectivity.csv")
    canonical=data.subject_id.map(pw.canon_id)
    assert canonical.is_unique and set(canonical)==set(ref["ids"])
    z=np.load(REF_PATH,allow_pickle=False)
    mapping={str(i):float(fd) for i,fd in zip(ref["ids"],z["ref_mean_fd"])}
    identity={sid:i for i,sid in enumerate(ref["ids"])}
    for (_,row),sid in zip(data.iterrows(),canonical):
        index=identity[sid]
        assert abs(float(row.age)-float(ref["age"][index]))<1e-8
        assert str(row.group)==ref["group"][index]
    assert np.allclose(data.mean_fd,[mapping[i] for i in canonical],atol=1e-6)
    child=data[data.group=="child"]
    assert len(child)==122 and len(data[data.group=="adult"])==33
    eff=_load("age_effects.json")
    for column in ("across_network","across_network_gsr","within_tom","within_pain"):
        r,p=spearmanr(child.age,child[column])
        assert abs(eff[column]["r"]-r)<.0001 and abs(eff[column]["p"]-p)<1e-6
        r,p=partial_rank_corr(child.age,child[column],child.mean_fd)
        assert abs(eff[column]["motion_adjusted_rank_r"]-r)<1e-6
        assert abs(eff[column]["motion_adjusted_rank_p"]-p)<1e-6
    adults=data[data.group=="adult"]
    for column in ("across_network","across_network_gsr","within_tom","within_pain"):
        assert abs(eff["adult_means"][column]-adults[column].mean())<1e-6
    assert eff["n_children"]==122 and eff["n_adults"]==33
    assert _load("run_metadata.json")["analysis_scope"]=="paper-derived GSR/motion sensitivity adaptation"

def test_findings_present():
    assert _findings().strip()
