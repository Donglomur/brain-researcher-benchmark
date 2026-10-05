"""Acceptance/forgery regressions derived only from an executed source oracle.

Set REPAIR_ORACLE_OUTPUT to a genuine production directory. No scientific bank,
epochs or fitted predictions are invented here. Mutations occur in tmp_path.
"""
import copy
import json
import os
from pathlib import Path
import shutil

import numpy as np
import pytest

from test_contract import q, write_rows, read_rows, write_statistics, prediction_rows, minimal_metadata


@pytest.fixture(scope="module")
def real_reference():
    if not os.environ.get("REPAIR_ORACLE_OUTPUT"):
        pytest.skip("requires genuine full production oracle output")
    return q.load_reference()


@pytest.fixture
def real_output(tmp_path,real_reference):
    source=Path(os.environ["REPAIR_ORACLE_OUTPUT"])
    for name in q.FILES: shutil.copy2(source/name,tmp_path/name)
    return tmp_path


def write_coherent_predictions(output,reference,scores,targets=None):
    write_rows(output/"oof_predictions.csv",list(prediction_rows(reference,scores,targets)),q.PRED_FIELDS)
    write_statistics(output,reference,(scores>0).astype(np.int8),targets)


def test_genuine_production_passes(real_output,real_reference):
    q.validate_output_directory(real_output,real_reference)


def test_public_template_is_exact_bank_recipe(real_reference):
    template=Path(__file__).resolve().parents[1]/"environment"/"method_contract.json"
    assert q.load_json(template)==real_reference["stats"]["metadata_contract"]


def test_minimal_metadata_from_public_template_passes(real_output,real_reference):
    metadata=minimal_metadata(real_reference)
    (real_output/"run_metadata.json").write_text(json.dumps(metadata))
    q.validate_output_directory(real_output,real_reference)


def test_row_column_order_and_extra_fields_pass(real_output,real_reference):
    for name in ("source_epochs.csv","oof_predictions.csv","fold_receipts.csv","per_subject.csv"):
        rows=read_rows(real_output/name)
        for row in rows: row["extra"]="not graded"
        write_rows(real_output/name,rows[::-1],list(rows[0])[::-1])
    metadata=q.load_json(real_output/"run_metadata.json"); metadata["n_epochs_by_run"].reverse()
    (real_output/"run_metadata.json").write_text(json.dumps(metadata))
    q.validate_output_directory(real_output,real_reference)


def test_scientific_integer_notation_passes(real_output,real_reference):
    rows=read_rows(real_output/"oof_predictions.csv")
    for row in rows:
        for key in q.PRED_FIELDS:
            if key!="decision_score": row[key]=f'{int(row[key])}.0'
    write_rows(real_output/"oof_predictions.csv",rows)
    q.validate_output_directory(real_output,real_reference)


def test_free_prose_and_ignored_optional_receipt_pass(real_output,real_reference):
    (real_output/"findings.md").write_text("The measured results are in the attached tables.")
    (real_output/"analysis_arrays.npz").write_text("not a required participant artifact")
    q.validate_output_directory(real_output,real_reference)


def test_eight_decimal_decision_scores_pass_with_recomputed_statistics(real_output,real_reference):
    scores=np.round(real_reference["scores"],8)
    write_coherent_predictions(real_output,real_reference,scores)
    q.validate_output_directory(real_output,real_reference)


def test_within_tolerance_scores_pass_with_coherent_statistics(real_output,real_reference):
    scores=real_reference["scores"].copy()
    scores+=.1*(q.SCORE_ATOL+q.SCORE_RTOL*np.abs(scores))
    write_coherent_predictions(real_output,real_reference,scores)
    q.validate_output_directory(real_output,real_reference)


def test_genuine_independent_refit_scores_pass(real_output,real_reference):
    path=os.environ.get("REPAIR_INDEPENDENT_SCORES")
    if not path: pytest.skip("requires genuine independent CSP/LDA refit artifact")
    with np.load(path,allow_pickle=False) as archive:
        arrays={key:archive[key] for key in archive.files}
    assert arrays["pipeline_id"].item()==q.PIPELINE_ID
    assert arrays["source_manifest_sha256"].item()==real_reference["stats"]["metadata_contract"]["source_manifest_sha256"]
    assert json.loads(arrays["source_sha256_json"].item())==real_reference["stats"]["source_sha256"]
    scores=real_reference["scores"].copy(); seen=set()
    for row in range(len(arrays["decision_score"])):
        key=tuple(int(arrays[name][row]) for name in ("subject","run","event_index"))
        index=real_reference["index"][key]; replicate=int(arrays["replicate"][row])
        assert (replicate,index) not in seen; seen.add((replicate,index))
        for name in ("event_sample","source_class"):
            assert arrays[name][row]==real_reference[name][index]
        assert arrays["target_class"][row]==real_reference["targets"][replicate,index]
        score=float(arrays["decision_score"][row])
        assert arrays["predicted_class"][row]==int(score>0)
        scores[replicate,index]=score
    expected={(rep,index) for rep in (0,1,100,200) for index in range(scores.shape[1])}
    assert seen==expected, "independent production check must cover all subjects/runs at four declared replicates"
    write_coherent_predictions(real_output,real_reference,scores)
    q.validate_output_directory(real_output,real_reference)


@pytest.mark.parametrize("mutation",["drop","duplicate","sample","label","event_alias","retention"])
def test_genuine_source_ledger_mutations_fail(real_output,real_reference,mutation):
    rows=read_rows(real_output/"source_epochs.csv")
    if mutation=="drop": rows.pop()
    elif mutation=="duplicate": rows.append(dict(rows[0]))
    elif mutation=="sample": rows[0]["event_sample"]=int(rows[0]["event_sample"])+1
    elif mutation=="label": rows[0]["source_class"]=1-int(rows[0]["source_class"])
    elif mutation=="event_alias": rows[0]["event_index"]=99
    else: rows[0].update(retained=False,drop_reason="annotation")
    write_rows(real_output/"source_epochs.csv",rows)
    with pytest.raises(AssertionError): q.validate_output_directory(real_output,real_reference)


@pytest.mark.parametrize("mutation",["drop_epoch","drop_null_replicate","duplicate","unknown_epoch","source_sample","source_label","sign","nonfinite"])
def test_complete_source_bound_oof_is_required(real_output,real_reference,mutation):
    rows=read_rows(real_output/"oof_predictions.csv")
    if mutation=="drop_epoch": rows.pop()
    elif mutation=="drop_null_replicate": rows=[row for row in rows if row["replicate"]!="200"]
    elif mutation=="duplicate": rows.append(dict(rows[0]))
    elif mutation=="unknown_epoch": rows[0]["event_index"]=99
    elif mutation=="source_sample": rows[0]["event_sample"]=0
    elif mutation=="source_label": rows[0]["source_class"]=1-int(rows[0]["source_class"])
    elif mutation=="sign": rows[0]["predicted_class"]=1-int(rows[0]["predicted_class"])
    else: rows[0]["decision_score"]="nan"
    write_rows(real_output/"oof_predictions.csv",rows)
    with pytest.raises(AssertionError): q.validate_output_directory(real_output,real_reference)


@pytest.mark.parametrize("mutation",["zero","constant","rescale","reverse_sign","reuse_observed_null","shift_epochs","swap_runs"])
def test_coherent_wrong_models_fail_source_score_check(real_output,real_reference,mutation):
    scores=real_reference["scores"].copy()
    if mutation=="zero": scores[:]=0
    elif mutation=="constant": scores[:]=1
    elif mutation=="rescale": scores*=2
    elif mutation=="reverse_sign": scores*=-1
    elif mutation=="reuse_observed_null": scores[1:]=scores[0]
    elif mutation=="shift_epochs": scores=np.roll(scores,1,axis=1)
    else:
        for subject in q.SUBJECTS:
            take=np.flatnonzero(real_reference["subject"]==subject)
            scores[:,take]=np.roll(scores[:,take],len(take)//3,axis=1)
    assert not np.allclose(scores,real_reference["scores"],atol=q.SCORE_ATOL,rtol=q.SCORE_RTOL)
    write_coherent_predictions(real_output,real_reference,scores)
    with pytest.raises(AssertionError,match="decision scores"):
        q.validate_output_directory(real_output,real_reference)


def incorrect_targets(reference,mode):
    labels=reference["source_class"]; targets=np.tile(labels,(q.N_PERM+1,1))
    if mode=="whole_run":
        for subject in q.SUBJECTS:
            rng=np.random.RandomState(0)
            for rep in range(1,q.N_PERM+1):
                for run in q.RUNS:
                    take=np.flatnonzero((reference["subject"]==subject)&(reference["run"]==run))
                    targets[rep,take]=rng.permutation(labels[take])
    elif mode=="unreset_subject_rng":
        rng=np.random.RandomState(0)
        for subject in q.SUBJECTS:
            for rep in range(1,q.N_PERM+1):
                for run in q.RUNS:
                    for pair in range(7):
                        take=np.flatnonzero((reference["subject"]==subject)&(reference["run"]==run)&(reference["event_index"]//2==pair))
                        if len(take)==2: targets[rep,take]=rng.permutation(labels[take])
    elif mode=="previous_replicate":
        for subject in q.SUBJECTS:
            rng=np.random.RandomState(0)
            for rep in range(1,q.N_PERM+1):
                for run in q.RUNS:
                    for pair in range(7):
                        take=np.flatnonzero((reference["subject"]==subject)&(reference["run"]==run)&(reference["event_index"]//2==pair))
                        if len(take)==2: targets[rep,take]=rng.permutation(targets[rep-1,take])
    else: targets[1:]=labels
    return targets


@pytest.mark.parametrize("mode",["whole_run","unreset_subject_rng","previous_replicate","no_permutation"])
def test_coherent_wrong_permutation_stream_fails(real_output,real_reference,mode):
    targets=incorrect_targets(real_reference,mode)
    assert not np.array_equal(targets,real_reference["targets"])
    write_coherent_predictions(real_output,real_reference,real_reference["scores"],targets)
    with pytest.raises(AssertionError,match="original-pair"):
        q.validate_output_directory(real_output,real_reference)


@pytest.mark.parametrize("mutation",["drop","duplicate","train_count","test_count","accuracy"])
def test_genuine_fold_receipts_recomputed(real_output,real_reference,mutation):
    rows=read_rows(real_output/"fold_receipts.csv")
    if mutation=="drop": rows.pop()
    elif mutation=="duplicate": rows.append(dict(rows[0]))
    elif mutation=="train_count": rows[0]["n_train_class0"]=int(rows[0]["n_train_class0"])+1
    elif mutation=="test_count": rows[0]["n_test_class0"]=int(rows[0]["n_test_class0"])+1
    else: rows[0]["accuracy"]=float(rows[0]["accuracy"])+.1
    write_rows(real_output/"fold_receipts.csv",rows)
    with pytest.raises(AssertionError): q.validate_output_directory(real_output,real_reference)


@pytest.mark.parametrize("field",["accuracy","kappa","perm_p","holm_p","null_mean","null_sd","n_null_ge_observed"])
def test_genuine_subject_statistics_recomputed(real_output,real_reference,field):
    rows=read_rows(real_output/"per_subject.csv")
    rows[0][field]=float(rows[0][field])+1
    write_rows(real_output/"per_subject.csv",rows)
    with pytest.raises(AssertionError): q.validate_output_directory(real_output,real_reference)


@pytest.mark.parametrize("field",["n_subjects","n_epochs_total","n_classes","chance_level","accuracy","cohen_kappa",
    "finite_sample_null_sd","group_t_vs_chance","group_p_vs_chance","n_subjects_significant_perm_p05",
    "n_subjects_significant_holm_p05","n_subjects_below_chance","n_subjects_above_half_nominal","permutation_p_resolution"])
def test_genuine_group_statistics_recomputed(real_output,real_reference,field):
    path=real_output/"decoding_results.json"; value=q.load_json(path)
    value[field]=1 if value[field] is None else value[field]+1
    path.write_text(json.dumps(value))
    with pytest.raises(AssertionError): q.validate_output_directory(real_output,real_reference)


@pytest.mark.parametrize("mode",["source_hash","pipeline","subject_count","run_inventory","global_CSP_claim","wrong_null_claim"])
def test_genuine_metadata_identity_checked(real_output,real_reference,mode):
    path=real_output/"run_metadata.json"; metadata=q.load_json(path)
    if mode=="source_hash": metadata["source_sha256"]={}
    elif mode=="pipeline": metadata["pipeline_id"]="old"
    elif mode=="subject_count": metadata["n_subjects"]=9
    elif mode=="run_inventory": metadata["n_epochs_by_run"].pop()
    elif mode=="global_CSP_claim": metadata["cv"]["refit_CSP_and_LDA_each_fold_and_replicate"]=False
    else: metadata["permutation"]["shuffle"]="shuffle_whole_run"
    path.write_text(json.dumps(metadata))
    with pytest.raises(AssertionError): q.validate_output_directory(real_output,real_reference)


@pytest.mark.parametrize("name",q.FILES)
def test_genuine_missing_outputs_fail(real_output,real_reference,name):
    (real_output/name).unlink()
    with pytest.raises(AssertionError): q.validate_output_directory(real_output,real_reference)


def test_genuine_empty_prose_fails(real_output,real_reference):
    (real_output/"findings.md").write_text(" \n")
    with pytest.raises(AssertionError): q.validate_output_directory(real_output,real_reference)
