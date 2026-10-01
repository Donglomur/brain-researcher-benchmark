"""Zero-clipped full-pair segregation on an exact movie cohort; signed contrast recomputation."""
import json
import os
from pathlib import Path
import numpy as np
import proof_of_work as pw

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def _table():
    return pw.load_submitted(OUT / "segregation.csv", ("participant","subject"), ("segregation",), ("group",))


def test_exact_cohort_group_and_zero_clipped_values():
    ref = pw.load_reference(Path(__file__).with_name("reference.npz"))
    values, groups = _table()
    assert len(values)==40 and set(values)==set(ref["ids"])
    assert set(groups)==set(values), "required child/adult manifest-derived groups missing"
    assert all(groups[i] == str(ref["grp_by_id"][i]).lower() for i in values)
    refvals = np.array([ref["by_id_clip"][i] for i in ref["ids"]])
    submitted = np.array([values[i] for i in ref["ids"]])
    assert np.isfinite(submitted).all() and np.std(submitted)>1e-3
    assert np.corrcoef(submitted, refvals)[0,1]>=.9
    assert np.mean(np.abs(submitted-refvals)<=.06)>=.8, "primary zero-clipped endpoint mismatch"


def test_cohort_and_child_adult_estimates_recompute():
    values, groups = _table()
    child = np.array([values[i] for i in values if groups[i]=="child"])
    adult = np.array([values[i] for i in values if groups[i]=="adult"])
    assert len(child)==31 and len(adult)==9
    meta = json.loads((OUT / "run_metadata.json").read_text())
    difference = float(adult.mean()-child.mean())
    se = float(np.sqrt(adult.var(ddof=1)/len(adult)+child.var(ddof=1)/len(child)))
    assert abs(meta["segregation_mean"]-np.mean(list(values.values())))<=.001
    assert abs(meta["segregation_child_mean"]-child.mean())<=.001
    assert abs(meta["segregation_adult_mean"]-adult.mean())<=.001
    assert abs(meta["adult_minus_child"]-difference)<=1e-5
    assert np.allclose(meta["adult_minus_child_ci95"], [difference-1.96*se,difference+1.96*se], atol=1e-5,rtol=0)


def test_findings_present():
    assert (OUT / "findings.md").read_text().strip()
