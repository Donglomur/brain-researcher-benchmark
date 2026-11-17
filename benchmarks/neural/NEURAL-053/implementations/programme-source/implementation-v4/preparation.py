"""Complete original derivative preparation, dormant without full-run admission.

No original data has been read or processed by this implementation. Real MNE,
pandas, metadata/header/drop_bad compatibility and source support remain future
qualification gates. This module imports those libraries only inside execution.
"""
import csv
import io
from collections import Counter, defaultdict
from pathlib import Path
from cohort import CANONICAL, require, validate_roster, partition_images
from io_support import (admit_full_run, authenticate_file, checked_bytes, safe_relative,
                        object_digest)

EYE_CHANNELS = ("UADC009-2104", "UADC010-2104", "UADC013-2104")
SOURCE_SPEC_OBJECT_SHA256 = "d17c8ed34ba8742d0de30b2fc380feb58606d56bd72358d0ab5cabcc48f87a37"
SENSOR_ORDER_SHA256 = "d3dbdf660a757a4a03a607084c2df0f6dbe3ba4f9b4bf2b5d6b90c8b76409dc1"


def integer(value):
    import math
    x = float(value)
    require(math.isfinite(x) and x.is_integer(), "Integral original identity")
    return int(x)


def read_table(root, relative, manifest, budget, delimiter=","):
    require(relative in manifest, "Independently admitted original metadata descriptor")
    raw = checked_bytes(safe_relative(root, relative), manifest[relative], budget)
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")), delimiter=delimiter)
    require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames),
            "Unique original table header")
    rows = list(reader)
    require(all(None not in row and None not in row.values() for row in rows), "Complete table rows")
    return rows


def source_metadata(root, admitted_metadata, budget):
    expected_paths = {f"sourcedata/sample_attributes_P{p}.csv" for p in range(1, 5)}
    expected_paths |= {f"sub-BIGMEG{p}/ses-{s:02}/meg/sub-BIGMEG{p}_ses-{s:02}_task-main_run-{r:02}_events.tsv"
                       for p in range(1, 5) for s in range(1, 13) for r in range(1, 11)}
    require(set(admitted_metadata) == expected_paths, "All four attributes and 480 event tables")
    all_attrs, experimental = {}, []
    for p, person in enumerate(CANONICAL.people, 1):
        attrs = read_table(root, f"sourcedata/sample_attributes_P{p}.csv", admitted_metadata, budget)
        require(len(attrs) == 27048, "Complete original 27,048 epoch attributes")
        grouped = defaultdict(list)
        for epoch, row in enumerate(attrs):
            grouped[(integer(row["session_nr"]), integer(row["run_nr"]))].append((epoch, row))
        require(set(grouped) == {(s, r) for s in range(1, 13) for r in range(1, 11)},
                "All sessions/runs including BIGMEG4 session02")
        kinds = Counter()
        for (session, run), group in sorted(grouped.items()):
            rel = f"sub-{person}/ses-{session:02}/meg/sub-{person}_ses-{session:02}_task-main_run-{run:02}_events.tsv"
            events = read_table(root, rel, admitted_metadata, budget, "\t")
            require(len(events) == len(group), "Exact event-to-attribute row join")
            prior_sample = -1
            for run_row, ((epoch, attr), event) in enumerate(zip(group, events)):
                kind = attr["trial_type"]
                require(kind == event["trial_type"] and kind in ("exp", "test", "catch"), "Exact trial role")
                kinds[kind] += 1
                sample = integer(event["sample"])
                require(sample > prior_sample and abs(float(event["onset"]) - sample / 1200) <= 1e-9,
                        "Strict optical-corrected sample/onset order")
                require(abs(float(event["duration"]) - .5) <= 1e-12, "Original presentation duration")
                prior_sample = sample
                if kind == "catch":
                    continue
                image, category = integer(attr["things_image_nr"]), integer(attr["things_category_nr"])
                require(image == integer(event["value"]) and category == integer(event["things_category_nr"]),
                        "Original global image/class identity join")
                if kind == "exp":
                    experimental.append({"person": person, "epoch_index": epoch, "session": session,
                                         "run": run, "run_row": run_row, "image_id": image,
                                         "category_id": category, "corrected_sample": sample})
        require(kinds == {"exp": 22248, "test": 2400, "catch": 2400}, "Complete original trial support")
        all_attrs[person] = attrs
    experimental.sort(key=lambda r: (r["person"], r["epoch_index"]))
    query, _ = partition_images({r["image_id"]: r["category_id"] for r in experimental})
    for row in experimental:
        row["partition"] = "query" if row["image_id"] in query else "training"
    validate_roster(experimental)
    return all_attrs, experimental


def finite_summary(values, axis=-1):
    import numpy as np
    values = np.asarray(values, dtype=np.float64)
    mask = np.isfinite(values)
    count = mask.sum(axis=axis)
    expanded = np.expand_dims(np.maximum(count, 1), axis)
    mean = np.sum(np.where(mask, values, 0) / expanded, axis=axis)
    require(np.isfinite(mean).all() and (np.abs(mean) <= np.finfo(np.float32).max).all(),
            "Finite representable mean, without clipping")
    return mean.astype(np.float32), (count / values.shape[axis]).astype(np.float32)


def neural_summary(data, times, channel_names, expected_names):
    import numpy as np
    data, times = np.asarray(data), np.asarray(times, dtype=np.float64)
    require(data.ndim == 3 and data.shape[1:] == (271, 281), "Full 271-sensor/281-sample epochs")
    require(len(channel_names) == len(set(channel_names)) == 271 and
            set(channel_names) == set(expected_names), "Exact processed channel identities")
    ticks = np.arange(-20, 261)
    require(times.shape == (281,) and np.allclose(times, ticks / 200, atol=1e-9, rtol=0),
            "Complete -100..1300ms 200Hz clock")
    order = [channel_names.index(name) for name in expected_names]
    # Onset-relative ticks20..59 are epoch array offsets40..79.
    return finite_summary(data[:, order, 40:80])


def meg_person(root, person, attrs, rows, sensors, budget):
    import mne
    import numpy as np
    base = safe_relative(root, f"derivatives/preprocessed/preprocessed_P{person[-1]}-epo.fif")
    # Read the stored author-processed values without activating extra SSP.
    epochs = mne.read_epochs(base, preload=False, proj=False, verbose="ERROR")
    require(len(epochs) == 27048 and float(epochs.info["sfreq"]) == 200, "Complete processed epoch count/clock")
    require(epochs.metadata is not None and len(epochs.metadata) == 27048, "Actual metadata required")
    require(set(epochs.ch_names) == set(sensors) and len(epochs.ch_names) == 271,
            "Exact actual processed header, not missing raw sidecar inference")
    require(all(mne.channel_type(epochs.info, i) == "mag" for i in range(271)), "Original processed MEG kinds")
    for index, attr in enumerate(attrs):
        meta = epochs.metadata.iloc[index]
        require(meta["trial_type"] == attr["trial_type"] and
                integer(meta["session_nr"]) == integer(attr["session_nr"]) and
                integer(meta["run_nr"]) == integer(attr["run_nr"]), "Full-role metadata/epoch join")
        if attr["trial_type"] != "catch":
            require(integer(meta["things_image_nr"]) == integer(attr["things_image_nr"]) and
                    integer(meta["things_category_nr"]) == integer(attr["things_category_nr"]) and
                    integer(epochs.events[index, 2]) == integer(attr["things_image_nr"]),
                    "Exact final epoch/image/class/event-code join after source drop_bad reconstruction")
    means = np.empty((22248, 271), dtype=np.float32)
    fractions = np.empty_like(means)
    for start in range(0, len(rows), 16):
        budget.check_clock()
        chosen = rows[start:start + 16]
        data = epochs[[r["epoch_index"] for r in chosen]].get_data(picks=epochs.ch_names)
        mean, fraction = neural_summary(data, epochs.times, epochs.ch_names, sensors)
        means[start:start + len(chosen)], fractions[start:start + len(chosen)] = mean, fraction
    return means, fractions


def eye_selection(display_ms, start):
    import numpy as np
    require(type(start) is int and start >= 0, "Nonnegative original eye ordinal")
    display_ms = np.asarray(display_ms, dtype=np.float64)
    ordinal = np.arange(start, start + len(display_ms))
    require((ordinal < 1681).all() and np.isfinite(display_ms).all() and
            np.all(np.abs(display_ms - (-100 + ordinal * (1000 / 1200))) <= .51),
            "Full original ocular ordinal/rounded-ms order")
    return (ordinal >= 240) & (ordinal < 480)


def eye_person(root, person, rows, budget):
    import numpy as np
    import pandas as pd
    index = {r["image_id"]: i for i, r in enumerate(rows)}
    sums, counts = np.zeros((22248, 3)), np.zeros((22248, 3), dtype=np.int64)
    support, total = np.zeros(22248, dtype=np.int64), np.zeros(22248, dtype=np.int64)
    cols = ["time", *EYE_CHANNELS, "trial_type", "things_image_nr", "things_category_nr", "session_nr", "run_nr"]
    for session in range(1, 13):
        path = safe_relative(root, f"derivatives/preprocessed/eyes_epoched_cleaned_P{person[-1]}_S{session}.csv")
        for chunk in pd.read_csv(path, usecols=cols, chunksize=100000):
            budget.check_clock()
            for image, group in chunk[chunk["trial_type"] == "exp"].groupby("things_image_nr", sort=False):
                image = integer(image)
                require(image in index, "Original ocular experimental image")
                i = index[image]
                row = rows[i]
                require((group["things_category_nr"] == row["category_id"]).all() and
                        (group["session_nr"] == session).all() and row["session"] == session and
                        (group["run_nr"] == row["run"]).all(), "Exact ocular/MEG full identity join")
                selected = eye_selection(group["time"].to_numpy(float), int(total[i]))
                total[i] += len(group)
                values = group.loc[selected, list(EYE_CHANNELS)].to_numpy(float)
                valid = np.isfinite(values)
                support[i] += len(values)
                counts[i] += valid.sum(axis=0)
                # At most240 selected samples per image. Overflow is failure below.
                sums[i] += np.where(valid, values, 0).sum(axis=0)
    require((total == 1681).all() and (support == 240).all(), "All original ocular samples without row removal")
    means = sums / np.maximum(counts, 1)
    require(np.isfinite(means).all() and (np.abs(means) <= np.finfo(np.float32).max).all(), "Finite ocular means")
    return means.astype(np.float32), (counts / 240).astype(np.float32)


def prepare_full_original(root, source_spec, metadata_manifest, sensors, permit,
                          expected_bindings, approved_receipts, budget):
    """Actual complete path; refuses before source operands without full authority.

    source_spec is the pinned64-descriptor projection; metadata_manifest supplies
    independently authenticated484 original-table descriptors, never invented
    from observed response values. The full-run receipt binds both and sensors.
    """
    admit_full_run(permit, expected_bindings, approved_receipts, "prepare_original")
    require(object_digest(source_spec) == SOURCE_SPEC_OBJECT_SHA256 and
            object_digest(sensors) == SENSOR_ORDER_SHA256, "Exact frozen64-asset and271-channel source definitions")
    require(expected_bindings.get("source_spec") == object_digest(source_spec) and
            expected_bindings.get("metadata_manifest") == object_digest(metadata_manifest) and
            expected_bindings.get("sensor_order") == object_digest(sensors), "Exact original input bindings")
    assets = source_spec["derivative_assets"]
    require(len(assets) == 64 and len({a["path"] for a in assets}) == 64 and
            sum(a["bytes"] for a in assets) == 66179063749,
            "All64 declared original derivative bodies")
    require(source_spec["dataset"] == "ds004212" and source_spec["version"] == "2.0.1" and
            source_spec["commit"] == "5405e3ef6478cd55da62d14c9340b4f95f620b03", "Pinned original release")
    require(len(sensors) == len(set(sensors)) == 271, "Canonical processed sensor order")
    before = {a["path"]: authenticate_file(safe_relative(root, a["path"]), a, budget) for a in assets}
    attrs, rows = source_metadata(root, metadata_manifest, budget)
    import numpy as np
    neural, ocular = np.empty((88992, 542), np.float32), np.empty((88992, 6), np.float32)
    for person in CANONICAL.people:
        selected = [(i, r) for i, r in enumerate(rows) if r["person"] == person]
        indices, owned = [x[0] for x in selected], [x[1] for x in selected]
        mean, fraction = meg_person(root, person, attrs[person], owned, sensors, budget)
        eye, eye_fraction = eye_person(root, person, owned, budget)
        neural[indices] = np.column_stack((mean, fraction))
        ocular[indices] = np.column_stack((eye, eye_fraction))
    for asset in assets:
        require(authenticate_file(safe_relative(root, asset["path"]), asset, budget) == before[asset["path"]],
                "Complete original input stable through preparation")
    require(np.isfinite(neural).all() and np.isfinite(ocular).all(), "Complete finite prepared summaries")
    return rows, {"neural": neural, "ocular": ocular}, {
        "schema": "neural053_original_preparation_v1", "experimental_rows": 88992,
        "source_spec": object_digest(source_spec), "metadata_manifest": object_digest(metadata_manifest),
        "window": "100<=t<300ms", "method_or_scientific_qualification": False,
        "limitations": ["Retrospective author preprocessing", "No source-body execution occurred during construction",
                        "Actual full header/drop_bad mapping compatibility requires this path's future successful admission"]}
