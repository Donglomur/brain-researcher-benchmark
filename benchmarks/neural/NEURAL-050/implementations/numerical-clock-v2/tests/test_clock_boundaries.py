"""Generated software controls only; no AJILE12 observations or model evidence."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


PACKAGE = Path(__file__).resolve().parents[1]
PREDECESSOR = PACKAGE.parent / "initial-evaluator-v1"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


e = load("neural050_clock_v2", PACKAGE / "evaluator.py")
old = load("neural050_clock_v1", PREDECESSOR / "evaluator.py")
controls = load("neural050_generated_controls", PREDECESSOR / "tests/test_evaluator.py")


def edge_manifest(tmp_path, offset):
    # These tones repeat every second. Every admitted grid-aligned two-second
    # window therefore has identical values even for a non-grid stream start.
    nominal_time = np.arange(4000) / 500
    signal = (2 * np.sin(2 * np.pi * 80 * nominal_time)
              + np.sin(2 * np.pi * 90 * nominal_time)
              + 4 * np.sin(2 * np.pi * 100 * nominal_time))
    pose_time = offset + np.arange(241) / 30
    path = tmp_path / "generated-edge-control.npz"
    np.savez(path, ecog=signal[:, None], ecog_time_s=offset + nominal_time,
             ecog_valid=np.ones(4000, dtype=bool), pose_time_s=pose_time,
             pose_xy=np.column_stack([3 * pose_time, 4 * pose_time]),
             pose_confidence=np.ones(241), pose_valid=np.ones(241, dtype=bool))
    manifest = controls.raw_manifest(tmp_path)
    recording = manifest["recordings"][0]
    recording.update(path=str(path), sha256=e.digest(path),
                     behavior_epochs=[{"start_s": offset, "stop_s": offset + 8,
                                       "state": "Eat"}])
    return manifest, signal[:1000]


def independent_power(samples):
    # For 1000 samples at 500 Hz, 80 Hz is bin 160 and 100 Hz is bin 200.
    # The explicit integer oracle keeps bin 160, excludes bin 200, and includes
    # the Hann taper's in-band sidelobes of both edge tones.
    taper = np.hanning(1000)
    samples = (samples - np.mean(samples)) * taper
    spectrum = np.fft.rfft(samples)
    return float(2 * np.sum(np.abs(spectrum[160:200]) ** 2)
                 / (1000 * np.sum(taper ** 2)))


def test_preserves_predecessor_counterexample(tmp_path):
    manifest, signal = edge_manifest(tmp_path, 1.0)
    wanted = independent_power(signal)
    original = old.prepare(manifest)
    corrected = e.prepare(manifest)
    # v1 accidentally includes the 100 Hz center bin and drops the 80 Hz center.
    assert abs(np.exp(original["rows"][0]["gamma"]) - wanted) > 1
    assert np.exp(corrected["rows"][0]["gamma"]) == pytest.approx(wanted, rel=1e-11)


@pytest.mark.parametrize("offset", [0.0, 1.0, 2.0, 1024.0, 36000.0])
def test_full_preparation_offset_invariant_at_both_band_edges(tmp_path, offset):
    manifest, signal = edge_manifest(tmp_path, offset)
    result = e.prepare(manifest)
    expected = independent_power(signal)
    assert np.exp([r["gamma"] for r in result["rows"]]) == pytest.approx(
        [expected] * len(result["rows"]), rel=1e-10)
    assert [r["movement"] for r in result["rows"]] == pytest.approx(
        [5.0] * len(result["rows"]), rel=1e-10)
    pin = result["source_pins"][0]
    assert pin["gamma_frequency_grid"]["fft_bin_start"] == 160
    assert pin["gamma_frequency_grid"]["fft_bin_stop_exclusive"] == 200
    assert result["feature_preparation_implementation"] == e.IMPLEMENTATION
    assert result["rows"][0]["start_utc_s"] >= 1577836800 + offset


@pytest.mark.parametrize("rate,expected", [(499.9995, (161, 201)),
                                            (500.0005, (160, 200))])
def test_real_frequency_difference_is_not_rounded_to_advertised_rate(rate, expected):
    clock = 36000 + np.arange(4000) / rate
    _, inferred = e.regular_clock(clock, "generated")
    band, metadata = e.gamma_bin_slice(1000, inferred, e.rate_roundoff_bound(clock))
    assert (band.start, band.stop) == expected
    assert metadata["edge_roundoff_snapped"] == [False, False]
    assert inferred == pytest.approx(rate, rel=1e-11)


@pytest.mark.parametrize("rate,n", [(257.25, 514), (513.25, 1026), (1000.0, 2000)])
def test_general_rate_agrees_with_direct_frequency_inequalities(rate, n):
    band, _ = e.gamma_bin_slice(n, rate, 0.0)
    frequencies = np.arange(n // 2 + 1) * rate / n
    expected = np.flatnonzero((frequencies >= 80) & (frequencies < 100))
    assert np.array_equal(np.arange(band.start, band.stop), expected)


def test_invalid_frequency_grids_and_clock_gaps_fail():
    with pytest.raises(ValueError, match="precision"):
        e.gamma_bin_slice(1000, 500.0, 0.01)
    with pytest.raises(ValueError, match="frequency grid"):
        e.gamma_bin_slice(1000, 200.0, 0.0)
    with pytest.raises(ValueError, match="regular"):
        e.regular_clock([0.0, 0.002, 0.006, 0.008], "gap")


@pytest.mark.parametrize("mode", ["population_transfer", "within_patient_days"])
def test_fixed_prediction_estimand_unchanged_and_legacy_not_relabelled(mode):
    packet = controls.packet()
    revised = e.evaluate(packet, mode)
    original = old.evaluate(packet, mode)
    assert revised.pop("evaluation_implementation") == e.IMPLEMENTATION
    assert revised.pop("feature_preparation_implementation") == "unrecorded"
    assert revised == original


def test_cli_writes_a_roundoff_auditable_feature_packet(tmp_path):
    manifest, _ = edge_manifest(tmp_path, 1.0)
    source, output = tmp_path / "raw.json", tmp_path / "features.json"
    source.write_text(json.dumps(manifest))
    assert e.main(["prepare", str(source), str(output)]) == 0
    packet = json.loads(output.read_text())
    assert packet["raw_manifest_sha256"] == e.canonical_digest(manifest)
    assert packet["source_pins"][0]["gamma_frequency_grid"]["rate_estimator"] == "full_clock_endpoint_span"
