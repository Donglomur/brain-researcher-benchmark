"""Generic nine-file writer plus explicitly manufactured tiny test source basis."""
import copy
import csv
import json
from pathlib import Path

import numpy as np
import io_contract as io
import category_statistics as stats
import population_contract as population


def dump_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def write_csv(path, rows, columns):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader(); writer.writerows(rows)


def emit(output, ref, headline=population.POPULATIONS[1]):
    output = io.safe_path(output)
    io.require(not output.exists(), "Refuse existing output")
    output.mkdir(parents=True)
    derived = population.analyze(ref)
    for filename, rows in (("sessions.csv", ref["sessions"]), ("trials.csv", ref["trials"]),
            ("units.csv", ref["units"]), ("neurons.csv", derived["neurons"]), ("split_events.csv", derived["split_events"])):
        columns = ref["method"]["outputs"][filename]["columns"]
        with (output/filename).open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader(); writer.writerows(rows)
    with (output/"responses.npz").open("xb") as stream: np.savez_compressed(stream, **ref["arrays"])
    dump_json(output/"results.json", population.summarize(ref, derived["neurons"], headline))
    metadata = copy.deepcopy(ref["metadata"]); metadata["headline_population"] = headline
    dump_json(output/"run_metadata.json", metadata)
    with (output/"findings.md").open("x", encoding="utf-8") as stream:
        stream.write("Descriptive released-event category selection summaries; source identity and numerical receipts are provided.\n")
    return output


def manufactured_reference(categories=None):
    method_path = Path(__file__).resolve().parents[1]/"environment/method_contract.json"
    method = io.authenticated_json(method_path, io.METHOD_SHA256)
    asset, subject, variant = "sub-fixture/session.nwb", "fixture-subject", "newolddelay"
    categories = np.repeat(np.arange(1, 6), 10) if categories is None else np.asarray(categories, dtype=np.int64)
    trials = []
    for row, code in enumerate([1, 2, 3, 4, 5]+categories.tolist()):
        included = row >= 5; on = 100.0+4*row
        trials.append(dict(asset_path=asset, source_trial_row=row, trial_id=5000+3*row,
            stim_phase="recog" if included else "learn", category_code=code,
            category_name=method["source"]["category_variants"][variant][code-1], variant_prefix=variant,
            source_label_token=str(row % 2) if included else "-1", source_label=row % 2 if included else None,
            external_image_file=f"{variant}\\category{code}\\image{row}.jpg", image_in_learning=False if included else None,
            start_time_s=on, stim_on_time_s=on, stim_off_time_s=on+1, stop_time_s=on+2, included=included,
            status="included_recognition" if included else "non_recognition_phase"))
    units = [dict(asset_path=asset, unit_key=asset+"::unit="+str(uid), source_unit_row=row, unit_id=uid,
        n_electrode_links=1, electrode_row=row, electrode_id=100+row, original_channel=3+row,
        location="Left Hippocampus", included=True, region="Hippocampus", exclusion_reason="included_mtl")
        for row, uid in enumerate([9, 4, 19])]
    sessions = [dict(asset_path=asset, asset_id="fixture-asset", source_sha256="c"*64, subject_id=subject,
        nwb_identifier="fixture-session", literal_session_id=None, variant_prefix=variant, n_source_trials=len(trials),
        n_learning_trials=5, n_recognition_trials=len(categories), n_new=sum(r["source_label"] == 0 for r in trials),
        n_old=sum(r["source_label"] == 1 for r in trials), n_source_units=3, n_mtl_units=3, n_electrodes=3, status="ok")]
    counts = [np.where(categories == 1, 30, 0).astype(np.int64), np.full(len(categories), 3, dtype=np.int64),
              np.where(categories == 1, 0, 10).astype(np.int64)]
    if np.any(categories == 1): counts[2][np.flatnonzero(categories == 1)[-1]] = 1000
    recognition = trials[5:]
    arrays = dict(unit_key=np.asarray([u["unit_key"] for u in units]),
        response_unit_index=np.repeat(np.arange(3), len(categories)),
        source_trial_row=np.tile([r["source_trial_row"] for r in recognition], 3).astype(np.int64),
        trial_id=np.tile([r["trial_id"] for r in recognition], 3).astype(np.int64),
        category_code=np.tile(categories, 3), spike_count=np.concatenate(counts), repeat_id=np.arange(50, dtype=np.int64))
    arrays["rate_hz"] = arrays["spike_count"]/1.5
    arrays["train_membership"] = stats.make_membership([categories]*3)[0]
    observation = dict(asset_path=asset, nwb_version="2.2.5", session_start_time="fixture-time", timestamps_reference_time="fixture-time",
        event_timestamp_unit="seconds", experiment_timestamp_unit="seconds", spike_times_literal_unit=None,
        n_events=3*len(trials), event_timestamps_finite=True, event_timestamps_nondecreasing=True,
        experiment_timestamps_exactly_match_events=True, phase_experiment_ids=dict(learn=1, recog=2),
        clock_mapping_counts={key:len(trials) for key in ("n_trials", "onset_exact_unique_ttl1", "offset_exact_unique_ttl2", "trial_end_exact_unique_ttl6", "start_equals_stim_on")},
        source_label_description="0 == Old, 1 == New", label_description_conflicts_with_released_code_semantics=True,
        label_membership_counts=dict(code0_absent_from_learning=sessions[0]["n_new"], code0_present_in_learning=0,
                                     code1_absent_from_learning=sessions[0]["n_old"], code1_present_in_learning=0),
        unit_electrode_link_counts=dict(zero=0, one=3, multiple=0), units_obs_intervals_present=False, invalid_times_present=False,
        observation_coverage="unknown", all_spikes_finite=True, all_unit_spikes_nondecreasing=False,
        raw_adjacent_inversions=1, n_unordered_units=1, raw_adjacent_duplicate_spikes=0, duplicate_timestamp_occurrences=1,
        n_learning_temporal_order_violations=0, n_recognition_temporal_order_violations=0,
        category_code_dtype="uint8", category_name_description="Source category", variant_prefix=variant,
        category_mapping=[dict(category_code=c, category_name=method["source"]["category_variants"][variant][c-1],
            variant_prefix=variant, n_recognition=int(np.count_nonzero(categories == c))) for c in stats.CATEGORIES])
    metadata = dict(status="complete", task_id="VISCAT-001", dandiset_id="000004", published_version="0.220126.1852",
        source_manifest_sha256=io.SOURCE_SHA256, method_contract_sha256=io.METHOD_SHA256, source_sha256={asset:"c"*64},
        method_contract=method, headline_population=population.POPULATIONS[1], software_versions={"synthetic":"fixture"}, warnings=[],
        source_observed=dict(n_sessions=1, n_patients=1, n_source_trials=len(trials), n_recognition_trials=len(categories),
                             n_source_units=3, n_mtl_units=3, sessions=[observation]))
    return dict(method=method, sessions=sessions, trials=trials, units=units, arrays=arrays, metadata=metadata)


def mutate_json(path, change):
    value = io.json_load(path); change(value)
    with Path(path).open("w", encoding="utf-8") as stream: json.dump(value, stream, allow_nan=False)


def mutate_npz(path, change):
    with np.load(path, allow_pickle=False) as z: arrays = {k:z[k] for k in z.files}
    change(arrays)
    with Path(path).open("wb") as stream: np.savez_compressed(stream, **arrays)
