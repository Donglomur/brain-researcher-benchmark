"""Tiny synthetic mechanics only: no original MEG source is read here."""
import csv
import importlib.util
import json
from pathlib import Path

import mne
import numpy as np
import pytest

SPEC = importlib.util.spec_from_file_location("somato_compute", Path(__file__).parents[1] / "solution" / "compute.py")
compute = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compute)


def raw_fixture(events=((600, 1), (1500, 1), (2400, 1)), first_samp=12345, sfreq=300.3074951171875):
    names = compute.CHANS + ["MEG 9992", "STI 014"]
    data = np.random.default_rng(31).normal(size=(len(names), 3000)) * 1e-12
    data[-1] = 0
    for sample, code in events:
        data[-1, sample:sample + 3] = code
    info = mne.create_info(names, sfreq, ["grad"] * 5 + ["stim"])
    return mne.io.RawArray(data, info, first_samp=first_samp, verbose="warning")


def test_pinned_contract_and_source_identity():
    root = Path(__file__).parents[1]
    assert compute.sha256(root / "environment/data_manifest.json") == compute.MANIFEST_SHA256
    assert compute.sha256(root / "environment/method_contract.json") == compute.METHOD_SHA256
    assert compute.check_versions() == compute.VERSIONS


def test_source_clock_noninteger_and_absolute_bounds():
    raw = raw_fixture()
    prepared = compute.prepare_raw(raw)
    assert prepared["selected_epochs"].shape == (3, 4, 901)
    assert prepared["sfreq_hz"] == 300.3074951171875
    assert prepared["first_samp"] == 12345
    assert prepared["source_events"][0]["event_sample"] == 12945
    assert prepared["source_events"][0]["epoch_start_sample"] == 12495
    assert prepared["source_events"][0]["epoch_end_sample"] == 13395
    assert prepared["times"][0] != -1.5
    baseline, target = compute.window_masks(prepared["times"])
    assert baseline.sum() == 225 and target.sum() == 75
    assert prepared["times"][target][0] > .1
    assert prepared["times"][target][-1] < .35
    np.testing.assert_array_equal(prepared["selected_epochs"][0], raw.get_data()[:4, 150:1051])


def test_event_ledger_preserves_non_targets_and_boundaries():
    raw = raw_fixture(events=((20, 1), (600, 1), (1500, 2), (2400, 1), (2950, 1)))
    prepared = compute.prepare_raw(raw)
    assert prepared["retained_event_indices"].tolist() == [1, 3]
    ledger = prepared["source_events"]
    assert [row["event_index"] for row in ledger] == list(range(5))
    assert ledger[0]["drop_reason"] == "NO_DATA"
    assert ledger[2]["drop_reason"] == "non_target_event"
    assert ledger[4]["drop_reason"] == "TOO_SHORT"
    assert ledger[1]["retained"] == 1 and ledger[1]["drop_reason"] == ""


def test_source_annotation_rejection_is_retained():
    raw = raw_fixture(first_samp=0)
    raw.set_annotations(mne.Annotations([4.9], [.15], ["BAD_fixture"]))
    prepared = compute.prepare_raw(raw)
    assert prepared["retained_event_indices"].tolist() == [0, 2]
    assert prepared["source_events"][1]["drop_reason"] == "BAD_fixture"


def test_project_full_grad_space_before_selecting_readouts():
    raw = raw_fixture()
    direction = np.array([1., 2., 3., 4., 5.])
    direction /= np.linalg.norm(direction)
    projection = mne.Projection(data=dict(col_names=raw.ch_names[:5], row_names=None,
                                          data=direction[None], nrow=1, ncol=5),
                                desc="synthetic cross-readout SSP", active=False)
    raw.add_proj(projection, verbose="warning")
    prepared = compute.prepare_raw(raw)
    expected_projector = np.eye(5) - np.outer(direction, direction)
    expected = (expected_projector @ raw.get_data()[:5, 150:1051])[:4]
    np.testing.assert_allclose(prepared["grad_projector"], expected_projector, rtol=0, atol=1e-15)
    np.testing.assert_allclose(prepared["selected_epochs"][0], expected, rtol=1e-12, atol=1e-27)
    early_direction = direction[:4] / np.linalg.norm(direction[:4])
    wrong = (np.eye(4) - np.outer(early_direction, early_direction)) @ raw.get_data()[:4, 150:1051]
    assert np.max(np.abs(wrong - expected)) > 1e-13
    assert prepared["n_source_projectors"] == 1
    assert prepared["source_projector_active"] == [False]


def test_pilot_does_not_invent_scientific_exclusions():
    full = compute.prepare_raw(raw_fixture())
    pilot = compute.prepare_raw(raw_fixture(), pilot_trials=1)
    assert pilot["status"] == "resource_pilot"
    assert pilot["retained_event_indices"].tolist() == [0]
    assert pilot["source_retained_event_indices"].tolist() == [0, 1, 2]
    assert pilot["source_events"] == full["source_events"]
    np.testing.assert_array_equal(pilot["selected_epochs"], full["selected_epochs"][:1])


@pytest.mark.parametrize("count", [0, 5, -1, True])
def test_invalid_pilot_count(count):
    with pytest.raises(ValueError, match="pilot"):
        compute.prepare_raw(raw_fixture(), pilot_trials=count)


@pytest.mark.parametrize("bad_kind", ["missing", "bad", "wrong_type", "nonfinite"])
def test_required_readout_preconditions(bad_kind):
    raw = raw_fixture()
    if bad_kind == "missing":
        raw.drop_channels([compute.CHANS[0]])
    elif bad_kind == "bad":
        raw.info["bads"] = [compute.CHANS[0]]
    elif bad_kind == "wrong_type":
        raw.set_channel_types({compute.CHANS[0]: "mag"}, verbose="warning")
    else:
        raw._data[0, 600] = np.nan
    with pytest.raises(ValueError):
        compute.prepare_raw(raw)


def test_unrelated_source_bad_is_recorded_not_used_to_drop_trials():
    raw = raw_fixture()
    raw.info["bads"] = ["MEG 9992"]
    prepared = compute.prepare_raw(raw)
    assert len(prepared["retained_event_indices"]) == 3
    assert prepared["source_bads"] == ["MEG 9992"]
    assert "MEG 9992" in prepared["source_grad_names"]


@pytest.mark.parametrize("events", [(), ((600, 2),)])
def test_no_target_source_event(events):
    with pytest.raises(ValueError, match="No target"):
        compute.prepare_raw(raw_fixture(events=events))


def test_average_power_before_baseline_not_trial_percent_average():
    times = np.array([-1., -.25, .1, .35])
    power = np.array([[[[1., 1., 2., 2.]]], [[[9., 9., 9., 9.]]]])
    result = compute.aggregate_power(power, times)
    assert result["beta_erd_percent"] == pytest.approx(10.)
    assert result["beta_erd_percent"] != pytest.approx(50.)
    np.testing.assert_array_equal(result["trial_baseline_power"].ravel(), [1., 9.])
    np.testing.assert_array_equal(result["trial_target_power"].ravel(), [2., 9.])


def test_normalize_channel_frequency_before_pooling():
    times = np.array([-1., -.25, .1, .35])
    power = np.array([[[[1., 1., 2., 2.]], [[9., 9., 9., 9.]]]])
    result = compute.aggregate_power(power, times)
    assert result["beta_erd_percent"] == pytest.approx(50.)
    assert result["beta_erd_percent"] != pytest.approx(10.)


def test_exact_window_boundaries_are_inclusive():
    times = np.array([-1.1, -1., -.25, -.249, .099, .1, .35, .351])
    baseline, target = compute.window_masks(times)
    assert np.flatnonzero(baseline).tolist() == [1, 2]
    assert np.flatnonzero(target).tolist() == [5, 6]


@pytest.mark.parametrize("value", [0., -1., np.nan, np.inf])
def test_bad_power_fails_without_floor_or_default(value):
    with pytest.raises(ValueError):
        compute.aggregate_power(np.full((2, 4, 16, 4), value), [-1., -.25, .1, .35])


@pytest.mark.parametrize("scale", [.5, 1., 2.])
def test_no_forced_sign_or_magnitude(scale):
    power = np.ones((2, 4, 16, 4))
    power[..., 2:] *= scale
    result = compute.aggregate_power(power, [-1., -.25, .1, .35])
    assert result["beta_erd_percent"] == pytest.approx(100 * (scale - 1))


def test_total_power_retains_opposite_phase_trials():
    sfreq = 300.3074951171875
    _, times = compute.source_times(sfreq)
    signal = np.sin(2 * np.pi * 20 * times)
    selected = np.broadcast_to(np.stack([signal, -signal])[:, None], (2, 4, len(times))).copy()
    result = compute.compute_power(dict(selected_epochs=selected, sfreq_hz=sfreq, times=times))
    assert np.min(result["baseline_power"]) > 0
    assert np.max(result["mean_power"]) > 1
    evoked = selected.mean(axis=0, keepdims=True)
    with pytest.raises(ValueError, match="positive"):
        compute.compute_power(dict(selected_epochs=evoked, sfreq_hz=sfreq, times=times))


def fake_inputs():
    return dict(source_manifest_sha256=compute.MANIFEST_SHA256, source_fif_sha256=compute.FIF_SHA256,
                method_contract_sha256=compute.METHOD_SHA256, source_sha256={"fixture": "synthetic"},
                manifest={"source_scope": "synthetic mechanics fixture"}, contract={"fixture": True})


def test_complete_outputs_private_arrays_and_exclusive_guard(tmp_path):
    prepared = compute.prepare_raw(raw_fixture(), pilot_trials=1)
    power = compute.compute_power(prepared)
    metadata = compute.make_metadata(fake_inputs(), prepared)
    result = compute.make_results(prepared, power)
    output, private = tmp_path / "out", tmp_path / "private"
    compute.ensure_fresh_outputs(output, private)
    compute.write_outputs(output, private, prepared, power, metadata, result)
    assert {path.name for path in output.iterdir()} == set(compute.PUBLIC_FILES)
    with (output / "mean_power.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 4 * 16 * len(prepared["times"])
    assert float(rows[0]["time_s"]) == prepared["times"][0]
    with (output / "trial_windows.csv").open() as handle:
        assert len(list(csv.DictReader(handle))) == 64
    with np.load(private / "analysis_arrays.npz", allow_pickle=False) as arrays:
        assert arrays["pipeline_id"].item() == compute.PIPELINE_ID
        assert json.loads(arrays["metadata_json"].item()) == metadata
        assert json.loads(arrays["results_json"].item()) == result
        assert json.loads(arrays["source_events_json"].item()) == prepared["source_events"]
    assert metadata["n_trials"] == 1 and metadata["n_source_retained_trials"] == 3
    with pytest.raises(FileExistsError):
        compute.ensure_fresh_outputs(output, private)


def test_existing_evidence_untouched(tmp_path):
    (tmp_path / "erd.json").write_text("existing")
    with pytest.raises(FileExistsError):
        compute.ensure_fresh_outputs(tmp_path, tmp_path)
    assert (tmp_path / "erd.json").read_text() == "existing"


def test_failure_is_parseable_no_fabricated_answer(tmp_path):
    with pytest.raises(FileNotFoundError):
        compute.main(["--data-dir", str(tmp_path / "missing"), "--output-dir", str(tmp_path / "out")])
    for name in ["erd.json", "run_metadata.json"]:
        value = json.loads((tmp_path / "out" / name).read_text())
        assert value["status"] == "failed_precondition" and value["reason"]
        assert "beta_erd_percent" not in value


@pytest.mark.parametrize("tamper", ["manifest", "method"])
def test_source_and_method_digest_fail_closed(tmp_path, tamper):
    root = Path(__file__).parents[1]
    (tmp_path / "data_manifest.json").write_bytes((root / "environment/data_manifest.json").read_bytes())
    method = tmp_path / "method.json"
    method.write_bytes((root / "environment/method_contract.json").read_bytes())
    target = tmp_path / "data_manifest.json" if tamper == "manifest" else method
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError, match="identity mismatch"):
        compute.load_inputs(tmp_path, method)
