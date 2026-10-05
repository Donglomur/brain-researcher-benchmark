"""Small synthetic fixtures only; no original source processing or fits."""
import ast
import csv
import importlib.util
import json
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

CHECKER = Path(__file__).with_name("check_independent.py")
SPEC = importlib.util.spec_from_file_location("objcat_independent", CHECKER)
q = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q)


def test_detrend_and_sample_sd_against_explicit_small_projection():
    rng = np.random.RandomState(42)
    X = rng.normal(size=(42, 6)) + np.arange(42)[:, None] * np.arange(6)[None, :]
    runs = np.repeat([0, 1], 21)
    clean, constants = q.clean_full_runs(X, runs)
    for run in (0, 1):
        values = X[runs == run]
        design = np.column_stack((np.ones(len(values)), np.arange(len(values))))
        beta = np.linalg.lstsq(design, values, rcond=None)[0]
        residual = values - design @ beta
        expected = (residual - residual.mean(axis=0)) / residual.std(axis=0, ddof=1)
        np.testing.assert_allclose(clean[runs == run], expected, atol=2e-13, rtol=2e-13)
        np.testing.assert_allclose(clean[runs == run].std(axis=0, ddof=1), 1.)
    assert constants == {"0": 0, "1": 0}


def test_tiny_equivalence_to_declared_nilearn_recipe_including_batches():
    # Test-only reference library; the independent implementation never imports it.
    from nilearn.signal import clean
    rng = np.random.RandomState(9)
    X = rng.normal(size=(40, 601)) + np.arange(40)[:, None] * .2
    X[:, 0] = 100.  # Exact source constants must stay zero, not amplified noise.
    runs = np.repeat([0, 1], 20)
    actual, constants = q.clean_full_runs(X, runs)
    expected = clean(X, runs=runs, detrend=True, standardize="zscore_sample", low_pass=None, high_pass=None, t_r=2.5)
    np.testing.assert_allclose(actual, expected, atol=1e-13, rtol=1e-13)
    assert np.all(actual[:, 0] == 0) and constants == {"0": 1, "1": 1}


def test_full_run_cleaning_before_rest_drop_is_load_bearing():
    rng = np.random.RandomState(3)
    X = rng.normal(size=(40, 4))
    runs = np.repeat([0, 1], 20)
    keep = np.arange(40) % 2 == 1
    X[~keep] += 10
    full, _ = q.clean_full_runs(X, runs)
    task_only, _ = q.clean_full_runs(X[keep], runs[keep])
    assert not np.allclose(full[keep], task_only)


@pytest.mark.parametrize("mutation", ["nonfinite", "one_sample", "run_length"])
def test_bad_cleaning_input_fails(mutation):
    X, runs = np.ones((4, 2)), np.zeros(4, int)
    if mutation == "nonfinite": X[0, 0] = np.nan
    elif mutation == "one_sample": runs[0] = 1
    else: runs = runs[:-1]
    with pytest.raises(ValueError): q.clean_full_runs(X, runs)


def test_explicit_anova_known_values_and_constant_cases():
    X = np.column_stack(([1., 2, 3, 4, 5, 6], [0.] * 6, [0., 0, 0, 1, 1, 1]))
    scores = q.explicit_anova(X, np.array(["a"] * 3 + ["b"] * 3))
    assert scores[0] == pytest.approx(13.5)
    assert np.isnan(scores[1]) and np.isposinf(scores[2])


def test_explicit_eight_group_anova_matches_scipy_on_synthetic_values():
    from scipy.stats import f_oneway
    rng = np.random.RandomState(5)
    labels = np.repeat(np.arange(8), 9)
    X = rng.normal(size=(72, 7)) + labels[:, None] * .3
    actual = q.explicit_anova(X, labels)
    expected = f_oneway(*(X[labels == group] for group in range(8))).statistic
    np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=1e-12)


def test_exact_tie_favors_later_indices_and_classifier_order_ascending():
    assert q.selected_features([10., 2, 2, 2, np.nan], 3).tolist() == [0, 2, 3]
    assert q.selected_features([1., 1, 1, 1], 2).tolist() == [2, 3]


@pytest.mark.parametrize("scores,k", [([1., np.nan], 2), ([1., 2, np.inf], 2), ([1.], 0), ([1.], 2)])
def test_nonfinite_or_insufficient_selected_support_fails(scores, k):
    with pytest.raises(ValueError): q.selected_features(scores, k)


def prepared_fixture():
    rng = np.random.RandomState(40)
    y = np.tile(np.repeat(np.asarray(q.CATEGORIES), 2), 3)
    runs = np.repeat(np.arange(3), 16)
    X = rng.normal(size=(48, 9)) * .1
    for index, label in enumerate(q.CATEGORIES): X[y == label, index] += 3
    return {"X": X, "run": runs, "true_label": y, "volume_id": 3 * np.arange(48) + 1,
            "mask_ijk": np.column_stack((np.arange(9), np.zeros(9, int), np.zeros(9, int))),
            "full_run": runs, "full_label": y}


def test_fresh_tiny_svc_folds_and_exact_source_ids():
    prepared = prepared_fixture()
    arrays, result, warnings = q.fit_independent(prepared, k=5)
    assert arrays["selected_indices"].shape == (3, 5)
    assert arrays["anova_f"].shape == (3, 9)
    assert arrays["fold_n_train"].tolist() == [32] * 3 and arrays["fold_n_test"].tolist() == [16] * 3
    np.testing.assert_array_equal(arrays["volume_id"], prepared["volume_id"])
    assert result["cv_accuracy"] == pytest.approx(np.mean(arrays["predicted_label"] == prepared["true_label"]))
    assert set(warnings) == {"0", "1", "2"}


def test_heldout_values_and_labels_cannot_select_fold_features():
    prepared = prepared_fixture()
    baseline, _, _ = q.fit_independent(prepared, k=5)
    modified = {key: np.array(value, copy=True) for key, value in prepared.items()}
    use = modified["run"] == 0
    modified["X"][use] *= 100
    modified["true_label"][use] = np.roll(modified["true_label"][use], 2)
    changed, _, _ = q.fit_independent(modified, k=5)
    np.testing.assert_array_equal(baseline["selected_indices"][0], changed["selected_indices"][0])
    np.testing.assert_array_equal(baseline["anova_f"][0], changed["anova_f"][0])


def synthetic_label_file(path):
    row = ["rest"] * 49 + [label for label in q.CATEGORIES for _ in range(9)]
    path.write_text("labels chunks\n" + "".join(f"{label} {run}\n" for run in range(12) for label in row))


def test_label_identity_and_balanced_original_support(tmp_path):
    path = tmp_path / "labels.txt"
    synthetic_label_file(path)
    labels, runs = q.source_labels(path)
    assert len(labels) == 1452 and np.count_nonzero(labels != "rest") == 864
    assert np.array_equal(np.unique(runs), np.arange(12))
    path.write_text(path.read_text().replace("bottle 0", "face 0", 1))
    with pytest.raises(ValueError, match="support"): q.source_labels(path)


def test_geometry_alignment_and_no_resampling():
    header = nib.Nifti1Header()
    header.set_data_shape((2, 3, 4, 1452))
    bold = nib.Nifti1Image(np.empty((2, 3, 4, 1452), dtype=np.int16), np.eye(4), header=header)
    mask = nib.Nifti1Image(np.ones((2, 3, 4), dtype=np.int16), np.eye(4))
    geometry = q.image_geometry(bold, mask)
    assert geometry["bold_shape"] == [2, 3, 4, 1452]
    shifted = np.eye(4); shifted[0, 3] = 1
    with pytest.raises(ValueError, match="affine"):
        q.image_geometry(bold, nib.Nifti1Image(np.ones((2, 3, 4)), shifted))


def fixture_output(tmp_path):
    arrays, result, _ = q.fit_independent(prepared_fixture(), k=5)
    output = tmp_path / "independent"
    q.emit_outputs(output, arrays, result, {"pipeline_id": q.PIPELINE_ID})
    return output, arrays, result


def rewrite_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def test_participant_outputs_match_and_row_order_is_irrelevant(tmp_path):
    output, arrays, result = fixture_output(tmp_path)
    path = output / "selected_features.csv"
    with path.open() as stream: rows = list(csv.DictReader(stream))
    rewrite_csv(path, list(reversed(rows)))
    comparison = q.compare_oracle_csvs(output, arrays)
    assert comparison["passed"] and comparison["n_predictions"] == 48
    assert set(path.name for path in output.iterdir()) == {"predictions.csv", "per_fold.csv", "selected_features.csv", "decoding_results.json", "run_metadata.json", "findings.md"}
    assert json.loads((output / "decoding_results.json").read_text()) == result


@pytest.mark.parametrize("mutation", ["prediction", "source_label", "coordinate", "F", "selected_set", "fold_accuracy", "duplicate"])
def test_oracle_csv_mutation_detected(tmp_path, mutation):
    output, arrays, _ = fixture_output(tmp_path)
    filename = "predictions.csv" if mutation in {"prediction", "source_label"} else "per_fold.csv" if mutation == "fold_accuracy" else "selected_features.csv"
    path = output / filename
    with path.open() as stream: rows = list(csv.DictReader(stream))
    if mutation == "prediction": rows[0]["predicted_label"] = "foreign"
    elif mutation == "source_label": rows[0]["true_label"] = "foreign"
    elif mutation == "coordinate": rows[0]["i"] = "999"
    elif mutation == "F": rows[0]["f_statistic"] = "0"
    elif mutation == "selected_set": rows[0]["feature_index"] = "999"
    elif mutation == "fold_accuracy": rows[0]["accuracy"] = "0.001"
    else: rows.append(dict(rows[0]))
    rewrite_csv(path, rows)
    if mutation in {"source_label", "duplicate"}:
        with pytest.raises(ValueError): q.compare_oracle_csvs(output, arrays)
    else:
        assert not q.compare_oracle_csvs(output, arrays)["passed"]


@pytest.mark.parametrize("which,link", [("output", False), ("report", False), ("artifact", False), ("report", True), ("output", True)])
def test_existing_evidence_preserved_before_source_processing(tmp_path, monkeypatch, which, link):
    output, report = tmp_path / "output", tmp_path / "report.json"
    target = {"output": output, "report": report, "artifact": report.with_suffix(".arrays.npz")}[which]
    if link: target.symlink_to(tmp_path / "missing")
    elif which == "output": target.mkdir()
    else: target.write_bytes(b"retained evidence")
    monkeypatch.setattr(q, "run_check", lambda *args: pytest.fail("source processing must not start"))
    assert q.main(["--oracle-output", str(tmp_path), "--output-dir", str(output), "--report", str(report)]) == 1
    if link: assert target.is_symlink()
    elif which != "output": assert target.read_bytes() == b"retained evidence"


def test_no_oracle_verifier_bank_or_selection_library_import():
    tree = ast.parse(CHECKER.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name.startswith(("nilearn", "compute", "proof_of_work", "sklearn.feature_selection")) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(("nilearn", "compute", "proof_of_work", "sklearn.feature_selection"))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr != "load" or not isinstance(node.func.value, ast.Name) or node.func.value.id != "np"


def test_changed_source_manifest_fails_before_image_load(tmp_path):
    (tmp_path / "data_manifest.json").write_text("{}\n")
    with pytest.raises(ValueError, match="manifest SHA256"):
        q.verify_inputs(tmp_path)
