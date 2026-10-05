"""Manufactured schema mechanics, not scientific calibration or model reruns."""
import copy
import hashlib
from pathlib import Path

import numpy as np
import pytest

import prediction_contract as q


def source_fixture():
    rows = []
    for index,code in enumerate((1,2,3,4,5,1)):
        target = code in (1,2,3,4)
        retained = target and index!=5
        rows.append(dict(source_event_index=index,event_sample=100+index*100,
            previous_value=0,event_code=code,
            modality=(0 if code in (1,2) else 1) if target else None,
            retained=int(retained),drop_reason="retained" if retained else "amplitude" if target else "not_target",
            trial_id=index if retained else None,
            max_ptp_T_per_m=(1e-11 if retained else 5e-10) if target else None,
            max_ptp_channel="MEG fixture" if target else None))
    submitted = [{key:"" if value is None else str(value) for key,value in row.items()} for row in rows]
    return submitted,{"source_rows":rows}


@pytest.mark.parametrize("encoding",("numeric","names","mixed","integral_notation"))
def test_source_modality_equivalent_encodings(encoding):
    rows,reference = source_fixture()
    for index,row in enumerate(rows):
        if not row["modality"]:
            continue
        value = int(row["modality"])
        if encoding=="names" or (encoding=="mixed" and index%2==0):
            row["modality"] = ("auditory","visual")[value]
        elif encoding=="integral_notation":
            row["modality"] = ("0.0","1e0")[value]
    before = copy.deepcopy(rows)
    q.validate_source(rows,reference)
    assert rows==before, "Validation must not rewrite the submitted evidence"


@pytest.mark.parametrize("index",(0,1,2,3,5))
@pytest.mark.parametrize("encoding",("numeric","name"))
def test_source_inconsistent_modality_rejected(index,encoding):
    rows,reference = source_fixture()
    wrong = 1-int(rows[index]["modality"])
    rows[index]["modality"] = str(wrong) if encoding=="numeric" else ("auditory","visual")[wrong]
    with pytest.raises(AssertionError,match="Wrong source modality"):
        q.validate_source(rows,reference)


@pytest.mark.parametrize("value",("","unknown","Auditory","auditory/0","2","-1","0.5","NaN","inf","true"))
def test_missing_or_invalid_target_modality_rejected(value):
    rows,reference = source_fixture()
    rows[0]["modality"] = value
    with pytest.raises(AssertionError):
        q.validate_source(rows,reference)


@pytest.mark.parametrize("value",("auditory","visual","0","1","not_target"))
def test_nontarget_modality_must_still_be_blank(value):
    rows,reference = source_fixture()
    rows[4]["modality"] = value
    with pytest.raises(AssertionError,match="must be blank"):
        q.validate_source(rows,reference)


@pytest.mark.parametrize("field,value",(("event_code","3"),("source_event_index","99"),
    ("retained","0"),("trial_id","7"),("max_ptp_T_per_m","9e-10"),
    ("max_ptp_channel","wrong channel"),("drop_reason","amplitude")))
def test_text_modality_does_not_bypass_other_source_checks(field,value):
    rows,reference = source_fixture()
    rows[0]["modality"] = "auditory"
    rows[0][field] = value
    with pytest.raises(AssertionError):
        q.validate_source(rows,reference)


@pytest.mark.parametrize("field,value",(("true_class","auditory"),("predicted_class","auditory"),
    ("true_class","1"),("decision_score","-2"),("fold","2")))
def test_ledger_alias_does_not_relax_classifier_contract(field,value):
    reference = dict(labels=np.array([0]),folds=np.array([1]),analysis_offsets=np.array([8]),
        retained_event_indices=np.array([0]),times=np.array([.05]),
        pooled_scores=np.array([[-1.]]),per_time_scores=np.array([[-1.]]))
    rows = [dict(estimator=name,source_event_index="0",trial_id="0",time_index="0",
        sample_offset="8",time_s="0.05",fold="1",true_class="0",predicted_class="0",
        decision_score="-1") for name in q.ESTIMATORS]
    q.validate_predictions(rows,reference)
    rows[0][field] = value
    with pytest.raises(AssertionError):
        q.validate_predictions(rows,reference)


def test_public_method_contract_identity_is_unchanged():
    path = Path(__file__).parents[1]/"environment/method_contract.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest()=="b4ff29fb1dcf767d6362fb944081fc7200cd77039ebacf83ca7398f761f1da73"
