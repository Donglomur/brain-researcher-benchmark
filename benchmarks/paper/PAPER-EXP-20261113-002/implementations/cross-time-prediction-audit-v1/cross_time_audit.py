"""Reconstruct the full Horrocks cross-time panel from operator-held predictions.

Arithmetic and support auditing only. The operator must independently qualify
the source roster, nTrials assignment, fit execution and prediction capture.
This is not a participant interface, sandbox, reproduction or improvement gate.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

TASK = "PAPER-EXP-20261113-002"
SOURCE_COMMIT = "e3796c13fe7afe7a84854cd5a02c36de268e88f4"
SESSIONS = (
    "M22027_20220517", "M22029_20220607", "M22031_20220524",
    "M22032_20220621", "M22033_20220706",
)
STATES = ("stat", "run")
REPEATS = 5
WINDOWS = 20
RECORDS = len(SESSIONS) * len(STATES) * REPEATS * WINDOWS * WINDOWS
HEX = re.compile(r"[0-9a-f]{64}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
MANIFEST_CAP = 16 * 1024 * 1024
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


def validate_manifest(manifest):
    """Validate a separately frozen operator export; never infer nTrials.

    Positions are one-based like MATLAB. Five draws are session-level, so both
    states and all train/test windows necessarily refer to the same split.
    """
    exact_fields(manifest, ("schema", "task_id", "source_commit", "bindings", "sessions"),
                 "manifest fields")
    require(manifest["schema"] == "horrocks-cross-time-audit-manifest/v1", "manifest schema")
    require(manifest["task_id"] == TASK and manifest["source_commit"] == SOURCE_COMMIT,
            "task/publication source mismatch")
    bindings = manifest["bindings"]
    exact_fields(bindings, ("observations_sha256", "eligibility_recipe_sha256",
                            "n_trials_assignment_sha256", "source_class_mapping_sha256"),
                 "four independent source bindings required")
    for value in bindings.values():
        digest(value)
    require(type(manifest["sessions"]) is dict and set(manifest["sessions"]) == set(SESSIONS),
            "all five original mice required")
    supports = {}
    for sid in SESSIONS:
        session = manifest["sessions"][sid]
        exact_fields(session, ("n_trials", "class_order", "states", "splits"), "session fields")
        n = session["n_trials"]
        require(type(n) is int and 2 <= n <= 10000, "n_trials bounded integer; no guessed default")
        require(type(session["class_order"]) is list and
                all(type(x) is int for x in session["class_order"]) and
                session["class_order"] == list(range(1, 7)), "six source class positions")
        exact_fields(session["states"], STATES, "both stat and run required")
        seen = set()
        units = None
        for state in STATES:
            item = session["states"][state]
            exact_fields(item, ("trial_ids", "unit_ids"), "state roster fields")
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
        splits = session["splits"]
        require(type(splits) is list and len(splits) == REPEATS, "five source half-split draws")
        for repeat, split in enumerate(splits, 1):
            exact_fields(split, ("train_positions", "test_positions"), "split fields")
            train, test = split["train_positions"], split["test_positions"]
            require(type(train) is list and type(test) is list, "split position lists")
            require(all(type(x) is int and 1 <= x <= n for x in train + test),
                    "one-based integer source positions")
            require(len(train) == n - n // 2 and len(test) == n // 2,
                    "source ceil-half training and floor-half testing")
            require(len(set(train)) == len(train), "repeated training position")
            require(test == [i for i in range(1, n + 1) if i not in set(train)],
                    "testing positions must be ordered exact training complement")
            for state in STATES:
                trial_rows = session["states"][state]["trial_ids"]
                held = [[row[i - 1] for i in test] for row in trial_rows]
                supports[(sid, state, repeat)] = (len(test), canonical_sha256(held))
    return supports


def validate_header(header, manifest_sha256):
    digest(manifest_sha256)
    exact_fields(header, ("schema", "audit_manifest_sha256", "method_sha256", "condition"),
                 "prediction header fields")
    require(header["schema"] == "horrocks-cross-time-predictions/v1", "prediction schema")
    require(header["audit_manifest_sha256"] == manifest_sha256, "prediction/manifest identity mismatch")
    digest(header["method_sha256"])
    require(header["condition"] in ("paper_data", "paper_data_author_code"), "information condition")


def reconstruct(manifest, manifest_sha256, header, records):
    """Recompute all20,000 integer correct counts and their fraction accuracies.

    Class-grouped predictions are an operator export, not a format to expose to
    participants: source class order reveals the scoring labels. Prediction
    provenance and protection must be established outside this arithmetic layer.
    """
    supports = validate_manifest(manifest)
    validate_header(header, manifest_sha256)

    def empty():
        return [[[None for _ in range(WINDOWS)] for _ in range(WINDOWS)]
                for _ in range(REPEATS)]

    result = {sid: {state: {"correct_counts": empty(), "cross_time": empty(),
                           "trials_per_cell": [6 * supports[(sid, state, r)][0]
                                               for r in range(1, REPEATS + 1)]}
                    for state in STATES} for sid in SESSIONS}
    seen = set()
    for record in records:
        require(len(seen) < RECORDS, "extra prediction record")
        exact_fields(record, ("session", "state", "repeat", "train_time_index", "test_time_index",
                              "held_trial_order_sha256", "predicted_classes"), "prediction record fields")
        sid, state, rep = record["session"], record["state"], record["repeat"]
        require(type(sid) is str and sid in SESSIONS and type(state) is str and state in STATES,
                "unknown session/state")
        require(type(rep) is int and 1 <= rep <= REPEATS, "repeat index")
        train, test = record["train_time_index"], record["test_time_index"]
        require(type(train) is int and type(test) is int and
                1 <= train <= WINDOWS and 1 <= test <= WINDOWS, "train/test time indices")
        key = (sid, state, rep, train, test)
        require(key not in seen, "duplicate prediction cell")
        n_test, identity = supports[(sid, state, rep)]
        require(record["held_trial_order_sha256"] == identity, "held trial order/source split mismatch")
        predictions = record["predicted_classes"]
        require(type(predictions) is list and len(predictions) == 6 and
                all(type(row) is list and len(row) == n_test for row in predictions),
                "complete balanced held prediction support")
        require(all(type(label) is int and 1 <= label <= 6
                    for row in predictions for label in row), "predictions must be integer classes1..6")
        correct = sum(label == true for true, row in enumerate(predictions, 1) for label in row)
        row = result[sid][state]
        row["correct_counts"][rep - 1][train - 1][test - 1] = correct
        row["cross_time"][rep - 1][train - 1][test - 1] = correct / (6 * n_test)
        seen.add(key)
    require(len(seen) == RECORDS, "incomplete full five-mouse/two-state/five-draw/20x20 panel")
    return {"schema": "horrocks-cross-time-prediction-audit/v1", "task_id": TASK,
            "audit_manifest_sha256": manifest_sha256, "method_sha256": header["method_sha256"],
            "condition": header["condition"], "source_commit": SOURCE_COMMIT,
            "sessions": result, "record_count": len(seen),
            "axes": ["repeat", "train_time", "test_time"],
            "time_centers_ms": list(range(-150, 1751, 100)), "accuracy_units": "fraction_correct",
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
    """Full streaming digest check completes before caller can write an output."""
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
