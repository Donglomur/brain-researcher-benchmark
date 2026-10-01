import importlib.util
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("social",ROOT/"tests/social_contract.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def test_fisher_average_not_raw_average():
    assert m.fisher_mean([.9,.1])!=pytest.approx(.5)
def test_partial_rank_motion_adjustment():
    rng=np.random.default_rng(1);motion=rng.normal(size=80)
    age=motion+rng.normal(size=80)*.1;values=motion+rng.normal(size=80)*.1
    r,p=m.partial_rank_corr(age,values,motion)
    assert abs(r)<.5 and 0<=p<=1
def test_new_reference_version():
    assert m.VERSION=="socialbrain-fisher-id-v2"

def test_oracle_entrypoint_and_failfast_are_executable(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    spec=importlib.util.spec_from_file_location("social_oracle",ROOT/"solution/compute.py")
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    assert callable(oracle.main)
    oracle.write_failfast("source unavailable")
    import json
    assert json.loads((tmp_path/"run_metadata.json").read_text())["status"]=="failed_precondition"
    assert "source unavailable" in (tmp_path/"findings.md").read_text()

def test_actual_subject_ids_do_not_depend_on_file_order(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    spec=importlib.util.spec_from_file_location("social_identity",ROOT/"solution/compute.py")
    oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    assert oracle.participant_id("sub-pixar155_task-pixar_desc-preproc_bold.nii.gz")=="sub-pixar155"
    with pytest.raises(ValueError):oracle.participant_id("ambiguous.nii.gz")

def test_values_bind_to_ids_not_same_age():
    spec=importlib.util.spec_from_file_location("social_pw",ROOT/"tests/proof_of_work.py")
    pw=importlib.util.module_from_spec(spec);spec.loader.exec_module(pw)
    reference={"ids":["1","2","3","4"],"age":[6.,6.,8.,9.],"value":[.1,.8,.3,.4]}
    rows=[{"id":sid,"age":age,"value":value} for sid,age,value in zip(reference["ids"],reference["age"],reference["value"])]
    pw.check_subjects_and_values(list(reversed(rows)),reference,"value","value",1e-8,.99,1.,1.)
    rows[0]["value"],rows[1]["value"]=rows[1]["value"],rows[0]["value"]
    with pytest.raises(AssertionError):
        pw.check_subjects_and_values(rows,reference,"value","value",1e-8,.99,1.,1.)

def test_public_pipeline_names_cannot_be_swapped_by_best_match():
    spec=importlib.util.spec_from_file_location("social_labels",ROOT/"tests/proof_of_work.py")
    pw=importlib.util.module_from_spec(spec);spec.loader.exec_module(pw)
    rows=[{"id":"1","across_by_col":{"across_network":.8,"across_network_gsr":.1}}]
    assert pw.assign_across_columns(rows,{},1.)[:2]==("across_network","across_network_gsr")

def test_mislabeled_gsr_pipeline_rejected():
    spec=importlib.util.spec_from_file_location("social_swapped",ROOT/"tests/proof_of_work.py")
    pw=importlib.util.module_from_spec(spec);spec.loader.exec_module(pw)
    reference={"ids":["1","2","3","4"],"across":[.1,.2,.3,.4],"across_gsr":[.8,.6,.4,.2]}
    rows=[{"id":sid,"across_by_col":{"across_network":gsr,"across_network_gsr":raw}} for sid,raw,gsr in zip(reference["ids"],reference["across"],reference["across_gsr"])]
    std,alt,_=pw.assign_across_columns(rows,reference,1.)
    pw.bind_column(rows,std,"across_std")
    with pytest.raises(AssertionError):
        pw.check_subjects_and_values(rows,reference,"across","across_std",1e-8,.99,1.,1.)
