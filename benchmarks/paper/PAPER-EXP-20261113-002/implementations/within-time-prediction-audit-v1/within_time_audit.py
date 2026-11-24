"""Audit the complete original Horrocks within-time panel from held predictions.

Operator arithmetic only: this neither authenticates observations nor verifies
fitting, training access, prediction capture, reproduction or improvement.
"""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

TASK = "PAPER-EXP-20261113-002"
SOURCE_COMMIT = "e3796c13fe7afe7a84854cd5a02c36de268e88f4"
SESSIONS = (
    "M22027_20220517", "M22029_20220607", "M22031_20220524",
    "M22032_20220621", "M22033_20220706",
)
STATES = ("stat", "run")
REPEATS, WINDOWS, FOLDS = 5, 191, 3
RECORDS = len(SESSIONS) * len(STATES) * REPEATS * WINDOWS
HEX = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
MANIFEST_CAP = 32 * 1024 * 1024
PREDICTION_CAP = 128 * 1024 * 1024
LINE_CAP = 1024 * 1024
END_OF_STREAM = object()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("nonfinite JSON")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def digest(value):
    require(type(value) is str and HEX.fullmatch(value), "expected lowercase SHA256")


def exact_fields(value, fields, message):
    require(type(value) is dict and set(value) == set(fields), message)


def identity_list(values, count=None):
    require(type(values) is list and values and
            (count is None or len(values) == count), "identity roster extent")
    require(all(type(x) is str and IDENTIFIER.fullmatch(x) for x in values),
            "identity roster syntax")
    require(len(set(values)) == len(values), "duplicate identity")


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def validate_partition(folds, n):
    """Source cvpartition: ordered, balanced, exhaustive threefold testing."""
    require(type(folds) is list and len(folds) == FOLDS, "three source folds required")
    held = []
    sizes = []
    for fold in folds:
        exact_fields(fold, ("train_positions", "test_positions"), "fold fields")
        train, test = fold["train_positions"], fold["test_positions"]
        require(type(train) is list and type(test) is list and train and test,
                "nonempty training/testing position lists")
        require(all(type(x) is int and 1 <= x <= n for x in train + test),
                "one-based integer source positions")
        require(test == sorted(set(test)), "testing positions must be unique and ordered")
        test_set = set(test)
        require(train == [i for i in range(1, n + 1) if i not in test_set],
                "training positions must be ordered exact testing complement")
        held.extend(test)
        sizes.append(len(test))
    require(sorted(held) == list(range(1, n + 1)),
            "three held folds must partition every source position exactly once")
    require(max(sizes) - min(sizes) <= 1, "source fold sizes differ by at most one")


def validate_manifest(manifest):
    """Retain a distinct partition for each state/repeat/window do_cvDA call.

    A split is shared across six classes inside one call, not across states or
    time windows. Recorded partitions are externally frozen, never generated.
    """
    exact_fields(manifest, ("schema", "task_id", "source_commit", "bindings", "sessions"),
                 "manifest fields")
    require(manifest["schema"] == "horrocks-within-time-audit-manifest/v1", "manifest schema")
    require(manifest["task_id"] == TASK and manifest["source_commit"] == SOURCE_COMMIT,
            "task/publication source mismatch")
    bindings = manifest["bindings"]
    exact_fields(bindings, ("observations_sha256", "eligibility_recipe_sha256",
                            "source_class_mapping_sha256"), "three independent source bindings required")
    for value in bindings.values():
        digest(value)
    exact_fields(manifest["sessions"], SESSIONS, "all five original mice required")
    supports = {}
    for sid in SESSIONS:
        session = manifest["sessions"][sid]
        exact_fields(session, ("n_trials", "class_order", "states"), "session fields")
        n = session["n_trials"]
        require(type(n) is int and 3 <= n <= 10000,
                "n_trials bounded integer supporting the selected threefold route")
        require(type(session["class_order"]) is list and
                all(type(x) is int for x in session["class_order"]) and
                session["class_order"] == list(range(1, 7)), "six source class positions")
        exact_fields(session["states"], STATES, "both stat and run required")
        seen, units = set(), None
        for state in STATES:
            item = session["states"][state]
            exact_fields(item, ("trial_ids", "unit_ids", "partitions"), "state roster fields")
            identity_list(item["unit_ids"])
            if units is None:
                units = item["unit_ids"]
            require(item["unit_ids"] == units, "same ordered full good-unit roster across states")
            trials = item["trial_ids"]
            require(type(trials) is list and len(trials) == 6, "six class trial rosters")
            for row in trials:
                identity_list(row, n)
                require(not seen.intersection(row), "trial repeated across class/state")
                seen.update(row)
            partitions = item["partitions"]
            require(type(partitions) is list and len(partitions) == REPEATS,
                    "five source repeats required")
            for repeat, windows in enumerate(partitions, 1):
                require(type(windows) is list and len(windows) == WINDOWS,
                        "all 191 source windows required")
                for window, folds in enumerate(windows, 1):
                    validate_partition(folds, n)
                    for fold_index, fold in enumerate(folds, 1):
                        test = fold["test_positions"]
                        held = [[row[i - 1] for i in test] for row in trials]
                        supports[(sid, state, repeat, window, fold_index)] = (
                            len(test), canonical_sha256(held))
    return supports


def validate_header(header, manifest_sha256):
    digest(manifest_sha256)
    exact_fields(header, ("schema", "audit_manifest_sha256", "method_sha256", "condition"),
                 "prediction header fields")
    require(header["schema"] == "horrocks-within-time-predictions/v1", "prediction schema")
    require(header["audit_manifest_sha256"] == manifest_sha256,
            "prediction/manifest identity mismatch")
    digest(header["method_sha256"])
    require(header["condition"] in ("paper_data", "paper_data_author_code"),
            "information condition")


def reconstruct(manifest, manifest_sha256, header, records):
    """Retain integer fold counts and equally average three fold accuracies."""
    supports = validate_manifest(manifest)
    validate_header(header, manifest_sha256)

    def empty():
        return [[None for _ in range(WINDOWS)] for _ in range(REPEATS)]

    result = {sid: {state: {name: empty() for name in (
        "correct_counts", "trials_per_fold", "fold_accuracy", "within_time")}
        for state in STATES} for sid in SESSIONS}
    seen = set()
    for record in records:
        require(len(seen) < RECORDS, "extra prediction record")
        exact_fields(record, ("session", "state", "repeat", "time_index", "folds"),
                     "prediction record fields")
        sid, state, rep, window = (record[key] for key in ("session", "state", "repeat", "time_index"))
        require(type(sid) is str and sid in SESSIONS and type(state) is str and state in STATES,
                "unknown session/state")
        require(type(rep) is int and 1 <= rep <= REPEATS, "repeat index")
        require(type(window) is int and 1 <= window <= WINDOWS, "time index")
        key = sid, state, rep, window
        require(key not in seen, "duplicate prediction cell")
        folds = record["folds"]
        require(type(folds) is list and len(folds) == FOLDS, "three prediction folds required")
        counts, denominators, accuracies = [], [], []
        for fold_index, fold in enumerate(folds, 1):
            exact_fields(fold, ("held_trial_order_sha256", "predicted_classes"), "prediction fold fields")
            n_test, identity = supports[(*key, fold_index)]
            require(fold["held_trial_order_sha256"] == identity,
                    "held trial order/source fold mismatch")
            predictions = fold["predicted_classes"]
            require(type(predictions) is list and len(predictions) == 6 and
                    all(type(row) is list and len(row) == n_test for row in predictions),
                    "complete balanced held prediction support")
            require(all(type(label) is int and 1 <= label <= 6
                        for row in predictions for label in row), "predictions must be integer classes1..6")
            correct = sum(label == true for true, row in enumerate(predictions, 1) for label in row)
            counts.append(correct)
            denominators.append(6 * n_test)
            accuracies.append(correct / (6 * n_test))
        row = result[sid][state]
        for name, value in (("correct_counts", counts), ("trials_per_fold", denominators),
                            ("fold_accuracy", accuracies), ("within_time", math.fsum(accuracies) / FOLDS)):
            row[name][rep - 1][window - 1] = value
        seen.add(key)
    require(len(seen) == RECORDS, "incomplete full five-mouse/two-state/five-repeat/191-window panel")
    return {"schema": "horrocks-within-time-prediction-audit/v1", "task_id": TASK,
            "audit_manifest_sha256": manifest_sha256, "method_sha256": header["method_sha256"],
            "condition": header["condition"], "source_commit": SOURCE_COMMIT,
            "sessions": result, "record_count": len(seen),
            "within_time_axes": ["repeat", "time"], "fold_array_axes": ["repeat", "time", "fold"],
            "time_centers_ms": list(range(-150, 1751, 10)), "accuracy_units": "fraction_correct",
            "qualification": "operator_prediction_arithmetic_and_support_only",
            "reproduction": None, "improvement": None, "scientific_readiness": "unqualified"}


def read_pinned(path, expected_sha256, cap):
    digest(expected_sha256)
    with path.open("rb") as stream:
        raw = stream.read(cap + 1)
    require(0 < len(raw) <= cap, "empty or oversized input")
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, "input digest mismatch")
    return raw


def read_json_line(stream, hasher, count):
    raw = stream.readline(LINE_CAP + 1)
    if not raw:
        return END_OF_STREAM
    require(len(raw) <= LINE_CAP and count[0] + len(raw) <= PREDICTION_CAP,
            "prediction input resource cap exceeded")
    count[0] += len(raw)
    hasher.update(raw)
    require(raw.endswith(b"\n") and raw.strip(), "one nonempty JSON record per newline")
    return strict_json(raw)


def audit_files(manifest_path, manifest_sha256, prediction_path, prediction_sha256):
    manifest = strict_json(read_pinned(manifest_path, manifest_sha256, MANIFEST_CAP))
    digest(prediction_sha256)
    hasher, count = hashlib.sha256(), [0]
    with prediction_path.open("rb") as stream:
        header = read_json_line(stream, hasher, count)

        def records():
            while True:
                record = read_json_line(stream, hasher, count)
                if record is END_OF_STREAM:
                    break
                yield record

        result = reconstruct(manifest, manifest_sha256, header, records())
    require(hasher.hexdigest() == prediction_sha256, "prediction digest mismatch")
    result["prediction_export_sha256"] = prediction_sha256
    result["prediction_export_bytes"] = count[0]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--predictions-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_files(args.manifest, args.manifest_sha256, args.predictions, args.predictions_sha256)
    output = (json.dumps(result, allow_nan=False, separators=(",", ":")) + "\n").encode()
    with args.output.open("xb") as stream:
        stream.write(output)
    print(json.dumps({"bytes": len(output), "sha256": hashlib.sha256(output).hexdigest(),
                      "qualification": result["qualification"]}))


if __name__ == "__main__":
    main()
