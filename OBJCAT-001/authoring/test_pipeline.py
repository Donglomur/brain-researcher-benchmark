"""Small synthetic classifier mechanics, not an empirical scientific bank."""
import csv
import importlib.util
import json
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("objcat_pipeline_mechanics", Path(__file__).parents[1] / "solution/compute.py")
c = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(c)


@pytest.fixture
def prepared():
    rng = np.random.RandomState(31)
    runs = np.repeat(np.arange(3), 24)
    labels = np.tile(np.repeat(c.CATEGORIES, 3), 3)
    X = rng.normal(size=(72, 12)).astype(np.float64)
    X[:, :8] += (labels[:, None] == c.CATEGORIES[None, :]) * 0.8
    return {"X": X, "mask_ijk": np.column_stack([np.zeros(12, int), np.zeros(12, int), np.arange(12)]),
            "volume_id": 5 + 2 * np.arange(72), "run": runs, "true_label": labels,
            "full_volume_id": np.arange(150), "full_run": np.repeat(np.arange(3), 50),
            "full_label": np.repeat("rest", 150)}


def test_module_import_does_not_create_output(monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("import attempted I/O")
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    spec = importlib.util.spec_from_file_location("objcat_import_probe", Path(c.__file__))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


def test_selector_sees_only_training_rows(prepared, monkeypatch):
    original = c.select_features; observed = []
    def recording(X, y, k):
        observed.append((X.copy(), y.copy()))
        return original(X, y, k)
    monkeypatch.setattr(c, "select_features", recording)
    arrays, result = c.fit_nested(prepared, k=4)
    for index, run in enumerate(np.unique(prepared["run"])):
        train = prepared["run"] != run
        np.testing.assert_array_equal(observed[index][0], prepared["X"][train])
        np.testing.assert_array_equal(observed[index][1], prepared["true_label"][train])
    assert arrays["selected_indices"].shape == (3, 4)
    assert result["n_samples"] == 72


def test_fitted_linear_state_reconstructs_ovo_ovr_and_vote_predictions(prepared):
    arrays, _ = c.fit_nested(prepared, k=4)
    for fi, run in enumerate(arrays["run_ids"]):
        test = prepared["run"] == run
        selected = arrays["selected_indices"][fi]
        scores = prepared["X"][test][:, selected] @ arrays["classifier_coef"][fi].T + arrays["classifier_intercept"][fi]
        np.testing.assert_allclose(scores, arrays["decision_ovo"][test], atol=1e-12, rtol=1e-12)
        votes, confidence = np.zeros((test.sum(), 8)), np.zeros((test.sum(), 8))
        column = 0
        for i in range(8):
            for j in range(i + 1, 8):
                votes[:, i] += scores[:, column] > 0
                votes[:, j] += scores[:, column] <= 0
                confidence[:, i] += scores[:, column]
                confidence[:, j] -= scores[:, column]
                column += 1
        np.testing.assert_array_equal(arrays["classes"][votes.argmax(axis=1)], arrays["predicted_label"][test])
        # Scores are nonzero in this fixture; sklearn's OVR zero edge is distinct.
        ovr = votes + confidence / (3 * (np.abs(confidence) + 1))
        np.testing.assert_allclose(ovr, arrays["decision_ovr"][test], atol=1e-12, rtol=1e-12)


def test_every_support_vector_comes_only_from_training_run(prepared):
    arrays, _ = c.fit_nested(prepared, k=4)
    for run in arrays["run_ids"]:
        support = arrays[f"svc_support_volume_ids_{run}"]
        assert set(support) <= set(prepared["volume_id"][prepared["run"] != run])
        assert not set(support) & set(prepared["volume_id"][prepared["run"] == run])


def test_optional_global_selection_is_separate_coherent_negative(prepared):
    arrays, result = c.fit_nested(prepared, k=4, select_once=True)
    for selected in arrays["selected_indices"][1:]:
        np.testing.assert_array_equal(selected, arrays["selected_indices"][0])
    assert result["cv_accuracy"] == arrays["fold_accuracy"].mean()


def test_resource_pilot_retains_only_first_run_predictions_and_is_not_ok(prepared):
    arrays, result = c.fit_nested(prepared, k=4, held_out_runs=[0])
    assert result["status"] == "resource_pilot"
    assert result["n_samples"] == 24 and result["n_runs"] == 1
    assert result["n_available_samples"] == 72 and result["n_available_runs"] == 3
    assert arrays["decision_ovo"].shape == (24, 28)
    assert np.all(arrays["run"] == 0)
    assert arrays["selected_indices"].shape == (1, 4)
    np.testing.assert_array_equal(arrays["volume_id"], prepared["volume_id"][prepared["run"] == 0])


@pytest.mark.parametrize("requested", [[1, 0], [0, 0], [9], []])
def test_invalid_pilot_run_identity_fails(prepared, requested):
    with pytest.raises(ValueError, match="held-out runs"):
        c.fit_nested(prepared, k=4, held_out_runs=requested)


def test_source_probe_checks_original_values_without_cleaning_or_fitting(tmp_path, monkeypatch):
    bold, mask = tmp_path / "bold.nii.gz", tmp_path / "mask.nii.gz"
    nib.save(nib.Nifti1Image(np.ones((8, 8, 8, 1452), dtype=np.int16), np.eye(4)), bold)
    nib.save(nib.Nifti1Image(np.ones((8, 8, 8), dtype=np.uint8), np.eye(4)), mask)
    labels = np.tile(np.asarray(["rest"] * 49 + [str(label) for label in c.CATEGORIES for _ in range(9)]), 12)
    inputs = {"paths": {"bold": bold, "mask": mask}, "source_sha256": {},
              "full_label": labels, "full_run": np.repeat(np.arange(12), 121)}
    def forbidden(*args, **kwargs): raise AssertionError("source probe attempted analysis")
    monkeypatch.setattr(c, "extract_and_clean", forbidden); monkeypatch.setattr(c, "fit_nested", forbidden)
    report = c.inspect_source(inputs)
    assert report["signal_processing_performed"] is False
    assert report["all_source_bold_finite"] and report["mask_finite_binary"]
    assert report["n_voxels"] == 512 and report["n_nonrest_volumes"] == 864
    assert report["per_run"][11]["last_volume_id"] == 1451


def test_full_precision_fold_and_headline_arithmetic(prepared):
    arrays, result = c.fit_nested(prepared, k=4)
    for fi, run in enumerate(arrays["run_ids"]):
        selected = arrays["run"] == run
        assert arrays["fold_accuracy"][fi] == np.mean(arrays["predicted_label"][selected] == arrays["true_label"][selected])
    assert result["cv_accuracy"] == np.mean(arrays["fold_accuracy"])


def test_compact_receipt_and_public_tables(prepared, tmp_path):
    arrays, result = c.fit_nested(prepared, k=4)
    inputs = {"source_sha256": {"fixture": "not-scientific-evidence"}, "geometry": {}}
    metadata = c.write_outputs(tmp_path, inputs, arrays, result)
    assert len(list(csv.DictReader((tmp_path / "selected_features.csv").open()))) == 12
    assert len(list(csv.DictReader((tmp_path / "predictions.csv").open()))) == 72
    with np.load(tmp_path / "analysis_arrays.npz", allow_pickle=False) as receipt:
        assert "X" not in receipt.files and "elapsed_seconds" not in receipt.files
        assert json.loads(receipt["metadata_json"].item()) == metadata
        assert json.loads(receipt["results_json"].item()) == result


def test_failed_input_authentication_still_writes_parseable_failure(tmp_path, monkeypatch):
    def fail(_): raise ValueError("fixture source checksum mismatch")
    monkeypatch.setattr(c, "load_inputs", fail)
    with pytest.raises(ValueError): c.main(["--output", str(tmp_path)])
    assert json.loads((tmp_path / "decoding_results.json").read_text())["status"] == "failed_precondition"
    assert json.loads((tmp_path / "run_metadata.json").read_text())["reason"]


def test_fitfree_contract_mode_never_extracts_or_fits(tmp_path, monkeypatch, capsys):
    inputs = {"source_sha256": {"fixture": "fixture"}, "geometry": {}}
    monkeypatch.setattr(c, "load_inputs", lambda _: inputs)
    def fail(*args, **kwargs): raise AssertionError("fit-free mode attempted analysis")
    monkeypatch.setattr(c, "prepare_source", fail); monkeypatch.setattr(c, "fit_nested", fail)
    c.main(["--print-contracts", "--output", str(tmp_path / "unused")])
    assert json.loads(capsys.readouterr().out)["pipeline_id"] == c.PIPELINE_ID
    assert not (tmp_path / "unused").exists()


def test_later_control_failure_preserves_genuine_primary_output(prepared, tmp_path, monkeypatch):
    inputs = {"source_sha256": {"fixture": "fixture"}, "geometry": {}}
    original = c.fit_nested
    monkeypatch.setattr(c, "load_inputs", lambda _: inputs)
    monkeypatch.setattr(c, "prepare_source", lambda _: prepared)
    def conditional_fit(data, select_once=False):
        if select_once: raise ValueError("negative fixture failed")
        return original(data, k=4)
    monkeypatch.setattr(c, "fit_nested", conditional_fit)
    primary, control = tmp_path / "primary", tmp_path / "control"
    with pytest.raises(ValueError, match="negative fixture"):
        c.main(["--output", str(primary), "--select-once-output", str(control)])
    assert json.loads((primary / "decoding_results.json").read_text())["status"] == "ok"
    assert json.loads((control / "decoding_results.json").read_text())["status"] == "failed_precondition"
