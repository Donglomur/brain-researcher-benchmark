"""Synthetic-only tests; never read a genuine recording or retained result bank."""
import csv
import importlib.util
import json
import math
from pathlib import Path

import h5py
import numpy as np
import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("allen2p_oracle_mechanics", ROOT / "solution/compute.py")
oracle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oracle)


def make_h5(path):
    chronological = [(direction, frequency, 0.) for repeat in range(3)
                     for direction in range(0, 360, 45) for frequency in (1., 2.)]
    chronological.insert(3, (np.nan, np.nan, 1.))
    n_trials = len(chronological)
    # Deliberately reverse original NWB rows; source IDs must survive sorting.
    features = np.asarray(chronological, dtype=float)[::-1]
    bounds = np.asarray([(2 + i * 5, 5 + i * 5) for i in range(n_trials)], dtype=np.int64)[::-1]
    n_frames = int(bounds.max()) + 2
    traces = np.random.default_rng(103).normal(2., .4, (3, n_frames)).astype(np.float32)
    with h5py.File(path, "w") as handle:
        dataset = handle.create_dataset(f"{oracle.BASE}/DfOverF/imaging_plane_1/data", data=traces)
        dataset.attrs["unit"] = "frame"
        handle.create_dataset(f"{oracle.BASE}/DfOverF/imaging_plane_1/timestamps", data=np.arange(n_frames) / 30.)
        handle.create_dataset(f"{oracle.BASE}/ImageSegmentation/cell_specimen_ids", data=[9003, 9001, 9002])
        handle.create_dataset(f"{oracle.BASE}/ImageSegmentation/roi_ids", data=np.asarray([b"roi007", b"roi005", b"roi006"]))
        handle.create_dataset(f"{oracle.STIM}/data", data=features)
        handle.create_dataset(f"{oracle.STIM}/features", data=np.asarray([b"orientation", b"temporal_frequency", b"blank_sweep"]))
        handle.create_dataset(f"{oracle.STIM}/frame_duration", data=bounds)
        handle.create_dataset("general/session_id", data=np.bytes_("501271265"))
        handle.create_dataset("general/optophysiology/imaging_plane_1/location", data=np.bytes_("VISp"))
        handle.create_dataset("general/session_type", data=np.bytes_("three_session_A"))
    return traces


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "synthetic.nwb"
    make_h5(path)
    return oracle.read_source({"source_path": path})


def fake_inputs():
    return dict(contract=json.loads((ROOT / "environment/method_contract.json").read_text()),
                source_manifest_sha256=oracle.MANIFEST_SHA256, source_nwb_sha256=oracle.SOURCE_SHA256,
                method_contract_sha256=oracle.METHOD_SHA256, source_sha256={"fixture": "synthetic"})


def test_pinned_stack_and_contract_files():
    oracle.check_versions()
    assert oracle.sha256(ROOT / "environment/method_contract.json") == oracle.METHOD_SHA256
    assert oracle.sha256(ROOT / "environment/source_manifest.json") == oracle.MANIFEST_SHA256


def test_direct_reader_preserves_original_cell_roi_pairs(source):
    assert source["cell_ids"].tolist() == [9003, 9001, 9002]
    assert source["roi_ids"].tolist() == ["roi007", "roi005", "roi006"]
    assert source["source_cell_index"].tolist() == [0, 1, 2]
    assert source["dff"].dtype == np.float64
    assert source["source_dff_dtype"] == "float32"
    assert source["source_dff_unit"] == "frame"


def test_chronological_order_keeps_original_nwb_row_ids(source):
    assert source["source_row_ids"].tolist() == list(range(48, -1, -1))
    rows = source["presentations"]
    assert [r["trial_index"] for r in rows] == list(range(49))
    assert rows[3]["direction_deg"] is None and rows[3]["temporal_frequency_hz"] is None
    assert rows[3]["blank_sweep"] == 1 and rows[3]["tuning_included"] == 0


def test_trial_means_half_open_float64_include_blank(source):
    values = oracle.trial_responses(source)
    assert values.shape == (3, 49)
    expected = [[math.fsum(source["dff"][c, a:b]) / (b-a)
                 for a, b in zip(source["start_frame"], source["end_frame"])] for c in range(3)]
    np.testing.assert_allclose(values, expected, rtol=0, atol=1e-15)
    assert np.isfinite(values[:, 3]).all()  # blank is retained, not zero-filled
    source["dff"][:, source["end_frame"][0]] = 123456.
    np.testing.assert_array_equal(oracle.trial_responses(source)[:, 0], values[:, 0])


def test_source_response_window_nonfinite_fails(source):
    source["dff"][0, source["start_frame"][0]] = np.nan
    with pytest.raises(ValueError, match="Nonfinite source"):
        oracle.trial_responses(source)


def test_nonfinite_outside_response_windows_not_an_extra_exclusion(source):
    source["dff"][0, 0] = np.nan
    assert np.isfinite(oracle.trial_responses(source)).all()


@pytest.mark.parametrize("bounds", [[[-1, 2]], [[2, 2]], [[3, 2]], [[0, 21]], [[.1, 2]]])
def test_invalid_intervals_are_not_repaired(bounds):
    with pytest.raises(ValueError):
        oracle.prepare_presentations([[0., 1., 0.]], ["orientation", "temporal_frequency", "blank_sweep"], bounds, 20)


def test_condition_means_are_equal_trial_not_duration_weighted(source):
    values = oracle.trial_responses(source)
    means, counts = oracle.condition_means(values, source, np.ones(49, bool))
    assert counts.shape == (8, 2) and np.all(counts == 3)
    assert means.shape == (3, 8, 2)
    selected = (source["direction"] == 0) & (source["temporal_frequency"] == 1)
    np.testing.assert_array_equal(means[:, 0, 0], values[:, selected].mean(axis=1))
    values[:, 3] = 1e100
    np.testing.assert_array_equal(oracle.condition_means(values, source, np.ones(49, bool))[0], means)


def estimate(select=None, measure=None, n_select=None, n_measure=None):
    select = np.ones((8, 2)) if select is None else select
    measure = np.ones((8, 2)) if measure is None else measure
    n_select = np.ones((8, 2), dtype=int) if n_select is None else n_select
    n_measure = np.ones((8, 2), dtype=int) if n_measure is None else n_measure
    return oracle.estimate_cell(9003, select, measure, n_select, n_measure, np.arange(0, 360, 45), np.array([1., 2.]))


def test_preference_tie_direction_then_frequency():
    select = np.zeros((8, 2))
    select[1, 1] = select[2, 0] = 7.
    row = estimate(select=select)
    assert row["preferred_direction_deg"] == 45.
    assert row["preferred_temporal_frequency_hz"] == 2.
    assert row["selection_pref_mean_dff"] == 7.
    select[1, 0] = 7.
    assert estimate(select=select)["preferred_temporal_frequency_hz"] == 1.


def test_no_selection_counts_are_undefined_not_zero():
    row = estimate(select=np.full((8, 2), np.nan), n_select=np.zeros((8, 2), int))
    assert row["selection_status"] == row["osi_status"] == row["dsi_status"] == "no_selection_conditions"
    assert row["preferred_direction_deg"] is None
    assert all(row[key] is None for key in oracle.COMPONENT_KEYS)


def test_missing_orthogonal_preserves_independent_dsi():
    measure = np.ones((8, 2))
    measure[0, 0] = 3.
    measure[2, 0] = np.nan
    counts = np.ones((8, 2), int)
    counts[2, 0] = 0
    row = estimate(measure=measure, n_measure=counts)
    assert row["n_measure_orth_plus"] == 0 and row["r_orth_plus"] is None
    assert row["osi"] is None and row["osi_status"] == "missing_measurement_condition"
    assert row["osi_denominator"] is None
    assert row["dsi"] == .5 and row["dsi_status"] == "ok"


@pytest.mark.parametrize("pref,other,expected", [(1., -.5, 3.), (-2., -1., 1/3), (-1., 2., -3.), (1e-100, 0., 1.)])
def test_signed_or_small_denominator_is_kept(pref, other, expected):
    value, denominator, status = oracle.ratio(pref, other)
    assert status == "ok" and denominator == pref + other
    assert value == pytest.approx(expected)


@pytest.mark.parametrize("pref,other", [(0., 0.), (1., -1.), (-1., 1.)])
def test_exact_zero_denominator_undefined(pref, other):
    assert oracle.ratio(pref, other) == (None, 0., "zero_denominator")


def test_ratio_overflow_fails_not_silently_dropped():
    with pytest.raises(ValueError, match="Nonfinite"):
        oracle.ratio(1e308, 1e308)


def test_strict_threshold_and_independent_undefined_policy():
    assert oracle.flag(.5, None) == 0
    assert oracle.flag(np.nextafter(.5, 1.), None) == 1
    assert oracle.flag(None, .6) == 1
    assert oracle.flag(None, None) == 0


def test_split_rng_draw_axis_includes_blanks(source):
    masks = oracle.make_masks(49)
    rng = np.random.Generator(np.random.PCG64(0))
    expected = np.stack([rng.random(49) < .5 for _ in range(50)])
    np.testing.assert_array_equal(masks, expected)
    assert not np.array_equal(masks[:, source["tuning_included"]], oracle.make_masks(48))


@pytest.mark.parametrize("method,n_estimates", [("same_trials", 1), ("repeated_split_mean_ratio", 100)])
def test_declared_method_complete_support_and_final_mean_ratios(source, method, n_estimates):
    responses = oracle.trial_responses(source)
    analysis = oracle.analyze(source, responses, method)
    assert len(analysis["estimates"]) == 3 * n_estimates
    assert analysis["results"]["n_estimates_per_cell"] == n_estimates
    for row in analysis["neurons"]:
        estimates = [entry for entry in analysis["estimates"] if entry["cell_specimen_id"] == row["cell_specimen_id"]]
        for metric in ["osi", "dsi"]:
            values = [entry[metric] for entry in estimates if entry[metric] is not None]
            assert row["n_valid_" + metric] == len(values)
            assert row[metric] == pytest.approx(math.fsum(values) / len(values))
        assert row["selective"] == oracle.flag(row["osi"], row["dsi"])
    if method == "repeated_split_mean_ratio":
        pairs = []
        for replicate in range(1, 51):
            fractions = []
            for half in ["A", "B"]:
                rows = [entry for entry in analysis["estimates"] if entry["replicate"] == replicate and entry["selection_half"] == half]
                assert len(rows) == 3
                fractions.append(sum(oracle.flag(entry["osi"], entry["dsi"]) for entry in rows) / 3)
            pairs.append(sum(fractions) / 2)
        assert analysis["results"]["split_fraction_mean"] == pytest.approx(np.mean(pairs))
        assert analysis["results"]["split_fraction_sd"] == pytest.approx(np.std(pairs, ddof=0))


def test_all_undefined_kept_in_denominator(source):
    analysis = oracle.analyze(source, np.zeros((3, 49)))
    assert analysis["results"]["n_neurons_total"] == 3
    assert analysis["results"]["n_both_undefined"] == 3
    assert analysis["results"]["selective_fraction"] == 0
    for row in analysis["neurons"]:
        assert row["osi"] is None and row["dsi"] is None
        assert row["n_valid_osi"] == row["n_valid_dsi"] == 0
        assert row["osi_status"] == row["dsi_status"] == "no_valid_estimates"


def test_pilot_preserves_full_source_count_and_first_stored_rows(tmp_path):
    path = tmp_path / "pilot.nwb"
    make_h5(path)
    source = oracle.read_source({"source_path": path}, pilot_cells=1)
    assert source["status"] == "resource_pilot"
    assert source["cell_ids"].tolist() == [9003]
    assert source["all_source_cell_ids"].tolist() == [9003, 9001, 9002]
    assert source["n_neurons_source_total"] == 3
    metadata = oracle.make_metadata(fake_inputs(), source, "same_trials")
    assert metadata["n_neurons_total"] == 1 and metadata["n_neurons_source_total"] == 3


@pytest.mark.parametrize("method", oracle.METHODS)
def test_serialized_schema_and_exclusive_output_guards(tmp_path, source, method):
    responses = oracle.trial_responses(source)
    analysis = oracle.analyze(source, responses, method)
    inputs = fake_inputs()
    metadata = oracle.make_metadata(inputs, source, method)
    output, private = tmp_path / "out", tmp_path / "private"
    oracle.ensure_fresh_outputs(output, private)
    oracle.write_outputs(output, private, inputs, source, responses, analysis, metadata)
    assert {p.name for p in output.iterdir()} == set(oracle.PUBLIC_FILES)
    expected_counts = {"presentations.csv": 49, "trial_responses.csv": 147, "condition_means.csv": 48,
                       "estimates.csv": 3 if method == "same_trials" else 300, "per_neuron.csv": 3}
    for filename, expected_count in expected_counts.items():
        with (output / filename).open() as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames == inputs["contract"]["outputs"][filename]
            rows = list(reader)
            assert len(rows) == expected_count
            assert not any(value in ("nan", "NaN", "inf", "Infinity", "None") for row in rows for value in row.values())
    for filename in ("results.json", "run_metadata.json"):
        assert set(inputs["contract"]["outputs"][filename]) <= json.loads((output / filename).read_text()).keys()
    with np.load(private / "analysis_arrays.npz", allow_pickle=False) as receipt:
        np.testing.assert_array_equal(receipt["trial_response"], responses)
        assert json.loads(receipt["results_json"].item()) == analysis["results"]
        assert json.loads(receipt["metadata_json"].item()) == metadata
    before = (output / "results.json").read_bytes()
    with pytest.raises(FileExistsError):
        oracle.ensure_fresh_outputs(output, private)
    assert (output / "results.json").read_bytes() == before


def test_failed_precondition_is_parseable_no_default_answer(tmp_path):
    with pytest.raises(FileNotFoundError):
        oracle.main(["--source-dir", str(tmp_path / "missing"), "--output-dir", str(tmp_path / "out"),
                     "--private-dir", str(tmp_path / "private")])
    value = json.loads((tmp_path / "out/results.json").read_text())
    assert value["status"] == "failed_precondition" and value["reason"]
    assert "selective_fraction" not in value


@pytest.mark.parametrize("which", ["manifest", "method"])
def test_frozen_hashes_are_enforced_before_source_read(tmp_path, which):
    manifest = tmp_path / "source_manifest.json"
    manifest.write_bytes((ROOT / "environment/source_manifest.json").read_bytes())
    method = tmp_path / "method_contract.json"
    method.write_bytes((ROOT / "environment/method_contract.json").read_bytes())
    path = manifest if which == "manifest" else method
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="fingerprint"):
        oracle.load_inputs(tmp_path, method)
