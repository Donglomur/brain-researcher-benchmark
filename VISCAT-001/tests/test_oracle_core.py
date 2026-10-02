"""Manufactured mechanics only; no original NWB or old reference inputs."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import h5py
import numpy as np
import pytest
from scipy.stats import kruskal, mannwhitneyu

TASK = Path(__file__).parents[1]
sys.path.insert(0, str(TASK / "solution"))
import core
import source_reader as reader
import compute


def record(key="asset::unit=9", counts=None, cats=None):
    cats = np.repeat(np.arange(1, 6), 6) if cats is None else np.asarray(cats, dtype=np.int64)
    counts = np.arange(len(cats)) % 8 if counts is None else np.asarray(counts, dtype=np.int64)
    return dict(unit_key=key, asset_path="asset", subject_id="P1", unit_id=9, region="Amygdala",
                source_trial_row=np.arange(len(cats), dtype=np.int64)+20,
                trial_id=np.arange(len(cats), dtype=np.int64)[::-1]+200,
                category_code=cats, counts=counts)


@pytest.mark.parametrize("seed", range(20))
def test_exact_rational_kw_matches_scipy_manufactured(seed):
    rng = np.random.default_rng(seed)
    cats = np.repeat(np.arange(1, 6), np.arange(4, 9))
    values = rng.integers(0, 15, len(cats))
    actual = core.category_statistics(values, cats)
    expected = kruskal(*(values[cats == c] for c in range(1, 6)), nan_policy="raise")
    assert actual["H"] == pytest.approx(expected.statistic, abs=1e-12)
    assert actual["p"] == pytest.approx(expected.pvalue, abs=1e-12)
    pref = actual["preferred_category"]
    u = mannwhitneyu(values[cats == pref], values[cats != pref], method="asymptotic").statistic
    assert actual["u_preferred_twice"] == 2*u
    assert actual["auc"] == u / (actual["n_preferred"]*actual["n_rest"])
    assert sum(actual[f"rank_sum_twice_cat_{c}"] for c in range(1, 6)) == len(cats)*(len(cats)+1)


def test_all_tied_distinct_from_nontied_equal_rank_sums():
    cats = np.repeat(np.arange(1, 6), 2)
    a = core.category_statistics(np.full(10, 7, dtype=np.int64), cats)
    assert (a["status"], a["H"], a["p"], a["auc"]) == ("all_tied", 0, 1, .5)
    assert a["tie_sum"] == 10**3-10 and a["preferred_category"] == 1 and a["preferred_tied"]
    b = core.category_statistics(np.tile([0, 1], 5), cats)
    assert (b["status"], b["H"], b["p"]) == ("ok", 0, 1)
    assert not b["selected"] and b["tie_sum"] == 2*(5**3-5)


def test_highest_mean_can_have_auc_below_half_without_flip():
    result = core.category_statistics(np.asarray([0, 0, 100]+[10]*12), np.repeat(np.arange(1, 6), 3))
    assert result["preferred_category"] == 1
    assert result["auc"] == pytest.approx(1/3) and result["u_preferred_twice"] == 24


def test_exact_mean_tie_uses_smallest_code():
    result = core.category_statistics(np.asarray([1, 2, 0, 3, 0, 0, 0, 0, 0, 0]), np.repeat(np.arange(1, 6), 2))
    assert result["preferred_category"] == 1 and result["preferred_tied"]


@pytest.mark.parametrize("p,expected", [(.05, False), (np.nextafter(.05, 0), True), (np.nextafter(.05, 1), False), (1, False)])
def test_strict_selection_boundary(p, expected):
    assert core.selection("ok", p) is expected
    assert not core.selection("all_tied", p)
    assert not core.selection("insufficient_category_support", p)


@pytest.mark.parametrize("bad", [np.array([True]), np.array([1.0]), np.array([-1]), np.array([2**63], dtype=np.uint64), np.ones((2, 2), dtype=int)])
def test_bad_count_arrays_fail(bad):
    with pytest.raises(ValueError):
        core.category_statistics(bad, np.ones(bad.size, dtype=int))


def test_missing_category_retains_support_and_null_statistics():
    result = core.category_statistics(np.array([2, 3]), np.array([1, 2]))
    assert result["status"] == "insufficient_category_support" and result["H"] is None
    assert result["n_cat_3"] == 0 and result["sum_count_cat_1"] == 2
    assert result["mean_rate_cat_3"] is None and result["preferred_category"] is None
    assert not result["selected"]
    assert core.auc_from_preference(np.array([2]), np.array([1]), 1)["auc"] is None


def test_large_integer_rank_identity_not_float_coerced():
    x = np.array([2**53+i for i in range(10)], dtype=np.int64)
    result = core.auc_from_preference(x, np.repeat(np.arange(1, 6), 2), 5)
    assert result["auc"] == 1 and result["u_preferred_twice"] == 32


def test_global_rng_schedule_masks_original_ids_and_all_events():
    recs = [record(), record("asset::unit=3")]
    neurons, events, arrays = core.analyze(recs)
    expected = np.zeros((50, 60), dtype=bool)
    rng = np.random.Generator(np.random.PCG64(0))
    for repeat in range(50):
        for unit, r in enumerate(recs):
            for c in range(1, 6):
                indices = np.where(r["category_code"] == c)[0].copy()
                rng.shuffle(indices)
                expected[repeat, unit*30+indices[:3]] = True
    np.testing.assert_array_equal(arrays["train_membership"], expected)
    np.testing.assert_array_equal(arrays["trial_id"][:30], recs[0]["trial_id"])
    assert len(events) == 100 and all(n["n_usable_splits"] == 50 for n in neurons)
    assert [(e["repeat"], e["unit_key"]) for e in events[:4]] == [(0, recs[0]["unit_key"]), (0, recs[1]["unit_key"]), (1, recs[0]["unit_key"]), (1, recs[1]["unit_key"])]


def test_unsupported_skip_consumes_no_rng_and_has_no_implied_test():
    supported = record()
    unsupported = record("unsupported", [1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
    one = core.analyze([supported])[2]
    neurons, events, arrays = core.analyze([unsupported, supported])
    np.testing.assert_array_equal(arrays["train_membership"][:, 5:], one["train_membership"])
    assert not arrays["train_membership"][:, :5].any()
    first = events[0]
    assert first["status"] == "insufficient_category_support" and first["n_test_cat_1"] is None
    assert first["train_preferred_tied"] is None and not first["train_selected"]
    assert neurons[0]["n_usable_splits"] == 0


def test_nonselected_and_all_tied_split_receipts_retained():
    neurons, events, arrays = core.analyze([record(counts=np.zeros(30, dtype=int))])
    assert len(events) == 50 and all(e["status"] == "all_tied" for e in events)
    assert all(e["test_auc"] == .5 and not e["included_in_conditional_summary"] for e in events)
    assert neurons[0]["conditional_auc"] is None and not neurons[0]["heldout_eligible"]
    assert arrays["train_membership"].sum() == 50*15


@pytest.mark.parametrize("n_selected", [0, 1, 4, 5, 50])
def test_per_unit_conditional_mean_and_five_repeat_eligibility(monkeypatch, n_selected):
    real = core.split_row
    def manufactured_decisions(record, repeat, mask):
        row = real(record, repeat, mask)
        row.update(train_selected=repeat < n_selected,
                   included_in_conditional_summary=repeat < n_selected,
                   test_auc=repeat/100)
        return row
    monkeypatch.setattr(core, "split_row", manufactured_decisions)
    neurons, events, _ = core.analyze([record()])
    neuron = neurons[0]
    assert neuron["n_selected_splits"] == n_selected
    assert neuron["heldout_eligible"] is (n_selected >= 5)
    if n_selected:
        assert neuron["conditional_auc"] == pytest.approx((n_selected-1)/200)
        assert neuron["conditional_status"] == "defined"
    else:
        assert neuron["conditional_auc"] is None and neuron["conditional_status"] == "no_selected_splits"
    assert len(events) == 50


@pytest.mark.parametrize("headline", core.POPULATIONS)
def test_distinct_populations_equal_unit_weight_and_either_headline(headline):
    neurons = [dict(category_selective=True, heldout_eligible=False, same_trial_auc=.1, conditional_auc=.9, full_status="ok"),
               dict(category_selective=False, heldout_eligible=True, same_trial_auc=.9, conditional_auc=.2, full_status="ok"),
               dict(category_selective=True, heldout_eligible=True, same_trial_auc=.3, conditional_auc=.4, full_status="ok")]
    sessions = [dict(subject_id="P1", n_source_units=3)]
    result = core.summarize(neurons, sessions, 30, headline)
    assert result["populations"][core.POPULATIONS[0]]["mean_auc"] == pytest.approx(.2)
    assert result["populations"][core.POPULATIONS[1]]["mean_auc"] == pytest.approx(.3)
    assert result["preferred_category_auc"] == result["populations"][headline]["mean_auc"]
    assert result["population_overlap"] == dict(full_only=1, conditional_only=1, both=1, neither=0)


def test_empty_population_remains_complete_null_not_half():
    result = core.summarize([], [], 0)
    assert result["status"] == "complete" and result["preferred_category_auc"] is None
    assert result["proportion_category_selective"] is None and result["headline_status"] == "empty_population"


def synthetic_nwb(path):
    strings = h5py.string_dtype("utf-8")
    with h5py.File(path, "w") as f:
        f.attrs["nwb_version"] = "2.1.0"
        for name, value in {"identifier":"literal-ID", "general/subject/subject_id":"P1", "session_start_time":"2020-01-01",
                            "timestamps_reference_time":"2020-01-01", "general/data_collection":"learning: 81, recognition: 82"}.items():
            f.create_dataset(name, data=value, dtype=strings)
        t = f.create_group("intervals/trials")
        t["id"] = np.array([41, 3, 900], dtype=np.int32)
        for name, value in {"stim_phase":["learn", "recog", "recog"], "new_old_labels_recog":["NA", "0", "1"],
                            "category_name":["houses", "houses", "landscapes"],
                            "external_image_file":[r"newolddelay\houses\old.jpg", r"newolddelay\houses\new.jpg", r"newolddelay\landscapes\other.jpg"]}.items():
            t.create_dataset(name, data=value, dtype=strings)
        t["stimCategory"] = np.array([1, 1, 2], dtype=np.uint8)
        t["new_old_labels_recog"].attrs["description"] = "0 == Old Stimuli, 1 = New Stimuli"
        on = np.array([10., 20., 30.])
        t["start_time"] = on; t["stim_on_time"] = on; t["stim_off_time"] = on+1; t["stop_time"] = on+2
        event_times = np.column_stack([on, on+1, on+2]).ravel()
        f.create_dataset("acquisition/events/data", data=["1.0", "2.0", "6.0"]*3, dtype=strings)
        f["acquisition/events/timestamps"] = event_times; f["acquisition/experiment_ids/timestamps"] = event_times
        f["acquisition/events/timestamps"].attrs["unit"] = "seconds"
        f["acquisition/experiment_ids/timestamps"].attrs["unit"] = "seconds"
        f["acquisition/experiment_ids/data"] = np.repeat([81., 82., 82.], 3)
        f["acquisition/experiment_ids"].attrs["description"] = "The learning trials are demarcated by: 81. The recognition trials are demarcated by: 82. "
        e = f.create_group("general/extracellular_ephys/electrodes")
        e["id"] = np.array([111, 222], dtype=np.int32); e["origChannel"] = np.array([5, 9], dtype=np.uint16)
        e.create_dataset("location", data=["RightAmygdala", "LeftHippocampus"], dtype=strings)
        u = f.create_group("units"); u["id"] = np.array([99, 7], dtype=np.int32)
        u["electrodes"] = np.array([1, 0], dtype=np.int32); u["electrodes"].attrs["table"] = e.ref
        u["electrodes_index"] = np.array([1, 2], dtype=np.int32)
        u["spike_times"] = np.array([20.2, 30.2, 20.2, 21.7, 20.1])
        u["spike_times_index"] = np.array([5, 5], dtype=np.int32)
    return dict(path="sub-P1/session.nwb", participant="P1", asset_id="fixture", sha256="a"*64)


def test_source_reader_literal_ids_category_and_multiplicity(tmp_path):
    path = tmp_path/"fixture.nwb"; source = synthetic_nwb(path)
    session, trials, units, records, observed = reader.read_session(path, source)
    assert session["variant_prefix"] == "newolddelay" and session["literal_session_id"] is None
    assert [u["unit_id"] for u in units] == [99, 7]
    assert units[0]["electrode_id"] == 222 and units[0]["original_channel"] == 9
    assert records[0]["trial_id"].tolist() == [3, 900] and records[0]["category_code"].tolist() == [1, 2]
    assert records[0]["counts"].tolist() == [2, 1]
    assert observed["raw_adjacent_inversions"] == 2 and observed["duplicate_timestamp_occurrences"] == 1
    assert observed["observation_coverage"] == "unknown" and observed["spike_times_literal_unit"] is None
    assert trials[0]["category_name"] == "houses" and trials[0]["source_label"] is None
    assert trials[2]["source_label"] == 1 and not trials[2]["image_in_learning"]


@pytest.mark.parametrize("mutation", ["category_float", "category_name", "variant", "label", "phase_description", "duplicate_trial", "bad_dtr", "bad_spike_offset", "nonfinite_spike", "clock", "observation", "ambiguous_anatomy"])
def test_source_preconditions_no_silent_repair(tmp_path, mutation):
    path = tmp_path/"fixture.nwb"; source = synthetic_nwb(path)
    with h5py.File(path, "r+") as f:
        if mutation == "category_float":
            del f["intervals/trials/stimCategory"]; f["intervals/trials/stimCategory"] = [1., 1., 2.]
        elif mutation == "category_name": f["intervals/trials/category_name"][1] = "fruit"
        elif mutation == "variant": f["intervals/trials/external_image_file"][1] = r"newolddelay2\fruit\x.jpg"
        elif mutation == "label": f["intervals/trials/new_old_labels_recog"][1] = "unknown"
        elif mutation == "phase_description": f["acquisition/experiment_ids"].attrs["description"] = "wrong"
        elif mutation == "duplicate_trial": f["intervals/trials/id"][1] = 41
        elif mutation == "bad_dtr": f["units/electrodes_index"][:] = [0, 2]
        elif mutation == "bad_spike_offset": f["units/spike_times_index"][1] = 4
        elif mutation == "nonfinite_spike": f["units/spike_times"][0] = np.inf
        elif mutation == "clock": f["acquisition/experiment_ids/timestamps"][0] += .1
        elif mutation == "observation": f["units/obs_intervals"] = np.empty((0, 2))
        else: f["general/extracellular_ephys/electrodes/location"][1] = "AmygdalaHippocampus"
    with pytest.raises(ValueError): reader.read_session(path, source)


@pytest.mark.parametrize("kind", ["soft", "external_link", "external_storage", "virtual"])
def test_external_hdf5_access_refused_before_payload(tmp_path, kind):
    path = tmp_path/"fixture.nwb"; source = synthetic_nwb(path)
    with h5py.File(path, "r+") as f:
        del f["units/spike_times"]
        if kind == "soft": f["units/spike_times"] = h5py.SoftLink("/intervals/trials/start_time")
        elif kind == "external_link": f["units/spike_times"] = h5py.ExternalLink("DO_NOT_OPEN", "/spikes")
        elif kind == "external_storage": f["units"].create_dataset("spike_times", (5,), dtype="f8", external=[("DO_NOT_OPEN", 0, 40)])
        else:
            layout = h5py.VirtualLayout(shape=(5,), dtype="f8")
            layout[:] = h5py.VirtualSource("DO_NOT_OPEN", "spikes", shape=(5,))
            f["units"].create_virtual_dataset("spike_times", layout)
    with pytest.raises(ValueError, match="Non-hard|External or virtual"): reader.read_session(path, source)


@pytest.mark.parametrize("variant", list(reader.CATEGORY_VARIANTS))
def test_session_local_dictionary_not_global_names(variant):
    names = list(reader.CATEGORY_VARIANTS[variant]); images = [variant+"\\"+name+"\\one.jpg" for name in names]
    cats, actual = reader.category_metadata(np.arange(1, 6), names, images)
    assert actual == variant and cats.tolist() == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("path", ["", ".", "./", "unknown\\one.jpg"])
def test_empty_or_unknown_variant_path_explicit_failure(path):
    with pytest.raises(ValueError): reader.category_metadata(np.array([1]), ["houses"], [path])


@pytest.mark.parametrize("phase", ["learn", "recog"])
def test_learning_stop_exception_not_recognition_exception(tmp_path, phase):
    path = tmp_path/"fixture.nwb"; source = synthetic_nwb(path); row = 0 if phase == "learn" else 1
    with h5py.File(path, "r+") as f:
        stop = 9.9 if row == 0 else 19.9
        f["intervals/trials/stop_time"][row] = stop
        event_times = f["acquisition/events/timestamps"][:]; event_times[row*3+2] = stop
        order = np.argsort(event_times, kind="stable")
        codes = f["acquisition/events/data"].asstr()[:]; ids = f["acquisition/experiment_ids/data"][:]
        for name in ("acquisition/events/timestamps", "acquisition/experiment_ids/timestamps"):
            f[name][:] = event_times[order]
        f["acquisition/events/data"][:] = codes[order]; f["acquisition/experiment_ids/data"][:] = ids[order]
    if phase == "recog":
        with pytest.raises(ValueError, match="recognition temporal order"): reader.read_session(path, source)
    else:
        _, trials, _, records, observed = reader.read_session(path, source)
        assert trials[0]["stop_time_s"] == 9.9 and observed["n_learning_temporal_order_violations"] == 1
        assert records[0]["counts"].tolist() == [2, 1]


def test_half_open_duplicates_and_no_source_mutation():
    source = np.array([1.7, .2, .2, 1.699999, .1]); before = source.copy()
    assert reader.count_intervals(source, np.array([0.])).tolist() == [3]
    np.testing.assert_array_equal(source, before)


@pytest.mark.parametrize("token", ["1.0000000000000000001", "NaN", "Infinity", "true", "9223372036854775808"])
def test_exact_ttl_tokens_fail(token):
    with pytest.raises(ValueError): reader.ttl_integers([token])


def test_original_integer_ttl_notation():
    assert reader.ttl_integers(["1.0", "2.000", "6e0", "-1"]).tolist() == [1, 2, 6, -1]


@pytest.mark.parametrize("a,b", [(80, 81), (83, 84), (88, 89), (82, 83), (81, 82), (80, 82)])
def test_actual_phase_dictionary_forms_not_hardcoded(a, b):
    result = reader.phase_mapping(f"learning: {a}, recognition: {b}",
                                 f"The learning trials are demarcated by: {a}. The recognition trials are demarcated by: {b}.")
    assert result == dict(learn=a, recog=b)


@pytest.mark.parametrize("kind", ["same", "nested", "private_under_source", "outputs_nested", "code", "symlink", "traversal", "existing", "existing_empty"])
def test_output_safety_preserves_source(tmp_path, kind):
    source = tmp_path/"source"; source.mkdir(); original = source/"original"; original.write_text("preserve")
    contract = tmp_path/"contract.json"; contract.write_text("{}")
    out, private = tmp_path/"out", tmp_path/"private"
    if kind == "same": out = source
    elif kind == "nested": out = source/"newdir"/"out"
    elif kind == "private_under_source": private = source/"newdir"/"private"
    elif kind == "outputs_nested": private = out/"private"
    elif kind == "code": out = TASK/"solution"/"newdir"
    elif kind == "symlink":
        link = tmp_path/"link"; link.symlink_to(source, target_is_directory=True); out = link/"out"
    elif kind == "traversal": out = str(tmp_path/"x")+"/../out"
    elif kind == "existing_empty": out.mkdir()
    else: out.mkdir(); (out/"keep").write_text("keep")
    with pytest.raises(ValueError): compute.prepare_destinations(source, contract, out, private)
    assert original.read_text() == "preserve" and not (source/"newdir").exists()


@pytest.mark.parametrize("pilot", [False, True])
def test_manufactured_nine_file_emission_and_private_schema(tmp_path, pilot):
    path = tmp_path/"fixture.nwb"; entry = synthetic_nwb(path)
    session, trials, units, records, observed = reader.read_session(path, entry)
    method = compute.load_method(TASK/"environment/method_contract.json")
    neurons, events, arrays = core.analyze(records)
    meta = compute.metadata(method, {"files":[entry]}, [session], [observed], core.POPULATIONS[1], pilot, [])
    result = core.summarize(neurons, [session], len(arrays["spike_count"]), status=meta["status"])
    output = tmp_path/"output"; output.mkdir(); private = tmp_path/"private"; private.mkdir()
    compute.write_outputs(output, private, method, [session], trials, units, neurons, events, arrays, meta, result)
    assert {p.name for p in output.iterdir()} == set(method["outputs"])
    assert json.loads((output/"run_metadata.json").read_text())["status"] == ("resource_pilot" if pilot else "complete")
    with np.load(output/"responses.npz", allow_pickle=False) as a:
        assert set(a.files) == set(method["outputs"]["responses.npz"]["arrays"])
        assert a["train_membership"].shape == (50, 4)
    assert (private/"analysis_arrays.npz").is_file()


def test_failed_input_produces_fail_closed_receipt(tmp_path, monkeypatch):
    source = tmp_path/"source"; source.mkdir()
    out = tmp_path/"output"
    monkeypatch.setattr(compute, "load_inputs", lambda *a: (_ for _ in ()).throw(ValueError("manufactured failure")))
    assert compute.main(["--data-dir", str(source), "--output-dir", str(out), "--contract-path", str(TASK/"environment/method_contract.json")]) == 1
    assert json.loads((out/"failure_report.json").read_text())["status"] == "failed_precondition"
    assert json.loads((out/"results.json").read_text())["status"] == "failed_precondition"


def test_late_failure_keeps_old_markers_but_writes_authoritative_failure(tmp_path):
    compute.write_json(tmp_path/"results.json", {"status":"complete"})
    compute.failure(tmp_path, ValueError("serialization failure"))
    assert json.loads((tmp_path/"results.json").read_text())["status"] == "complete"
    assert json.loads((tmp_path/"failure_report.json").read_text())["status"] == "failed_precondition"


def test_import_and_print_contract_are_source_free(tmp_path):
    env = {**os.environ, "PYTHONPATH":str(TASK/"solution"), "OUTPUT_DIR":str(tmp_path/"never-created"), "PYTHONDONTWRITEBYTECODE":"1"}
    result = subprocess.run([sys.executable, "-c", "import compute, source_reader, core"], env=env, capture_output=True, text=True)
    assert result.returncode == 0 and not (tmp_path/"never-created").exists()
    result = subprocess.run([sys.executable, str(TASK/"solution/compute.py"), "--print-contract", "--contract-path", str(TASK/"environment/method_contract.json")], env=env, capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)["task_id"] == "VISCAT-001"
    assert not (tmp_path/"never-created").exists()


def test_actual_shell_wrapper_fit_free_contract_cli(tmp_path):
    env = {**os.environ, "OUTPUT_DIR":str(tmp_path/"never-created"), "PYTHONDONTWRITEBYTECODE":"1"}
    result = subprocess.run(["bash", str(TASK/"solution/solve.sh"), "--print-contract", "--contract-path", str(TASK/"environment/method_contract.json")],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0 and result.stderr == ""
    assert json.loads(result.stdout)["task_id"] == "VISCAT-001" and not (tmp_path/"never-created").exists()


def test_relocated_runtime_solution_layout_and_sibling_output(tmp_path, monkeypatch):
    runtime = tmp_path/"runtime"
    solution = runtime/"solution"; solution.mkdir(parents=True)
    app = runtime/"app"; app.mkdir()
    contract = app/"method_contract.json"
    contract.write_bytes((TASK/"environment/method_contract.json").read_bytes())
    for name in ("compute.py", "source_reader.py", "core.py", "solve.sh"):
        (solution/name).write_bytes((TASK/"solution"/name).read_bytes())
    assert not (runtime/"task.toml").exists()
    output, private = app/"output", app/"private"
    env = {**os.environ, "OUTPUT_DIR":str(output), "PYTHONDONTWRITEBYTECODE":"1"}
    result = subprocess.run(["bash", str(solution/"solve.sh"), "--print-contract", "--contract-path", str(contract)],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0 and result.stderr == "" and not output.exists()
    assert json.loads(result.stdout)["task_id"] == "VISCAT-001"
    source = app/"data"/"viscat"; source.mkdir(parents=True)
    monkeypatch.setattr(compute, "__file__", str(solution/"compute.py"))
    prepared = compute.prepare_destinations(source, contract, output, private)
    assert prepared == (output, private) and all(p.is_dir() for p in prepared)
    with pytest.raises(ValueError, match="overlap"):
        compute.prepare_destinations(source, contract, solution/"new-output")


def test_frozen_public_method_and_helper_pins():
    assert hashlib.sha256((TASK/"environment/method_contract.json").read_bytes()).hexdigest() == compute.METHOD_SHA256
    assert hashlib.sha256((TASK/"environment/stage_data.py").read_bytes()).hexdigest() == compute.HELPER_SHA256
