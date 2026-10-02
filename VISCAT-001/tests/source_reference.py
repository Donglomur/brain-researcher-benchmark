"""Independent source reconstruction using h5py, bisect and Counter statistics.

No oracle, staging-helper code, prior bank or generated response arrays are input.
Low-level HDF5 decoding and PCG64 are shared dependencies, explicitly disclosed.
"""
from __future__ import annotations

from bisect import bisect_left
from collections import Counter
from pathlib import Path, PureWindowsPath
import platform
import re

import h5py
import numpy as np

import category_statistics as math_core
import io_contract as io

require = io.require


def source_text(value):
    if isinstance(value, (bytes, np.bytes_)): return bytes(value).decode("utf-8", errors="strict")
    require(isinstance(value, (str, np.str_)), "Literal source text required")
    return str(value)


def vector(value, name):
    a = np.asarray(value, dtype=np.float64)
    require(a.ndim == 1 and np.isfinite(a).all(), f"{name}: finite vector required")
    return a


def ids(value, name, unique=False):
    a = math_core.integers(value, name)
    if unique: require(len(set(map(int, a))) == len(a), f"{name}: duplicate identity")
    return list(map(int, a))


def ragged_ends(value, n_rows, length):
    result = ids(value, "ragged offsets")
    require(len(result) == n_rows and all(a <= b for a, b in zip([0]+result, result)), "Invalid ragged offsets")
    require((result[-1] if result else 0) == length, "Invalid ragged final offset")
    return [0]+result


def safe_hdf5(root):
    """Reject external links, virtual arrays and external raw storage, metadata only."""
    seen = set()
    def visit(group):
        address = h5py.h5o.get_info(group.id).addr
        if address in seen: return
        seen.add(address)
        for key in group:
            link = group.get(key, getlink=True)
            require(not isinstance(link, h5py.ExternalLink), "External HDF5 link forbidden")
            item = group[key]
            require(item.file.filename == root.filename, "External HDF5 object forbidden")
            if isinstance(item, h5py.Group): visit(item)
            else: require(not item.is_virtual and not item.external, "External/virtual HDF5 storage forbidden")
    visit(root)


def count_intervals(raw_spikes, onsets):
    spikes = vector(raw_spikes, "spike times")
    onset = vector(onsets, "recognition onsets")
    ordered = sorted(map(float, spikes))
    result = []
    for time in onset:
        left, right = time+np.float64(.2), time+np.float64(1.7)
        require(np.isfinite(left) and np.isfinite(right) and right > left, "Invalid response endpoints")
        result.append(bisect_left(ordered, float(right))-bisect_left(ordered, float(left)))
    return np.asarray(result, dtype=np.int64)


def read_asset(path, record, method):
    asset = record["path"]
    trials, unit_rows, responses = [], [], []
    with h5py.File(io.regular(path), "r") as f:
        safe_hdf5(f)
        subject = source_text(f["general/subject/subject_id"][()])
        require(subject == record["participant"], "Original subject mismatch")
        declaration = source_text(f["general/data_collection"][()])
        parsed = re.fullmatch(r"learning: (\d+), recognition: (\d+)", declaration)
        require(parsed is not None, "Unknown source phase declaration")
        phases = dict(zip(("learn", "recog"), map(int, parsed.groups())))
        require(phases["learn"] != phases["recog"], "Ambiguous source phase codes")
        experiment_description = source_text(f["acquisition/experiment_ids"].attrs["description"])
        for phase, term in (("learn", "learning"), ("recog", "recognition")):
            matches = re.findall(rf"The {term} trials are demarcated by: (\d+)\.", experiment_description)
            require(len(matches) == 1 and int(matches[0]) == phases[phase], "Inconsistent phase description")
        event_times = vector(f["acquisition/events/timestamps"][:], "event timestamps")
        experiment_times = vector(f["acquisition/experiment_ids/timestamps"][:], "experiment timestamps")
        codes = [io.integer(source_text(v)) for v in f["acquisition/events/data"][:]]
        experiments = [io.integer(v.item() if isinstance(v, np.generic) else v)
                       for v in f["acquisition/experiment_ids/data"][:]]
        require(len(event_times) == len(codes) == len(experiments), "Acquisition axes mismatch")
        require(np.array_equal(event_times, experiment_times) and np.all(np.diff(event_times) >= 0), "Invalid common source clock")
        clock = Counter(zip(experiments, codes, map(float, event_times)))
        table = f["intervals/trials"]
        trial_ids = ids(table["id"][:], "trial IDs", True)
        n = len(trial_ids)
        phases_by_row = [source_text(v) for v in table["stim_phase"][:]]
        labels = [source_text(v) for v in table["new_old_labels_recog"][:]]
        images = [source_text(v) for v in table["external_image_file"][:]]
        category_codes = ids(table["stimCategory"][:], "category codes")
        names = [source_text(v) for v in table["category_name"][:]]
        times = {key: vector(table[key][:], key) for key in ("start_time", "stim_on_time", "stim_off_time", "stop_time")}
        require(all(len(v) == n for v in [phases_by_row, labels, images, category_codes, names, *times.values()]), "Trial axis mismatch")
        require(set(phases_by_row) <= {"learn", "recog"}, "Unknown trial phase")
        learned = {image for phase, image in zip(phases_by_row, images) if phase == "learn"}
        label_membership = {f"code{code}_{kind}_learning": 0 for code in (0, 1) for kind in ("absent_from", "present_in")}
        prefixes = []
        for row, trial_id in enumerate(trial_ids):
            parts = PureWindowsPath(images[row]).parts
            require(bool(parts), "Missing source image path")
            prefix = parts[0]; prefixes.append(prefix)
            variants = method["source"]["category_variants"]
            code = category_codes[row]
            require(prefix in variants and code in math_core.CATEGORIES and names[row] == variants[prefix][code-1], "Unknown/conflicting source category dictionary")
            start, on, off, stop = [float(times[key][row]) for key in times]
            phase = phases_by_row[row]
            require(start == on and on <= off and (phase != "recog" or off <= stop), "Invalid original trial timing")
            for event_code, timestamp in ((1, on), (2, off), (6, stop)):
                require(clock[(phases[phase], event_code, timestamp)] == 1, "Missing/ambiguous original TTL mapping")
            included = phase == "recog"
            source_label = image_in_learning = None
            if included:
                require(labels[row] in ("0", "1"), "Unknown original recognition label")
                source_label, image_in_learning = int(labels[row]), images[row] in learned
                kind = "present_in" if image_in_learning else "absent_from"
                label_membership[f"code{source_label}_{kind}_learning"] += 1
            trials.append(dict(asset_path=asset, source_trial_row=row, trial_id=trial_id, stim_phase=phase,
                category_code=code, category_name=names[row], variant_prefix=prefix, source_label_token=labels[row],
                source_label=source_label, external_image_file=images[row], image_in_learning=image_in_learning,
                start_time_s=start, stim_on_time_s=on, stim_off_time_s=off, stop_time_s=stop, included=included,
                status="included_recognition" if included else "non_recognition_phase"))
        require(len(set(prefixes)) == 1, "Mixed session category variants")
        variant = prefixes[0]
        recognition = [row for row in trials if row["included"]]
        electrodes = f["general/extracellular_ephys/electrodes"]
        electrode_ids = ids(electrodes["id"][:], "electrode IDs", True)
        channels = ids(electrodes["origChannel"][:], "original channels")
        locations = [source_text(v) for v in electrodes["location"][:]]
        require(len(electrode_ids) == len(channels) == len(locations), "Electrode axes mismatch")
        units = f["units"]
        unit_ids = ids(units["id"][:], "unit IDs", True)
        require(f[units["electrodes"].attrs["table"]].name == electrodes.name, "Incorrect electrode table link")
        links = ids(units["electrodes"][:], "electrode rows")
        link_ends = ragged_ends(units["electrodes_index"][:], len(unit_ids), len(links))
        spike_ends = ragged_ends(units["spike_times_index"][:], len(unit_ids), len(units["spike_times"]))
        require(all(b-a == 1 for a, b in zip(link_ends, link_ends[1:])), "Each unit must have one electrode link")
        require("obs_intervals" not in units and "intervals/invalid_times" not in f, "Unexpected observation table")
        inversion = unordered = adjacent_duplicate = duplicate = 0
        for row, unit_id in enumerate(unit_ids):
            erow = links[link_ends[row]]
            require(0 <= erow < len(electrode_ids), "Electrode row outside table")
            location = locations[erow]
            region = [r for r in ("Hippocampus", "Amygdala") if r in location]
            require(len(region) <= 1, "Ambiguous source anatomy")
            key = asset+"::unit="+str(unit_id)
            unit_rows.append(dict(asset_path=asset, unit_key=key, source_unit_row=row, unit_id=unit_id,
                n_electrode_links=1, electrode_row=erow, electrode_id=electrode_ids[erow], original_channel=channels[erow],
                location=location, included=bool(region), region=region[0] if region else None,
                exclusion_reason="included_mtl" if region else "non_mtl_location"))
            raw = vector(units["spike_times"][spike_ends[row]:spike_ends[row+1]], "original spike vector")
            changes = np.diff(raw); n_inv = int(np.count_nonzero(changes < 0))
            inversion += n_inv; unordered += int(n_inv > 0)
            adjacent_duplicate += int(np.count_nonzero(changes == 0)); duplicate += len(raw)-len(set(map(float, raw)))
            if region:
                counts = count_intervals(raw, [r["stim_on_time_s"] for r in recognition])
                responses.append((key, recognition, counts))
        def attr(node, key): return source_text(node.attrs[key]) if key in node.attrs else None
        label_description = attr(table["new_old_labels_recog"], "description")
        description = label_description or ""
        observed = dict(asset_path=asset, nwb_version=source_text(f.attrs["nwb_version"]),
            session_start_time=source_text(f["session_start_time"][()]), timestamps_reference_time=source_text(f["timestamps_reference_time"][()]),
            event_timestamp_unit=attr(f["acquisition/events/timestamps"], "unit"),
            experiment_timestamp_unit=attr(f["acquisition/experiment_ids/timestamps"], "unit"),
            spike_times_literal_unit=attr(units["spike_times"], "unit"), n_events=len(event_times),
            event_timestamps_finite=True, event_timestamps_nondecreasing=True, experiment_timestamps_exactly_match_events=True,
            phase_experiment_ids=phases, clock_mapping_counts=dict(n_trials=n, onset_exact_unique_ttl1=n,
                offset_exact_unique_ttl2=n, trial_end_exact_unique_ttl6=n, start_equals_stim_on=n),
            source_label_description=label_description,
            label_description_conflicts_with_released_code_semantics=bool(re.search(r"0\s*=+\s*Old", description) and re.search(r"1\s*=+\s*New", description)),
            label_membership_counts=label_membership, unit_electrode_link_counts=dict(zero=0, one=len(unit_ids), multiple=0),
            units_obs_intervals_present=False, invalid_times_present=False, observation_coverage="unknown", all_spikes_finite=True,
            all_unit_spikes_nondecreasing=unordered == 0, raw_adjacent_inversions=inversion, n_unordered_units=unordered,
            raw_adjacent_duplicate_spikes=adjacent_duplicate, duplicate_timestamp_occurrences=duplicate,
            n_learning_temporal_order_violations=sum(r["stim_phase"] == "learn" and not
                (r["start_time_s"] <= r["stim_on_time_s"] <= r["stim_off_time_s"] <= r["stop_time_s"]) for r in trials),
            n_recognition_temporal_order_violations=sum(r["stim_phase"] == "recog" and not
                (r["start_time_s"] <= r["stim_on_time_s"] <= r["stim_off_time_s"] <= r["stop_time_s"]) for r in trials),
            category_code_dtype=str(table["stimCategory"].dtype), category_name_description=attr(table["category_name"], "description"),
            variant_prefix=variant, category_mapping=[dict(category_code=c, category_name=method["source"]["category_variants"][variant][c-1],
                variant_prefix=variant, n_recognition=sum(r["category_code"] == c for r in recognition)) for c in math_core.CATEGORIES])
        session = dict(asset_path=asset, asset_id=record["asset_id"], source_sha256=record["sha256"], subject_id=subject,
            nwb_identifier=source_text(f["identifier"][()]),
            literal_session_id=source_text(f["general/session_id"][()]) if "general/session_id" in f else None,
            variant_prefix=variant, n_source_trials=n, n_learning_trials=n-len(recognition), n_recognition_trials=len(recognition),
            n_new=sum(r["source_label"] == 0 for r in recognition), n_old=sum(r["source_label"] == 1 for r in recognition),
            n_source_units=len(unit_rows), n_mtl_units=len(responses), n_electrodes=len(electrode_ids), status="ok")
    return session, trials, unit_rows, responses, observed


def load_reference(source_dir="/app/data/viscat", method_path="/app/method_contract.json", pilot=False, progress=None):
    method = io.authenticated_json(method_path, io.METHOD_SHA256)
    root, manifest = io.authenticate_source(source_dir)
    records = sorted(manifest["files"], key=lambda r: r["path"])
    selected = records[:1] if pilot else records
    ref = dict(method=method, sessions=[], trials=[], units=[])
    fields = {key: [] for key in ("unit_key", "response_unit_index", "source_trial_row", "trial_id", "category_code", "spike_count")}
    observed, categories = [], []
    for record in selected:
        session, trials, units, responses, observation = read_asset(root/record["path"], record, method)
        ref["sessions"].append(session); ref["trials"].extend(trials); ref["units"].extend(units); observed.append(observation)
        for key, rows, counts in responses:
            index = len(fields["unit_key"]); fields["unit_key"].append(key)
            fields["response_unit_index"].extend([index]*len(rows))
            for name in ("source_trial_row", "trial_id", "category_code"): fields[name].extend(r[name] for r in rows)
            fields["spike_count"].extend(map(int, counts)); categories.append(np.asarray([r["category_code"] for r in rows], dtype=np.int64))
        if progress: progress(dict(asset_path=record["path"], n_mtl_units=session["n_mtl_units"]))
    arrays = {key: np.asarray(value, dtype=str if key == "unit_key" else np.int64) for key, value in fields.items()}
    arrays["rate_hz"] = arrays["spike_count"]/1.5
    arrays["repeat_id"] = np.arange(math_core.N_REPEATS, dtype=np.int64)
    arrays["train_membership"] = math_core.make_membership(categories)[0]
    ref["arrays"] = arrays
    status = "resource_pilot" if pilot else "complete"
    source_observed = dict(n_sessions=len(selected), n_patients=len({r["subject_id"] for r in ref["sessions"]}),
        n_source_trials=len(ref["trials"]), n_recognition_trials=sum(r["included"] for r in ref["trials"]),
        n_source_units=len(ref["units"]), n_mtl_units=len(arrays["unit_key"]), sessions=observed)
    if not pilot:
        structural = method["source"]["structural_counts_not_outcome_targets"]
        require(source_observed["n_sessions"] == structural["n_sessions"] and source_observed["n_patients"] == structural["n_subject_ids"]
                and source_observed["n_recognition_trials"] == structural["n_recognition_rows"], "Frozen source cohort mismatch")
        require(dict(Counter(r["variant_prefix"] for r in ref["sessions"])) == structural["variant_sessions"], "Frozen category variants mismatch")
        require(all(r["n_recognition"] == structural["recognition_per_category_per_session"]
                    for session in observed for r in session["category_mapping"]), "Frozen category support mismatch")
    ref["metadata"] = dict(status=status, task_id="VISCAT-001", dandiset_id="000004", published_version="0.220126.1852",
        source_manifest_sha256=io.SOURCE_SHA256, method_contract_sha256=io.METHOD_SHA256,
        source_sha256={r["path"]: r["sha256"] for r in records}, method_contract=method,
        headline_population="crossfit_selected_at_least_five_splits", source_observed=source_observed,
        software_versions=dict(python=platform.python_version(), numpy=np.__version__, h5py=h5py.__version__,
                               counting="sorted-copy bisect multiset", statistics="Counter Fraction KW closed-df4-tail integer pairwise AUC"), warnings=[])
    if pilot: ref["metadata"]["resource_pilot_scope"] = dict(asset_path=selected[0]["path"], n_processed_assets=1)
    return ref
