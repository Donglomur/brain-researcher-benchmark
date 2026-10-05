"""Tiny synthetic fixtures only: never open the original NWB recording bundle."""
import importlib.util
import json
from pathlib import Path
import sys

import h5py
import numpy as np
import pytest
from scipy.stats import mannwhitneyu

SOLUTION = Path(__file__).resolve().parents[1] / "solution"
sys.path.insert(0, str(SOLUTION))
spec = importlib.util.spec_from_file_location("mtl_oracle", SOLUTION / "compute.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
import source_reader as reader


def record(labels, counts, key="session::unit=9"):
    labels = np.asarray(labels, dtype=np.int64)
    return dict(unit_key=key, asset_path=key.split("::")[0], subject_id="P1", unit_id=int(key.split("=")[-1]),
        region="Hippocampus", labels=labels, counts=np.asarray(counts, dtype=np.int64),
        source_trial_row=np.arange(len(labels), dtype=np.int64)+11, trial_id=np.arange(len(labels), dtype=np.int64)*3+21)


@pytest.mark.parametrize("n0,n1", [(1, 1), (2, 3), (4, 4), (7, 8), (25, 25), (50, 50)])
def test_rank_batch_matches_manual_pairs_and_asymptotic_scipy(n0, n1):
    rng = np.random.default_rng(42)
    new = rng.integers(0, 9, size=(6, n0)); old = rng.integers(0, 9, size=(6, n1))
    result = oracle.rank_batch(new, old)
    for row in range(6):
        u2 = sum(2*int(a > b)+int(a == b) for a in old[row] for b in new[row])
        expected = mannwhitneyu(old[row], new[row], alternative="two-sided", method="asymptotic", use_continuity=True)
        assert result["u2"][row] == u2
        assert result["auc"][row] == u2/(2*n0*n1)
        assert result["p"][row] == pytest.approx(expected.pvalue, abs=1e-15)


def test_all_tied_convention():
    got = oracle.rank_batch(np.full((1, 7), 3), np.full((1, 5), 3))
    assert got["u2"].tolist() == [35]
    assert got["auc"].tolist() == [.5]
    assert got["p"].tolist() == [1]
    assert got["sign"].tolist() == [1]
    assert not got["selected"].any()


@pytest.mark.parametrize("bad", [np.array([[True]]), np.array([[1.]]), np.array([[-1]])])
def test_rank_invalid_counts_fail(bad):
    with pytest.raises(ValueError):
        oracle.rank_batch(bad, np.ones((1, 1), dtype=int))


def test_old_direction_and_no_exact_mww_substitution():
    got = oracle.rank_batch(np.array([[0, 0, 1, 2]]), np.array([[8, 9, 10, 10]]))
    assert got["auc"][0] == 1 and got["sign"][0] == 1
    reverse = oracle.rank_batch(np.array([[8, 9, 10, 10]]), np.array([[0, 0, 1, 2]]))
    assert reverse["auc"][0] == 0 and reverse["sign"][0] == -1
    assert got["p"][0] == reverse["p"][0]
    assert got["p"][0] != mannwhitneyu([8, 9, 10, 10], [0, 0, 1, 2], method="exact").pvalue


def test_unsorted_duplicate_half_open_counts_and_source_unchanged():
    values = np.array([11.7, 10.2, 10.1, 10.2, 11.699999, 30.])
    before = values.copy()
    assert reader.count_intervals(values, np.array([10.])).tolist() == [3]
    np.testing.assert_array_equal(values, before)
    assert reader.count_intervals(np.array([]), np.array([10.])).tolist() == [0]


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_spikes_fail(bad):
    with pytest.raises(ValueError):
        reader.count_intervals(np.array([bad]), np.array([10.]))


def test_global_rng_repeat_then_unit_and_no_draws_for_unsupported():
    a = record([0, 1]*5, np.arange(10), "z::unit=90")
    b = record([1, 0]*6, np.arange(12), "a::unit=2")
    unsupported = record([0, 0, 1], [1, 2, 3], "z::unit=8")
    got, bounds = oracle.generate_membership([a, unsupported, b])
    expected = np.zeros_like(got); rng = np.random.Generator(np.random.PCG64(0))
    for repeat in range(60):
        for i, item in [(0, a), (2, b)]:
            for label in [0, 1]:
                ix = np.where(item["labels"] == label)[0]
                chosen = rng.choice(ix, size=len(ix)//2, replace=False, shuffle=True)
                expected[repeat, bounds[i]+chosen] = True
    np.testing.assert_array_equal(got, expected)
    assert not got[:, bounds[1]:bounds[2]].any()
    without, other = oracle.generate_membership([a, b])
    np.testing.assert_array_equal(got[:, :bounds[1]], without[:, :other[1]])
    np.testing.assert_array_equal(got[:, bounds[2]:], without[:, other[1]:])


def test_supported_partitions_are_exact_and_test_direction_is_train_only():
    item = record([0]*8+[1]*8, [0, 0, 0, 0, 10, 10, 10, 10, 1, 1, 1, 1, 9, 9, 9, 9])
    neurons, events, primitive, private = oracle.analyze([item])
    below = False
    for event in events:
        mask = primitive["train_membership"][event["repeat"]]
        assert mask.sum() == 8
        assert np.sum(mask & (item["labels"] == 0)) == 4
        test = ~mask
        n = item["counts"][test & (item["labels"] == 0)]
        o = item["counts"][test & (item["labels"] == 1)]
        manual_auc = sum(int(x > y)+.5*int(x == y) for x in o for y in n)/(len(o)*len(n))
        directed = manual_auc if event["train_preferred_sign"] == 1 else 1-manual_auc
        assert event["test_directed_auc"] == directed
        below |= directed < .5
        assert event["train_selected"] == event["included_in_conditional_summary"]
    assert below, "This fixture must detect forbidden held-out folding"
    assert neurons[0]["n_usable_splits"] == 60


@pytest.mark.parametrize("labels", [[], [0, 0], [1, 1], [0, 1], [0, 0, 0, 1, 1, 1]])
def test_unsupported_splits_retained_with_null_support(labels):
    neurons, events, arrays, _ = oracle.analyze([record(labels, [0]*len(labels))])
    assert len(events) == 60 and not arrays["train_membership"].any()
    for row in events:
        assert row["status"] == "insufficient_class_support"
        assert row["n_train_new"] is None and row["test_auc_old"] is None
        assert row["train_selected"] is False
    assert neurons[0]["conditional_auc"] is None
    if len(set(labels)) < 2:
        assert neurons[0]["auc_old"] is None and neurons[0]["full_p"] is None
    else:
        assert neurons[0]["auc_old"] == .5


def test_empty_population_no_fabricated_chance():
    neurons, events, arrays, _ = oracle.analyze([])
    result = oracle.summarize([], neurons, oracle.POPULATIONS[1])
    assert result["memory_selective_new_old_auc"] is None
    assert result["proportion_memory_selective"] is None
    assert result["headline_status"] == "empty_population"
    assert arrays["train_membership"].shape == (60, 0)
    assert arrays["unit_key"].dtype.kind == "U"


def test_population_equal_unit_means_and_nonoverlap():
    base = dict(n_trials=10, full_status="ok")
    neurons = [dict(base, memory_selective=True, heldout_eligible=False, same_trial_auc=.9, conditional_auc=.1),
               dict(base, memory_selective=False, heldout_eligible=True, same_trial_auc=.6, conditional_auc=.2),
               dict(base, memory_selective=True, heldout_eligible=True, same_trial_auc=.8, conditional_auc=.8),
               dict(base, memory_selective=False, heldout_eligible=False, same_trial_auc=.5, conditional_auc=None)]
    sessions = [dict(subject_id="p", n_source_units=4), dict(subject_id="p", n_source_units=0)]
    result = oracle.summarize(sessions, neurons, oracle.POPULATIONS[1])
    assert result["memory_selective_new_old_auc"] == .5
    assert result["population_overlap"] == dict(full_only=1, conditional_only=1, both=1, neither=1)
    assert result["n_patients"] == 1 and result["n_sessions"] == 2
    assert result["populations"][oracle.POPULATIONS[0]]["mean_auc"] == pytest.approx(.85)


def synthetic_nwb(path):
    strings = h5py.string_dtype("utf-8")
    with h5py.File(path, "w") as f:
        f.attrs["nwb_version"] = "2.1.0"
        for name, value in {"identifier":"different_from_path", "general/subject/subject_id":"P1", "session_start_time":"2020-01-01",
                            "timestamps_reference_time":"2020-01-01", "general/data_collection":"learning: 81, recognition: 82"}.items():
            f.create_dataset(name, data=value, dtype=strings)
        t = f.create_group("intervals/trials")
        t["id"] = np.array([41, 3, 900], dtype=np.int32)
        for name, value in {"stim_phase":["learn", "recog", "recog"], "new_old_labels_recog":["NA", "0", "1"],
                            "external_image_file":[r"C:\learn\face.jpg", r"C:\new\face.jpg", r"C:\unknown\old.jpg"]}.items():
            t.create_dataset(name, data=value, dtype=strings)
        t["new_old_labels_recog"].attrs["description"] = "0 == Old Stimuli, 1 = New Stimuli"
        on = np.array([10., 20., 30.])
        t["start_time"] = on; t["stim_on_time"] = on; t["stim_off_time"] = on+1; t["stop_time"] = on+2
        event_times = np.column_stack([on, on+1, on+2]).ravel()
        f.create_dataset("acquisition/events/data", data=["1.0", "2.0", "6.0"]*3, dtype=strings)
        f["acquisition/events/timestamps"] = event_times
        f["acquisition/experiment_ids/timestamps"] = event_times
        f["acquisition/events/timestamps"].attrs["unit"] = "seconds"
        f["acquisition/experiment_ids/timestamps"].attrs["unit"] = "seconds"
        f["acquisition/experiment_ids/data"] = np.repeat([81., 82., 82.], 3)
        f["acquisition/experiment_ids"].attrs["description"] = "The learning trials are demarcated by: 81. The recognition trials are demarcated by: 82. "
        e = f.create_group("general/extracellular_ephys/electrodes")
        e["id"] = np.array([111, 222], dtype=np.int32); e["origChannel"] = np.array([5, 9], dtype=np.uint16)
        e.create_dataset("location", data=["RightAmygdala", "LeftHippocampus"], dtype=strings)
        u = f.create_group("units")
        u["id"] = np.array([99, 7], dtype=np.int32)
        u["electrodes"] = np.array([1, 0], dtype=np.int32); u["electrodes"].attrs["table"] = e.ref
        u["electrodes_index"] = np.array([1, 2], dtype=np.int32)
        u["spike_times"] = np.array([20.2, 30.2, 20.2, 21.7, 20.1])
        u["spike_times_index"] = np.array([5, 5], dtype=np.int32)
    return dict(path="sub-P1/session.nwb", participant="P1", asset_id="fixture", sha256="fixture")


def test_direct_source_reader_identity_clock_multiplicity_and_missing_old_history(tmp_path):
    p = tmp_path/"fixture.nwb"; source = synthetic_nwb(p)
    session, trials, units, records, meta = reader.read_session(p, source)
    assert session["literal_session_id"] is None and session["nwb_identifier"] == "different_from_path"
    assert [x["unit_id"] for x in units] == [99, 7]
    assert units[0]["electrode_row"] == 1 and units[0]["electrode_id"] == 222 and units[0]["original_channel"] == 9
    assert records[0]["trial_id"].tolist() == [3, 900]
    assert records[0]["counts"].tolist() == [2, 1]
    assert trials[0]["source_label"] is None and trials[0]["source_label_token"] == "NA"
    assert trials[1]["image_in_learning"] is False and trials[2]["image_in_learning"] is False
    assert trials[2]["included"] is True and trials[2]["source_label"] == 1
    assert meta["raw_adjacent_inversions"] == 2 and meta["duplicate_timestamp_occurrences"] == 1
    assert meta["raw_adjacent_duplicate_spikes"] == 0 and meta["n_unordered_units"] == 1
    assert meta["spike_times_literal_unit"] is None and meta["observation_coverage"] == "unknown"
    assert meta["phase_experiment_ids"] == dict(learn=81, recog=82)
    assert meta["label_description_conflicts_with_released_code_semantics"] is True


@pytest.mark.parametrize("mutation", ["label", "phase_description", "duplicate_trial_id", "bad_spike_offset", "bad_dtr", "ambiguous_region", "nonfinite_spike", "ttl_clock", "observation"])
def test_source_preconditions_fail_instead_of_repair(tmp_path, mutation):
    p = tmp_path/"fixture.nwb"; source = synthetic_nwb(p)
    with h5py.File(p, "r+") as f:
        if mutation == "label": f["intervals/trials/new_old_labels_recog"][1] = "unknown"
        elif mutation == "phase_description": f["acquisition/experiment_ids"].attrs["description"] = "The learning trials are demarcated by: 80. The recognition trials are demarcated by: 81."
        elif mutation == "duplicate_trial_id": f["intervals/trials/id"][1] = 41
        elif mutation == "bad_spike_offset": f["units/spike_times_index"][1] = 4
        elif mutation == "bad_dtr": f["units/electrodes_index"][:] = [0, 2]
        elif mutation == "ambiguous_region": f["general/extracellular_ephys/electrodes/location"][1] = "Amygdala_Hippocampus"
        elif mutation == "nonfinite_spike": f["units/spike_times"][0] = np.nan
        elif mutation == "ttl_clock": f["acquisition/experiment_ids/timestamps"][0] += .01
        elif mutation == "observation": f["units/obs_intervals"] = np.empty((0, 2))
    with pytest.raises(ValueError): reader.read_session(p, source)


def test_non_mtl_source_unit_remains_in_ledger(tmp_path):
    p = tmp_path/"fixture.nwb"; source = synthetic_nwb(p)
    with h5py.File(p, "r+") as f:
        f["general/extracellular_ephys/electrodes/location"][1] = "Occipital"
    session, _, units, records, _ = reader.read_session(p, source)
    assert len(units) == 2 and len(records) == 1 and session["n_mtl_units"] == 1
    assert units[0]["included"] is False and units[0]["region"] is None


def set_original_stop_and_reorder_acquisition(path, trial_row, stop):
    """Synthetic original with a literal anomalous stop and exact sorted source TTLs."""
    with h5py.File(path, "r+") as f:
        f["intervals/trials/stop_time"][trial_row] = stop
        event_times = f["acquisition/events/timestamps"][:]
        event_times[trial_row*3+2] = stop
        order = np.argsort(event_times, kind="stable")
        codes = f["acquisition/events/data"].asstr()[:]
        experiments = f["acquisition/experiment_ids/data"][:]
        f["acquisition/events/timestamps"][:] = event_times[order]
        f["acquisition/experiment_ids/timestamps"][:] = event_times[order]
        f["acquisition/events/data"][:] = codes[order]
        f["acquisition/experiment_ids/data"][:] = experiments[order]


@pytest.mark.parametrize("stop", [9.9, 10.5])
def test_learning_stop_anomaly_retained_and_diagnosed_without_changing_counts(tmp_path, stop):
    p = tmp_path/"fixture.nwb"; source = synthetic_nwb(p)
    before = reader.read_session(p, source)
    set_original_stop_and_reorder_acquisition(p, 0, stop)
    session, trials, units, records, observed = reader.read_session(p, source)
    assert trials[0]["stop_time_s"] == stop and trials[0]["included"] is False
    assert observed["n_learning_temporal_order_violations"] == 1
    assert observed["n_recognition_temporal_order_violations"] == 0
    assert observed["clock_mapping_counts"]["trial_end_exact_unique_ttl6"] == 3
    for original, after in zip(before[3], records):
        np.testing.assert_array_equal(original["counts"], after["counts"])
        np.testing.assert_array_equal(original["labels"], after["labels"])


@pytest.mark.parametrize("stop", [19.9, 20.5])
def test_recognition_stop_anomaly_still_fails(tmp_path, stop):
    p = tmp_path/"fixture.nwb"; source = synthetic_nwb(p)
    set_original_stop_and_reorder_acquisition(p, 1, stop)
    with pytest.raises(ValueError, match="recognition temporal order"):
        reader.read_session(p, source)


@pytest.mark.parametrize("pair", [(80, 81), (83, 84), (88, 89), (82, 83), (81, 82), (80, 82)])
def test_source_phase_pairs_not_hardcoded(pair):
    a, b = pair
    assert reader.phase_mapping(f"learning: {a}, recognition: {b}", f"The learning trials are demarcated by: {a}. The recognition trials are demarcated by: {b}.") == dict(learn=a, recog=b)


@pytest.mark.parametrize("token", ["1.0000000000000000001", "NaN", "Infinity", "true", "9223372036854775808"])
def test_exact_decimal_ttl_rejects_fractional_or_invalid_tokens(token):
    with pytest.raises(ValueError):
        reader.ttl_integers([token])


def test_exact_decimal_ttl_allows_original_integer_notation():
    np.testing.assert_array_equal(reader.ttl_integers(["1.0", "2.000", "6e0", "-1"]), [1, 2, 6, -1])


@pytest.mark.parametrize("layout", ["equal", "output_in_source", "source_in_output", "private_in_source", "nested_outputs", "symlink"])
def test_destination_source_evidence_safety(tmp_path, layout):
    source = tmp_path/"source"; source.mkdir(); (source/"original").write_text("preserve")
    output, private = tmp_path/"output", tmp_path/"private"
    if layout == "equal": output = source
    elif layout == "output_in_source": output = source/"out"
    elif layout == "source_in_output": output = tmp_path
    elif layout == "private_in_source": private = source/"private"
    elif layout == "nested_outputs": private = output/"private"
    elif layout == "symlink":
        alias = tmp_path/"alias"; alias.symlink_to(tmp_path, target_is_directory=True); output = alias/"output"
    with pytest.raises(ValueError): oracle.prepare_destinations(source, output, private)
    assert (source/"original").read_text() == "preserve"


def test_empty_destination_allowed_but_existing_evidence_not_overwritten(tmp_path):
    source, output, private = tmp_path/"source", tmp_path/"output", tmp_path/"private"
    output.mkdir(); private.mkdir()
    assert oracle.prepare_destinations(source, output, private) == (output, private)
    (output/"findings.md").write_text("prior evidence")
    assert oracle.main(["--data-dir", str(source), "--output-dir", str(output), "--private-dir", str(private)]) == 1
    assert list(output.iterdir()) == [output/"findings.md"]
    assert (output/"findings.md").read_text() == "prior evidence"


def test_missing_inputs_have_failed_precondition_and_findings(tmp_path):
    output, private = tmp_path/"output", tmp_path/"private"
    assert oracle.main(["--data-dir", str(tmp_path/"source"), "--method-contract", str(tmp_path/"missing"), "--output-dir", str(output), "--private-dir", str(private)]) == 1
    for name in ["results.json", "run_metadata.json", "failure.json"]:
        value = json.loads((output/name).read_text())
        assert value["status"] == "failed_precondition" and value["reason"]
    assert (output/"findings.md").read_text().strip()


def test_synthetic_complete_serialization_has_exact_nine_public_artifacts(tmp_path, monkeypatch):
    p = tmp_path/"fixture.nwb"; source = synthetic_nwb(p); source["path"] = p.name
    method = json.loads((SOLUTION.parent/"environment/method_contract.json").read_text())
    manifest = dict(files=[source])
    monkeypatch.setattr(oracle, "load_inputs", lambda *args: (method, manifest))
    out, private = tmp_path/"out", tmp_path/"private"; out.mkdir(); private.mkdir()
    oracle.execute(tmp_path, "unused", out, private)
    assert set(x.name for x in out.iterdir()) == set(method["outputs"])
    assert json.loads((out/"results.json").read_text())["status"] == "complete"
    with np.load(out/"trial_counts.npz", allow_pickle=False) as arrays:
        assert arrays["unit_key"].dtype.kind == "U"
        assert arrays["train_membership"].dtype == bool
        assert arrays["spike_count"].tolist() == [2, 1, 0, 0]
    assert (private/"analysis_arrays.npz").exists()


def test_private_failure_cannot_publish_complete_status(tmp_path, monkeypatch):
    p = tmp_path/"fixture.nwb"; source = synthetic_nwb(p); source["path"] = p.name
    method = json.loads((SOLUTION.parent/"environment/method_contract.json").read_text())
    monkeypatch.setattr(oracle, "load_inputs", lambda *args: (method, dict(files=[source])))
    monkeypatch.setattr(oracle, "save_npz", lambda *args: (_ for _ in ()).throw(OSError("private storage failure")))
    out, private = tmp_path/"out", tmp_path/"private"
    # Source directory must remain disjoint from evidence roots even in this fixture.
    source_root = tmp_path/"originals"; source_root.mkdir(); p.rename(source_root/p.name)
    assert oracle.main(["--data-dir", str(source_root), "--output-dir", str(out), "--private-dir", str(private)]) == 1
    assert json.loads((out/"results.json").read_text())["status"] == "failed_precondition"
    assert json.loads((out/"run_metadata.json").read_text())["status"] == "failed_precondition"


def test_pilot_retains_schema_but_never_claims_complete_cohort(tmp_path, monkeypatch):
    p = tmp_path/"fixture.nwb"; source = synthetic_nwb(p); source["path"] = p.name
    method = json.loads((SOLUTION.parent/"environment/method_contract.json").read_text())
    monkeypatch.setattr(oracle, "load_inputs", lambda *args: (method, dict(files=[source])))
    out, private = tmp_path/"out", tmp_path/"private"; out.mkdir(); private.mkdir()
    oracle.execute(tmp_path, "unused", out, private, pilot=True)
    result = json.loads((out/"results.json").read_text())
    assert result["status"] == "resource_pilot" and result["n_sessions"] == 1
    assert "not the full cohort" in result["scope"]
    assert set(method["outputs"]["results.json"]["required_fields"]) <= set(result)
