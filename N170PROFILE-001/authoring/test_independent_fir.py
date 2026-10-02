"""Manufactured-only prospective FIR qualification; no original sources.

Fixed before execution: atol=rtol=1e-10 for analytic taps and unit-scale
manufactured signals versus public MNE1.12.1 create_filter/filter_data.
Failures must be retained and investigated; these constants are not tunable
from original signals. No fixture reads original data or a historical bank.
"""

import builtins
import importlib.util
from pathlib import Path
import warnings

import numpy as np
import pytest
from scipy.signal import fftconvolve, firwin

import independent_fir as fir


ATOL = 1e-10
RTOL = 1e-10
RATES = (256.0, 250.0, 128.0, 100.0)


def mne_kernel(fs):
    from mne.filter import create_filter
    return create_filter(
        None, fs, 0.1, 30.0, filter_length="auto",
        l_trans_bandwidth="auto", h_trans_bandwidth="auto", method="fir",
        phase="zero", fir_window="hamming", fir_design="firwin", verbose=False,
    )


def mne_filtered(data, fs):
    from mne.filter import filter_data
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        result = filter_data(
            data.copy(), fs, 0.1, 30.0, filter_length="auto",
            l_trans_bandwidth="auto", h_trans_bandwidth="auto", n_jobs=1,
            method="fir", copy=True, phase="zero", fir_window="hamming",
            fir_design="firwin", pad="reflect_limited", verbose=False,
        )
    return result, [str(item.message) for item in captured]


def unit_signals(n):
    impulses = np.zeros((3, n), dtype=np.float64)
    impulses[0, n // 2] = 1.0
    impulses[1, 0] = 1.0
    impulses[2, -1] = 1.0
    return np.ascontiguousarray(np.vstack((
        impulses,
        np.ones(n),
        np.linspace(-1.0, 1.0, n),
        np.where(np.arange(n) % 2, -1.0, 1.0),
        np.random.default_rng(20261002).normal(size=n),
    )), dtype=np.float64)


def assert_close(actual, expected):
    np.testing.assert_allclose(actual, expected, atol=ATOL, rtol=RTOL)


@pytest.mark.parametrize("fs", RATES + (75.0, 64.0))
def test_analytic_taps_match_mne_and_are_finite_odd_symmetric(fs):
    actual = fir.kernel(fs)
    assert actual.ndim == 1
    assert actual.dtype == np.float64
    assert len(actual) % 2 == 1
    assert np.isfinite(actual).all()
    assert_close(actual, mne_kernel(fs))
    assert_close(actual, actual[::-1])
    assert abs(float(np.sum(actual))) <= ATOL


@pytest.mark.parametrize("fs", RATES)
@pytest.mark.parametrize("length_case", ("one", "two", "short", "below", "equal", "above", "long"))
def test_all_signal_shapes_and_edges_match_public_mne(fs, length_case):
    size = len(fir.kernel(fs))
    n = {
        "one": 1, "two": 2, "short": 31, "below": size - 1,
        "equal": size, "above": size + 1, "long": 65536,
    }[length_case]
    data = unit_signals(n)
    original = data.copy()
    actual = fir.filter_segment(data, fs)
    expected, warning_messages = mne_filtered(data, fs)
    assert actual.shape == data.shape
    assert actual.dtype == np.float64
    assert actual.flags.c_contiguous
    assert not np.shares_memory(data, actual)
    np.testing.assert_array_equal(data, original)
    assert_close(actual, expected)
    # All samples are compared above; separately retain explicit edge coverage.
    assert_close(actual[:, :min(11, n)], expected[:, :min(11, n)])
    assert_close(actual[:, -min(11, n):], expected[:, -min(11, n):])
    assert any("longer than the signal" in text for text in warning_messages) == (n < size)


@pytest.mark.parametrize("boundary", ("lower_component", "upper_component"))
@pytest.mark.parametrize("direction", (-1, 0, 1))
def test_rates_adjacent_to_component_rounding_boundaries(boundary, direction):
    # Derived nominal half-integer component lengths; normalized breakpoint
    # arithmetic is intentionally retained, including any floating-point ulp.
    fs = 8449.5 / 33.0 if boundary == "lower_component" else 113.5 * 7.5 / 3.3
    if direction:
        fs = float(np.nextafter(fs, np.inf if direction > 0 else -np.inf))
    assert_close(fir.kernel(fs), mne_kernel(fs))
    data = unit_signals(97)
    expected, _ = mne_filtered(data, fs)
    assert_close(fir.filter_segment(data, fs), expected)


@pytest.mark.parametrize("fs", (64.0, 75.0))
def test_nyquist_limited_upper_transition_signal_conformance(fs):
    data = unit_signals(501)
    expected, _ = mne_filtered(data, fs)
    assert_close(fir.filter_segment(data, fs), expected)


def test_single_sample_is_filtered_not_discarded_or_zeroed():
    fs = 128.0
    taps = fir.kernel(fs)
    data = np.array([[1.0], [-2.0]])
    expected = data * taps[len(taps) // 2]
    assert_close(fir.filter_segment(data, fs), expected)
    assert np.all(expected != 0.0)


def test_explicit_full_convolution_and_limited_reflection_small_signal():
    fs = 100.0
    data = np.array([[1.0, 2.0, 4.0], [-2.0, 3.0, 1.0]])
    taps = fir.kernel(fs)
    padded = np.array([[-2.0, 0.0, 1.0, 2.0, 4.0, 6.0, 7.0],
                       [-5.0, -7.0, -2.0, 3.0, 1.0, -1.0, 4.0]])
    start = 2 + (len(taps) - 1) // 2
    direct = np.vstack([
        np.convolve(row, taps, mode="full")[start:start + 3] for row in padded
    ])
    assert_close(fir.filter_segment(data, fs), direct)


def test_independent_segments_are_not_implicitly_joined():
    fs = 128.0
    first, second = unit_signals(67), unit_signals(109) + 0.25
    actual = np.concatenate((fir.filter_segment(first, fs), fir.filter_segment(second, fs)), axis=1)
    first_mne, _ = mne_filtered(first, fs)
    second_mne, _ = mne_filtered(second, fs)
    assert_close(actual, np.concatenate((first_mne, second_mne), axis=1))
    joined = fir.filter_segment(np.concatenate((first, second), axis=1), fs)
    assert np.max(np.abs(actual - joined)) > 1e-6


def test_wrong_edge_repeat_padding_is_detectably_different():
    fs = 100.0
    data = np.linspace(-1.0, 1.0, 73)[None, :]
    taps = fir.kernel(fs)
    edge = min(len(taps), data.shape[1]) - 1
    wrong_padded = np.pad(data, ((0, 0), (edge, edge)), mode="edge")
    start = edge + (len(taps) - 1) // 2
    wrong = fftconvolve(wrong_padded, taps[None, :], mode="full", axes=-1)[:, start:start + data.shape[1]]
    assert np.max(np.abs(fir.filter_segment(data, fs) - wrong)) > 1e-6


def test_single_full_bandpass_firwin_is_not_this_kernel():
    actual = fir.kernel(256.0)
    wrong = firwin(len(actual), [0.1, 30.0], pass_zero=False, window="hamming", fs=256.0)
    assert np.max(np.abs(actual - wrong)) > 1e-6


@pytest.mark.parametrize("layout", ("fortran", "strided", "readonly", "float32", "integer", "nested_list"))
def test_safe_real_storage_and_noncontiguous_inputs(layout):
    base = unit_signals(129)
    if layout == "fortran":
        data = np.asfortranarray(base)
    elif layout == "strided":
        data = base[:, ::2]
    elif layout == "readonly":
        data = base.copy()
        data.flags.writeable = False
    elif layout == "float32":
        data = base.astype(np.float32)
    elif layout == "integer":
        data = np.arange(258, dtype=np.int16).reshape(2, 129)
    else:
        data = base.tolist()
    canonical = np.asarray(data, dtype=np.float64)
    snapshot = canonical.copy()
    actual = fir.filter_segment(data, 128.0)
    expected, _ = mne_filtered(canonical, 128.0)
    assert_close(actual, expected)
    np.testing.assert_array_equal(np.asarray(data), snapshot)


@pytest.mark.parametrize("fs", [True, np.bool_(False), "256", None, 60.0, 0.0, -1.0,
                                  float("nan"), float("inf"), -float("inf"),
                                  256.0 + 0j, np.array(256.0)])
def test_invalid_sampling_frequency_rejected(fs):
    with pytest.raises(fir.FIRInputError):
        fir.kernel(fs)
    with pytest.raises(fir.FIRInputError):
        fir.filter_segment(np.ones((1, 2)), fs)


@pytest.mark.parametrize("data", [
    [], [1.0, 2.0], np.ones(3), np.ones((1, 2, 3)), np.empty((0, 3)),
    np.empty((2, 0)), np.array([[True, False]]), [[True, 1.0]],
    np.array([[1.0, 2.0]], dtype=object), [["1", "2"]], [[1.0 + 0j]],
    np.ma.array([[1.0, 2.0]], mask=[[False, True]]),
    [[float("nan")]], [[float("inf")]], [[-float("inf")]],
    [[1.0], [1.0, 2.0]],
])
def test_invalid_or_nonfinite_channel_matrices_are_never_masked(data):
    with pytest.raises(fir.FIRInputError):
        fir.filter_segment(data, 128.0)


def test_finite_input_reflection_overflow_fails_not_zero_imputed():
    largest = np.finfo(np.float64).max
    with pytest.raises(fir.FIRInputError, match="nonfinite"):
        fir.filter_segment(np.array([[largest, -largest]]), 128.0)


def test_kernel_return_is_fresh_not_shared_mutable_cache():
    first = fir.kernel(100.0)
    expected = first.copy()
    first[:] = 0.0
    assert_close(fir.kernel(100.0), expected)


def test_independent_route_imports_and_runs_with_all_mne_imports_blocked(monkeypatch):
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "mne" or name.startswith("mne."):
            raise AssertionError("independent FIR attempted to import MNE")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    module_path = Path(fir.__file__).resolve()
    spec = importlib.util.spec_from_file_location("isolated_analytic_fir", module_path)
    independent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(independent)
    taps = independent.kernel(100.0)
    result = independent.filter_segment(np.array([[0.0, 1.0, -1.0]]), 100.0)
    assert taps.dtype == np.float64
    assert result.shape == (1, 3)
    assert np.isfinite(result).all()
