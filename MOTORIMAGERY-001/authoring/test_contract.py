"""Explicit invented parser/statistics fixtures, never a scientific reference bank."""
import copy
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tests"))
import proof_of_work as q


def write_rows(path, rows, columns=None):
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns or list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def read_rows(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def write_statistics(output, reference, predictions, targets=None):
    targets = reference["targets"] if targets is None else targets
    subjects, folds, results = q.statistics_from_predictions(reference["subject"], reference["run"], targets, predictions)
    write_rows(output/"per_subject.csv", subjects, q.SUBJECT_FIELDS)
    write_rows(output/"fold_receipts.csv", list(folds.values()), q.FOLD_FIELDS)
    (output/"decoding_results.json").write_text(json.dumps(results, allow_nan=False))


def prediction_rows(reference, scores=None, targets=None):
    scores = reference["scores"] if scores is None else scores
    targets = reference["targets"] if targets is None else targets
    for rep in range(scores.shape[0]):
        for index in range(scores.shape[1]):
            row = {key: int(reference[key][index]) for key in ("subject", "run", "event_index", "event_sample", "source_class")}
            row.update(replicate=rep, target_class=int(targets[rep,index]),
                       predicted_class=int(scores[rep,index] > 0), decision_score=float(scores[rep,index]))
            yield row


def minimal_metadata(reference):
    metadata = copy.deepcopy(reference["stats"]["metadata_contract"])
    n = len(reference["subject"]); total = len(reference["events"])
    metadata.update(status="ok", n_subjects=len(np.unique(reference["subject"])), n_epochs_total=n,
                    n_source_events=total, n_dropped_epochs=total-n, n_epochs_by_run=q.inventory(reference["events"]))
    return metadata


def write_output(output, reference):
    write_rows(output/"source_epochs.csv", list(reference["events"].values()), q.EVENT_FIELDS)
    write_rows(output/"oof_predictions.csv", list(prediction_rows(reference)), q.PRED_FIELDS)
    write_statistics(output, reference, reference["predictions"])
    (output/"run_metadata.json").write_text(json.dumps(minimal_metadata(reference)))
    (output/"findings.md").write_text("An invented mechanical fixture. No scientific result is claimed.")


@pytest.fixture
def reference(monkeypatch):
    monkeypatch.setattr(q, "SUBJECTS", (1, 2)); monkeypatch.setattr(q, "N_PERM", 3)
    source = []
    for subject in (1, 2):
        for run in q.RUNS:
            for event in range(15):
                keep = event in (0, 1, 2, 3, 14)
                source.append(dict(subject=subject, run=run, event_index=event, event_sample=1000+event*160,
                    source_class=(event+subject+run)%2, retained=keep,
                    drop_reason="" if keep else ("annotation" if event == 4 else "out_of_bounds")))
    retained = [row for row in source if row["retained"]]
    ref = {name: np.array([row[name] for row in retained]) for name in ("subject", "run", "event_index", "event_sample", "source_class")}
    targets = q.permutation_targets(ref["subject"], ref["run"], ref["source_class"], ref["event_index"], 3)
    scores = (2*targets-1).astype(float)
    scores[0, ::3] *= -1; scores[1, ::2] *= -1; scores[2, 1::3] *= -1
    scores[0, 0] = 1e-9
    contract = dict(pipeline_id=q.PIPELINE_ID, source_sha256={"invented": "fixture-not-real"},
                    channels=[f"fixture{i}" for i in range(64)], sfreq=160,
                    permutation=dict(n_permutations=3, seed=0, unit="original_balanced_pair"),
                    tiny_numerical_setting=1e-15)
    ref.update(source_rows=source, targets=targets, scores=scores, predictions=(scores>0).astype(np.int8),
               stats=dict(pipeline_id=q.PIPELINE_ID, source_sha256=contract["source_sha256"], metadata_contract=contract))
    return q.validate_reference(ref)


@pytest.fixture
def output(tmp_path, reference):
    write_output(tmp_path, reference)
    return tmp_path


def test_explicit_small_mechanics_fixture_passes(output, reference):
    q.validate_output_directory(output, reference)


@pytest.mark.parametrize("value", [None, "", True, False, "NaN", "inf", ".1"])
def test_integer_rejects_invalid(value):
    with pytest.raises(AssertionError): q.integer(value, "id")


@pytest.mark.parametrize("value", [1, 1., "1", "1.0", "1e0"])
def test_integer_notation(value):
    assert q.integer(value, "id") == 1


def test_original_pair_rng_reset_and_fixed_singleton(reference):
    for subject in (1, 2):
        rng = np.random.RandomState(0)
        for rep in range(1, 4):
            for run in q.RUNS:
                for pair in range(2):
                    take = np.flatnonzero((reference["subject"]==subject)&(reference["run"]==run)&(reference["event_index"]//2==pair))
                    np.testing.assert_array_equal(reference["targets"][rep,take], rng.permutation(reference["source_class"][take]))
    singleton = reference["event_index"] == 14
    np.testing.assert_array_equal(reference["targets"][:,singleton], np.tile(reference["source_class"][singleton], (4,1)))


def test_dropped_pair_survivor_not_repaired_and_does_not_consume_rng():
    events=np.array([0,2,3,5,14]); labels=np.array([1,0,1,0,1])
    result=q.permutation_targets(np.ones(5,int), np.full(5,6), labels, events, 3)
    np.testing.assert_array_equal(result[:,[0,3,4]],np.tile(labels[[0,3,4]],(4,1)))
    rng=np.random.RandomState(0)
    for rep in range(1,4): np.testing.assert_array_equal(result[rep,1:3],rng.permutation(labels[1:3]))


def test_permutation_is_order_independent_within_original_pair():
    events=np.array([3,0,14,2,1]); labels=events%2
    result=q.permutation_targets(np.ones(5,int),np.full(5,6),labels,events,5)
    order=np.argsort(events)
    sorted_result=q.permutation_targets(np.ones(5,int),np.full(5,6),labels[order],events[order],5)
    np.testing.assert_array_equal(result[:,order],sorted_result)


def test_pooled_epoch_accuracy_not_mean_fold_accuracy():
    runs=np.array([6,6,10,10,14,14,14,14]); subject=np.ones(8,int)
    labels=np.tile([0,1],4); targets=np.tile(labels,(3,1)); predictions=targets.copy()
    predictions[0,runs!=14]=1-predictions[0,runs!=14]
    rows,folds,result=q.statistics_from_predictions(subject,runs,targets,predictions)
    assert rows[0]["accuracy"]==.5
    assert np.mean([folds[(1,0,r)]["accuracy"] for r in q.RUNS])==pytest.approx(1/3)
    assert rows[0]["perm_p"]==1 and rows[0]["n_null_ge_observed"]==2
    assert result["group_t_vs_chance"] is None and result["group_p_vs_chance"] is None


def test_permutation_includes_ties_and_plus_one():
    runs=np.repeat(q.RUNS,2); targets=np.tile([0,1]*3,(4,1)); pred=targets.copy()
    pred[2,:]=1-pred[2,:]; pred[3,:2]=1-pred[3,:2]
    rows,_,_=q.statistics_from_predictions(np.ones(6,int),runs,targets,pred)
    assert rows[0]["n_null_ge_observed"]==1 and rows[0]["perm_p"]==.5
    assert rows[0]["null_sd"]==pytest.approx(np.std([1,0,2/3],ddof=0))


def test_holm_family_and_order():
    np.testing.assert_allclose(q.holm_adjust([.02,.001,.03,.5]),[.06,.004,.06,.5])


def test_negative_kappa_is_not_filtered():
    assert q.kappa_score(np.array([0,1]),np.array([1,0]))==-1


@pytest.mark.parametrize("mutation", ["drop","duplicate","sample","label","retained","fractional_id","reason"])
def test_source_ledger_mutation(output,reference,mutation):
    path=output/"source_epochs.csv"; rows=read_rows(path)
    if mutation=="drop": rows.pop()
    elif mutation=="duplicate": rows.append(dict(rows[0]))
    elif mutation=="sample": rows[0]["event_sample"]=float(rows[0]["event_sample"])+1
    elif mutation=="label": rows[0]["source_class"]=1-int(rows[0]["source_class"])
    elif mutation=="retained": rows[0].update(retained=False,drop_reason="annotation")
    elif mutation=="fractional_id": rows[0]["event_index"]=".5"
    else: rows[0]["drop_reason"]="amplitude"
    write_rows(path,rows)
    with pytest.raises(AssertionError): q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation", ["drop","duplicate","sample","source","target","replicate","fractional","score","sign","nan"])
def test_oof_mutation(output,reference,mutation):
    path=output/"oof_predictions.csv"; rows=read_rows(path)
    if mutation=="drop": rows.pop()
    elif mutation=="duplicate": rows.append(dict(rows[0]))
    elif mutation=="sample": rows[0]["event_sample"]=0
    elif mutation=="source": rows[0]["source_class"]=1-int(rows[0]["source_class"])
    elif mutation=="target": rows[0]["target_class"]=1-int(rows[0]["target_class"])
    elif mutation=="replicate": rows[0]["replicate"]=999
    elif mutation=="fractional": rows[0]["event_index"]=".5"
    elif mutation=="score": rows[0]["decision_score"]=1000
    elif mutation=="sign": rows[0]["predicted_class"]=1-int(rows[0]["predicted_class"])
    else: rows[0]["decision_score"]="nan"
    write_rows(path,rows)
    with pytest.raises(AssertionError): q.validate_output_directory(output,reference)


def test_tolerance_equivalent_boundary_prediction_requires_recomputed_statistics(output,reference):
    scores=reference["scores"].copy(); scores[0,0]=-1e-9
    write_rows(output/"oof_predictions.csv",list(prediction_rows(reference,scores)),q.PRED_FIELDS)
    with pytest.raises(AssertionError): q.validate_output_directory(output,reference)
    write_statistics(output,reference,(scores>0).astype(np.int8))
    q.validate_output_directory(output,reference)


@pytest.mark.parametrize("field", q.FOLD_FIELDS)
def test_every_fold_field_checked(output,reference,field):
    rows=read_rows(output/"fold_receipts.csv"); rows[0][field]=float(rows[0][field])+1
    write_rows(output/"fold_receipts.csv",rows)
    with pytest.raises(AssertionError): q.validate_output_directory(output,reference)


@pytest.mark.parametrize("field", q.SUBJECT_FIELDS)
def test_every_subject_field_checked(output,reference,field):
    rows=read_rows(output/"per_subject.csv"); rows[0][field]=float(rows[0][field])+1
    write_rows(output/"per_subject.csv",rows)
    with pytest.raises(AssertionError): q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation", ["counts","run_counts","hash","channels","sfreq","seed","tiny_setting"])
def test_bad_metadata(output,reference,mutation):
    path=output/"run_metadata.json"; data=q.load_json(path)
    if mutation=="counts": data["n_epochs_total"]+=1
    elif mutation=="run_counts": data["n_epochs_by_run"][0]["n_retained"]+=1
    elif mutation=="hash": data["source_sha256"]={}
    elif mutation=="channels": data["channels"]=data["channels"][::-1]
    elif mutation=="sfreq": data["sfreq"]=159
    elif mutation=="seed": data["permutation"]["seed"]=1
    else: data["tiny_numerical_setting"]=0
    path.write_text(json.dumps(data))
    with pytest.raises(AssertionError): q.validate_output_directory(output,reference)


def test_order_extras_numeric_notation_and_free_prose(output,reference):
    for name in ("source_epochs.csv","oof_predictions.csv","fold_receipts.csv","per_subject.csv"):
        rows=read_rows(output/name)
        for row in rows:
            row["subject"]=f'{int(row["subject"])}.0'; row["extra"]= "ignored"
        write_rows(output/name,rows[::-1],list(rows[0])[::-1])
    meta=q.load_json(output/"run_metadata.json"); meta["n_epochs_by_run"].reverse()
    (output/"run_metadata.json").write_text(json.dumps(meta)); (output/"findings.md").write_text("Here are the measurements.")
    q.validate_output_directory(output,reference)


@pytest.mark.parametrize("name",q.FILES)
def test_missing_file(output,reference,name):
    (output/name).unlink()
    with pytest.raises(AssertionError): q.validate_output_directory(output,reference)


def test_empty_prose(output,reference):
    (output/"findings.md").write_text(" \n")
    with pytest.raises(AssertionError): q.validate_output_directory(output,reference)


def test_old_bank_id_is_rejected(reference):
    reference["stats"]["pipeline_id"]="eegbci-run-held-out-csp-v2"
    with pytest.raises(AssertionError): q.validate_reference(reference)


def test_builder_reapplies_private_csp_lda_without_training():
    from build_reference import reconstruct_scores
    x=np.arange(1,37,dtype=float).reshape(6,2,3)/10
    runs=np.repeat(q.RUNS,2)
    filters=np.tile(np.eye(2),(6,1,1))
    coef=np.tile([.2,-.3],(6,1)); intercept=np.full(6,.1)
    score=np.tile(np.log(np.mean(x*x,axis=-1))@coef[0]+intercept[0],(2,1))
    receipt=dict(X=x,subject=np.ones(6,int),run=runs,decision_score=score,
        fold_subject=np.ones(6,int),fold_replicate=np.repeat([0,1],3),fold_test_run=np.tile(q.RUNS,2),
        csp_filters=filters,csp_rank=np.full(6,2),csp_eigenvalues=np.full((6,2),.5),
        lda_coef=coef,lda_intercept=intercept,lda_classes=np.tile([0,1],(6,1)))
    assert reconstruct_scores(receipt)<1e-12
    receipt["lda_coef"][0,0]+=.1
    with pytest.raises(AssertionError,match="reconstruct OOF"):
        reconstruct_scores(receipt)


def test_global_zero_variance_group_rule_is_not_performance_gate():
    labels=np.tile([0,1],6); runs=np.tile(np.repeat(q.RUNS,2),2)
    targets=np.tile(labels,(3,1)); subject=np.repeat([1,2],6)
    rows,_,result=q.statistics_from_predictions(subject,runs,targets,targets.copy())
    assert result["accuracy"]==1 and result["group_t_vs_chance"] is None
    assert result["group_p_vs_chance"] is None and all(row["perm_p"]==1 for row in rows)


def test_constant_decimal_accuracy_has_mathematically_zero_variance():
    labels=np.tile([0,1,0,1,0],10); runs=np.tile([6,6,10,14,14],10)
    subject=np.repeat(np.arange(1,11),5); targets=np.tile(labels,(3,1)); prediction=targets.copy()
    for current in range(10): prediction[0,current*5:current*5+2]=1-prediction[0,current*5:current*5+2]
    _,_,result=q.statistics_from_predictions(subject,runs,targets,prediction)
    assert result["accuracy"]==pytest.approx(.6)
    assert result["group_t_vs_chance"] is None and result["group_p_vs_chance"] is None
