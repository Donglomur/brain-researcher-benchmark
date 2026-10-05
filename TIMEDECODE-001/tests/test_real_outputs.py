"""Original-source positives and coherent forgeries; no invented answer bank."""
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import numpy as np
import pytest
import prediction_contract as q
from proof_of_work import load_reference,METHOD_SHA256

FILES = ("source_epochs.csv","oof_predictions.csv","per_fold.csv","decoding_timecourse.csv",
    "decoding_results.json","run_metadata.json","findings.md")
TABLES = dict(zip(FILES[:4],(q.SOURCE_FIELDS,q.PREDICTION_FIELDS,q.FOLD_FIELDS,q.TIME_FIELDS)))


@pytest.fixture(scope="module")
def reference():
    if not os.environ.get("REPAIR_ORACLE_OUTPUT"):
        pytest.skip("Original-source oracle output unavailable")
    return load_reference(Path(os.environ.get("REPAIR_REFERENCE_PATH",Path(__file__).with_name("reference.npz"))))


@pytest.fixture(scope="module")
def original(reference):
    return Path(os.environ["REPAIR_ORACLE_OUTPUT"])


@pytest.fixture
def output(original,tmp_path):
    with tempfile.TemporaryDirectory(prefix="real-output-mutation-",dir=tmp_path) as directory:
        path = Path(directory)
        for name in FILES:
            shutil.copyfile(original/name,path/name)
        yield path


def write_csv(path,fields,rows):
    with path.open("w",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def mutate_json(path,operation):
    value = json.loads(path.read_text())
    operation(value)
    path.write_text(json.dumps(value,allow_nan=False))


def recompute_summaries(output,reference):
    rows = q.csv_load(output/"oof_predictions.csv",q.PREDICTION_FIELDS)
    n,t = len(reference["labels"]),len(reference["analysis_offsets"])
    predictions = {name:np.empty((n,t),int) for name in q.ESTIMATORS}
    for row in rows:
        predictions[row["estimator"]][q.integer(row["trial_id"]),q.integer(row["time_index"])] = q.integer(row["predicted_class"])
    folds,times,result = q.summaries(reference,predictions)
    write_csv(output/"per_fold.csv",q.FOLD_FIELDS,folds)
    write_csv(output/"decoding_timecourse.csv",q.TIME_FIELDS,times)
    (output/"decoding_results.json").write_text(json.dumps(result,allow_nan=False))


def test_genuine_source_oracle(original,reference):
    q.validate_output_directory(original,reference)


def test_genuine_independent_source_solver(reference):
    if not os.environ.get("REPAIR_INDEPENDENT_OUTPUT"):
        pytest.skip("Independent original-source output unavailable")
    q.validate_output_directory(Path(os.environ["REPAIR_INDEPENDENT_OUTPUT"]),reference)


def test_public_contract_identity(reference):
    method = Path(__file__).parents[1]/"environment/method_contract.json"
    assert hashlib.sha256(method.read_bytes()).hexdigest()==METHOD_SHA256
    assert reference["metadata"]["method_contract_sha256"]==METHOD_SHA256


def test_reordered_rows_columns_and_extra_fields(output,reference):
    for name,fields in TABLES.items():
        rows = q.csv_load(output/name,fields)
        for row in rows:
            row["description"] = "ungraded extra information"
        write_csv(output/name,["description",*reversed(fields)],list(reversed(rows)))
    mutate_json(output/"decoding_results.json",lambda value:value.update(extra_analysis={"ungraded_random_accuracy":.123}))
    q.validate_output_directory(output,reference)


def test_equivalent_numeric_notation_and_rounding(output,reference):
    text_fields = {"estimator","drop_reason","max_ptp_channel"}
    float_fields = {"max_ptp_T_per_m","decision_score","time_s","accuracy","pooled_accuracy"}
    for name,fields in TABLES.items():
        rows = q.csv_load(output/name,fields)
        for row in rows:
            for field,value in row.items():
                if not value or field in text_fields:
                    continue
                if field in float_fields:
                    row[field] = format(float(value),".12e")
                else:
                    converted = format(float(value),".17e")
                    assert q.integer(converted)==q.integer(value)
                    row[field] = converted
        write_csv(output/name,fields,rows)
    q.validate_output_directory(output,reference)


def test_honest_alternate_versions_and_nonkeyword_prose(output,reference):
    def change(value):
        value["software_versions"] = {"independent_cpu_solver":"documented-local-version"}
        value["fitting_diagnostics"]["actual_iterations"] = "An optional implementation diagnostic"
        value["source_metadata"]["additional_observation"] = "No source replacement"
        value["optional_analysis"] = {"leaky_accuracy":.99}
    mutate_json(output/"run_metadata.json",change)
    (output/"findings.md").write_text("Only the specified within-recording comparison is supported; no transfer claim is made.")
    q.validate_output_directory(output,reference)


@pytest.mark.parametrize("name",FILES)
@pytest.mark.parametrize("mutation",("missing","empty"))
def test_all_required_outputs(output,reference,name,mutation):
    if mutation=="missing":
        (output/name).unlink()
    else:
        (output/name).write_text("")
    with pytest.raises((AssertionError,OSError)):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("name",FILES[:4])
@pytest.mark.parametrize("mutation",("drop","duplicate","malformed"))
def test_complete_keyed_tables(output,reference,name,mutation):
    fields = TABLES[name]
    rows = q.csv_load(output/name,fields)
    if mutation=="drop":
        rows.pop()
    elif mutation=="duplicate":
        rows[-1] = rows[0].copy()
    else:
        rows[0][fields[0]] = "NaN"
    write_csv(output/name,fields,rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("field",("source_event_index","event_sample","previous_value","event_code","modality","retained","trial_id","max_ptp_T_per_m","max_ptp_channel","drop_reason"))
def test_source_trial_selection_binding(output,reference,field):
    rows = q.csv_load(output/"source_epochs.csv",q.SOURCE_FIELDS)
    row = next(row for row in rows if row["retained"]=="1")
    if field=="max_ptp_channel":
        row[field] = "invented sensor"
    elif field=="drop_reason":
        row[field] = "amplitude"
    elif field=="max_ptp_T_per_m":
        row[field] = 2*float(row[field])+1e-11
    else:
        row[field] = q.integer(row[field])+1
    write_csv(output/"source_epochs.csv",q.SOURCE_FIELDS,rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("field",("source_event_index","trial_id","time_index","sample_offset","time_s","fold","true_class","predicted_class","decision_score"))
def test_full_oof_source_binding(output,reference,field):
    rows = q.csv_load(output/"oof_predictions.csv",q.PREDICTION_FIELDS)
    if field=="decision_score":
        rows[0][field] = float(rows[0][field])+1
    elif field=="time_s":
        rows[0][field] = float(rows[0][field])+.01
    elif field=="predicted_class":
        rows[0][field] = 1-q.integer(rows[0][field])
    else:
        rows[0][field] = q.integer(rows[0][field])+1
    write_csv(output/"oof_predictions.csv",q.PREDICTION_FIELDS,rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation",("sign_preserving_scale","opposite_decisions","pooled_as_per_time","new_trial_split","all_zero"))
def test_coherent_forged_predictions_and_summaries(output,reference,mutation):
    rows = q.csv_load(output/"oof_predictions.csv",q.PREDICTION_FIELDS)
    alternate = reference.copy()
    if mutation=="new_trial_split":
        alternate["folds"] = reference["folds"]%5+1
    for row in rows:
        trial,ti = q.integer(row["trial_id"]),q.integer(row["time_index"])
        score = float(row["decision_score"])
        if mutation=="sign_preserving_scale":
            score *= .5
        elif mutation=="opposite_decisions":
            score = -score
        elif mutation=="pooled_as_per_time" and row["estimator"]=="per_time":
            score = float(reference["pooled_scores"][trial,ti])
        elif mutation=="new_trial_split":
            row["fold"] = int(alternate["folds"][trial])
        elif mutation=="all_zero":
            score = 0.
        row["decision_score"],row["predicted_class"] = score,int(score>0)
    write_csv(output/"oof_predictions.csv",q.PREDICTION_FIELDS,rows)
    recompute_summaries(output,alternate)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("field",("n_train_trials","n_test_trials","n_train_samples","n_test_samples","n_train_class0","n_train_class1","n_test_class0","n_test_class1","n_correct","accuracy"))
def test_recomputed_fold_counts_and_accuracy(output,reference,field):
    rows = q.csv_load(output/"per_fold.csv",q.FOLD_FIELDS)
    rows[0][field] = float(rows[0][field])+(.01 if field=="accuracy" else 1)
    write_csv(output/"per_fold.csv",q.FOLD_FIELDS,rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


def test_affine_curve_transform_no_longer_passes_shape_gate(output,reference):
    rows = q.csv_load(output/"decoding_timecourse.csv",q.TIME_FIELDS)
    for row in rows:
        row["accuracy"] = .1+.8*float(row["accuracy"])
        row["pooled_accuracy"] = .1+.8*float(row["pooled_accuracy"])
    write_csv(output/"decoding_timecourse.csv",q.TIME_FIELDS,rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("field",("accuracy","pooled_oof_accuracy","n_trials","n_time_samples_per_trial","n_samples_total","n_classes","n_channels","n_folds","chance_level"))
def test_recomputed_headline_and_source_counts(output,reference,field):
    mutate_json(output/"decoding_results.json",lambda value:value.update({field:value[field]+(.01 if field in ("accuracy","pooled_oof_accuracy","chance_level") else 1)}))
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


@pytest.mark.parametrize("mutation",("source_hash","method_hash","missing_source","first_samp","channel_order","missing_support","offsets","overlap_count","code_counts","versions","model_count","converged","gradient","convergence_warning"))
def test_source_and_fitting_metadata(output,reference,mutation):
    def change(value):
        if mutation in ("source_hash","method_hash"):
            value["source_manifest_sha256" if mutation=="source_hash" else "method_contract_sha256"] = "0"*64
        elif mutation=="missing_source":
            del value["source_metadata"]
        elif mutation=="first_samp":
            value["source_metadata"]["first_samp"] += 1
        elif mutation=="channel_order":
            value["source_metadata"]["selected_grad_names"].reverse()
        elif mutation=="missing_support":
            del value["support_metadata"]
        elif mutation=="offsets":
            value["support_metadata"]["analysis_offsets"][0] += 1
        elif mutation=="overlap_count":
            value["support_metadata"]["candidate_full_epoch_overlap_pairs"] += 1
        elif mutation=="code_counts":
            value["source_metadata"]["source_event_code_counts"]["999"] = 0
        elif mutation=="versions":
            value["software_versions"] = {}
        elif mutation=="model_count":
            value["fitting_diagnostics"]["n_models"] -= 1
        elif mutation=="converged":
            value["fitting_diagnostics"]["all_converged"] = False
        elif mutation=="gradient":
            value["fitting_diagnostics"]["max_mean_gradient_inf"] = 1e-6
        else:
            value["fitting_diagnostics"]["warnings"] = [{"category":"ConvergenceWarning","message":"Solver failed to converge"}]
    mutate_json(output/"run_metadata.json",change)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output,reference)


def test_actual_global_scaling_control_is_rejected(reference):
    if not os.environ.get("REPAIR_GLOBAL_CONTROL_OUTPUT"):
        pytest.skip("Actual independently computed global-scaling control unavailable")
    path = Path(os.environ["REPAIR_GLOBAL_CONTROL_OUTPUT"])
    q.validate_source(q.csv_load(path/"source_epochs.csv",q.SOURCE_FIELDS),reference)
    q.validate_metadata(q.json_load(path/"run_metadata.json"),reference)
    # The rejection must come from genuine wrong-method scores, not a keyword.
    with pytest.raises(AssertionError,match="decision score"):
        q.validate_output_directory(path,reference)
