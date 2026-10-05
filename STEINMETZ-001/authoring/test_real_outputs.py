"""Genuine-output mutation gates. Skipped unless an actual source-run receipt is supplied.

These tests never create a reference bank or fit a classifier. The optional leakage
control must come from separately executed, deliberately globally scaled models;
changing a metadata label is not evidence of detecting numerical data leakage.
"""
import csv
import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tests"))
from proof_of_work import (RECIPES, SPLITS, load_reference, read_json, sigmoid,
                           recipe_split, load_trial_predictions)
from decoding_contract import validate_output_directory

FILES = ("trial_predictions.csv", "folds.csv", "results.json", "run_metadata.json", "findings.md")
SOURCE_SHA256 = "d8433a826049f82cd832f41f98a9f9fafad0ac66998d4dbfd89b15b594fc4236"


@pytest.fixture(scope="module")
def genuine():
    value = os.environ.get("REPAIR_ORACLE_OUTPUT")
    if not value:
        pytest.skip("requires a genuine source-run REPAIR_ORACLE_OUTPUT, not a synthetic bank")
    output = Path(value)
    reference = load_reference()
    assert reference["stats"]["source_sha256"] == {"sub-Cori_ses-20161214T120000.nwb": SOURCE_SHA256}
    validate_output_directory(output, reference)
    return output, reference


@pytest.fixture
def output_copy(genuine, tmp_path):
    source, reference = genuine
    for name in FILES:
        shutil.copyfile(source / name, tmp_path / name)
    return tmp_path, reference


def rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def write_rows(path, values):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader(); writer.writerows(values)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n")


def flip_prediction(row):
    row["predicted_choice"] = -int(float(row["predicted_choice"]))
    # Preserve the declared sign/probability relation while making a wrong OOF result.
    row["decision_value"] = float(row["predicted_choice"]) * max(abs(float(row["decision_value"])), .1)
    row["probability_left"] = float(sigmoid(np.array([row["decision_value"]]))[0])


def recalculate(output, predictions):
    """Forge *consistent* public arithmetic without reading the reference answers."""
    fold_rows, means, pooled, deviations, base_means, base_pooled = [], {}, {}, {}, {}, {}
    for recipe in RECIPES:
        group = [r for r in predictions if r["recipe"] == recipe]
        y = np.array([int(float(r["true_choice"])) for r in group])
        pred = np.array([int(float(r["predicted_choice"])) for r in group])
        folds = np.array([int(float(r["fold"])) for r in group])
        accuracy, baseline_accuracy, baseline = [], [], np.zeros(len(group), int)
        for fold in range(5):
            test, train = folds == fold, folds != fold
            majority = 1 if np.sum(y[train] == 1) > np.sum(y[train] == -1) else -1
            baseline[test] = majority
            n = int(test.sum()); assert n > 0
            correct, base_correct = int(np.sum(pred[test] == y[test])), int(np.sum(y[test] == majority))
            accuracy.append(correct/n); baseline_accuracy.append(base_correct/n)
            fold_rows.append(dict(recipe=recipe, fold=fold, n_train=int(train.sum()), n_test=n,
                n_correct=correct, accuracy=correct/n, baseline_choice=majority,
                baseline_n_correct=base_correct, baseline_accuracy=base_correct/n))
        for row, value in zip(group, baseline): row["baseline_choice"] = int(value)
        means[recipe], pooled[recipe] = float(np.mean(accuracy)), float(np.mean(pred == y))
        deviations[recipe] = float(np.std(accuracy, ddof=0))
        split = recipe_split(recipe)
        base_means[split], base_pooled[split] = float(np.mean(baseline_accuracy)), float(np.mean(baseline == y))
    result = read_json(output / "results.json")
    result.update(cross_validated_accuracy=means["stimulus_blocked"], accuracy_by_window_and_split=means,
        pooled_accuracy_by_window_and_split=pooled, accuracy_std_by_window_and_split=deviations,
        baseline_accuracy_by_split=base_means, pooled_baseline_accuracy_by_split=base_pooled)
    write_rows(output / "trial_predictions.csv", predictions)
    write_rows(output / "folds.csv", fold_rows)
    write_json(output / "results.json", result)


def test_genuine_oracle_passes(genuine):
    validate_output_directory(*genuine)


def test_public_template_is_exact_reference_metadata_contract(genuine):
    _, reference = genuine
    template = read_json(Path(__file__).parents[1] / "environment/method_contract.json")
    assert template == reference["stats"]["metadata_contract"]


def test_public_template_plus_measured_counts_is_sufficient(output_copy):
    output, reference = output_copy
    template = read_json(Path(__file__).parents[1] / "environment/method_contract.json")
    result = read_json(output / "results.json")
    metadata = {**template, "status": "ok", "primary_recipe": "stimulus_blocked",
        **{key: result[key] for key in ("n_trials", "n_units", "selection_counts", "response_timing_counts")}}
    assert "optimizer_iterations_by_recipe" not in metadata and "unit_quality_counts" not in metadata
    write_json(output / "run_metadata.json", metadata)
    validate_output_directory(output, reference)


def test_wrong_global_fit_metadata_claim_fails_separately_from_numeric_control(output_copy):
    output, reference = output_copy
    metadata = read_json(output / "run_metadata.json")
    metadata["standardizer"]["fit_on"] = "all_trials"
    write_json(output / "run_metadata.json", metadata)
    with pytest.raises(AssertionError, match="standardizer.fit_on"):
        validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["missing", "empty"])
def test_findings_required_but_wording_is_not_scored(output_copy, kind):
    output, reference = output_copy
    if kind == "missing":
        (output / "findings.md").unlink()
    else:
        (output / "findings.md").write_text(" \n\t")
    with pytest.raises((AssertionError, FileNotFoundError)):
        validate_output_directory(output, reference)


def test_rows_columns_numeric_ids_and_free_prose_are_flexible(output_copy):
    output, reference = output_copy
    for name in ("trial_predictions.csv", "folds.csv"):
        values = rows(output / name)[::-1]
        for row in values:
            row["comment"] = "additional description"
            for field in ("trial_id", "fold", "n_train", "n_test", "n_correct", "baseline_n_correct"):
                if field in row: row[field] = f"{int(row[field])}.0"
        values = [dict(reversed(list(row.items()))) for row in values]
        write_rows(output / name, values)
    (output / "findings.md").write_text("这是一个单次记录的方法检查，不做跨动物推断。\n")
    # Optional authoring artifacts are not required submission formats or gates.
    (output / "analysis_arrays.npz").write_text("ignored optional artifact")
    validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["missing", "duplicate", "foreign_trial", "fractional_trial", "zero_label"])
def test_exact_trial_membership_and_signed_categories(output_copy, kind):
    output, reference = output_copy; values = rows(output / "trial_predictions.csv")
    if kind == "missing": values.pop()
    elif kind == "duplicate": values.append(values[0].copy())
    elif kind == "foreign_trial": values[0]["trial_id"] = int(max(reference["trial_ids"]))+1000
    elif kind == "fractional_trial": values[0]["trial_id"] = float(values[0]["trial_id"])+.1
    else: values[0]["predicted_choice"] = 0
    write_rows(output / "trial_predictions.csv", values)
    with pytest.raises((AssertionError, ValueError)):
        validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["one_prediction", "constant_predictions", "reverse_signed_choice", "wrong_split", "swap_windows", "swap_splits"])
def test_coherent_forged_predictions_and_aggregates_are_rejected(output_copy, kind):
    output, reference = output_copy; values = rows(output / "trial_predictions.csv")
    reason = "OOF predictions differ"
    if kind == "one_prediction": flip_prediction(values[0])
    elif kind == "constant_predictions":
        target = -int(values[0]["predicted_choice"])
        for row in values:
            row["predicted_choice"], row["decision_value"] = target, float(target)
            row["probability_left"] = float(sigmoid(np.array([target]))[0])
    elif kind == "reverse_signed_choice":
        for row in values:
            row["true_choice"] = -int(row["true_choice"]); flip_prediction(row)
        reason = "OOF signed truth differs"
    elif kind == "wrong_split":
        for row in values:
            if row["recipe"] == "stimulus_blocked": row["fold"] = (int(row["fold"])+1) % 5
        reason = "OOF fold identity differs"
    elif kind == "swap_windows":
        for row in values:
            window, split = row["recipe"].rsplit("_", 1)
            row["recipe"] = f"{'peri_response' if window == 'stimulus' else 'stimulus'}_{split}"
        reason = "OOF (predictions|decision_value) differ"
    else:
        for row in values:
            window, split = row["recipe"].rsplit("_", 1)
            row["recipe"] = f"{window}_{'random' if split == 'blocked' else 'blocked'}"
        reason = "OOF fold identity differs"
    recalculate(output, values)
    with pytest.raises(AssertionError, match=reason):
        validate_output_directory(output, reference)


def test_wrong_trial_predictions_can_preserve_mean_and_pooled_accuracy(output_copy):
    output, reference = output_copy; values = rows(output / "trial_predictions.csv")
    group = [r for r in values if r["recipe"] == "stimulus_blocked"]
    sizes = {fold: sum(int(r["fold"]) == fold for r in group) for fold in range(5)}
    pair = next(((a, b) for a in group for b in group
                 if a["true_choice"] == a["predicted_choice"] and b["true_choice"] != b["predicted_choice"]
                 and a["fold"] != b["fold"] and sizes[int(a["fold"])] == sizes[int(b["fold"])]), None)
    if pair is None:
        pytest.skip("this genuine run has no equal-sized cross-fold correct/error pair")
    before = read_json(output / "results.json")
    flip_prediction(pair[0]); flip_prediction(pair[1]); recalculate(output, values)
    after = read_json(output / "results.json")
    assert after["cross_validated_accuracy"] == pytest.approx(before["cross_validated_accuracy"], abs=1e-14)
    assert after["pooled_accuracy_by_window_and_split"] == before["pooled_accuracy_by_window_and_split"]
    with pytest.raises(AssertionError, match="OOF predictions differ"):
        validate_output_directory(output, reference)


def test_trial_identity_cannot_be_permuted_with_labels_and_predictions(output_copy):
    output, reference = output_copy; values = rows(output / "trial_predictions.csv")
    group = [r for r in values if r["recipe"] == "stimulus_blocked"]
    a = group[0]; b = next(r for r in group if r["fold"] == a["fold"] and r["true_choice"] != a["true_choice"])
    a["trial_id"], b["trial_id"] = b["trial_id"], a["trial_id"]
    recalculate(output, values)
    with pytest.raises(AssertionError, match="OOF signed truth differs"):
        validate_output_directory(output, reference)


def test_decisions_not_only_thresholded_labels_are_source_bound(output_copy):
    output, reference = output_copy; values = rows(output / "trial_predictions.csv")
    for row in values:
        row["decision_value"] = float(row["decision_value"])*2
        row["probability_left"] = float(sigmoid(np.array([row["decision_value"]]))[0])
    recalculate(output, values)
    with pytest.raises(AssertionError, match="OOF decision_value differs"):
        validate_output_directory(output, reference)


def test_pooled_headline_is_not_the_unweighted_fold_mean(output_copy):
    output, reference = output_copy; result = read_json(output / "results.json")
    pooled = result["pooled_accuracy_by_window_and_split"]["stimulus_blocked"]
    if abs(pooled-result["cross_validated_accuracy"]) <= 1e-6:
        pytest.skip("genuine headline happens to equal pooled; unequal-size fixture checks distinction")
    result["cross_validated_accuracy"] = pooled; write_json(output / "results.json", result)
    with pytest.raises(AssertionError, match="cross_validated_accuracy"):
        validate_output_directory(output, reference)


@pytest.mark.parametrize("kind", ["unit_count", "selection_count", "timing"])
def test_coherent_source_summary_forgery_fails(output_copy, kind):
    output, reference = output_copy
    result, metadata = read_json(output / "results.json"), read_json(output / "run_metadata.json")
    for document in (result, metadata):
        if kind == "unit_count":
            document["n_units"] += 1; document["selection_counts"]["n_source_units"] += 1
        elif kind == "selection_count":
            document["selection_counts"]["n_source_trials"] += 1
            document["selection_counts"]["n_not_included"] += 1
        else:
            timing = document["response_timing_counts"]
            source = next(key for key, value in timing.items() if value)
            target = next(key for key in timing if key != source)
            timing[source] -= 1; timing[target] += 1
    write_json(output / "results.json", result); write_json(output / "run_metadata.json", metadata)
    with pytest.raises(AssertionError):
        validate_output_directory(output, reference)


def test_source_sha_cannot_be_relabelled(output_copy):
    output, reference = output_copy; metadata = read_json(output / "run_metadata.json")
    metadata["source_sha256"] = {key: "0"*64 for key in metadata["source_sha256"]}
    write_json(output / "run_metadata.json", metadata)
    with pytest.raises(AssertionError, match="source_sha256"):
        validate_output_directory(output, reference)


def test_actual_globally_scaled_negative_control(genuine):
    value = os.environ.get("REPAIR_LEAKAGE_OUTPUT")
    if not value:
        pytest.skip("no actual global-standardization control supplied; metadata-only change is not leakage evidence")
    _, reference = genuine
    # The control's authoring receipt identifies deliberate leakage; public output
    # uses the same schema so the asserted rejection must come from numeric OOF evidence.
    load_trial_predictions(Path(value) / "trial_predictions.csv")
    with pytest.raises(AssertionError, match="OOF (predictions|decision_value|probability_left) differ"):
        validate_output_directory(Path(value), reference)
