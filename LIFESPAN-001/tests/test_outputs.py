"""Declared cross-sectional summary estimator; no forced age-direction/absence narrative."""
import csv
import json
import os
from pathlib import Path
import numpy as np
from scipy import stats
import proof_of_work as pw

OUT=Path(os.environ.get("OUTPUT_DIR","/app/output"))


def test_reference_is_regenerated_and_exact_cohort():
    ref=pw.load_reference(Path(__file__).with_name("reference.npz"))
    assert ref["stats"].get("estimator_contract")=="diagonal-zero-clip-v1", "regenerate reference after diagonal/denominator repair"
    sub=pw.load_submitted(OUT/"connectome_summary.csv")
    assert len(sub)==59 and set(sub)==set(ref["ids"])
    pw.check_subjects_and_values(sub,ref,ref["stats"])


def test_signed_age_relationships_recompute():
    sub=pw.load_submitted(OUT/"connectome_summary.csv")
    result=json.loads((OUT/"results.json").read_text())
    assert result["n_subjects"]==len(sub)==59
    ages=np.array([r["age"] for r in sub.values()])
    for r in sub.values():
        assert abs(r["seg"]-(r["within"]-r["between"])/r["within"])<=1e-5
    for key,column in (("overall_connectivity_vs_age","global"),("system_segregation_vs_age","seg")):
        values=np.array([r[column] for r in sub.values()])
        corr,p=stats.pearsonr(values,ages)
        interval=np.tanh(np.arctanh(np.clip(corr,-.999999,.999999))+np.array([-1,1])*1.96/np.sqrt(len(ages)-3))
        assert abs(result[key]["pearson_r"]-corr)<=1e-5
        assert abs(result[key]["p"]-p)<=1e-5
        assert np.allclose(result[key]["ci95"],interval,atol=1e-5,rtol=0)


def test_network_partition_is_complete():
    rows=list(csv.DictReader((OUT/"roi_partition.csv").open()))
    assert len(rows)==148 and {int(r["roi_index"]) for r in rows}==set(range(148))
    assert len({int(r["network"]) for r in rows})==7


def test_findings_present():
    assert (OUT/"findings.md").read_text().strip()
