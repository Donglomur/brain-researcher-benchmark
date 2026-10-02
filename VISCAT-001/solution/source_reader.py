"""Original-source reader adapted openly from repaired #174 source IO.

Shared h5py/TTL/link/counting implementation, not an independent validation route.
No source I/O occurs at import; category statistics live separately in core.py.
"""
from decimal import Decimal, InvalidOperation
from pathlib import PureWindowsPath
import re

import h5py
import numpy as np


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    if isinstance(value, (bytes, np.bytes_)):
        return bytes(value).decode("utf-8", errors="strict")
    require(isinstance(value, (str, np.str_)), "Expected an original scalar string")
    return str(value)


def integers(value, name, allow_float=False):
    a = np.asarray(value)
    require(a.ndim == 1, f"{name}: expected one dimension")
    if allow_float and a.dtype.kind == "f":
        require(np.isfinite(a).all() and np.equal(a, np.floor(a)).all(), f"{name}: nonintegral value")
        require(np.all(np.abs(a) < 2**53), f"{name}: unsafe floating integer")
    else:
        require(a.dtype.kind in "iu", f"{name}: expected integer dtype")
    require(not len(a) or (int(a.min()) >= -(2**63) and int(a.max()) < 2**63), f"{name}: int64 overflow")
    return a.astype(np.int64)


def unique_ids(value, name):
    a = integers(value, name)
    require(len(np.unique(a)) == len(a), f"{name}: duplicate IDs")
    return a


def ragged_offsets(value, n_rows, total, name):
    a = integers(value, name)
    require(len(a) == n_rows and np.all(np.diff(np.r_[0, a]) >= 0), f"{name}: invalid ragged offsets")
    require((int(a[-1]) if len(a) else 0) == total, f"{name}: final offset mismatch")
    return a


def phase_mapping(data_collection, description):
    match = re.fullmatch(r"learning: (\d+), recognition: (\d+)", data_collection)
    require(match is not None, "Unrecognized original experiment phase mapping")
    mapping = dict(learn=int(match[1]), recog=int(match[2]))
    require(mapping["learn"] != mapping["recog"], "Ambiguous phase IDs")
    for phase, word in [("learn", "learning"), ("recog", "recognition")]:
        found = re.findall(rf"The {word} trials are demarcated by: (\d+)\.", description)
        require(len(found) == 1 and int(found[0]) == mapping[phase], "Phase description disagrees with source mapping")
    return mapping


def ttl_integers(tokens):
    """Validate original decimal tokens before any binary floating conversion."""
    output = []
    for token in tokens:
        try:
            value = Decimal(token)
        except InvalidOperation as error:
            raise ValueError("Invalid original TTL token") from error
        require(value.is_finite() and value == value.to_integral_value(), "Nonintegral original TTL token")
        require(-(2**63) <= value < 2**63, "TTL integer overflow")
        output.append(int(value))
    return np.asarray(output, dtype=np.int64)


def count_intervals(spikes, onsets):
    """Stable-sort a copy; count every occurrence, including duplicate timestamps."""
    values = np.asarray(spikes, dtype=np.float64)
    onsets = np.asarray(onsets, dtype=np.float64)
    require(values.ndim == onsets.ndim == 1 and np.isfinite(values).all() and np.isfinite(onsets).all(), "Invalid count input")
    ordered = np.sort(values, kind="stable")
    start, end = onsets + np.float64(.2), onsets + np.float64(1.7)
    require(np.isfinite(start).all() and np.isfinite(end).all() and np.all(end > start), "Invalid response endpoints")
    return (np.searchsorted(ordered, end, side="left") - np.searchsorted(ordered, start, side="left")).astype(np.int64)


CATEGORY_VARIANTS = {
    "newolddelay": ("houses", "landscapes", "mobility", "phones", "smallAnimal"),
    "newolddelay2": ("fruit", "kids", "military", "space", "zzanimal"),
    "newolddelay3": ("1cars", "2food", "3people", "4spatial", "5animals"),
}


def hard_node(handle, path):
    node = handle
    for part in path.split("/"):
        require(isinstance(node, (h5py.File, h5py.Group)), "Invalid source hierarchy")
        require(isinstance(node.get(part, getlink=True), h5py.HardLink), "Non-hard source HDF5 link")
        node = node[part]
        if isinstance(node, h5py.Dataset):
            require(not node.is_virtual and not node.external, "External or virtual source dataset")
    return node


def category_metadata(categories, names, images):
    categories = integers(categories, "category codes")
    require(len(categories) == len(names) == len(images), "Category axis mismatch")
    require(np.all((categories >= 1) & (categories <= 5)), "Unknown original category code")
    require(all(isinstance(x, str) and x for x in names + images), "Empty category name or image path")
    path_parts = [PureWindowsPath(x).parts for x in images]
    require(all(parts for parts in path_parts), "Image path has no variant component")
    prefixes = [parts[0] for parts in path_parts]
    require(len(set(prefixes)) == 1 and prefixes[0] in CATEGORY_VARIANTS, "Unknown or mixed source variant")
    variant = prefixes[0]
    require(all(name == CATEGORY_VARIANTS[variant][int(code)-1] for code, name in zip(categories, names)),
            "Source category name disagrees with session variant")
    return categories, variant


def read_session(path, source):
    """Return public source ledgers, per-unit count inputs, and measured metadata."""
    asset = source["path"]
    with h5py.File(path, "r") as f:
        required = ["identifier", "general/subject/subject_id", "general/data_collection",
                    "session_start_time", "timestamps_reference_time",
                    "acquisition/experiment_ids", "acquisition/experiment_ids/data",
                    "acquisition/experiment_ids/timestamps", "acquisition/events/data",
                    "acquisition/events/timestamps"]
        required += ["intervals/trials/" + name for name in
                     ("id", "stim_phase", "new_old_labels_recog", "external_image_file",
                      "stimCategory", "category_name", "start_time", "stim_on_time", "stim_off_time", "stop_time")]
        required += ["general/extracellular_ephys/electrodes/" + name for name in ("id", "origChannel", "location")]
        required += ["units/" + name for name in ("id", "electrodes", "electrodes_index", "spike_times", "spike_times_index")]
        for name in required:
            hard_node(f, name)
        if "general/session_id" in f:
            hard_node(f, "general/session_id")
        subject = text(f["general/subject/subject_id"][()])
        require(subject == source["participant"], "Source subject differs from frozen manifest")
        identifier = text(f["identifier"][()])
        literal_session = text(f["general/session_id"][()]) if "general/session_id" in f else None
        phase_ids = phase_mapping(text(f["general/data_collection"][()]), text(f["acquisition/experiment_ids"].attrs["description"]))
        event_times = np.asarray(f["acquisition/events/timestamps"][:], dtype=np.float64)
        experiment_times = np.asarray(f["acquisition/experiment_ids/timestamps"][:], dtype=np.float64)
        tokens = [text(x) for x in f["acquisition/events/data"][:]]
        codes = ttl_integers(tokens)
        experiment_ids = integers(f["acquisition/experiment_ids/data"][:], "experiment IDs", allow_float=True)
        require(event_times.ndim == 1 and len(event_times) == len(codes) == len(experiment_ids), "Acquisition axis mismatch")
        require(np.isfinite(event_times).all() and np.all(np.diff(event_times) >= 0), "Invalid source event clock")
        require(np.array_equal(event_times, experiment_times), "Acquisition clocks disagree")
        clock_counts = {}
        for experiment, code, time in zip(experiment_ids, codes, event_times):
            key = (int(experiment), int(code), float(time))
            clock_counts[key] = clock_counts.get(key, 0) + 1
        table = f["intervals/trials"]
        trial_ids = unique_ids(table["id"][:], "trial IDs")
        n_trials = len(trial_ids)
        phases = [text(x) for x in table["stim_phase"][:]]
        labels = [text(x) for x in table["new_old_labels_recog"][:]]
        images = [text(x) for x in table["external_image_file"][:]]
        category_names = [text(x) for x in table["category_name"][:]]
        categories, variant = category_metadata(table["stimCategory"][:], category_names, images)
        times = {key: np.asarray(table[key][:], dtype=np.float64) for key in ["start_time", "stim_on_time", "stim_off_time", "stop_time"]}
        require(all(len(x) == n_trials for x in [phases, labels, images, categories, *times.values()]), "Trial axis mismatch")
        require(all(x.ndim == 1 and np.isfinite(x).all() for x in times.values()), "Invalid source trial timestamps")
        require(set(phases) <= {"learn", "recog"}, "Unknown trial phase")
        require(np.array_equal(times["start_time"], times["stim_on_time"]), "Source trial start differs from onset")
        require(np.all(times["stim_on_time"] <= times["stim_off_time"]), "Source onset exceeds stimulus offset")
        recognition_mask = np.asarray(phases, dtype=str) == "recog"
        full_temporal_order = ((times["start_time"] <= times["stim_on_time"])
            & (times["stim_on_time"] <= times["stim_off_time"])
            & (times["stim_off_time"] <= times["stop_time"]))
        require(np.all(full_temporal_order[recognition_mask]), "Invalid source recognition temporal order")
        learned = {image for phase, image in zip(phases, images) if phase == "learn"}
        membership = {f"code{label}_{state}_learning": 0 for label in [0, 1] for state in ["absent_from", "present_in"]}
        trials, recog_rows, decoded = [], [], []
        for row in range(n_trials):
            phase = phases[row]
            for column, ttl in [("stim_on_time", 1), ("stim_off_time", 2), ("stop_time", 6)]:
                require(clock_counts.get((phase_ids[phase], ttl, float(times[column][row])), 0) == 1, "Trial lacks a unique same-phase exact TTL link")
            included = phase == "recog"
            if included:
                require(labels[row] in {"0", "1"}, "Unknown recognition label token")
                label = int(labels[row]); in_learning = images[row] in learned
                membership[f"code{label}_{'present_in' if in_learning else 'absent_from'}_learning"] += 1
                recog_rows.append(row); decoded.append(label)
            else:
                label = in_learning = None
            trials.append(dict(asset_path=asset, source_trial_row=row, trial_id=int(trial_ids[row]), stim_phase=phase,
                category_code=int(categories[row]), category_name=category_names[row], variant_prefix=variant,
                source_label_token=labels[row], source_label=label, external_image_file=images[row], image_in_learning=in_learning,
                start_time_s=float(times["start_time"][row]), stim_on_time_s=float(times["stim_on_time"][row]),
                stim_off_time_s=float(times["stim_off_time"][row]), stop_time_s=float(times["stop_time"][row]),
                included=included, status="included_recognition" if included else "non_recognition_phase"))
        recog_rows = np.asarray(recog_rows, dtype=np.int64)
        decoded = np.asarray(decoded, dtype=np.int64)
        electrodes = f["general/extracellular_ephys/electrodes"]
        electrode_ids = unique_ids(electrodes["id"][:], "electrode IDs")
        original_channels = integers(electrodes["origChannel"][:], "original channels")
        locations = [text(x) for x in electrodes["location"][:]]
        require(len(electrode_ids) == len(original_channels) == len(locations), "Electrode axis mismatch")
        units = f["units"]
        unit_ids = unique_ids(units["id"][:], "unit IDs")
        require(f[units["electrodes"].attrs["table"]].name == electrodes.name, "Wrong electrode target table")
        links = integers(units["electrodes"][:], "electrode rows")
        link_ends = ragged_offsets(units["electrodes_index"][:], len(unit_ids), len(links), "electrode offsets")
        require(np.all(np.diff(np.r_[0, link_ends]) == 1), "Each unit must reference exactly one electrode")
        require(np.all((links >= 0) & (links < len(electrode_ids))), "Electrode row out of bounds")
        spike_ends = ragged_offsets(units["spike_times_index"][:], len(unit_ids), len(units["spike_times"]), "spike offsets")
        require("obs_intervals" not in units and "intervals/invalid_times" not in f, "Unexpected observation interval tables")
        unit_rows, records = [], []
        descents = unordered = adjacent_duplicates = duplicate_occurrences = 0
        for row, unit_id in enumerate(unit_ids):
            e_row = int(links[row]); location = locations[e_row]
            regions = [x for x in ["Hippocampus", "Amygdala"] if x in location]
            require(len(regions) <= 1, "Ambiguous unit anatomy")
            region = regions[0] if regions else None
            unit_key = f"{asset}::unit={int(unit_id)}"
            unit_rows.append(dict(asset_path=asset, unit_key=unit_key, source_unit_row=row, unit_id=int(unit_id), n_electrode_links=1,
                electrode_row=e_row, electrode_id=int(electrode_ids[e_row]), original_channel=int(original_channels[e_row]),
                location=location, included=bool(regions), region=region, exclusion_reason="included_mtl" if regions else "non_mtl_location"))
            begin = int(spike_ends[row-1]) if row else 0
            spikes = np.asarray(units["spike_times"][begin:int(spike_ends[row])], dtype=np.float64)
            require(spikes.ndim == 1 and np.isfinite(spikes).all(), "Nonfinite source spike timestamp")
            differences = np.diff(spikes)
            n_descents = int(np.count_nonzero(differences < 0))
            descents += n_descents; unordered += int(n_descents > 0)
            adjacent_duplicates += int(np.count_nonzero(differences == 0))
            duplicate_occurrences += int(len(spikes) - len(np.unique(spikes)))
            if regions:
                records.append(dict(unit_key=unit_key, asset_path=asset, subject_id=subject, unit_id=int(unit_id), region=region,
                    source_trial_row=recog_rows.copy(), trial_id=trial_ids[recog_rows].copy(), category_code=categories[recog_rows].copy(),
                    counts=count_intervals(spikes, times["stim_on_time"][recog_rows])))
        description = text(table["new_old_labels_recog"].attrs["description"])
        conflict = bool(re.search(r"0\s*=+\s*Old", description) and re.search(r"1\s*=+\s*New", description))
        def attr_text(node, attr):
            return text(node.attrs[attr]) if attr in node.attrs else None
        observed = dict(asset_path=asset, nwb_version=text(f.attrs["nwb_version"]),
            session_start_time=text(f["session_start_time"][()]), timestamps_reference_time=text(f["timestamps_reference_time"][()]),
            event_timestamp_unit=attr_text(f["acquisition/events/timestamps"], "unit"),
            experiment_timestamp_unit=attr_text(f["acquisition/experiment_ids/timestamps"], "unit"),
            spike_times_literal_unit=attr_text(units["spike_times"], "unit"), n_events=len(event_times),
            event_timestamps_finite=True, event_timestamps_nondecreasing=True, experiment_timestamps_exactly_match_events=True,
            phase_experiment_ids=phase_ids, clock_mapping_counts=dict(n_trials=n_trials, onset_exact_unique_ttl1=n_trials,
                offset_exact_unique_ttl2=n_trials, trial_end_exact_unique_ttl6=n_trials, start_equals_stim_on=n_trials),
            source_label_description=description, label_description_conflicts_with_released_code_semantics=conflict,
            label_membership_counts=membership, unit_electrode_link_counts=dict(zero=0, one=len(unit_ids), multiple=0),
            units_obs_intervals_present=False, invalid_times_present=False, observation_coverage="unknown", all_spikes_finite=True,
            all_unit_spikes_nondecreasing=unordered == 0, raw_adjacent_inversions=descents, n_unordered_units=unordered,
            raw_adjacent_duplicate_spikes=adjacent_duplicates, duplicate_timestamp_occurrences=duplicate_occurrences,
            n_learning_temporal_order_violations=int(np.count_nonzero(~full_temporal_order & ~recognition_mask)),
            n_recognition_temporal_order_violations=int(np.count_nonzero(~full_temporal_order & recognition_mask)),
            category_code_dtype=str(table["stimCategory"].dtype),
            category_name_description=attr_text(table["category_name"], "description"),
            variant_prefix=variant, category_mapping=[
                dict(category_code=code, category_name=CATEGORY_VARIANTS[variant][code-1], variant_prefix=variant,
                     n_recognition=int(np.count_nonzero(categories[recog_rows] == code)))
                for code in range(1, 6)])
        session = dict(asset_path=asset, asset_id=source["asset_id"], source_sha256=source["sha256"], subject_id=subject,
            nwb_identifier=identifier, literal_session_id=literal_session, variant_prefix=variant, n_source_trials=n_trials,
            n_learning_trials=phases.count("learn"), n_recognition_trials=len(recog_rows),
            n_new=int(np.count_nonzero(decoded == 0)), n_old=int(np.count_nonzero(decoded == 1)),
            n_source_units=len(unit_ids), n_mtl_units=len(records), n_electrodes=len(electrode_ids), status="ok")
        return session, trials, unit_rows, records, observed
