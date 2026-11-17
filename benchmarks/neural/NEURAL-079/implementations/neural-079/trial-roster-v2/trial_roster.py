"""Build full EEG row identities and optional eye covariates, without signals.

The operator supplies already isolated primitive metadata. This module never
unpickles NPY metadata, opens recordings, or exports held neural responses.
Original trial order is retained; eye rejection never selects EEG target rows.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path


PERSONS = tuple(f"sub-{i:02d}" for i in range(1, 7))
SESSIONS = tuple(f"ses-{i:02d}" for i in range(1, 9))
TRIAL_FIELDS = ("stimulus_id", "run_number", "trial_number")
MAX_BYTES = 8 * 1024 * 1024


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fields(value, names):
    require(type(value) is dict and set(value) == set(names),
            "Unexpected metadata fields; supply isolated primitive metadata only")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def pin(value):
    body = canonical(value)
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def validate_axes(meta, eeg):
    fields(meta, TRIAL_FIELDS + (("ch_names", "times") if eeg else ("times",)))
    times = meta["times"]
    require(type(times) is list and len(times) == 1800,
            "All 1800 source time samples are required")
    require(all(type(t) in (int, float) and math.isfinite(t)
                and abs(t - (-0.1 + i / 500)) <= 1e-9
                for i, t in enumerate(times)),
            "Source clock must be 500 Hz, -0.100 through 3.498 seconds")
    if eeg:
        channels = meta["ch_names"]
        require(type(channels) is list and len(channels) == 127
                and all(type(c) is str and c and c.strip() == c for c in channels)
                and len(set(channels)) == 127, "All 127 ordered channel names are required")
    for name in TRIAL_FIELDS:
        require(type(meta[name]) is dict and set(meta[name]) == set(SESSIONS),
                "All eight source sessions are required")


def source_rows(meta, session):
    """Return rows in array order, never sorted by run, trial, or video."""
    columns = []
    for name, upper in zip(TRIAL_FIELDS, (1102, 16, 66)):
        values = meta[name][session]
        require(type(values) is list and len(values) <= 16 * 66
                and all(type(v) is int and 1 <= v <= upper for v in values),
                "Invalid source integer trial column")
        columns.append(values)
    require(len({len(v) for v in columns}) == 1, "Trial column lengths differ")
    seen = set()
    rows = []
    for position, (video, run, trial) in enumerate(zip(*columns)):
        key = (run, trial)
        require(key not in seen, "Duplicate session/run/trial identity")
        seen.add(key)
        rows.append({"row": position, "video_id": video, "run": run, "trial": trial})
    return rows


def build_roster(document):
    """Construct complete encoding rosters; return operator-private metadata.

    Empty/partial eye support is allowed and explicitly represented. EEG must
    cover every video for every person, with fitting trials in every session.
    A matching trial key with different video identities is always an error.
    """
    fields(document, ("schema", "people"))
    require(document["schema"] == "n079_primitive_trial_metadata_v1", "Input schema")
    people = document["people"]
    require(type(people) is list and len(people) == 6, "All six people are required")
    by_person = {}
    for person in people:
        fields(person, ("person", "eeg", "eye"))
        require(type(person["person"]) is str and person["person"] in PERSONS
                and person["person"] not in by_person, "Unique source participant identity")
        by_person[person["person"]] = person
    result = []
    channels = None
    summaries = []
    for person_id in PERSONS:
        person = by_person[person_id]
        eeg, eye = person["eeg"], person["eye"]
        validate_axes(eeg, True)
        if eye is not None:
            validate_axes(eye, False)
        if channels is None:
            channels = list(eeg["ch_names"])
        require(channels == eeg["ch_names"], "Channel ordering differs across people")
        counts = Counter()
        paired_counts = Counter()
        eye_only_count = 0
        for number, session in enumerate(SESSIONS, 1):
            eeg_rows = source_rows(eeg, session)
            require(any(r["video_id"] <= 1000 for r in eeg_rows),
                    "Each original EEG session requires fitting trials")
            eye_rows = [] if eye is None else source_rows(eye, session)
            eye_index = {(r["run"], r["trial"]): r for r in eye_rows}
            eeg_keys = {(r["run"], r["trial"]) for r in eeg_rows}
            joined = []
            for row in eeg_rows:
                counts[row["video_id"]] += 1
                matching = eye_index.get((row["run"], row["trial"]))
                require(matching is None or matching["video_id"] == row["video_id"],
                        "EEG/eye video disagreement at the same source trial key")
                if matching is not None:
                    paired_counts[row["video_id"]] += 1
                joined.append({**row, "eye_row": None if matching is None else matching["row"]})
            extra_eye = [r for r in eye_rows if (r["run"], r["trial"]) not in eeg_keys]
            eye_only_count += len(extra_eye)
            # Person/session scope is inside the hashed value, so identical
            # run/trial pairs in different recordings cannot share identity.
            identities = {"person": person_id, "session": number, "rows": eeg_rows}
            result.append({
                "person": person_id, "session": number,
                "trial_video_ids": [r["video_id"] for r in eeg_rows],
                "trial_roster_pin": pin(identities), "source_rows": joined,
                "train_rows": [r["row"] for r in eeg_rows if r["video_id"] <= 1000],
                "query_rows": [r["row"] for r in eeg_rows if r["video_id"] > 1000],
                "eye_metadata_present": eye is not None,
                "eye_only_rows": extra_eye,
                "unpaired_eeg_rows": [r["row"] for r in joined if r["eye_row"] is None],
            })
        missing = [v for v in range(1, 1103) if counts[v] == 0]
        require(not missing, f"Missing EEG videos for {person_id}: {missing}")
        summaries.append({"person": person_id,
                          "eeg_counts_per_video": [counts[v] for v in range(1, 1103)],
                          "paired_eye_counts_per_video": [paired_counts[v] for v in range(1, 1103)],
                          "eeg_trials": sum(counts.values()),
                          "paired_eye_trials": sum(paired_counts.values()),
                          "unpaired_eeg_trials": sum(counts.values()) - sum(paired_counts.values()),
                          "eye_only_trials": eye_only_count})
    return {"schema": "n079_full_eeg_trial_roster_v2", "task": "NEURAL-079",
            "metadata_pin": pin(document), "channel_names": channels,
            "times": {"count": 1800, "start_microseconds": -100000, "step_microseconds": 2000},
            "sessions": result, "people": summaries,
            "operator_private_only": True,
            "scope": "Full retained EEG support; eye intersection is a covariate view only"}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "Duplicate JSON member")
        value[key] = item
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="Fresh operator-private path outside the source checkout")
    args = parser.parse_args()
    # This program is not an NPY loader. Inputs must be reviewed primitive JSON.
    with args.metadata.open("rb") as stream:
        body = stream.read(MAX_BYTES + 1)
    require(len(body) <= MAX_BYTES, "Metadata exceeds the bounded input extent")
    document = json.loads(body, object_pairs_hook=unique_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    result = build_roster(document)
    result["input_bytes_pin"] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    output = canonical(result) + b"\n"
    require(len(output) <= MAX_BYTES, "Roster exceeds the bounded output extent")
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(output)
    # Do not print target-correspondence rows, local paths or video support.
    print(json.dumps({"bytes": len(output), "sha256": hashlib.sha256(output).hexdigest(),
                      "sessions": len(result["sessions"]), "signal_arrays_read": False}))


if __name__ == "__main__":
    main()
