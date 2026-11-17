"""Actual full-source pooling without fitted EEG normalization.

Trusted operator API only. The caller selects this package's accepted private
and public import roots before calling. All scientific imports are lazy. No data
or library is opened by importing this source module. Released derivative units,
offline preprocessing and exposed media remain explicit; no source descriptor
or logical Owner grants empirical-input, native, or execution qualification.
"""
from __future__ import annotations

import math
from pathlib import Path, PurePosixPath
import stat

JOIN_SHA = "fa3b05a001c897327990d60f13ba0969cced17a4f1aa1e6a5b64cb284148cd24"
REQUIRED_SHA = "629f374eb781cb37ae207b295d7ab4aa758013e601bb5350274b9df2054add78"
PERSONS = tuple(f"sub-{i:02d}" for i in range(1, 7))
SESSIONS = tuple(f"ses-{i:02d}" for i in range(1, 9))
VIDEO_IDS = tuple(range(1, 1103))
CHANNELS = 127
SOURCE_SAMPLES = 1800
EEG_BINS = 150
EYE_FEATURES = 8
DECLARED_JOINED_ROWS = 45144


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _relative(value):
    _need(type(value) is str and bool(value), "Source relative path required")
    path = PurePosixPath(value)
    _need(not path.is_absolute() and path.as_posix() == value and
          "\\" not in value and all(part not in ("", ".", "..") for part in value.split("/")) and
          not any(ord(char) < 32 or ord(char) == 127 for char in value),
          "Canonical local source path required")
    return path


def _clock(values):
    _need(type(values) is list and len(values) == SOURCE_SAMPLES,
          "Complete declared 1,800-sample clock required")
    for index, value in enumerate(values):
        _need(type(value) in (int, float) and math.isfinite(value) and
              abs(value - (-0.1 + index / 500)) <= 1e-9,
              "Declared native clock must be -0.1..3.498 seconds at 500 Hz")


def _coordinate(row, joined):
    expected = {"run", "trial", "video_id", "eeg_row", "eye_row"} if joined else {
        "run", "trial", "video_id"}
    _need(type(row) is dict and set(row) == expected,
          "Closed original joined or unmatched trial row required")
    _need(_integer(row["run"], 1, 16) and _integer(row["trial"], 1, 66) and
          _integer(row["video_id"], 1, 1102), "Exact original trial coordinates required")
    return row["run"], row["trial"]


def validate_joined(joined):
    """Validate all declared rows/clocks; no numerical operand or header is read."""
    _need(type(joined) is dict and joined.get("schema") == "neural080_joined_metadata_v1",
          "Original complete joined-metadata schema required")
    people = joined.get("subjects")
    _need(type(people) is list and len(people) == 6,
          "All six source persons required")
    result = {}
    common_channels = None
    grand_total = 0
    for person in people:
        _need(type(person) is dict and person.get("subject") in PERSONS and
              person["subject"] not in result, "Unique canonical source person required")
        pid = person["subject"]
        channels = person.get("channel_names")
        _need(type(channels) is list and len(channels) == CHANNELS and
              all(type(name) is str and bool(name) for name in channels) and
              len(set(channels)) == CHANNELS, "All 127 unique released channel names required")
        if common_channels is None:
            common_channels = tuple(channels)
        _need(tuple(channels) == common_channels, "Identical released channel order across persons required")
        _clock(person.get("eeg_times"))
        _clock(person.get("eye_times"))
        sessions = person.get("sessions")
        _need(type(sessions) is dict and set(sessions) == set(SESSIONS),
              "All eight source sessions required")
        observed = [0] * len(VIDEO_IDS)
        for session_name in SESSIONS:
            session = sessions[session_name]
            _need(type(session) is dict and
                  set(session) == {"eeg_trials", "eye_trials", "joined", "eeg_only", "eye_only"},
                  "Closed complete session join required")
            eeg_n, eye_n = session["eeg_trials"], session["eye_trials"]
            _need(_integer(eeg_n, 1, 16 * 66) and _integer(eye_n, 1, 16 * 66),
                  "Source recording trial extents must cover original run coordinates")
            rows = session["joined"]
            _need(type(rows) is list and bool(rows), "Nonempty declared joint support in every session")
            keys = set()
            eeg_indices, eye_indices = set(), set()
            for row in rows:
                key = _coordinate(row, True)
                _need(key not in keys and _integer(row["eeg_row"], 0, eeg_n - 1) and
                      _integer(row["eye_row"], 0, eye_n - 1) and
                      row["eeg_row"] not in eeg_indices and row["eye_row"] not in eye_indices,
                      "Unique exact source indices and joined trial coordinates required")
                keys.add(key)
                eeg_indices.add(row["eeg_row"])
                eye_indices.add(row["eye_row"])
                observed[row["video_id"] - 1] += 1
            unmatched = {}
            for label, extent in (("eeg_only", eeg_n), ("eye_only", eye_n)):
                values = session[label]
                _need(type(values) is list and len(rows) + len(values) == extent,
                      "Every source row must have a joined or unmatched disposition")
                exclusive = set()
                for row in values:
                    key = _coordinate(row, False)
                    _need(key not in keys and key not in exclusive,
                          "Unmatched source coordinates must be unique and outside the join")
                    exclusive.add(key)
                unmatched[label] = exclusive
            _need(not (unmatched["eeg_only"] & unmatched["eye_only"]),
                  "A common source coordinate cannot be declared unmatched in both modalities")
            grand_total += len(rows)
        counts = person.get("counts_per_video")
        _need(type(counts) is list and len(counts) == len(VIDEO_IDS) and
              all(type(value) is int and value > 0 for value in counts) and counts == observed,
              "Exact positive repeat count for every one of 1,102 source videos required")
        support = person.get("support")
        _need(type(support) is dict and support.get("joined_trials") == sum(counts) and
              support.get("missing_videos") == [], "Declared support must reconcile with every retained row")
        result[pid] = person
    _need(set(result) == set(PERSONS) and grand_total == DECLARED_JOINED_ROWS,
          "Complete six-person 45,144-row accepted intersection required")
    return result, common_channels


def validate_recordings(document):
    """Validate source-role identity from the pinned original recording roster."""
    _need(type(document) is dict and type(document.get("files")) is list and
          len(document["files"]) == 96, "All 96 original recording descriptors required")
    expected = {(person, session, modality) for person in PERSONS
                for session in SESSIONS for modality in ("eeg", "eye")}
    result = {}
    paths = set()
    for row in document["files"]:
        _need(type(row) is dict, "Original recording descriptor required")
        key = row.get("subject"), row.get("session"), row.get("modality")
        _need(all(type(value) is str for value in key) and key in expected and key not in result,
              "Unique complete person/session/modality recording role required")
        relative = str(_relative(row.get("relative_path")))
        _need(relative not in paths and _integer(row.get("bytes"), 1, 2**63 - 1),
              "Distinct source file and positive exact recording extent required")
        md5 = row.get("md5")
        _need(type(md5) is str and len(md5) == 32 and
              all(character in "0123456789abcdef" for character in md5),
              "Selected publisher recording MD5 required")
        paths.add(relative)
        result[key] = row
    _need(set(result) == expected, "Complete 6 x 8 x 2 recording census required")
    return result


def _source_paths(raw_root, recordings):
    """Inspect only file identities before any native recording body is opened."""
    root = Path(raw_root)
    _need(root.is_dir() and not root.is_symlink(), "Ordinary selected raw recording root required")
    paths = {}
    for key, row in recordings.items():
        path = root
        for part in _relative(row["relative_path"]).parts:
            path = path / part
            _need(not path.is_symlink(), "Source recording path components cannot be symbolic links")
        info = path.stat(follow_symlinks=False)
        _need(stat.S_ISREG(info.st_mode) and info.st_size == row["bytes"],
              "All 96 selected regular recordings with exact extents required before projection")
        paths[key] = path
    return paths


def _basis(channel_names):
    return {
        "channel_names": list(channel_names),
        "eeg_shape_per_video": [CHANNELS, EEG_BINS],
        "eye_shape_per_video": [EEG_BINS, EYE_FEATURES],
        "source_epoch_samples": SOURCE_SAMPLES,
        "declared_source_sampling_hz": 500,
        "declared_source_epoch_start_s": -0.1,
        "declared_source_epoch_last_sample_s": 3.498,
        "analysis_native_sample_slice": [50, 1550],
        "analysis_interval_s": [0.0, 3.0],
        "analysis_bin_width_s": 0.02,
        "native_samples_per_bin": 10,
        "eeg_units": "Published derivative numerical units, retained without conversion; empirical unit confirmation remains required",
        "eeg_normalization": "none; no fitted target mean or scale is applied here",
        "repeat_reduction": "Equal weight to every retained EEG-eye joined repeat within each person/video",
        "eye_features": ["x_gaze_mean", "y_gaze_mean", "pupil_mean",
                         "x_absolute_derivative_per_second", "y_absolute_derivative_per_second",
                         "pupil_absolute_derivative_per_second", "observed_sample_fraction",
                         "valid_adjacent_sample_pair_fraction"],
        "eye_units": "Released gaze degrees and baseline-corrected source pupil units; no new physical-unit calibration",
        "timing_features": {"session_proportions": 8, "run_proportions": 16,
                            "normalized_trial_position_mean_and_population_sd": 2},
        "scaling_scope": "Every later feature/target transform must be fitted only on the selected inner or outer TRAIN-person/video coordinates",
    }


def prepare_unscaled(metadata_root, raw_root, joined_descriptor,
                     recordings_descriptor, output, owner, chunk_trials=16):
    """Produce full unnormalized private operands using the accepted source readers.

    The whole source hash scan and selected native row reads are separately
    charged. Working/serialized array reservations are cumulative logical
    payload bounds, not a measured native memory peak. HDF5 caches, compressed
    physical I/O, Python objects, CPU, deadlines and isolation remain host gates.
    """
    record = owner.begin("complete_unnormalized_recording_pool")
    answer = None
    try:
        from input_owner import Owner, Writer, capture, descriptor
        from io_contract import decode

        _need(type(owner) is Owner, "Existing explicit source Owner required")
        _need(_integer(chunk_trials, 1, 16), "Joined trial batches must contain one to sixteen rows")
        descriptor(joined_descriptor, max_bytes=12_000_000)
        descriptor(recordings_descriptor, max_bytes=100_000)
        _need(joined_descriptor["path"] == "JOINED_METADATA.json" and
              joined_descriptor["sha256"] == JOIN_SHA,
              "Exact accepted EEG-eye join descriptor required")
        _need(recordings_descriptor["path"] == "source/REQUIRED_RECORDINGS.json" and
              recordings_descriptor["sha256"] == REQUIRED_SHA,
              "Exact accepted 96-recording descriptor required")
        joined_raw = capture(metadata_root, joined_descriptor, owner, max_bytes=12_000_000)
        recording_raw = capture(metadata_root, recordings_descriptor, owner, max_bytes=100_000)
        joined = decode(joined_raw)
        selected_recordings = decode(recording_raw)
        people, channel_names = validate_joined(joined)
        recordings = validate_recordings(selected_recordings)
        paths = _source_paths(raw_root, recordings)

        # Scientific imports occur only after the complete metadata/file census,
        # within the caller's retained original attempt. No candidate is started.
        import numpy as np
        import h5py
        from prepare_pool import recording, native, take
        from signals_core import eeg_bins, eye_bins, timing_features

        _need(np.__version__ == "2.2.6" and h5py.__version__ == "3.13.0",
              "Selected numerical/HDF5 source API profile required")
        writer = Writer(output, owner)
        subjects = []
        provenance = []
        total_projected = 0
        eeg_payload = len(VIDEO_IDS) * CHANNELS * EEG_BINS * 8
        eye_payload = len(VIDEO_IDS) * EEG_BINS * EYE_FEATURES * 8
        timing_payload = len(VIDEO_IDS) * 26 * 8
        count_payload = len(VIDEO_IDS) * 8
        for person_id in PERSONS:
            person = people[person_id]
            # Separate anchors and sums preserve equal-repeat arithmetic without
            # fitting or borrowing any mean/variance from another video/person.
            owner.reserve("retained_bytes", 2 * (eeg_payload + eye_payload) +
                          timing_payload + count_payload + 2 * (CHANNELS * EEG_BINS + EEG_BINS * EYE_FEATURES) * 8)
            eeg_anchor = np.zeros((1102, CHANNELS, EEG_BINS), dtype=np.float64)
            eeg_delta = np.zeros_like(eeg_anchor)
            eye_anchor = np.zeros((1102, EEG_BINS, EYE_FEATURES), dtype=np.float64)
            eye_delta = np.zeros_like(eye_anchor)
            counts = np.zeros(1102, dtype=np.int64)
            timing_rows = {video_id: [] for video_id in VIDEO_IDS}
            for session_number, session_name in enumerate(SESSIONS, 1):
                session = person["sessions"][session_name]
                eeg_key = person_id, session_name, "eeg"
                eye_key = person_id, session_name, "eye"
                eeg_record = recordings[eeg_key]
                eye_record = recordings[eye_key]
                with recording(paths[eeg_key], eeg_record, owner) as (eeg_file, eeg_sha), \
                     recording(paths[eye_key], eye_record, owner) as (eye_file, eye_sha):
                    eeg_dataset = native(eeg_file, "eeg", session["eeg_trials"], CHANNELS)
                    eye_dataset = native(eye_file, "eyetracking", session["eye_trials"], 3)
                    rows = session["joined"]
                    for start in range(0, len(rows), chunk_trials):
                        batch = rows[start:start + chunk_trials]
                        n = len(batch)
                        eeg_native_bytes = n * CHANNELS * SOURCE_SAMPLES * eeg_dataset.dtype.itemsize
                        eye_native_bytes = n * 3 * SOURCE_SAMPLES * eye_dataset.dtype.itemsize
                        owner.reserve("read_bytes", eeg_native_bytes + eye_native_bytes)
                        # Native-index reorder, float64 projections, masks and
                        # arithmetic temporaries. This reserves array payloads;
                        # native parser/cache peaks are deliberately not claimed.
                        batch_reservation = (
                            2 * (eeg_native_bytes + eye_native_bytes) +
                            2 * n * CHANNELS * SOURCE_SAMPLES * 8 +
                            12 * n * 3 * SOURCE_SAMPLES * 8 +
                            4 * n * (CHANNELS * EEG_BINS + EEG_BINS * EYE_FEATURES) * 8 +
                            8 * n * 8)
                        owner.reserve("retained_bytes", batch_reservation)
                        eeg = eeg_bins(take(eeg_dataset, [row["eeg_row"] for row in batch]))
                        eye = eye_bins(take(eye_dataset, [row["eye_row"] for row in batch]))
                        _need(eeg.shape == (n, CHANNELS, EEG_BINS) and
                              eye.shape == (n, EEG_BINS, EYE_FEATURES) and
                              np.isfinite(eeg).all() and np.isfinite(eye).all(),
                              "Complete finite joined source projection required")
                        for row, eeg_row, eye_row in zip(batch, eeg, eye):
                            index = row["video_id"] - 1
                            if counts[index] == 0:
                                eeg_anchor[index] = eeg_row
                                eye_anchor[index] = eye_row
                            eeg_delta[index] += eeg_row - eeg_anchor[index]
                            eye_delta[index] += eye_row - eye_anchor[index]
                            counts[index] += 1
                            timing_rows[row["video_id"]].append({"session": session_number,
                                                                 "run": row["run"], "trial": row["trial"]})
                            total_projected += 1
                    provenance.extend([
                        {"subject": person_id, "session": session_name, "modality": "eeg",
                         "relative_path": eeg_record["relative_path"], "bytes": eeg_record["bytes"],
                         "publisher_md5": eeg_record["md5"], "captured_sha256": eeg_sha,
                         "projected_joined_rows": len(rows)},
                        {"subject": person_id, "session": session_name, "modality": "eye",
                         "relative_path": eye_record["relative_path"], "bytes": eye_record["bytes"],
                         "publisher_md5": eye_record["md5"], "captured_sha256": eye_sha,
                         "projected_joined_rows": len(rows)},
                    ])
            _need(np.array_equal(counts, person["counts_per_video"]) and (counts > 0).all(),
                  "Every exact retained repeat and all video identities must be projected")
            eeg_delta /= counts[:, None, None]
            eye_delta /= counts[:, None, None]
            eeg_anchor += eeg_delta
            eye_anchor += eye_delta
            timing = np.asarray([timing_features(timing_rows[video_id]) for video_id in VIDEO_IDS],
                                dtype=np.float64)
            _need(timing.shape == (1102, 26), "Complete source timing basis required")
            # The unchanged Writer checks every published primitive array for
            # finite values and owns serialization, write and cleanup failures.
            descriptors = {
                "eeg_unscaled": writer.array(person_id + "-eeg-unscaled.npy", eeg_anchor),
                "eye": writer.array(person_id + "-eye.npy", eye_anchor),
                "timing": writer.array(person_id + "-timing.npy", timing),
                "repeat_counts": writer.array(person_id + "-repeat-counts.npy", counts),
            }
            support = {
                "schema": "neural080_unnormalized_person_support_v1",
                "subject": person_id,
                "joined_descriptor": joined_descriptor,
                "sessions": person["sessions"],
                "counts_per_video": person["counts_per_video"],
                "retained_joined_trials": int(counts.sum()),
                "eeg_only_trials": sum(len(person["sessions"][session]["eeg_only"]) for session in SESSIONS),
                "eye_only_trials": sum(len(person["sessions"][session]["eye_only"]) for session in SESSIONS),
                "support_rule": "Only exact joined source indices enter means; unmatched source coordinates are retained as dispositions, never silently dropped from this ledger",
            }
            support_descriptor = writer.document(person_id + "-support.json", support)
            subjects.append({"subject": person_id, "arrays": descriptors,
                             "support": support_descriptor, "joined_trials": int(counts.sum())})
            del eeg_anchor, eeg_delta, eye_anchor, eye_delta, counts, timing
        _need(total_projected == DECLARED_JOINED_ROWS and len(provenance) == 96,
              "Complete source panel must finish before the pool manifest is emitted")
        answer = {
            "schema": "neural080_unscaled_recording_pool_v1",
            "persons": list(PERSONS), "video_ids": list(VIDEO_IDS),
            "basis": _basis(channel_names), "subjects": subjects,
            "joined_descriptor": joined_descriptor,
            "recordings_descriptor": recordings_descriptor,
            "source_recordings": provenance,
            "projected_joined_trials": total_projected,
            "access_scope": "Operator-private source preparation, including all eventual query EEG; no candidate view or protected score is emitted",
            "derivative_limitations": [
                "Published derivatives retain offline full-recording ICA and artifact-processing dependencies",
                "Source preprocessing is not re-executed or recast as inductive TRAIN-only preprocessing",
                "Original published 102 test videos and the full stimulus collection remain exposed development resources",
                "Source-declared 500 Hz epoch alignment is not independent physical display/audio/EEG/eye synchronization evidence",
            ],
            "remaining_empirical_gates": [
                "Genuine admitted complete original recordings, source identities and input rights",
                "Actual HDF5 geometry, derivative units and exact matched trial support",
                "Independent media and neural/eye hardware-clock qualification",
                "Native HDF5 decompression/cache/CPU/peak-memory and physical-I/O enforcement",
                "TRAIN-person-only fitting of every subsequent feature and target transform",
                "Fresh-improvement exposure review, candidate isolation and protected comparison",
            ],
            "resource_accounting": "Original Owner: full recording hashes plus selected native row payload reads; cumulative array-payload and serialized-output reservations; not native peak or physical-I/O measurement",
        }
        manifest = writer.document("UNSCALED_POOL.json", answer)
        answer = {"manifest": manifest, "pool": answer, "output": str(writer.root)}
    except BaseException as exc:
        owner.failure(record, exc)
    owner.complete(record)
    return answer
