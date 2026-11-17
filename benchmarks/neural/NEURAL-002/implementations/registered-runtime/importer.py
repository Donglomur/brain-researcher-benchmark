"""Strict identity-preserving raw marker adapter, for future admitted inputs.

No ordinal/minimum-length event/behavior pairing. Behavioral TSVs are not used
for the primary endpoint. Parsing these functions is not permission to acquire
or inspect authentic headers, events, labels or recordings.
"""
import csv
import io
import re
from collections import Counter
from decimal import Decimal, InvalidOperation

from contract import PEOPLE, TASKS, SPEEDS, RATE, vocabulary, require


def _int(text, name):
    require(isinstance(text, str) and re.fullmatch(r"[0-9]+", text) is not None,
            "invalid " + name)
    return int(text)


def parse_markers(text):
    require(isinstance(text, str) and len(text.encode()) <= 2**20, "marker text bound")
    markers, identifiers = {}, set()
    section = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("["):
            section = line
            continue
        if section != "[Marker Infos]":
            continue
        name, sep, rest = line.partition("=")
        require(sep and re.fullmatch(r"Mk[0-9]+", name) is not None, "marker syntax")
        require(name not in identifiers, "duplicate marker identifier")
        identifiers.add(name)
        fields = rest.split(",")
        require(len(fields) >= 5, "marker field count")
        if fields[0] != "Stimulus":
            continue
        hit = re.fullmatch(r"S\s*([0-9]+)", fields[1])
        require(hit is not None, "unsupported stimulus marker")
        sample = _int(fields[2], "marker sample")
        value = str(int(hit.group(1)))
        require(sample >= 1 and 1 <= int(value) <= 78, "marker domain")
        require(sample not in markers, "two stimulus markers share a sample")
        require(_int(fields[3], "marker size") in (0, 1), "unexpected marker extent")
        require(_int(fields[4], "marker channel") == 0, "channel-specific trigger")
        markers[sample] = {"value": value, "marker_id": name}
    require(len(markers) == 156, "expected all 156 stimulus markers")
    return markers


def parse_events(text, participant, task, markers):
    require(participant in PEOPLE and task in TASKS, "recording identity")
    require(isinstance(text, str) and len(text.encode()) <= 2**20, "event text bound")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    expected = {"onset", "duration", "sample", "trial_type", "value", "block", "speed", "stim_file"}
    require(reader.fieldnames is not None and len(reader.fieldnames) == len(expected)
            and set(reader.fieldnames) == expected, "event schema")
    rows, used, counts = [], set(), Counter()
    for row in reader:
        require(set(row) == expected and all(isinstance(v, str) for v in row.values()), "event row shape")
        sample = _int(row["sample"], "sample")
        require(sample >= 1 and sample not in used, "unique 1-based sample required")
        used.add(sample)
        value = str(_int(row["value"], "trigger"))
        speed = row["speed"]
        require(speed in SPEEDS, "speed condition")
        cell = task + "/" + speed
        require(value in vocabulary(cell), "trigger outside cell vocabulary")
        require(row["trial_type"] == "morse_" + value, "stimulus identity mismatch")
        block = _int(row["block"], "block")
        require(block == SPEEDS.index(speed) + 1, "fixed block/speed mismatch")
        try:
            onset = Decimal(row["onset"])
        except InvalidOperation as exc:
            raise ValueError("invalid onset") from exc
        require(onset.is_finite() and onset >= 0, "nonfinite onset")
        # Step0 prints onset with six decimals, hence half a decimal microsecond.
        require(abs(onset - Decimal(sample - 1) / RATE) <= Decimal("0.000000501"),
                "event sample/onset clock disagreement")
        require(sample in markers and markers[sample]["value"] == value,
                "event lacks exact raw marker sample+value match")
        counts[cell, value] += 1
        rows.append({"participant": participant, "task": task, "cell": cell,
                     "sample": sample, "start": sample - 1, "value": value,
                     "label": vocabulary(cell).index(value),
                     "marker_id": markers[sample]["marker_id"],
                     "source_identity": f"{participant}/{task}/{sample}/{value}"})
    require(len(rows) == 156 and set(markers) == used, "complete one-to-one event/marker coverage")
    require(all(counts[task + "/" + speed, value] == 2
                for speed in SPEEDS for value in vocabulary(task + "/" + speed)),
            "each cell requires all26 raw IDs twice")
    # Source order is private, retained only in the trusted ledger.
    rows.sort(key=lambda row: row["sample"])
    require([row["cell"] for row in rows] ==
            [task + "/" + speed for speed in SPEEDS for _ in range(52)],
            "chronological block order differs from declared source design")
    return rows


def validate_cohort(recordings):
    require(isinstance(recordings, dict) and
            set(recordings) == {(p, t) for p in PEOPLE for t in TASKS},
            "complete32 participant/two-task cohort required")
    all_ids = set()
    for (participant, task), rows in recordings.items():
        require(len(rows) == 156, "complete recording required")
        counts = Counter()
        for row in rows:
            require(row["participant"] == participant and row["task"] == task,
                    "recording/row identity mismatch")
            require(row["source_identity"] not in all_ids, "duplicate source trial")
            require(row["cell"] in tuple(task + "/" + s for s in SPEEDS)
                    and row["value"] in vocabulary(row["cell"])
                    and type(row["label"]) is int
                    and row["label"] == vocabulary(row["cell"]).index(row["value"]),
                    "row label/vocabulary mismatch")
            require(type(row["sample"]) is int and row["sample"] >= 1
                    and row["start"] == row["sample"] - 1
                    and row["source_identity"] == f"{participant}/{task}/{row['sample']}/{row['value']}",
                    "native sample or source identity mismatch")
            all_ids.add(row["source_identity"])
            counts[row["cell"], row["value"]] += 1
        require(all(counts[task + "/" + s, v] == 2 for s in SPEEDS
                    for v in vocabulary(task + "/" + s)), "cohort cell coverage")
    return {"participant_count": 32, "recordings": 64, "trials": len(all_ids)}
