"""Small mechanical fixtures only; these are not a scientific reference bank."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("allenosi_compute_mechanics", Path(__file__).parents[1] / "solution/compute.py")
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)


def table():
    n = 16
    start = 10 + np.arange(n, dtype=float) * 4
    return {"id": 100 + np.arange(n) * 3, "start_time": start,
            "stop_time": start + np.tile([1.0, 2.0], 8),
            "orientation": np.repeat(np.arange(0, 360, 45, dtype=float), 2),
            "temporal_frequency": np.tile([1.0, 2.0], 8)}


def test_half_open_boundary_and_duplicate_timestamps():
    train = np.array([0.5, 1, 1, 1.5, 2, 2, 3])
    np.testing.assert_array_equal(c.count_spikes([train], [1, 2], [2, 3]), [[3, 2]])
    np.testing.assert_array_equal(c.count_spikes([train], [0.5], [1]), [[1]])


@pytest.mark.parametrize("train", [[2, 1], [0, np.nan], [np.inf]])
def test_counting_never_sorts_or_drops_invalid_spikes(train):
    with pytest.raises(ValueError):
        c.count_spikes([train], [0], [3])


@pytest.mark.parametrize("starts,stops", [([0], [0]), ([1], [0]), ([np.nan], [1]), ([0], [np.inf])])
def test_invalid_windows_fail(starts, stops):
    with pytest.raises(ValueError):
        c.count_spikes([[]], starts, stops)


def test_empty_train_retained():
    np.testing.assert_array_equal(c.count_spikes([[]], [0, 4], [1, 5]), [[0, 0]])


def test_source_support_retains_original_ids():
    raw = table()
    p = c.presentation_support(raw)
    np.testing.assert_array_equal(p["presentation_id"], raw["id"])
    np.testing.assert_array_equal(p["condition_n_presentations"], np.ones((8, 2)))
    np.testing.assert_array_equal(p["duration_seconds"], np.tile([1.0, 2.0], 8))


def test_blank_orientation_is_only_trial_exclusion():
    raw = table()
    raw = {key: np.append(value, {"id": 999, "start_time": 80, "stop_time": 81,
                                "orientation": np.nan, "temporal_frequency": np.nan}[key])
           for key, value in raw.items()}
    p = c.presentation_support(raw)
    assert p["n_original_presentations"] == 17
    assert p["n_blank_presentations"] == 1
    assert len(p["presentation_id"]) == 16


@pytest.mark.parametrize("change", ["missing_cell", "wrong_direction", "missing_tf", "zero_tf", "duplicate_id", "fractional_id", "unordered", "zero_duration"])
def test_malformed_support_fails_closed(change):
    raw = table()
    if change == "missing_cell":
        raw = {key: value[1:] for key, value in raw.items()}
    elif change == "wrong_direction":
        raw["orientation"][0] = 22.5
    elif change == "missing_tf":
        raw["temporal_frequency"][0] = np.nan
    elif change == "zero_tf":
        raw["temporal_frequency"][0] = 0
    elif change == "duplicate_id":
        raw["id"][1] = raw["id"][0]
    elif change == "fractional_id":
        raw["id"] = raw["id"].astype(float)
        raw["id"][0] += 0.5
    elif change == "unordered":
        raw = {key: value[::-1] for key, value in raw.items()}
    elif change == "zero_duration":
        raw["stop_time"][0] = raw["start_time"][0]
    with pytest.raises(ValueError):
        c.presentation_support(raw)


@pytest.mark.parametrize("token", ["null", b"NaN", "none", "", None, np.nan])
def test_explicit_missing_tokens(token):
    assert np.isnan(c.source_number(token))


@pytest.mark.parametrize("token", ["broken", "inf", -np.inf])
def test_malformed_tokens_not_silently_missing(token):
    with pytest.raises(ValueError):
        c.source_number(token)


def test_rate_is_actual_duration_and_condition_is_mean_of_rates():
    raw = table()
    raw = {key: np.append(value, {"id": 999, "start_time": 80, "stop_time": 84,
                                "orientation": 0, "temporal_frequency": 1}[key])
           for key, value in raw.items()}
    p = c.presentation_support(raw)
    counts = np.full((1, 17), 4)
    rates, means = c.condition_means(counts, p)
    assert rates[0, 0] == 4
    assert rates[0, 1] == 2
    assert means[0, 0, 0] == 2.5  # (4/1 + 4/4)/2, not 8/5.


def test_tf_uses_peak_direction_not_mean_over_directions():
    means = np.full((1, 8, 2), 5.0)
    means[:, :, 1] = 1
    means[:, 2, 1] = 10
    result = c.two_point_osi(means, [1, 2])
    assert result["preferred_temporal_frequency"].item() == 2
    assert result["preferred_orientation"].item() == 90


def test_tf_and_orientation_ties_choose_lowest_levels():
    result = c.two_point_osi(np.ones((1, 8, 3)), [1, 2, 8])
    assert result["preferred_temporal_frequency"].item() == 1
    assert result["preferred_orientation"].item() == 0
    assert result["osi"].item() == 0
    assert result["osi_defined"].item()


def test_fold_opposite_directions_equally_and_orthogonal_mod180():
    means = np.array([0, 2, 0, 10, 0, 6, 0, 14], dtype=float)[None, :, None]
    result = c.two_point_osi(means, [1])
    assert result["preferred_orientation"].item() == 135
    assert result["r_pref_hz"].item() == 12
    assert result["r_orth_hz"].item() == 4
    assert result["osi"].item() == 0.5
    assert not result["selective"].item()  # strict boundary


def test_zero_response_convention_is_explicit_not_an_exclusion():
    result = c.two_point_osi(np.zeros((2, 8, 1)), [1])
    np.testing.assert_array_equal(result["osi"], [0, 0])
    assert not np.any(result["osi_defined"])
    assert not np.any(result["selective"])
    assert len(result["osi"]) == 2


def test_tiny_positive_rate_not_zeroed_by_epsilon():
    means = np.zeros((1, 8, 1))
    means[0, [0, 4], 0] = 1e-20
    result = c.two_point_osi(means, [1])
    assert result["osi"].item() == 1.0
    assert result["osi_defined"].item()


def test_qc_strict_thresholds_and_missing_metrics():
    source = {"isi_violations": np.array([0.1, 0.5, 0.1, 0.1, np.nan]),
              "amplitude_cutoff": np.array([0.01, 0.01, 0.1, 0.01, 0.01]),
              "presence_ratio": np.array([0.99, 0.99, 0.99, 0.9, 0.99])}
    qc = c.qc_sensitivity(source, np.zeros((5, 8)), np.full(5, 3.0))
    np.testing.assert_array_equal(qc["qc_pass"], [True, False, False, False, False])
    np.testing.assert_array_equal(qc["qc_metrics_complete"], [True, True, True, True, False])


def test_responsiveness_strict_rate_and_drive():
    source = {"isi_violations": np.zeros(3), "amplitude_cutoff": np.zeros(3), "presence_ratio": np.ones(3)}
    qc = c.qc_sensitivity(source, np.ones((3, 8)), np.array([2, 3, 3.000001]))
    np.testing.assert_array_equal(qc["responsive"], [False, False, True])


def test_negative_or_fractional_counts_fail():
    p = c.presentation_support(table())
    for value in [-1, 0.5, np.nan]:
        counts = np.ones((1, 16))
        counts[0, 0] = value
        with pytest.raises(ValueError):
            c.condition_means(counts, p)
