"""Manufactured source/accepted vectors only; no original files or imports."""
import copy

import numpy as np
import pytest

import measurement_kernel as mk
import wave_contract as wc

TIMES = np.arange(13, dtype=float)
OPTIONS = dict(baseline_window_ms=(0, 0), amplitude_window_ms=(3, 9), onset_window_ms=(3, 9))


def source_pair():
    return {"face": np.asarray([0, 0, 0, 0, -3, -8, -3, 0, 0, 0, 0, 0, 0], float),
            "car": np.zeros(13)}


def replay(accepted, source):
    return wc.replay_conditions(TIMES, accepted, source, **OPTIONS)


def test_identical_conditions_replay_exactly_the_private_kernel():
    source = source_pair()
    result = replay(copy.deepcopy(source), source)
    assert result["measurement"] == mk.measure_waveform(TIMES, source["face"]-source["car"], **OPTIONS)
    assert result["source_support"]["status"] == "resolved"
    assert all(row["max_abs_error_uv"] == 0 for row in result["fidelity"].values())


@pytest.mark.parametrize("magnitude", [0.0, 0.1, 1.0, 1e8, 1e308])
def test_budget_is_exact_declared_fixed_unit_expression(magnitude):
    expected = 1e-8*magnitude + 64*np.finfo(float).eps*max(1.0, magnitude)
    assert wc.waveform_budget([magnitude, -magnitude]) == expected


def test_zero_reference_supnorm_equality_passes_and_next_float_fails():
    bound = 64*wc.EPS64
    assert wc.check_supnorm([bound], [0.0])["max_abs_error_uv"] == bound
    with pytest.raises(wc.WaveContractError, match="fidelity"):
        wc.check_supnorm([np.nextafter(bound, np.inf)], [0.0])


@pytest.mark.parametrize("which", ["face", "car"])
def test_each_condition_is_bound_even_when_difference_is_unchanged(which):
    source = source_pair()
    accepted = copy.deepcopy(source)
    accepted["face"] += 1.0
    accepted["car"] += 1.0
    # Test order-independent isolated checks too: cancellation cannot hide error.
    with pytest.raises(wc.WaveContractError, match="fidelity"):
        wc.check_supnorm(accepted[which], source[which])
    with pytest.raises(wc.WaveContractError, match="fidelity"):
        replay(accepted, source)


def test_large_common_erp_cannot_erase_a_weak_difference():
    common = np.ones(13)*1e6
    effect = source_pair()["face"]*1e-4
    source = {"face": common+effect, "car": common.copy()}
    accepted = {"face": common.copy(), "car": common.copy()}
    # Both condition gates pass; only the required rebased-difference gate fails.
    wc.check_supnorm(accepted["face"], source["face"])
    wc.check_supnorm(accepted["car"], source["car"])
    with pytest.raises(wc.WaveContractError, match="rebased difference.*fidelity"):
        replay(accepted, source)


def test_exact_flat_difference_with_admissible_tiny_jitter_keeps_signed_amplitude():
    source = {"face": np.ones(13), "car": np.ones(13)}
    accepted = copy.deepcopy(source)
    accepted["face"][5] += 2.0**-50
    result = replay(accepted, source)
    assert result["source_support"]["status"] == "numerical_zero_difference"
    assert result["measurement"]["onset_status"] == "numerical_zero_difference"
    assert result["measurement"]["onset_ms"] is None
    assert result["measurement"]["amplitude_uv"] > 0.0
    assert result["measurement"]["peak_uv"] is None


@pytest.mark.parametrize("factor,supported", [(0.0, False), (0.5, False), (1.0, False), (2.0, True)])
def test_canonical_numerical_zero_threshold_is_inclusive(factor, supported):
    source = {"face": np.zeros(13), "car": np.zeros(13)}
    source["face"][5] = -factor*64*wc.EPS64
    result = replay(copy.deepcopy(source), source)
    assert result["source_support"]["onset_supported"] is supported
    assert result["source_support"]["numerical_zero_limit_uv"] == 64*wc.EPS64
    assert result["measurement"]["onset_status"] == ("ok" if supported else "numerical_zero_difference")


def test_resolution_uses_original_condition_magnitude_not_difference_magnitude():
    common = np.ones(13)*1e8
    source = {"face": common.copy(), "car": common.copy()}
    source["face"][5] -= 1e-7
    result = replay(copy.deepcopy(source), source)
    assert result["source_support"]["numerical_zero_limit_uv"] == 64*wc.EPS64*1e8
    assert result["source_support"]["status"] == "numerical_zero_difference"
    assert result["measurement"]["amplitude_uv"] < 0


def test_underflowing_half_height_is_never_attempted_for_canonical_zero_support():
    source = {"face": np.zeros(13), "car": np.zeros(13)}
    source["face"][5] = -np.nextafter(0.0, 1.0)
    result = replay(copy.deepcopy(source), source)
    assert result["measurement"]["onset_status"] == "numerical_zero_difference"
    assert result["measurement"]["amplitude_status"] == "ok"


@pytest.mark.parametrize("missing", [("face",), ("car",), ("face", "car")])
def test_canonical_missing_masks_translate_to_none_not_zero_measurements(missing):
    source = source_pair()
    for name in missing: source[name] = None
    result = replay(copy.deepcopy(source), source)
    assert result["source_support"]["status"] == "missing_condition"
    assert result["measurement"]["amplitude_uv"] is result["measurement"]["onset_ms"] is None
    assert result["fidelity"]["rebased_difference"] is None
    for name in missing: assert result["fidelity"][name] is None


@pytest.mark.parametrize("kind", ["false_missing", "reactivated", "present_invalid"])
def test_missing_condition_does_not_allow_manufactured_or_unchecked_present_wave(kind):
    source = source_pair(); accepted = copy.deepcopy(source)
    if kind == "false_missing": accepted["face"] = None
    elif kind == "reactivated": source["face"] = None
    else:
        source["face"] = accepted["face"] = None
        accepted["car"][:] = 1.0
    with pytest.raises(ValueError):
        replay(accepted, source)


def test_coherent_near_peak_perturbation_can_change_onset_without_source_endpoint_gate():
    source = {"face": np.asarray([0, 0, 0, 0, -8, 0, 0, 0, -8, 0, 0, 0, 0], float),
              "car": np.zeros(13)}
    accepted = copy.deepcopy(source)
    accepted["face"][8] -= 1e-8
    original = replay(copy.deepcopy(source), source)
    changed = replay(accepted, source)
    assert original["measurement"]["peak_index"] == 4
    assert changed["measurement"]["peak_index"] == 8
    assert original["measurement"]["onset_ms"] == 3
    assert changed["measurement"]["onset_ms"] == 7
    assert changed["measurement"] == mk.measure_waveform(TIMES, accepted["face"]-accepted["car"], **OPTIONS)


def test_coherent_accepted_values_not_canonical_scalars_feed_complete_groups():
    source = source_pair(); accepted = copy.deepcopy(source)
    accepted["face"] *= 1.0+2e-9
    result = replay(accepted, source)["measurement"]
    canonical = replay(copy.deepcopy(source), source)["measurement"]
    assert result["amplitude_uv"] != canonical["amplitude_uv"]
    group = mk.aggregate_complete([result["amplitude_uv"]]*37)
    assert group["mean"] == result["amplitude_uv"] and group["interval_kind"] == "constant_point"


def test_rebaseline_expression_is_applied_once_to_the_accepted_measurement():
    source = source_pair()
    source["face"] += 2.0
    result = replay(copy.deepcopy(source), source)["measurement"]
    assert result["measurement_baseline_uv"] == 2.0
    assert result["amplitude_uv"] == np.mean((source["face"]-2.0)[3:10])
    assert result == mk.measure_waveform(TIMES, source["face"]-source["car"], **OPTIONS)


def test_nonnegative_resolved_wave_has_own_null_not_a_forced_finite_onset():
    source = source_pair(); source["face"] *= -1
    result = replay(copy.deepcopy(source), source)
    assert result["source_support"]["status"] == "resolved"
    assert result["measurement"]["onset_status"] == "no_negative_peak"
    assert result["measurement"]["amplitude_uv"] > 0


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int64])
def test_exactly_representable_storage_and_readonly_vectors_are_valid(dtype):
    source = source_pair()
    accepted = {k: v.astype(dtype) for k, v in source.items()}
    for value in accepted.values(): value.flags.writeable = False
    before = copy.deepcopy(source)
    replay(accepted, source)
    assert all(np.array_equal(source[k], before[k]) for k in source)


def test_float32_is_not_unconditionally_accepted_when_precision_is_insufficient():
    source = {"face": np.ones(13)*0.1, "car": np.zeros(13)}
    accepted = {k: v.astype(np.float32) for k, v in source.items()}
    with pytest.raises(wc.WaveContractError, match="fidelity"):
        replay(accepted, source)


@pytest.mark.parametrize("kind", ["missing_key", "extra_key", "alias", "nondict"])
@pytest.mark.parametrize("which", ["source", "accepted"])
def test_condition_mapping_membership_is_exact(kind, which):
    source = source_pair(); accepted = copy.deepcopy(source)
    target = source if which == "source" else accepted
    if kind == "missing_key": del target["face"]
    elif kind == "extra_key": target["other"] = np.zeros(13)
    elif kind == "alias": target["Face"] = target.pop("face")
    elif which == "source": source = list(source.values())
    else: accepted = list(accepted.values())
    with pytest.raises(wc.WaveContractError, match="condition keys"):
        replay(accepted, source)


@pytest.mark.parametrize("bad", [np.zeros(12), np.zeros((13, 1)), np.ones(13, bool),
    [0.0]*12+[True], np.ones(13, complex), np.ones(13, object),
    [0.0]*12+[np.nan], [0.0]*12+[np.inf], ["0"]*13])
@pytest.mark.parametrize("which", ["source", "accepted"])
def test_malformed_scientific_arrays_fail_closed(bad, which):
    source = source_pair(); accepted = copy.deepcopy(source)
    (source if which == "source" else accepted)["face"] = bad
    with pytest.raises(ValueError):
        replay(accepted, source)


def test_nonrepresentable_subtraction_fails_instead_of_creating_a_null():
    source = {"face": np.ones(13)*1e308, "car": np.ones(13)*-1e308}
    with pytest.raises(wc.WaveContractError, match="overflow"):
        replay(copy.deepcopy(source), source)


def test_source_support_cannot_be_overridden_by_a_caller_flag():
    source = source_pair()
    with pytest.raises(TypeError):
        wc.replay_conditions(TIMES, source, source, onset_supported=False, **OPTIONS)


def test_missingness_does_not_bypass_grid_validation():
    source = {"face": None, "car": None}
    with pytest.raises(mk.MeasurementError, match="increasing"):
        wc.replay_conditions(TIMES[::-1], source, source, **OPTIONS)
