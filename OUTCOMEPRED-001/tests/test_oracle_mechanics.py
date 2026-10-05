"""Source-free numerical, identity and evidence-safety fixtures for the fixed method."""
import copy
import importlib.util
import json
from pathlib import Path
import warnings

import numpy as np
import pytest
from sklearn.preprocessing import StandardScaler

TASK = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("outcomepred_oracle", TASK / "solution/compute.py")
oracle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oracle)
CONTRACT = json.loads((TASK / "environment/method_contract.json").read_text())


def fixture_source(n=32, units=4):
    labels = np.asarray([True] * 20 + [False] * (n-20), dtype=bool)
    feedback = np.arange(n, dtype=np.float64) * 2 + 1
    trials = dict(id=np.arange(101, 101+n, dtype=np.int64),
                  start_time=feedback-1, stop_time=feedback+1,
                  gabor_stimulus_onset_time=feedback-.5, feedback_time=feedback,
                  choice_registration_time=feedback-.001, wheel_movement_onset_time=feedback-.25,
                  mouse_wheel_choice=np.full(n, "clockwise", dtype="<U32"), is_mouse_rewarded=labels)
    trains = [np.sort(np.r_[feedback-.15, feedback+.1, feedback+.1, feedback+.4]) for _ in range(units)]
    source = dict(trials=trials, labels=labels.astype(np.int64), unit_ids=np.arange(300, 300+units),
                  spike_times=np.concatenate(trains), spike_ends=np.arange(1, units+1)*len(trains[0]),
                  source_summary=dict(n_source_trials=n, n_units=units, n_stored_spikes=units*len(trains[0]),
                                      duplicate_adjacent_spike_pairs=n*units, nwb_version="fixture",
                                      session_start_time="same", timestamps_reference_time="same",
                                      kilosort_label_counts={"mua": units}, ibl_quality_score_counts={"0.0": units},
                                      probe_counts={"fixture": units}, observation_support="unknown",
                                      task_epoch_start_s=0.0, task_epoch_stop_s=float(2*n)), source_manifest={})
    return source


def test_exact_frozen_contract_loads_without_source_read():
    assert oracle.load_contract(TASK / "environment/method_contract.json") == CONTRACT
    assert len(CONTRACT["windows"]) == 21


@pytest.mark.parametrize("values", [[0, 1], np.array([0., 1.]), np.array([False, True], dtype=object), [None, True]])
def test_outcome_requires_original_boolean_dtype(values):
    with pytest.raises(ValueError): oracle.original_labels(values)


def test_boolean_outcome_is_not_synthetic_or_coerced():
    np.testing.assert_array_equal(oracle.original_labels(np.array([True, False, True])), [1, 0, 1])


@pytest.mark.parametrize("values", [np.array([True, False]), np.array([1., 2.]), np.array([1, 1]),
                                   np.array([], dtype=int), np.array([2**63], dtype=np.uint64)])
def test_identity_must_be_unique_int64_compatible(values):
    with pytest.raises(ValueError): oracle.integer_ids(values, "test")


def test_nonconsecutive_original_ids_are_preserved():
    np.testing.assert_array_equal(oracle.integer_ids(np.array([15, -2, 11]), "test"), [15, -2, 11])


@pytest.mark.parametrize("times,ends", [([.2, .1], [2]), ([.1, np.nan], [2]), ([-.1, .1], [2]),
    ([.1, .2], [1]), ([.1, .2], [-1, 2]), ([.1, .2], [2, 1]), ([.1, .2], [2.0])])
def test_bad_spike_source_fails_without_sorting(times, ends):
    with pytest.raises(ValueError): oracle.validate_spikes(np.array(times, dtype=float), np.array(ends), len(ends))


def test_ragged_duplicate_spikes_and_empty_train_preserved():
    ends, duplicates = oracle.validate_spikes(np.array([.1, .1, .2], dtype=float), np.array([0, 3]), 2)
    np.testing.assert_array_equal(ends, [0, 3]); assert duplicates == 1


def test_selection_exact_draw_order_including_full_minority_draw():
    source = fixture_source()
    selection = oracle.select_trials(source["trials"], source["labels"])
    rng = np.random.RandomState(0)
    expected = np.sort(np.r_[rng.choice(np.arange(20), 12, replace=False), rng.choice(np.arange(20, 32), 12, replace=False)])
    np.testing.assert_array_equal(selection["selected"], expected)
    assert set(selection["folds"]) == set(range(5))
    assert np.all(np.bincount(source["labels"][expected]) == 12)
    assert np.array_equal(selection["all_folds"][expected], selection["folds"])


def test_eligibility_reason_precedence_and_unselected_folds():
    source = fixture_source()
    trials = source["trials"]
    trials["mouse_wheel_choice"][0] = "none"
    trials["gabor_stimulus_onset_time"][:2] = np.nan
    trials["feedback_time"][:3] = np.nan
    selection = oracle.select_trials(trials, source["labels"])
    assert selection["reasons"][:3].tolist() == ["invalid_choice", "nonfinite_stimulus", "nonfinite_feedback"]
    assert np.all(selection["all_folds"][:3] == -1)
    rows = oracle.source_trial_rows(source, selection)
    assert rows[0]["stimulus_time_s"] is None and rows[0]["feedback_time_s"] is None
    assert rows[0]["fold"] is None and rows[0]["trial_id"] == 101


def test_fewer_than_five_per_class_fails():
    source = fixture_source(n=24)
    with pytest.raises(ValueError): oracle.select_trials(source["trials"], source["labels"])


def test_half_open_counting_and_duplicates_no_rounding():
    source = dict(trials={"feedback_time": np.array([10.])}, unit_ids=np.array([77]),
                  spike_times=np.array([9.799999, 9.8, 9.8, 9.85, 9.95, 10.]), spike_ends=np.array([6]))
    counts = oracle.count_windows(source, {"selected": np.array([0])}, [{"analysis": "test", "start_ms": -200, "end_ms": -50}])
    assert counts.shape == (1, 1, 1) and counts[0, 0, 0] == 3
    assert counts.dtype.kind in "iu"


def test_endpoint_uses_integer_ms_independently():
    feedback = np.array([123.123456789012345])
    left, right = oracle.window_endpoints(feedback, {"start_ms": 150, "end_ms": 350})
    assert left[0] == feedback[0] + np.float64(150/1000)
    assert right[0] == feedback[0] + np.float64(350/1000)


def test_support_is_descriptive_and_half_open_touch_is_not_overlap():
    source = fixture_source()
    source["trials"]["feedback_time"][:3] = [1., 1.2, 1.3]
    source["trials"]["start_time"][:3] = [1.1, 1.1, 1.1]
    windows = [{"analysis": "test", "start_ms": 0, "end_ms": 200}]
    row = oracle.describe_support(source, {"selected": np.arange(3)}, windows)[0]
    assert row["n_overlapping_selected_window_pairs"] == 1
    assert row["n_starts_before_trial_start"] == 1


def test_train_scaling_matches_declared_standard_scaler_and_not_test_statistics():
    train = np.array([[1, 3, 9], [2, 3, 9], [7, 3, 9]], dtype=float)
    test = np.array([[1000, 99, 9]], dtype=float)
    a, b, mean, variance, scale = oracle.scale_training(train, test)
    reference = StandardScaler().fit(train)
    np.testing.assert_allclose(a, reference.transform(train), atol=1e-14)
    np.testing.assert_allclose(b, reference.transform(test), atol=1e-14)
    np.testing.assert_allclose(mean, np.mean(train, axis=0))
    assert scale[1] == 1 and scale[2] == 1 and variance[1] == 0


def test_logistic_gradient_matches_centered_finite_difference():
    rng = np.random.RandomState(23)
    X = rng.normal(size=(12, 5)); y = np.array([0, 1]*6)
    q = rng.normal(size=6)
    objective, gradient = oracle.objective_gradient(X, y, q[:-1], q[-1])
    numerical = []
    for coordinate in range(6):
        delta = np.zeros(6); delta[coordinate] = 1e-5
        plus, _ = oracle.objective_gradient(X, y, (q+delta)[:-1], (q+delta)[-1])
        minus, _ = oracle.objective_gradient(X, y, (q-delta)[:-1], (q-delta)[-1])
        numerical.append((plus-minus)/(2e-5*len(y)))
    np.testing.assert_allclose(gradient, numerical, atol=1e-10, rtol=1e-8)
    assert np.isfinite(objective)


def test_rank_deficient_more_features_than_trials_is_allowed():
    X = np.tile(np.arange(8, dtype=float)[:, None], (1, 12))
    X = np.c_[X, np.ones(8)]
    scores, model = oracle.fit_one(X, np.array([0, 1]*4), X[:2])
    assert np.isfinite(scores).all() and model["finite_parameters"]
    assert model["mean_gradient_inf"] <= 1e-9
    assert model["scaler_scale"][-1] == 1


def test_preserved_warning_does_not_reject_stationary_fit(monkeypatch, capsys):
    fit = oracle.LogisticRegression.fit
    def warned(self, *args, **kwargs):
        warnings.warn("synthetic diagnostic", RuntimeWarning)
        return fit(self, *args, **kwargs)
    monkeypatch.setattr(oracle.LogisticRegression, "fit", warned)
    scores, model = oracle.fit_one(np.arange(24).reshape(12, 2), np.array([0, 1]*6), np.zeros((1, 2)))
    assert model["warnings"] == ["RuntimeWarning: synthetic diagnostic"]
    assert "synthetic diagnostic" in capsys.readouterr().err
    assert model["mean_gradient_inf"] <= 1e-9


def test_complete_summaries_distinguish_fold_mean_from_pooled_and_zero_tie():
    source = fixture_source()
    selection = oracle.select_trials(source["trials"], source["labels"])
    labels, folds = source["labels"][selection["selected"]], selection["folds"]
    scores = np.tile(np.where(labels, 2., -2.), (21, 1))
    scores[:, folds == 0] *= -1
    scores[0, 0] = 0
    predictions, fold_rows, curve, result = oracle.summarize_predictions(source, selection, scores, CONTRACT["windows"])
    assert len(predictions) == 21*len(labels) and len(fold_rows) == 105 and len(curve) == 19
    assert predictions[0]["decision_score"] == 0 and predictions[0]["prediction"] == 0
    current = [row for row in fold_rows if row["analysis"] == "control_post"]
    assert result["post_feedback"]["mean_accuracy"] == np.mean([r["accuracy"] for r in current])
    assert result["post_feedback"]["pooled_oof_accuracy"] == sum(r["n_correct"] for r in current)/len(labels)


def test_pilot_fits_exact_two_models_and_is_not_complete():
    source = fixture_source(); selection = oracle.select_trials(source["trials"], source["labels"])
    counts = oracle.count_windows(source, selection, CONTRACT["windows"])
    scores = np.full(counts.shape[:2], np.nan); models = []
    oracle.fit_models(counts, source["labels"][selection["selected"]], selection["folds"], CONTRACT["windows"], scores, models, pilot=True)
    assert [(m["analysis"], m["fold"]) for m in models] == [("headline_pre", 0), ("control_post", 0)]
    *_, result = oracle.summarize_predictions(source, selection, scores, CONTRACT["windows"], pilot=True)
    assert result["status"] == "resource_pilot" and result["headline"] is None
    with pytest.raises(ValueError): oracle.summarize_predictions(source, selection, scores, CONTRACT["windows"])


def test_private_evidence_primitive_and_model_bound(tmp_path):
    source = fixture_source(); selection = oracle.select_trials(source["trials"], source["labels"])
    counts = oracle.count_windows(source, selection, CONTRACT["windows"])
    scores = np.full(counts.shape[:2], np.nan); models = []
    oracle.fit_models(counts, source["labels"][selection["selected"]], selection["folds"], CONTRACT["windows"], scores, models, pilot=True)
    oracle.save_private(tmp_path, source, selection, counts, scores, models, CONTRACT)
    with np.load(tmp_path / "analysis_arrays.npz", allow_pickle=False) as arrays:
        assert all(arrays[key].dtype.kind != "O" for key in arrays.files)
        assert arrays["spike_count"].shape == counts.shape
        assert arrays["model_coef"].shape == (2, len(source["unit_ids"]))


@pytest.mark.parametrize("mode", ["nonempty", "symlink", "ancestor", "nested", "same"])
def test_output_safety_preserves_user_files(tmp_path, mode):
    output, private = tmp_path / "output", tmp_path / "private"
    if mode == "nonempty": output.mkdir(); (output / "keep").write_text("original")
    elif mode == "symlink": output.symlink_to(tmp_path / "other")
    elif mode == "ancestor":
        real = tmp_path / "real"; real.mkdir(); link = tmp_path / "link"; link.symlink_to(real); output = link / "output"
    elif mode == "nested": private = output / "private"
    else: private = output
    with pytest.raises((ValueError, FileExistsError)): oracle.prepare_destinations(output, private)
    if mode == "nonempty": assert (output / "keep").read_text() == "original"


def test_harbor_and_checkout_stager_paths(tmp_path):
    local = tmp_path / "task/environment"; local.mkdir(parents=True); (local / "stage_data.py").write_text("# fixture")
    assert oracle.stager_path(tmp_path / "task/solution/compute.py") == local / "stage_data.py"
    assert oracle.stager_path(tmp_path / "solution/compute.py", Path("/opt/source/stage_data.py")) == Path("/opt/source/stage_data.py")


def test_failed_source_keeps_required_failure_evidence_and_env_output(tmp_path, monkeypatch):
    output, private = tmp_path / "output", tmp_path / "private"
    monkeypatch.setenv("OUTPUT_DIR", str(output)); monkeypatch.setenv("PRIVATE_DIR", str(private))
    monkeypatch.setattr(oracle, "read_source", lambda *a: (_ for _ in ()).throw(ValueError("missing original fixture")))
    assert oracle.main(["--method-contract", str(TASK / "environment/method_contract.json")]) == 1
    assert json.loads((output / "results.json").read_text())["status"] == "failed_precondition"
    assert json.loads((output / "run_metadata.json").read_text())["reason"]
    assert (output / "findings.md").read_text().strip()
    assert (private / "failure.json").exists()


def test_no_object_arrays_can_be_exported(tmp_path):
    with pytest.raises(ValueError): oracle.write_npz(tmp_path / "unsafe.npz", {"bad": np.array([{}], dtype=object)})
    assert not (tmp_path / "unsafe.npz").exists()


@pytest.mark.parametrize("which", ["output_equal", "private_equal", "output_contains", "private_contains", "output_inside", "private_inside"])
def test_source_evidence_overlap_rejected_before_any_mutation(tmp_path, which):
    source = tmp_path / "source"; source.mkdir(); (source / "original").write_text("unchanged")
    output, private = tmp_path / "output", tmp_path / "private"
    if which == "output_equal": output = source
    elif which == "private_equal": private = source
    elif which == "output_contains": output = tmp_path; private = tmp_path.parent / "uncreated-private"
    elif which == "private_contains": private = tmp_path; output = tmp_path.parent / "uncreated-output"
    elif which == "output_inside": output = source / "output"
    else: private = source / "private"
    with pytest.raises(ValueError): oracle.prepare_destinations(output, private, source)
    assert (source / "original").read_text() == "unchanged"
    assert {p.name for p in source.iterdir()} == {"original"}


def test_private_failure_cannot_leave_complete_status(tmp_path, monkeypatch):
    output, private = tmp_path / "output", tmp_path / "private"
    monkeypatch.setattr(oracle, "read_source", lambda *a: fixture_source())
    def fail_save(*args): raise OSError("fixture private write failure")
    monkeypatch.setattr(oracle, "save_private", fail_save)
    assert oracle.main(["--output-dir", str(output), "--private-dir", str(private),
                        "--method-contract", str(TASK / "environment/method_contract.json"), "--pilot"]) == 1
    assert json.loads((output / "results.json").read_text())["status"] == "failed_precondition"
    assert json.loads((output / "run_metadata.json").read_text())["status"] == "failed_precondition"
    assert "Failed precondition" in (output / "findings.md").read_text()
