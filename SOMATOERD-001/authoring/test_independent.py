"""Tiny numerical/mechanical fixtures, never a scientific reference bank."""
import copy
import csv
import importlib.util
from pathlib import Path

import mne
import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("independent_somato", Path(__file__).with_name("check_independent.py"))
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


@pytest.mark.parametrize("sfreq", [160.0, 300.3074951171875, 512.0])
@pytest.mark.parametrize("frequency", [15., 21., 30.])
def test_explicit_wavelet_matches_pinned_mne_definition(sfreq, frequency):
    actual = CHECK.explicit_morlet(sfreq, frequency)
    expected = mne.time_frequency.morlet(sfreq, frequency, n_cycles=frequency / 2, zero_mean=True)
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=3e-15)
    assert len(actual) % 2 == 1
    assert np.sum(np.abs(actual) ** 2) == pytest.approx(2., abs=1e-14)
    np.testing.assert_allclose(actual, actual[::-1].conjugate(), atol=0, rtol=0)


@pytest.mark.parametrize("invalid", [(0, 20), (160, 0), (float("nan"), 20), (160, float("inf"))])
def test_wavelet_invalid_parameters(invalid):
    with pytest.raises(ValueError):
        CHECK.explicit_morlet(*invalid)


def test_independent_binary_onsets_preserve_source_clock_and_ignore_initial_high():
    stim = np.array([1, 1, 0, 0, 1, 1, 0, 1, 0], float)
    actual = CHECK.binary_events(stim, 237600)
    np.testing.assert_array_equal(actual, [[237604, 0, 1], [237607, 0, 1]])
    raw = mne.io.RawArray(stim[None], mne.create_info(["STI 014"], 160, ["stim"]),
                         first_samp=237600, verbose=False)
    expected = mne.find_events(raw, stim_channel="STI 014", initial_event=False, verbose=False)
    np.testing.assert_array_equal(actual, expected)


@pytest.mark.parametrize("stim", [[0, 2, 0], [0, .5, 0], [0, float("nan"), 0], [0, 0, 0]])
def test_changed_source_stimulus_fails_closed(stim):
    with pytest.raises(ValueError):
        CHECK.binary_events(stim, 0)


def test_manual_epochs_boundary_and_absolute_identity():
    data = np.arange(2 * 1500).reshape(2, 1500).astype(float)
    events = np.array([[1005, 0, 1], [1500, 0, 1], [1700, 0, 2], [2499, 0, 1]])
    result = CHECK.slice_epochs(data, events, 160, 1000)
    np.testing.assert_array_equal(result["retained_event_indices"], [1])
    np.testing.assert_array_equal(result["selected_epochs"][0], data[:, 260:741])
    assert [row["drop_reason"] for row in result["source_events"]] == ["NO_DATA", "", "non_target_event", "TOO_SHORT"]
    np.testing.assert_array_equal(result["sample_offsets"], np.arange(-240, 241))
    assert result["source_events"][1]["epoch_start_sample"] == 1260


def test_manual_epochs_equal_mne_when_no_source_projection_or_annotations():
    sfreq = 300.3074951171875
    data = np.random.RandomState(9).normal(size=(4, 2200)) * 1e-12
    raw = mne.io.RawArray(data, mne.create_info(CHECK.CHANNELS, sfreq, ["grad"] * 4),
                         first_samp=237600, verbose=False)
    events = np.array([[238100, 0, 1], [238600, 0, 1]])
    own = CHECK.slice_epochs(data, events, sfreq, raw.first_samp)
    expected = mne.Epochs(raw, events, event_id=1, tmin=-1.5, tmax=1.5, baseline=None,
                          preload=True, reject=None, flat=None, verbose=False)
    np.testing.assert_array_equal(own["selected_epochs"], expected.get_data())
    np.testing.assert_array_equal(own["times"], expected.times)


@pytest.mark.parametrize("sfreq", [160., 300.3074951171875])
def test_full_small_trial_numerics_against_mne_fft(sfreq):
    times = np.arange(round(-1.5 * sfreq), round(1.5 * sfreq) + 1) / sfreq
    epochs = np.random.RandomState(42).normal(size=(3, 2, len(times))) * 1e-12
    freqs = np.array([15., 23., 30.])
    actual, direct = CHECK.independent_power(epochs, sfreq, times, freqs)
    expected = mne.time_frequency.tfr_array_morlet(epochs, sfreq, freqs, n_cycles=freqs / 2,
                                                  zero_mean=True, output="power", use_fft=True,
                                                  n_jobs=1, verbose=False)
    np.testing.assert_allclose(actual["mean_power"], expected.mean(axis=0), rtol=5e-12, atol=1e-35)
    baseline = (times >= -1) & (times <= -.25)
    target = (times >= .1) & (times <= .35)
    np.testing.assert_allclose(actual["trial_baseline_power"], expected[..., baseline].mean(axis=-1), rtol=5e-12)
    np.testing.assert_allclose(actual["trial_target_power"], expected[..., target].mean(axis=-1), rtol=5e-12)
    assert len(direct) == 18


def test_normalization_order_is_not_trialwise_or_sensor_pooled():
    times = np.array([-1., -.5, 0., .1, .35, 1.])
    mean = np.array([[[2, 2, 4, 6, 6, 2]], [[10, 10, 10, 10, 10, 10]]], float)
    result = CHECK.normalize(mean, times)
    assert result["beta_erd_percent"] == pytest.approx(100.)
    assert result["beta_erd_percent"] != pytest.approx(100 * ((6 + 10) / (2 + 10) - 1))


@pytest.mark.parametrize("bad", [np.zeros((1, 1, 6)), np.full((1, 1, 6), np.nan), -np.ones((1, 1, 6))])
def test_undefined_or_invalid_power_fails(bad):
    with pytest.raises(ValueError):
        CHECK.normalize(bad, np.array([-1., -.5, 0., .1, .35, 1.]))


def test_source_scaled_tolerance_not_raw_si_absolute_tolerance():
    expected = np.array([[[1e-24, 2e-24]]])
    baseline = np.array([[[1e-24]]])
    CHECK.power_comparison(expected * (1 + 1e-7), expected, baseline, "fixture")
    with pytest.raises(AssertionError):
        CHECK.power_comparison(expected * 2, expected, baseline, "fixture")


@pytest.fixture
def independent_fixture(tmp_path):
    times = np.array([-1., -.5, 0., .1, .35, 1.])
    epochs = np.ones((2, 4, len(times)))
    prepared = dict(selected_epochs=epochs, retained_event_indices=np.array([0, 1]), times=times,
                    source_events=[dict(event_index=i, event_sample=100 + i * 500, event_code=1,
                                        retained=1, drop_reason="", epoch_start_sample=-140 + i * 500,
                                        epoch_end_sample=340 + i * 500) for i in range(2)])
    mean = np.ones((4, 16, len(times))) * 1e-24
    mean[..., 3:5] *= .8
    power = dict(mean_power=mean, **CHECK.normalize(mean, times),
                 trial_baseline_power=np.ones((2, 4, 16)) * 1e-24,
                 trial_target_power=np.ones((2, 4, 16)) * .8e-24)
    metadata = dict(status="ok", task_id="SOMATOERD-001", source_manifest_sha256="fixture",
                    source_fif_sha256="fixture", method_contract_sha256="fixture", sfreq_hz=160,
                    first_samp=0, n_source_samples=1000, n_discovered_events=2, n_trials=2,
                    n_epoch_times=6, source_bads=[], n_source_projectors=0, method_contract={})
    output = tmp_path / "independent"
    result = CHECK.write_positive(output, prepared, power, metadata)
    return output, prepared, power, metadata, result


def test_independent_serializer_and_full_public_comparison(independent_fixture):
    output, prepared, power, metadata, result = independent_fixture
    assert result["beta_erd_percent"] == pytest.approx(-20.)
    CHECK.compare_outputs(output, None, prepared, power, metadata)
    altered = copy.deepcopy(power)
    altered["mean_power"] *= 2
    with pytest.raises(AssertionError):
        CHECK.compare_outputs(output, None, prepared, altered, metadata)
    with pytest.raises(FileExistsError):
        CHECK.write_positive(output, prepared, power, metadata)


@pytest.mark.parametrize("bad_time", ["NaN", "inf", "-inf"])
def test_nonfinite_mean_power_clock_rejected(independent_fixture, bad_time):
    output, prepared, power, metadata, _result = independent_fixture
    path = output / "mean_power.csv"
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    rows[0]["time_s"] = bad_time
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(AssertionError, match="Power time clock mismatch"):
        CHECK.compare_outputs(output, None, prepared, power, metadata)
