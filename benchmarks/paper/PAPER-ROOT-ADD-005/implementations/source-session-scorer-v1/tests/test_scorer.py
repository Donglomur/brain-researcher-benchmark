"""Generated engineering controls only: no empirical arrays or author inference."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

MODULE = Path(__file__).resolve().parents[1] / "scorer.py"
spec = importlib.util.spec_from_file_location("source_session_scorer", MODULE)
scorer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scorer)


def fixture():
    sessions = np.repeat([f"ses-{i:02}" for i in range(1, 13)], 4)
    trials = np.array([f"trial-{i:02}" for i in range(48)])
    stimuli = np.tile(["img-A", "img-B", "img-C", "img-D"], 12)
    voxels = np.array(["v-A", "v-B"])
    y = np.tile([-3.0, -1.0, 1.0, 3.0], 12)
    roster = {"task_id": scorer.TASK_ID, "schema_version": scorer.POLICY, "participants": {}}
    reference, author, candidate = {}, {}, {}
    for sub in scorer.PARTICIPANTS:
        roster["participants"][sub] = {"trial_ids": trials.tolist(), "stimulus_ids": stimuli.tolist(),
            "session_ids": sessions.tolist(), "voxel_ids": voxels.tolist()}
        prefix = f"sub_{sub}_"
        reference.update({prefix + "trial_id": trials.copy(), prefix + "stimulus_id": stimuli.copy(),
                          prefix + "session_id": sessions.copy(), prefix + "voxel_id": voxels.copy(),
                          prefix + "response": np.column_stack((y, -y))})
        for bundle in (author, candidate):
            bundle.update({prefix + "trial_id": trials.copy(), prefix + "voxel_id": voxels.copy(),
                           prefix + "heldout_session_id": sessions.copy(),
                           prefix + "prediction": np.column_stack((y, -y))})
    return roster, reference, author, candidate


def test_signed_mean_fold_metric_is_not_pooled_or_squared():
    sessions = np.repeat([f"session-{i}" for i in range(12)], 4)
    residual = np.tile([-3., -1., 1., 3.], 12)
    offset = np.repeat(np.arange(12) * 100, 4)
    y = (residual + offset)[:, None]
    # Every within-session author correlation is +1, but pooled r is negative.
    author = (2 * residual - offset)[:, None]
    candidate = ((residual * np.repeat([1.] * 3 + [-1.] * 9, 4)) + offset)[:, None]
    result = scorer.score_maps(y, author, candidate, sessions)
    assert np.corrcoef(y[:, 0], author[:, 0])[0, 1] < -0.9
    assert result["author_mean_fold_pearson_r"] == pytest.approx([1])
    assert result["candidate_mean_fold_pearson_r"] == pytest.approx([-0.5])
    assert result["paired_mean_fold_delta_r"] == pytest.approx([-1.5])
    assert np.mean(np.array(result["candidate_fold_pearson_r"]) ** 2) == pytest.approx(1)


def test_kfold_unequal_sizes_keep_equal_fold_weight():
    # 49 rows: author KFold has 5 rows first, then 4 in each remaining fold.
    sessions = np.concatenate([np.repeat(f"s{i}", 5 if i == 0 else 4) for i in range(12)])
    y = np.concatenate([np.arange(5 if i == 0 else 4, dtype=float) for i in range(12)])[:, None]
    candidate = y.copy()
    candidate[:5] *= -1
    result = scorer.score_maps(y, y, candidate, sessions)
    assert result["candidate_mean_fold_pearson_r"] == pytest.approx([10 / 12])
    assert result["candidate_mean_fold_pearson_r"] != pytest.approx([39 / 49])


@pytest.mark.parametrize("mutation", ["mixed", "wrong_sizes", "eleven", "short"])
def test_session_equivalence_is_checked_in_original_order(mutation):
    sessions = np.repeat([f"s{i}" for i in range(12)], 4)
    if mutation == "mixed":
        sessions[[3, 4]] = sessions[[4, 3]]
    elif mutation == "wrong_sizes":
        sessions[4] = sessions[0]
    elif mutation == "eleven":
        sessions[sessions == "s11"] = "s10"
    else:
        sessions = np.array([f"s{i}" for i in range(12)])
    with pytest.raises(ValueError):
        scorer.source_folds(sessions)


def test_all_participants_repetitions_and_independent_axis_reordering():
    roster, reference, author, candidate = fixture()
    baseline = scorer.evaluate(roster, reference, author, candidate)
    rows = np.roll(np.arange(48)[::-1], 7)
    columns = np.array([1, 0])
    for bundle, is_reference in ((reference, True), (author, False), (candidate, False)):
        for sub in scorer.PARTICIPANTS:
            prefix = f"sub_{sub}_"
            for field in (("trial_id", "stimulus_id", "session_id") if is_reference else
                          ("trial_id", "heldout_session_id")):
                bundle[prefix + field] = bundle[prefix + field][rows]
            bundle[prefix + "voxel_id"] = bundle[prefix + "voxel_id"][columns]
            data = prefix + ("response" if is_reference else "prediction")
            bundle[data] = bundle[data][np.ix_(rows, columns)]
        rows = np.roll(rows, 3)
    result = scorer.evaluate(roster, reference, author, candidate)
    assert result == baseline
    assert set(result["participants"]) == {"01", "02", "03"}
    for record in result["participants"].values():
        assert record["trial_count"] == 48  # repeated images were not averaged
        assert record["unique_stimulus_count"] == 4
        assert record["voxel_count"] == 2
        assert record["paired_mean_fold_delta_r"] == pytest.approx([0, 0])
    assert result["paper_win"] is None


@pytest.mark.parametrize("mutation", ["missing_participant", "duplicate_trial", "unknown_voxel",
    "wrong_session", "wrong_stimulus", "nonfinite", "extra_key", "wrong_shape"])
def test_incomplete_or_misaligned_evidence_is_rejected(mutation):
    roster, reference, author, candidate = fixture()
    if mutation == "missing_participant":
        del roster["participants"]["03"]
    elif mutation == "duplicate_trial":
        candidate["sub_01_trial_id"][0] = candidate["sub_01_trial_id"][1]
    elif mutation == "unknown_voxel":
        candidate["sub_01_voxel_id"][0] = "v-X"
    elif mutation == "wrong_session":
        candidate["sub_01_heldout_session_id"][0] = "ses-02"
    elif mutation == "wrong_stimulus":
        reference["sub_01_stimulus_id"][0] = "img-B"
    elif mutation == "nonfinite":
        candidate["sub_03_prediction"][0, 0] = np.nan
    elif mutation == "extra_key":
        candidate["extra_predictions"] = np.ones((48, 1))
    else:
        reference["sub_01_response"] = reference["sub_01_response"][:-1]
    with pytest.raises(ValueError):
        scorer.evaluate(roster, reference, author, candidate)


def test_constant_fold_is_visible_without_silently_dropping_it():
    roster, reference, author, candidate = fixture()
    candidate["sub_01_prediction"][:4, 0] = 2.0
    result = scorer.evaluate(roster, reference, author, candidate)["participants"]["01"]
    assert result["candidate_fold_pearson_r"][0][0] is None
    assert result["candidate_mean_fold_pearson_r"][0] is None
    assert result["paired_mean_fold_delta_r"][0] is None
    assert result["candidate_defined_folds_per_voxel"] == [11, 12]


@pytest.mark.parametrize("scale", [1e250, 1e-250])
def test_pearson_is_scale_safe(scale):
    values = np.array([-3., -1., 1., 3.])[:, None] * scale
    assert scorer.pearson_columns(values, 2 * values) == pytest.approx([1])
    assert scorer.pearson_columns(values, -values) == pytest.approx([-1])


def test_cli_hashes_evidence_and_preserves_existing_outputs(tmp_path):
    roster, reference, author, candidate = fixture()
    roster_path = tmp_path / "roster.json"
    roster_path.write_text(json.dumps(roster))
    paths = {"roster": roster_path}
    for name, data in (("reference", reference), ("author", author), ("candidate", candidate)):
        paths[name] = tmp_path / f"{name}.npz"
        np.savez(paths[name], **data)
    output = tmp_path / "scores.json"
    command = [sys.executable, "-B", str(MODULE)]
    for name, path in paths.items():
        command.extend(["--" + name, str(path)])
    command.extend(["--output", str(output)])
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    result = json.loads(output.read_text())
    assert result["input_sha256"] == {key: scorer.digest(path) for key, path in paths.items()}
    original = output.read_bytes()
    rerun = subprocess.run(command, capture_output=True, text=True)
    assert rerun.returncode != 0
    assert output.read_bytes() == original


def test_pickle_arrays_rejected(tmp_path):
    path = tmp_path / "object.npz"
    np.savez(path, object_values=np.array([{"unsafe": "payload"}], dtype=object))
    with pytest.raises(ValueError, match="Object arrays"):
        scorer.load_npz(path)


def test_duplicate_roster_keys_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"participants": {}, "participants": {"01": {}}}')
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        scorer.load_roster(path)
