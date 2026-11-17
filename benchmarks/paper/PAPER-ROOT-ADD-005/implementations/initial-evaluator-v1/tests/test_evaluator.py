"""Generated engineering controls. No THINGS observations are included."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

MODULE = Path(__file__).resolve().parents[1] / "evaluator.py"
spec = importlib.util.spec_from_file_location("root005_evaluator", MODULE)
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def fixture_bundle():
    n = 20
    rng = np.random.default_rng(5005)
    stimulus = np.array([f"image_{i:03d}" for i in range(n)])
    x = np.zeros((n, 66))
    x[:, :3] = rng.normal(size=(n, 3))
    category = rng.normal(size=(n, 2))
    shape = rng.normal(size=(n, 1))
    bundle = {"stimulus_id": stimulus, "dimensions": x, "category": category,
              "shape": shape, "image_family_id": np.array([f"family_{i:03d}" for i in range(n)]),
              "category_group_id": np.array([f"category_{i:03d}" for i in range(n)])}
    roster = {"task_id": ev.TASK_ID, "stimulus_ids": stimulus.tolist(), "participants": {}}
    roster["feature_provenance"] = {
        name: {"source_uri": "generated:engineering-control", "revision": "fixture-v1",
               "sha256": "0" * 64, "mapping_rule": "generated fixture rows; not empirical source provenance"}
        for name in ["dimensions", "category", "shape", "holdout_labels"]
    }
    for s in ev.PARTICIPANTS:
        # Include a repeated image with opposite trial deviations; both trials must survive.
        images = np.concatenate((stimulus, stimulus[:1]))
        trial = np.array([f"{s}_trial_{i:03d}" for i in range(n + 1)])
        y = (2 * x[:, 0] - x[:, 1] + category[:, 0] + int(s))[:, None]
        y = np.concatenate((y, y[:1])).copy()
        y[0] -= 0.25
        y[-1] += 0.25
        prefix = f"sub_{s}_"
        bundle.update({prefix + "trial_id": trial, prefix + "stimulus_id": images,
                       prefix + "voxel_id": np.array([f"{s}_voxel_0"]), prefix + "response": y})
        roster["participants"][s] = {"trial_ids": trial.tolist(), "stimulus_ids_by_trial": images.tolist(),
                                      "voxel_ids": [f"{s}_voxel_0"]}
    return bundle, roster


def test_exact_binding_is_identity_based_and_preserves_repeats():
    np.testing.assert_array_equal(ev.bind_rows(["zebra", "aardvark"], ["aardvark", "zebra", "aardvark"]), [1, 0, 1])
    with pytest.raises(ValueError, match="Unknown"):
        ev.bind_rows(["zebra"], ["Zebra"])
    with pytest.raises(ValueError, match="duplicate"):
        ev.bind_rows(["zebra", "zebra"], ["zebra"])


def test_transitive_family_and_category_components_never_cross_folds():
    family = np.array(["f1", "f1", "f2", "f3", "f4", "f5", "f6", "f7"])
    category = np.array(["c1", "c2", "c2", "c3", "c4", "c5", "c6", "c7"])
    groups = ev.group_components(family, category)
    assert groups[0] == groups[1] == groups[2]
    for train, test in ev.grouped_folds(groups, 5):
        assert not set(family[train]) & set(family[test])
        assert not set(category[train]) & set(category[test])
    order = np.array([7, 3, 0, 4, 2, 6, 1, 5])
    reordered = ev.group_components(family[order], category[order])
    np.testing.assert_array_equal(groups[order], reordered)
    with pytest.raises(ValueError, match="independent components"):
        ev.grouped_folds(np.array(["one"] * 10), 5)


def test_ridge_matches_independent_augmented_least_squares():
    # Independent penalized LS reference uses an augmented design rather than SVD shrinkage.
    x = np.array([[1., 4., 9.], [2., 2., 9.], [4., 0., 9.], [8., 3., 9.]])
    y = np.column_stack(([2., 3., 7., 12.], [-1., 5., 2., 6.]))
    test = np.array([[3., 1., 9.], [20., 5., 9.]])
    alpha = np.array([0.1, 10.])
    center, scale = x.mean(0), x.std(0)
    scale[scale == 0] = 1
    design = np.column_stack((np.ones(len(x)), (x - center) / scale))
    test_design = np.column_stack((np.ones(len(test)), (test - center) / scale))
    expected = []
    for voxel in range(2):
        penalty = np.diag([0.] + [np.sqrt(alpha[voxel])] * 3)
        beta = np.linalg.lstsq(np.vstack((design, penalty)), np.r_[y[:, voxel], np.zeros(4)], rcond=None)[0]
        expected.append(test_design @ beta)
    np.testing.assert_allclose(ev.ridge_predict(x, y, test, alpha), np.array(expected).T, atol=1e-10)


def test_scaling_uses_training_only_and_constant_column_is_harmless():
    x = np.arange(1., 7.)[:, None]
    y = 2 * x + 4
    ordinary = ev.ridge_predict(x, y, [[7.]], 1.)
    # A second extreme held-out point must not change the first prediction.
    extended = ev.ridge_predict(x, y, np.array([[7.], [1e12]]), 1.)
    np.testing.assert_allclose(ordinary, extended[:1])


def test_signed_r2_is_not_squared_correlation():
    y = np.arange(4.)[:, None]
    shifted = ev.fit_scores(y, y + 1)
    np.testing.assert_allclose(shifted["pearson_r"], [1.])
    np.testing.assert_allclose(shifted["r2"], [.2])
    reversed_score = ev.fit_scores(y, 3 - y)
    np.testing.assert_allclose(reversed_score["pearson_r"], [-1.])
    np.testing.assert_allclose(reversed_score["r2"], [-3.])
    constant = ev.fit_scores(np.ones((4, 1)), np.ones((4, 1)))
    assert np.isnan(constant["r2"]).all()
    assert ev._summary(constant["r2"])["mean_all_voxels"] is None


def test_numeric_dynamic_range_is_correct_or_fails_explicitly():
    # Independent final reviewer found silent Pearson=0 with naive SST*PSS.
    y = np.array([-1e80, 0., 1e80])[:, None]
    scores = ev.fit_scores(y, y)
    np.testing.assert_allclose(scores["r2"], [1.])
    np.testing.assert_allclose(scores["pearson_r"], [1.])
    # Raw SSE/SST cannot be represented at these scales; never call them constant.
    for scale, reason in [(1e200, "overflow"), (1e-200, "underflow")]:
        extreme = np.array([-scale, 0., scale])[:, None]
        with pytest.raises(ValueError, match=reason):
            ev.fit_scores(extreme, extreme)


def test_partition_matches_orthogonal_reference_and_preserves_negative_shared():
    # Independently derived by reference worker: orthogonal additive predictors.
    dim = np.array([-1., -1., 1., 1.])[:, None]
    cat = np.array([-1., 1., -1., 1.])[:, None]
    y = dim + cat
    part = ev.variance_partition(ev.fit_scores(y, dim)["r2"], ev.fit_scores(y, cat)["r2"], ev.fit_scores(y, y)["r2"])
    np.testing.assert_allclose(part["unique_dimensions"], [.5])
    np.testing.assert_allclose(part["unique_category_shape"], [.5])
    np.testing.assert_allclose(part["shared"], [0.])
    # Native residual-y partial correlations would instead give 1, 1, -1.
    negative = ev.variance_partition(np.array([.2]), np.array([.3]), np.array([.9]))
    np.testing.assert_allclose(negative["shared"], [-.4])
    np.testing.assert_allclose(sum(negative[k] for k in ["unique_dimensions", "unique_category_shape", "shared"]), negative["total"])


def test_outer_test_response_perturbation_cannot_change_its_prediction_or_alpha():
    bundle, roster = fixture_bundle()
    data = ev.validate_bundle(bundle, roster)
    x, y, groups = data["dimensions"], data["participants"]["01"]["y"], data["groups"]
    original, audit = ev.nested_predict(x, y, groups)
    _, test = ev.grouped_folds(groups, ev.OUTER_FOLDS)[0]
    changed = y.copy()
    changed[test] += 100000
    new, new_audit = ev.nested_predict(x, changed, groups)
    np.testing.assert_allclose(original[test], new[test], atol=0, rtol=0)
    assert audit[0]["selected_alpha_per_voxel"] == new_audit[0]["selected_alpha_per_voxel"]
    for fold in audit:
        outer_test = set(fold["test_indices"])
        for inner in fold["inner_folds"]:
            assert not outer_test & set(inner["train_indices"] + inner["validation_indices"])


def test_trial_average_and_complete_roster_checks():
    bundle, roster = fixture_bundle()
    data = ev.validate_bundle(bundle, roster)
    expected = 2 * bundle["dimensions"][:, 0] - bundle["dimensions"][:, 1] + bundle["category"][:, 0] + 1
    np.testing.assert_allclose(data["participants"]["01"]["y"][:, 0], expected)
    assert data["participants"]["01"]["trial_counts"][0] == 2
    broken = copy.deepcopy(bundle)
    broken["sub_01_stimulus_id"][0] = bundle["stimulus_id"][1]
    with pytest.raises(ValueError, match="identity mismatch"):
        ev.validate_bundle(broken, roster)
    broken = copy.deepcopy(roster)
    del broken["participants"]["03"]
    with pytest.raises(ValueError, match="exactly participants"):
        ev.validate_bundle(bundle, broken)
    broken = copy.deepcopy(bundle)
    broken["dimensions"] = np.zeros((20, 65))
    with pytest.raises(ValueError, match="wrong shape"):
        ev.validate_bundle(broken, roster)
    broken = copy.deepcopy(bundle)
    broken["sub_02_response"][2, 0] = np.nan
    with pytest.raises(ValueError, match="nonfinite"):
        ev.validate_bundle(broken, roster)


def test_cli_all_three_participants_six_matched_baselines_and_holds(tmp_path):
    bundle, roster = fixture_bundle()
    input_file, roster_file, output_file = tmp_path / "input.npz", tmp_path / "roster.json", tmp_path / "output.json"
    np.savez(input_file, **bundle)
    roster_file.write_text(json.dumps(roster))
    subprocess.run([sys.executable, str(MODULE), "--input", str(input_file), "--roster", str(roster_file), "--output", str(output_file)], check=True)
    result = json.loads(output_file.read_text())
    assert set(result["participants"]) == {"01", "02", "03"}
    assert result["scientific_qualified"] is result["native_reproduction"] is result["full_contract_complete"] is False
    assert result["feature_counts"]["dimensions66"] == 66
    for subject in result["participants"].values():
        assert subject["input_trials"] == 21
        assert subject["image_count"] == 20
        assert set(subject["scores"]) == {"dimensions66", "category", "shape", "category_shape", "combined", "train_mean"}
        assert all(len(prediction) == 20 for prediction in subject["out_of_fold_predictions"].values())
        assert len(subject["fold_audit"]["combined"]) == 5
    assert len(result["input_sha256"]) == len(result["roster_sha256"]) == 64


def test_npz_pickle_is_not_accepted(tmp_path):
    input_file = tmp_path / "objects.npz"
    np.savez(input_file, stimulus_id=np.array([{"not": "a string"}], dtype=object))
    with np.load(input_file, allow_pickle=False) as archive:
        with pytest.raises(ValueError, match="Object arrays"):
            archive["stimulus_id"]
