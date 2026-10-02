"""Manufactured-only fixtures. No original data, helper or runtime accesses."""

import numpy as np
import pytest
from scipy.stats import t as student_t

import measurement_kernel as mk


def measured(search, *, left=(0.0, 0.0, 0.0), right=(0.0, 0.0, 0.0)):
    wave = np.asarray([*left, *search, *right], dtype=np.float64)
    times = np.arange(len(wave), dtype=np.float64)
    window = (3.0, float(len(wave) - 4))
    return mk.measure_waveform(
        times, wave, baseline_window_ms=(0.0, 0.0),
        amplitude_window_ms=window, onset_window_ms=window,
    )


def test_multiple_crossings_select_nearest_preceding_not_earliest():
    result = measured([0, -7, -3, -8, -2, -10, 0])
    assert result["peak_index"] == 8
    assert result["crossing_index"] == 7
    assert result["onset_ms"] == 7.0
    assert result["onset_status"] == "ok"


def test_deepest_local_wins_over_more_negative_nonlocal_plateau():
    result = measured([-10, -10, -10, 0, 0, 0, -6, 0, 0])
    assert result["peak_selection"] == "deepest_local_peak"
    assert result["peak_uv"] == -6.0
    assert result["peak_index"] == 9
    assert result["crossing_index"] == 8


@pytest.mark.parametrize("search,peak_index", [
    ([0, -8, 0, 0, 0, -8, 0], 4),
    ([0, -6, 0, -10, 0, -10, 0], 6),
])
def test_equal_deepest_local_peaks_choose_first_not_median(search, peak_index):
    result = measured(search)
    assert result["peak_selection"] == "deepest_local_peak"
    assert result["peak_index"] == peak_index
    assert result["crossing_index"] == peak_index - 1


def test_no_local_peak_falls_back_to_earliest_global_minimum():
    result = measured([-8, -8, -8, -8])
    assert result["local_peak_indices"] == []
    assert result["peak_selection"] == "in_window_global_minimum"
    assert result["peak_index"] == 3
    assert result["onset_status"] == "no_in_window_half_height_sample"


def test_plateau_minimum_is_not_strict_local_candidate():
    result = measured([0, -4, -4, 0])
    assert result["local_peak_indices"] == []
    assert result["peak_index"] == 4
    assert result["onset_ms"] == 3.0


@pytest.mark.parametrize("remote", [-12.0, -18.0])
def test_immediate_minimum_must_also_be_below_each_side_mean(remote):
    # Candidate at search index3 has immediate neighbors0, but its left mean
    # is exactly -4 or below -4. The strict neighborhood test disqualifies it.
    result = measured([remote, 0, 0, -4, 0, 0, 0, -8, 0])
    assert 6 not in result["local_peak_indices"]
    assert 10 in result["local_peak_indices"]


def test_right_side_mean_is_also_strict():
    result = measured([0, -4, 0, 0, -12, 0, 0])
    assert 4 not in result["local_peak_indices"]


def test_half_height_equality_is_a_valid_sample():
    result = measured([0, -5, -10, -6, 0])
    assert result["half_height_uv"] == -5.0
    assert result["onset_ms"] == 4.0


def test_return_sample_time_not_interpolated_threshold_time():
    result = measured([0, -2, -10, -2, 0])
    assert result["onset_ms"] == 4.0
    assert result["onset_ms"] != 4.375


def test_missing_crossing_does_not_substitute_left_boundary_or_padding():
    result = measured([-6, -8, -10, -8, -6])
    assert result["peak_uv"] == -10.0
    assert result["onset_ms"] is None
    assert result["crossing_index"] is None
    assert result["onset_status"] == "no_in_window_half_height_sample"


def test_genuine_half_height_boundary_sample_is_eligible():
    result = measured([-5, -6, -10, -6, -5])
    assert result["onset_status"] == "ok"
    assert result["onset_ms"] == 3.0


def test_padding_can_qualify_peak_at_window_edge_but_not_supply_onset():
    result = measured([-10, -5, -2, 0])
    assert result["peak_index"] == 3
    assert 3 in result["local_peak_indices"]
    assert result["onset_ms"] is None


@pytest.mark.parametrize("search", [[2, 1, 2, 3, 4], [0, 0, 0, 0], [1, 1, 1, 1]])
def test_nonnegative_selected_peak_has_null_onset_but_signed_amplitude(search):
    result = measured(search)
    assert result["amplitude_uv"] == pytest.approx(np.mean(search))
    assert result["amplitude_status"] == "ok"
    assert result["onset_ms"] is None
    assert result["onset_status"] == "no_negative_peak"


def test_negative_polarity_candidates_are_selected_before_absolute_sign_guard():
    # A negative plateau is not locally strict. A later positive local minimum
    # qualifies geometrically, is selected, then fails the <0 voltage guard.
    result = measured([-10, -10, -10, 3, 3, 3, 1, 3, 3])
    assert result["peak_selection"] == "deepest_local_peak"
    assert result["peak_uv"] == 1.0
    assert result["onset_status"] == "no_negative_peak"


def test_amplitude_keeps_negative_sign_and_is_an_ordinary_sample_mean():
    result = measured([-1, -2, -9, -4, -4])
    assert result["amplitude_uv"] == -4.0
    assert result["amplitude_uv"] != 4.0


def test_irregular_time_grid_does_not_time_weight_amplitude():
    times = np.asarray([-20, -10, 0, 10, 11, 50, 100, 110, 119, 150, 200, 300, 400], float)
    wave = np.asarray([2, 2, 2, 2, 2, 2, 2, 0, -6, 2, 2, 2, 2], float)
    result = mk.measure_waveform(times, wave, baseline_window_ms=(-20, 0))
    assert result["measurement_baseline_uv"] == 2.0
    assert result["amplitude_uv"] == pytest.approx((-2 - 8 + 0) / 3)


def test_windows_and_baseline_choose_first_sample_on_nearest_distance_ties():
    times = np.arange(-4, 22, 2, dtype=float)
    wave = np.asarray([2, 4, 8, 1, -3, -5, -2, 4, 5, 6, 7, 8, 9], float)
    result = mk.measure_waveform(
        times, wave, baseline_window_ms=(-3, -1),
        amplitude_window_ms=(5, 7), onset_window_ms=(3, 9),
    )
    assert result["windows"]["baseline"]["sample_indices"] == [0, 1]
    assert result["windows"]["amplitude"]["sample_indices"] == [4, 5]
    assert result["windows"]["onset"]["sample_indices"] == [3, 6]
    assert result["measurement_baseline_uv"] == 3.0
    assert result["amplitude_uv"] == -7.0


def test_nearest_baseline_snap_can_use_rounded_epoch_first_sample():
    times = np.arange(-199.21875, 500.0, 3.90625)
    wave = np.zeros(len(times))
    result = mk.measure_waveform(times, wave)
    assert result["windows"]["baseline"]["sample_indices"][0] == 0
    assert result["onset_status"] == "no_negative_peak"


def test_measurement_rebaseline_once_matches_direct_corrected_scalar_mean():
    times = np.arange(-200.0, 401.0, 10.0)
    wave = np.linspace(1.0, 3.0, len(times))
    wave[(times >= 110) & (times <= 150)] -= 8.0
    before = wave.copy()
    baseline = np.mean(wave[(times >= -200) & (times <= 0)])
    expected = np.mean((wave - baseline)[(times >= 110) & (times <= 150)])
    result = mk.measure_waveform(times, wave)
    assert result["measurement_baseline_uv"] == baseline
    assert result["amplitude_uv"] == expected
    assert np.array_equal(wave, before)


def test_peak_and_amplitude_use_the_same_measurement_baseline():
    result = measured([10, 7, 4, 7, 10], left=(10, 10, 10), right=(10, 10, 10))
    assert result["measurement_baseline_uv"] == 10.0
    assert result["peak_uv"] == -6.0
    assert result["amplitude_uv"] == -2.4
    assert result["onset_ms"] == 4.0


def test_inputs_are_not_mutated_and_readonly_arrays_work():
    times = np.arange(13, dtype=float)
    wave = np.asarray([0, 0, 0, 0, -3, -8, -3, 0, 0, 0, 0, 0, 0], float)
    times_before, wave_before = times.copy(), wave.copy()
    times.flags.writeable = False
    wave.flags.writeable = False
    mk.measure_waveform(times, wave, baseline_window_ms=(0, 0),
                        amplitude_window_ms=(3, 9), onset_window_ms=(3, 9))
    assert np.array_equal(times, times_before)
    assert np.array_equal(wave, wave_before)


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int32])
def test_safe_real_numeric_storage_is_accepted(dtype):
    times = np.arange(13, dtype=dtype)
    wave = np.zeros(13, dtype=dtype)
    result = mk.measure_waveform(times, wave, baseline_window_ms=(0, 0),
                                 amplitude_window_ms=(3, 9), onset_window_ms=(3, 9))
    assert result["amplitude_uv"] == 0.0


def test_missing_condition_has_typed_nulls_not_zero_measurement():
    result = mk.measure_waveform(np.arange(13), None, baseline_window_ms=(0, 0),
                                 amplitude_window_ms=(3, 9), onset_window_ms=(3, 9))
    assert result["amplitude_uv"] is None and result["onset_ms"] is None
    assert result["amplitude_status"] == result["onset_status"] == "missing_condition"


@pytest.mark.parametrize("window", [(2, 8), (3, 10), (-20, 8), (3, 50)])
@pytest.mark.parametrize("missing", [False, True])
def test_full_three_sample_padding_is_a_precondition(window, missing):
    wave = None if missing else np.zeros(13)
    with pytest.raises(mk.MeasurementError, match="padding"):
        mk.measure_waveform(np.arange(13), wave, baseline_window_ms=(0, 0),
                            amplitude_window_ms=(3, 9), onset_window_ms=window)


@pytest.mark.parametrize("window", [(5, 4), (np.nan, 4), (3, np.inf), (True, 5), (3,), (), np.asarray(3)])
def test_malformed_windows_raise(window):
    with pytest.raises(ValueError):
        mk.measure_waveform(np.arange(13), np.zeros(13), baseline_window_ms=(0, 0),
                            amplitude_window_ms=window, onset_window_ms=(3, 9))


@pytest.mark.parametrize("bad", [
    np.zeros((13, 1)), np.asarray(["0"] * 13), np.zeros(13, complex),
    np.zeros(13, bool), np.zeros(13, object), [0.0] * 12 + [True],
    [0.0] * 12 + [np.nan], [0.0] * 12 + [np.inf], np.zeros(12),
])
def test_invalid_waveforms_fail_closed(bad):
    with pytest.raises(ValueError):
        mk.measure_waveform(np.arange(13), bad, baseline_window_ms=(0, 0),
                            amplitude_window_ms=(3, 9), onset_window_ms=(3, 9))


@pytest.mark.parametrize("times", [
    np.zeros(13), np.arange(13)[::-1], np.zeros((13, 1)),
    np.asarray(list(range(12)) + [np.nan]), [False] + list(range(1, 13)),
])
def test_invalid_time_axes_raise(times):
    with pytest.raises(ValueError):
        mk.measure_waveform(times, np.zeros(13), baseline_window_ms=(0, 0),
                            amplitude_window_ms=(3, 9), onset_window_ms=(3, 9))


def test_nonfinite_baseline_subtraction_is_not_serialized():
    wave = np.zeros(13)
    wave[0] = 1e308
    wave[5] = -1e308
    with pytest.raises(ValueError, match="overflow"):
        mk.measure_waveform(np.arange(13), wave, baseline_window_ms=(0, 0),
                            amplitude_window_ms=(3, 9), onset_window_ms=(3, 9))


def test_baseline_mean_overflow_is_an_error():
    wave = np.ones(13) * 1e308
    with pytest.raises(ValueError, match="mean overflow"):
        mk.measure_waveform(np.arange(13), wave, baseline_window_ms=(0, 2),
                            amplitude_window_ms=(3, 9), onset_window_ms=(3, 9))


def test_nonrepresentable_negative_half_height_is_an_arithmetic_error():
    smallest = np.nextafter(0.0, 1.0)
    with pytest.raises(ValueError, match="half-height underflow"):
        measured([0, -smallest, 0])


def test_complete37_mean_and_t36_interval():
    values = np.linspace(-7.0, 11.0, 37)
    before = values.copy()
    result = mk.aggregate_complete(values)
    mean = np.mean(values)
    sd = np.std(values, ddof=1)
    margin = student_t.ppf(.975, 36) * sd / np.sqrt(37)
    assert result["status"] == "ok" and result["df"] == 36
    assert result["mean"] == pytest.approx(mean)
    assert result["sample_sd"] == pytest.approx(sd)
    assert result["ci95"] == pytest.approx([mean - margin, mean + margin])
    assert np.array_equal(values, before)


@pytest.mark.parametrize("value", [0.0, 0.1, -4.5, 1e308])
def test_exact_constant37_has_point_interval_without_variance_epsilon(value):
    result = mk.aggregate_complete([value] * 37)
    assert result["status"] == "ok"
    assert result["interval_kind"] == "constant_point"
    assert result["ci95"] == [value, value]
    assert result["mean"] == value
    assert result["sample_sd"] == result["standard_error"] == 0.0


def test_small_nonconstant_group_does_not_become_constant_by_variance_floor():
    values = np.asarray([-1.0, 0.0, 1.0]) * 2.0 ** -600
    result = mk.aggregate_complete(values, expected_n=3)
    assert result["interval_kind"] == "student_t"
    assert result["sample_sd"] > 0
    assert result["ci95"][0] < 0 < result["ci95"][1]


@pytest.mark.parametrize("missing", [[0], [3, 20], list(range(37))])
def test_group_missingness_retains_all37_and_nulls_estimate(missing):
    values = [-3.0] * 37
    for index in missing:
        values[index] = None
    result = mk.aggregate_complete(values)
    assert result["status"] == "incomplete_support"
    assert result["n_expected"] == 37 and result["n_defined"] == 37 - len(missing)
    assert result["missing_indices"] == missing
    assert result["mean"] is result["ci95"] is result["df"] is None


def test_endpoint_groups_can_have_different_missingness():
    amplitudes = [-2.0] * 37
    onsets = [80.0] * 36 + [None]
    assert mk.aggregate_complete(amplitudes)["mean"] == -2.0
    assert mk.aggregate_complete(onsets)["mean"] is None


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf, True, "2", 1j, [2]])
def test_group_invalid_values_are_errors_not_missing(bad):
    with pytest.raises(ValueError):
        mk.aggregate_complete([0.0] * 36 + [bad])


@pytest.mark.parametrize("values", [[0.0] * 36, [0.0] * 38, np.zeros((37, 1))])
def test_group_cannot_silently_drop_or_add_people(values):
    with pytest.raises(ValueError):
        mk.aggregate_complete(values)


@pytest.mark.parametrize("expected", [1, 0, -1, True, 37.0])
def test_invalid_expected_cohort_count_is_rejected(expected):
    with pytest.raises(ValueError):
        mk.aggregate_complete([0.0] * 37, expected_n=expected)


def test_group_interval_overflow_is_an_error():
    with pytest.raises(ValueError):
        mk.aggregate_complete([-1e308, 0.0, 1e308], expected_n=3)


def test_group_mean_overflow_is_an_error():
    with pytest.raises(ValueError, match="mean overflow"):
        mk.aggregate_complete([1e308, 1e308, -1e308], expected_n=3)


@pytest.mark.parametrize("kind", ["constant", "positive", "tiny_half_underflow"])
def test_unsupported_onset_keeps_amplitude_and_bypasses_peak_arithmetic(kind):
    wave = np.ones(13) * 2.0
    if kind == "positive": wave[3:10] += np.arange(7)
    elif kind == "tiny_half_underflow":
        wave[:] = 0.0
        wave[5] = -np.nextafter(0.0, 1.0)
    before = wave.copy()
    result = mk.measure_waveform(np.arange(13), wave, baseline_window_ms=(0, 0),
        amplitude_window_ms=(3, 9), onset_window_ms=(3, 9), onset_supported=False)
    assert result["amplitude_status"] == "ok"
    assert result["amplitude_uv"] == np.mean((wave-wave[0])[3:10])
    assert result["measurement_baseline_uv"] == wave[0]
    assert result["onset_status"] == "numerical_zero_difference"
    for key in ("onset_ms", "peak_selection", "peak_index", "peak_time_ms",
                "peak_uv", "half_height_uv", "crossing_index"):
        assert result[key] is None
    assert result["local_peak_indices"] == [] and result["windows"]["onset"]["n_samples"] == 7
    assert np.array_equal(wave, before)


def test_missing_condition_with_unsupported_onset_remains_missing():
    result = mk.measure_waveform(np.arange(13), None, baseline_window_ms=(0, 0),
        amplitude_window_ms=(3, 9), onset_window_ms=(3, 9), onset_supported=False)
    assert result["amplitude_status"] == result["onset_status"] == "missing_condition"
    assert result["amplitude_uv"] is result["measurement_baseline_uv"] is None


@pytest.mark.parametrize("bad", [None, 0, 1, 0.0, 1.0, "false", [], np.bool_(False)])
def test_onset_support_flag_is_strictly_boolean(bad):
    with pytest.raises(mk.MeasurementError, match="onset_supported"):
        mk.measure_waveform(np.arange(13), np.zeros(13), baseline_window_ms=(0, 0),
            amplitude_window_ms=(3, 9), onset_window_ms=(3, 9), onset_supported=bad)


def test_explicit_supported_onset_matches_unchanged_default():
    wave = np.asarray([0, 0, 0, 0, -3, -8, -3, 0, 0, 0, 0, 0, 0], float)
    options = dict(baseline_window_ms=(0, 0), amplitude_window_ms=(3, 9), onset_window_ms=(3, 9))
    assert mk.measure_waveform(np.arange(13), wave, **options) == mk.measure_waveform(
        np.arange(13), wave, onset_supported=True, **options)
