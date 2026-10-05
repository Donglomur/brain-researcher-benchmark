"""Actual-source positives and coherent/incoherent mutations; no model fits here."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import warnings

import numpy as np
import pytest

import fixture_support as f
import metric_contract as q
import proof_of_work as p


@pytest.fixture(scope="module")
def oracle():
    raw = os.environ.get("REPAIR_ORACLE_OUTPUT")
    if raw is None:
        pytest.skip("requires a completed original-source oracle output")
    path = Path(raw)
    assert path.is_dir(), "supplied original-source output is missing"
    return path


@pytest.fixture(scope="module")
def reference(oracle):
    return p.load_reference()


@pytest.fixture
def case(oracle):
    with tempfile.TemporaryDirectory(prefix="aasmstage-mutation-") as directory:
        out = Path(directory)/"output"
        shutil.copytree(oracle, out)
        yield out


def reject(path, ref, pattern=None):
    with pytest.raises((AssertionError, ValueError, KeyError, TypeError, EOFError), match=pattern):
        p.validate_output_directory(path, ref)


def assess_control(path, ref, equivalent, name, record_property, pattern=None):
    """Decide from public numerical bounds, never from the verifier's verdict."""
    record_property("control_name", name)
    if equivalent:
        p.validate_output_directory(path, ref)
        record_property("control_status", "control_not_discriminating")
        warnings.warn(f"control_not_discriminating: {name}; accepted numerical equivalence", UserWarning)
    else:
        reject(path, ref, pattern)
        record_property("control_status", "effective_negative_control")


def rows_source_close(rows, ref, fields, primitive, atol, rtol):
    index = {tuple(key): i for i, key in enumerate(ref["keys"])}
    for row in rows:
        key = tuple(q.integer(row[k]) for k in ("subject", "recording", "onset_sample"))
        if not np.allclose([float(row[k]) for k in fields], ref[primitive][index[key]], atol=atol, rtol=rtol):
            return False
    return True


def rewrite_metrics(output, ref):
    """Recompute redundant fields from actual mutated predictions, not reference scores."""
    _, rows = f.read_csv(output/"epoch_predictions.csv")
    keys = [[q.integer(r[k]) for k in ("subject", "recording", "onset_sample")] for r in rows]
    mats = q.matrices(keys, [q.integer(r["true_stage"]) for r in rows], [q.integer(r["predicted_stage"]) for r in rows])
    columns, subjects = f.read_csv(output/"per_subject.csv")
    for row in subjects:
        s = q.integer(row["subject"]); m = q.confusion_metrics(mats[s])
        train = sum(v for key, v in mats.items() if key != s).sum(axis=1)
        row.update(n_train_epochs=int(train.sum()), n_test_epochs=m["n"], overall_accuracy=m["overall"],
                   balanced_accuracy=m["balanced"], kappa=m["kappa"], kappa_status=m["kappa_status"], n_supported_classes=m["n_supported"])
        for i, name in enumerate(("w", "n1", "n2", "n3", "rem")):
            row["n_train_"+name] = int(train[i]); row["n_test_"+name] = int(mats[s].sum(axis=1)[i])
    f.write_csv(output/"per_subject.csv", columns, subjects)
    cells = [{"subject": s, "true_stage": a+1, "predicted_stage": b+1, "n_epochs": int(matrix[a, b])}
             for s, matrix in mats.items() for a in range(5) for b in range(5)]
    f.write_csv(output/"confusion_counts.csv", ref["method"]["outputs"]["confusion_counts.csv"]["columns"], cells)
    f.write_json(output/"staging_results.json", q.results_from_matrices(mats))


def test_genuine_original_oracle(oracle, reference):
    p.validate_output_directory(oracle, reference)


def test_genuine_independent_source_route(reference):
    raw = os.environ.get("REPAIR_INDEPENDENT_OUTPUT")
    if raw is None:
        pytest.skip("requires completed independently reconstructed original source output")
    path = Path(raw)
    assert path.is_dir(), "supplied independent source output is missing"
    p.validate_output_directory(path, reference)


def test_genuine_multitaper_component_rejected_numerically_before_metadata(reference, record_property):
    raw = os.environ.get("REPAIR_WRONG_MULTITAPER_OUTPUT")
    if raw is None:
        pytest.skip("requires completed original-epoch multitaper component control")
    output = Path(raw)
    assert output.is_dir(), "supplied actual multitaper output is missing"
    with pytest.raises(AssertionError, match="feature domain|weighted feature normalization|features differ|PSD sums differ"):
        p.validate_feature_output(output/"epoch_features.csv", reference)
    record_property("control_name", "actual_method_omitted_multitaper")
    record_property("control_status", "effective_negative_control")


def test_public_contract_identity(reference):
    path = Path(__file__).parents[1]/"environment"/"method_contract.json"
    assert p.digest(path.read_bytes()) == q.METHOD_SHA
    q.match(q.read_json(path), reference["method"], closed=True)


def test_all_csv_reordering_extra_columns_and_integral_notation(case, reference):
    for name, spec in reference["method"]["outputs"].items():
        if not name.endswith(".csv"):
            continue
        columns, rows = f.read_csv(case/name)
        for row in rows:
            for key in spec["key"]:
                old = q.integer(row[key]); row[key] = format(old, ".17e")
                assert q.integer(row[key]) == old
            row["extra_note"] = "harmless"
        f.write_csv(case/name, list(reversed(columns))+["extra_note"], list(reversed(rows)))
    p.validate_output_directory(case, reference)


def test_independent_rounding_and_own_argmax_recomputation(case, reference):
    columns, rows = f.read_csv(case/"epoch_features.csv")
    for row in rows:
        for key in (*q.FEATURES, "psd_sum_fpz_cz", "psd_sum_pz_oz"):
            row[key] = format(float(row[key]), ".12g")
    f.write_csv(case/"epoch_features.csv", columns, rows)
    columns, rows = f.read_csv(case/"epoch_predictions.csv")
    for row in rows:
        for key in q.PROBS:
            row[key] = format(float(row[key]), ".12g")
        row["predicted_stage"] = int(q.own_predictions([[float(row[k]) for k in q.PROBS]])[0])
    f.write_csv(case/"epoch_predictions.csv", columns, rows)
    rewrite_metrics(case, reference)
    columns, rows = f.read_csv(case/"per_subject.csv")
    for row in rows:
        for key in ("overall_accuracy", "balanced_accuracy", "kappa"):
            if row[key] != "":
                row[key] = format(float(row[key]), ".6f")
    f.write_csv(case/"per_subject.csv", columns, rows)
    p.validate_output_directory(case, reference)


def test_genuine_top_tie_own_argmax_with_coherent_metrics(case, reference, record_property):
    columns, rows = f.read_csv(case/"epoch_predictions.csv")
    for row in rows:
        probabilities = np.array([float(row[key]) for key in q.PROBS])
        tied = np.flatnonzero(probabilities == probabilities.max())
        if len(tied) < 2:
            continue
        old_prediction = int(q.own_predictions([probabilities])[0])
        probabilities[tied[0]] -= 1e-11
        probabilities[tied[1]] += 1e-11
        row.update(dict(zip(q.PROBS, probabilities)))
        row["predicted_stage"] = int(q.own_predictions([probabilities])[0])
        assert row["predicted_stage"] != old_prediction
        f.write_csv(case/"epoch_predictions.csv", columns, rows)
        rewrite_metrics(case, reference)
        p.validate_output_directory(case, reference)
        record_property("control_name", "genuine_top_tie_own_argmax")
        record_property("control_status", "effective_equivalence_positive")
        return
    assess_control(case, reference, True, "genuine_top_tie_absent", record_property)


def test_minimal_metadata_other_versions_free_prose_and_extras(case, reference):
    meta = q.read_json(case/"run_metadata.json")
    required = reference["method"]["object_types"]["RunMetadata"]["fields"]
    meta = {key: meta[key] for key in required}
    meta["software_versions"] = {"independently_equivalent_implementation": "1.0"}
    meta["source_observed"]["subjects"].reverse()
    meta["notes"] = {"optional_analysis": {"accuracy": 999, "claim": "ungraded extra text"}}
    for row in meta["source_observed"]["subjects"]:
        for name in ("annotation_status_counts", "epoch_status_counts"):
            row[name] = {key: value for key, value in row[name].items() if value}
    f.write_json(case/"run_metadata.json", meta)
    result = q.read_json(case/"staging_results.json"); result["per_class"].reverse(); result["optional"] = "extra"
    f.write_json(case/"staging_results.json", result)
    (case/"findings.md").write_text("The finite results describe these recordings.\n")
    (case/"optional_private.txt").write_text("Not required for submission.\n")
    p.validate_output_directory(case, reference)


@pytest.mark.parametrize("filename", ["annotations.csv", "epochs.csv", "epoch_features.csv", "epoch_predictions.csv", "per_subject.csv", "confusion_counts.csv", "staging_results.json", "run_metadata.json", "findings.md"])
@pytest.mark.parametrize("mode", ["missing", "empty"])
def test_missing_empty(case, reference, filename, mode):
    if mode == "missing":
        (case/filename).unlink()
    else:
        (case/filename).write_text("")
    reject(case, reference)


@pytest.mark.parametrize("filename", ["annotations.csv", "epochs.csv", "epoch_features.csv", "epoch_predictions.csv", "per_subject.csv", "confusion_counts.csv"])
@pytest.mark.parametrize("mode", ["duplicate", "drop", "missing_column"])
def test_table_coverage(case, reference, filename, mode):
    columns, rows = f.read_csv(case/filename)
    if mode == "duplicate":
        rows.append(rows[0].copy())
    elif mode == "drop":
        rows.pop()
    else:
        columns.remove(next(iter(reference["method"]["outputs"][filename]["columns"])))
    f.write_csv(case/filename, columns, rows)
    reject(case, reference)


@pytest.mark.parametrize("filename,field", [("annotations.csv", "tal_index"), ("annotations.csv", "onset_s"), ("annotations.csv", "duration_s"), ("annotations.csv", "stage_id"), ("annotations.csv", "n_complete_chunks"), ("epochs.csv", "onset_sample"), ("epochs.csv", "end_sample_exclusive"), ("epochs.csv", "annotation_index"), ("epochs.csv", "chunk_index"), ("epochs.csv", "stage_id"), ("epoch_predictions.csv", "true_stage"), ("epoch_predictions.csv", "heldout_subject")])
def test_source_identity_fields(case, reference, filename, field):
    columns, rows = f.read_csv(case/filename)
    row = next(r for r in rows if r[field] != "")
    row[field] = str(float(row[field])+1)
    f.write_csv(case/filename, columns, rows)
    reject(case, reference)


@pytest.mark.parametrize("mode", ["wrong_channel", "wrong_band", "sum_not_mean", "zero_feature", "nan_feature", "negative_feature", "microvolts_not_volts", "zero_psd", "wrong_psd", "infinite_psd"])
def test_feature_and_physical_scale(case, reference, mode, record_property):
    columns, rows = f.read_csv(case/"epoch_features.csv")
    row = rows[0]
    if mode == "wrong_channel":
        for band in ("delta", "theta", "alpha", "sigma", "beta"):
            a, b = band+"_fpz_cz", band+"_pz_oz"; row[a], row[b] = row[b], row[a]
    elif mode == "wrong_band":
        row["delta_fpz_cz"], row["beta_fpz_cz"] = row["beta_fpz_cz"], row["delta_fpz_cz"]
    elif mode == "sum_not_mean":
        for key, n in zip(q.FEATURES, np.repeat(q.BIN_COUNTS, 2)):
            row[key] = str(float(row[key])*n)
    elif mode.endswith("feature"):
        row["delta_fpz_cz"] = {"zero_feature": "0", "nan_feature": "NaN", "negative_feature": "-1e-8"}[mode]
    else:
        row["psd_sum_fpz_cz"] = {"microvolts_not_volts": str(float(row["psd_sum_fpz_cz"])*1e12),
                                  "zero_psd": "0", "wrong_psd": str(float(row["psd_sum_fpz_cz"])*1.01), "infinite_psd": "Inf"}[mode]
    f.write_csv(case/"epoch_features.csv", columns, rows)
    if mode in ("wrong_channel", "wrong_band", "zero_feature"):
        equivalent = rows_source_close([row], reference, q.FEATURES, "features", 1e-12, 1e-9)
        assess_control(case, reference, equivalent, mode, record_property)
    else:
        reject(case, reference)


@pytest.mark.parametrize("mode", ["coherent_probability_shift", "class_column_swap", "one_hot", "negative", "not_normalized", "nan", "wrong_argmax"])
def test_probability_binding_and_argmax(case, reference, mode, record_property):
    columns, rows = f.read_csv(case/"epoch_predictions.csv")
    row = rows[0]; prob = np.array([float(row[k]) for k in q.PROBS])
    if mode == "coherent_probability_shift":
        low, high = int(np.argmin(prob)), int(np.argmax(prob))
        if low == high:  # Uniform vectors must not turn this control into a no-op.
            low = (high+1) % 5
        prob[low] += .001; prob[high] -= .001
    elif mode == "class_column_swap":
        prob = np.roll(prob, 1)
    elif mode == "one_hot":
        prob = np.eye(5)[(int(np.argmax(prob))+1) % 5]
    elif mode == "negative":
        prob[0] = -1e-8
    elif mode == "not_normalized":
        prob *= .99
    elif mode == "nan":
        prob[0] = np.nan
    else:
        row["predicted_stage"] = (q.integer(row["predicted_stage"]) % 5)+1
    if mode != "wrong_argmax":
        row.update(dict(zip(q.PROBS, prob)))
        if np.isfinite(prob).all() and np.all(prob >= 0) and abs(prob.sum()-1) <= 5.5e-9:
            row["predicted_stage"] = int(q.own_predictions([prob])[0])
    f.write_csv(case/"epoch_predictions.csv", columns, rows)
    rewrite_metrics(case, reference)
    if mode == "class_column_swap":
        equivalent = rows_source_close([row], reference, q.PROBS, "probabilities", 1e-10, 1e-9)
        assess_control(case, reference, equivalent, mode, record_property)
    else:
        reject(case, reference)


def test_confusion_preserving_wrong_epoch_probabilities(case, reference, record_property):
    columns, rows = f.read_csv(case/"epoch_predictions.csv")
    groups = {}
    for i, row in enumerate(rows):
        groups.setdefault((row["subject"], row["true_stage"]), []).append(i)
    pair = fallback = None
    for indices in groups.values():
        if len(indices) < 2:
            continue
        fallback = (indices[0], indices[1])
        probs = np.array([[float(rows[i][k]) for k in q.PROBS] for i in indices])
        # Extreme pairs suffice to find a source-discriminating component;
        # absence is a measured control limitation, not a baseline failure.
        for column in range(5):
            a, b = indices[int(probs[:, column].argmin())], indices[int(probs[:, column].argmax())]
            trial = [dict(rows[a]), dict(rows[b])]
            for field in q.PROBS:
                trial[0][field], trial[1][field] = trial[1][field], trial[0][field]
            if not rows_source_close(trial, reference, q.PROBS, "probabilities", 1e-10, 1e-9):
                pair = (a, b)
                break
        if pair is not None:
            break
    pair = pair or fallback
    if pair is None:
        assess_control(case, reference, True, "within_class_swap_no_pair", record_property)
        return
    a, b = pair
    for field in (*q.PROBS, "predicted_stage"):
        rows[a][field], rows[b][field] = rows[b][field], rows[a][field]
    f.write_csv(case/"epoch_predictions.csv", columns, rows)
    # Every confusion cell stays identical; this specifically needs epoch/probability binding.
    equivalent = rows_source_close([rows[a], rows[b]], reference, q.PROBS, "probabilities", 1e-10, 1e-9)
    assess_control(case, reference, equivalent, "within_class_probability_swap", record_property, "probabilities differ")


def test_coherent_epoch_duplication_old_false_accept(case, reference):
    columns, rows = f.read_csv(case/"epoch_predictions.csv")
    duplicated = []
    for row in rows:
        extra = row.copy(); extra["onset_sample"] = q.integer(row["onset_sample"])+100000000
        duplicated.extend((row, extra))
    f.write_csv(case/"epoch_predictions.csv", columns, duplicated)
    rewrite_metrics(case, reference)
    reject(case, reference, "prediction source epoch coverage")


@pytest.mark.parametrize("mode", ["boolean_method", "extra_method", "extra_source", "wrong_hash", "missing_method", "failed_status", "wrong_clock", "wrong_rate", "wrong_calibration", "wrong_count", "duplicate_subject", "missing_nested", "bad_versions"])
def test_metadata_integrity(case, reference, mode):
    meta = q.read_json(case/"run_metadata.json")
    row = meta["source_observed"]["subjects"][0]
    if mode == "boolean_method": meta["method_contract"]["classifier"]["parameters"]["n_jobs"] = True
    elif mode == "extra_method": meta["method_contract"]["new_filter"] = True
    elif mode == "extra_source": meta["source_sha256"]["fake.edf"] = "f"*64
    elif mode == "wrong_hash": meta["source_manifest_sha256"] = "f"*64
    elif mode == "missing_method": del meta["method_contract"]
    elif mode == "failed_status": meta["status"] = "failed_precondition"
    elif mode == "wrong_clock": row["annotation_orig_time"] = "1989-01-01T00:00:00Z"
    elif mode == "wrong_rate": row["sfreq_hz"] += 5e-10
    elif mode == "wrong_calibration": row["eeg_channels"][0]["physical_min_text"] = "-999"
    elif mode == "wrong_count": row["n_retained_epochs"] += 1
    elif mode == "duplicate_subject": meta["source_observed"]["subjects"][1] = copy.deepcopy(row)
    elif mode == "missing_nested": del row["annotation_orig_time"]
    else: meta["software_versions"] = {}
    f.write_json(case/"run_metadata.json", meta)
    reject(case, reference)


@pytest.mark.parametrize("mode", ["headline", "kappa", "boolean_count", "missing_null", "mean_subject_macro", "confusion", "training_leakage", "training_count", "supported_classes"])
def test_reported_arithmetic(case, reference, mode, record_property):
    equivalent = False
    if mode in ("headline", "kappa", "boolean_count", "missing_null", "mean_subject_macro"):
        result = q.read_json(case/"staging_results.json")
        if mode == "headline": result["accuracy"] += .01
        elif mode == "kappa": result["cohen_kappa"] += .01
        elif mode == "boolean_count": result["n_subjects"] = True
        elif mode == "missing_null": del result["per_class"][0]["recall_status"]
        else:
            _, rows = f.read_csv(case/"per_subject.csv")
            alternate = float(np.mean([float(r["balanced_accuracy"]) for r in rows]))
            _, predictions = f.read_csv(case/"epoch_predictions.csv")
            keys = [[q.integer(r[k]) for k in ("subject", "recording", "onset_sample")] for r in predictions]
            mats = q.matrices(keys, [q.integer(r["true_stage"]) for r in predictions], [q.integer(r["predicted_stage"]) for r in predictions])
            expected = q.results_from_matrices(mats)["accuracy"]
            equivalent = abs(alternate-expected) <= 1e-6
            result["accuracy"] = result["balanced_accuracy"] = alternate
        f.write_json(case/"staging_results.json", result)
    elif mode == "confusion":
        cols, rows = f.read_csv(case/"confusion_counts.csv"); rows[0]["n_epochs"] = q.integer(rows[0]["n_epochs"])+1
        f.write_csv(case/"confusion_counts.csv", cols, rows)
    else:
        cols, rows = f.read_csv(case/"per_subject.csv")
        if mode == "training_leakage": rows[0]["training_subjects"] = "[0,1,2,3,4]"
        elif mode == "training_count": rows[0]["n_train_epochs"] = q.integer(rows[0]["n_train_epochs"])+1
        else: rows[0]["n_supported_classes"] = 4
        f.write_csv(case/"per_subject.csv", cols, rows)
    if mode == "mean_subject_macro":
        assess_control(case, reference, equivalent, mode, record_property)
    else:
        reject(case, reference)
