"""Independently verify Figure 4 score arithmetic in owner-only observations.

This module does not fit models, authenticate recording support, establish
training provenance, or make a paper-reproduction/improvement decision.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path

TASK_ID = "PAPER-paper-method-replacement-011"
NUMERICAL_ATOL = 1e-12  # Arithmetic agreement, never a paper-reproduction margin.
MAXIMUM_EVENT_JSON_BYTES = 1048576  # SourceObserver excludes the JSONL newline.
WINDOW_EVENTS = {"split", "label_mapping", "training_cv_fold", "training_cv_scores",
                 "heldout_probabilities", "window_result"}
OTHER_EVENTS = {"sampling", "source_support_disagreement"}


class VerificationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise VerificationError(message)


def finite(value, name):
    require(type(value) in (int, float) and math.isfinite(value), name + " must be finite numeric")
    return float(value)


def score(value, name):
    value = finite(value, name)
    require(0 <= value <= 1, name + " outside [0,1]")
    return value


def binary_labels(values, name):
    require(isinstance(values, list) and values and
            all(type(value) is int and value in (0, 1) for value in values),
            name + " requires encoded binary integer labels")
    return values


def indices(values, size, name):
    require(isinstance(values, list) and all(type(i) is int and 0 <= i < size for i in values),
            name + " contains invalid positional indices")
    require(len(set(values)) == len(values), name + " contains duplicate positions")
    return values


def rank_auc(labels, values):
    """Positive/negative pair counting in O(n log n), with exact-tie half credit."""
    labels = binary_labels(labels, "AUC labels")
    require(isinstance(values, list) and len(values) == len(labels), "AUC score/label length differs")
    values = [finite(x, "AUC score") for x in values]
    positives = sum(labels)
    negatives = len(labels) - positives
    require(positives and negatives, "AUC requires both classes")
    ordered = sorted(zip(values, labels))
    neg_below = pair_credit_twice = start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][0] == ordered[start][0]:
            end += 1
        tied_positive = sum(label for _, label in ordered[start:end])
        tied_negative = end - start - tied_positive
        pair_credit_twice += tied_positive * (2 * neg_below + tied_negative)
        neg_below += tied_negative
        start = end
    return pair_credit_twice / (2 * positives * negatives)


def strict_loads(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    def constant(value):
        raise VerificationError("nonfinite JSON constant: " + value)
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise VerificationError("invalid JSON") from exc


def _support(prepared, windows, saved_scores):
    require(isinstance(prepared, dict) and prepared.get("schema") == "treebank-figure4-preparation/v2"
            and prepared.get("task_id") == TASK_ID, "wrong preparation schema/task")
    eligibility = prepared.get("eligibility")
    require(isinstance(eligibility, dict) and eligibility, "declared eligible support required")
    for subject, contacts in eligibility.items():
        require(isinstance(subject, str) and subject and isinstance(contacts, list) and contacts and
                all(isinstance(x, str) and x for x in contacts) and len(set(contacts)) == len(contacts),
                "invalid or duplicate eligible contact support")
    require(isinstance(windows, list) and windows, "source windows required")
    keys = []
    for window in windows:
        require(isinstance(window, dict), "invalid source window")
        key = window.get("source_key")
        require(isinstance(key, str) and key and key not in keys, "duplicate/invalid source window key")
        finite(window.get("nominal_start"), "source nominal start")
        require(type(window.get("requested_start_sample")) is int and window["requested_start_sample"] >= 0,
                "invalid source sample start")
        require(type(window.get("requested_sample_count")) is int and window["requested_sample_count"] > 0,
                "invalid source sample duration")
        keys.append(key)
    require(isinstance(saved_scores, dict) and set(saved_scores) == set(eligibility), "saved score subject support differs")
    for subject, contacts in eligibility.items():
        require(isinstance(saved_scores[subject], dict) and set(saved_scores[subject]) == set(contacts),
                "saved score contact support differs")
        for contact in contacts:
            values = saved_scores[subject][contact]
            require(isinstance(values, dict) and set(values) == set(keys), "saved score window support differs")
            for row in values.values():
                _score_object(row)
    return eligibility, keys


def _score_object(row):
    require(isinstance(row, dict) and set(row) == {"test_score", "cv_score"}, "expected two-field source score")
    return {key: score(value, key) for key, value in row.items()}


def _context(event, eligibility, windows):
    context = event.get("context")
    require(isinstance(context, dict), "window event lacks context")
    sid, contact = context.get("source_subject"), context.get("contact")
    require(isinstance(sid, str) and sid in eligibility and contact in eligibility[sid],
            "event outside declared eligible support")
    require(event.get("subject") == sid, "top-level and source subject disagree")
    window = context.get("window")
    require(isinstance(window, dict) and type(window.get("index")) is int and
            0 <= window["index"] < len(windows), "invalid observed window index")
    expected = windows[window["index"]]
    for observed, declared in (("nominal_start", "nominal_start"),
                               ("requested_sample_start", "requested_start_sample"),
                               ("requested_sample_duration", "requested_sample_count")):
        require(type(window.get(observed)) in (int, float) and type(window.get(observed)) is not bool and
                window[observed] == expected[declared], "observed source window definition differs")
    return sid, contact, window["index"]


def _check_window(records, max_examples, saved):
    for name in WINDOW_EVENTS - {"training_cv_fold"}:
        require(len(records[name]) == 1, "missing or duplicate " + name)
    split = records["split"][0]
    require(split.get("status") == "observed", "split unavailable")
    labels = binary_labels(split.get("dataset_labels"), "dataset labels")
    require(len(labels) <= max_examples, "per-window example budget exceeded")
    train = indices(split.get("train"), len(labels), "train")
    test = indices(split.get("test"), len(labels), "test")
    require(split.get("validation") == [] and split.get("validation_labels") == [],
            "source selected protocol has no separate validation partition")
    require(train and test and len(train) + len(test) == len(labels) and
            set(train).isdisjoint(test), "source train/test is not a complete disjoint partition")
    train_y, test_y = [labels[i] for i in train], [labels[i] for i in test]
    require(binary_labels(split.get("train_labels"), "split training labels") == train_y and
            binary_labels(split.get("test_labels"), "split test labels") == test_y,
            "split labels disagree with positional membership")
    mapping = records["label_mapping"][0]
    require(mapping.get("status") == "observed" and isinstance(mapping.get("mapping"), list), "class mapping unavailable")
    mapped = mapping["mapping"]
    require(len(mapped) == 2 and all(isinstance(x, dict) and set(x) == {"label", "index"}
            and type(x["index"]) is int and x["index"] in (0, 1) for x in mapped), "invalid class mapping")
    require({x["index"] for x in mapped} == {0, 1}, "duplicate encoded class")
    # Preserve the actual semantic class mapping without choosing a polarity.
    # JSON serialization distinguishes False/0, as the observed source may use booleans.
    require(len({json.dumps(x["label"], sort_keys=True, allow_nan=False) for x in mapped}) == 2,
            "duplicate original class label")

    folds = records["training_cv_fold"]
    require(len(folds) == 5, "exactly five observed source CV folds required")
    seen_validation = set()
    for fold in folds:
        fit = indices(fold.get("train_relative_to_training"), len(train), "CV train")
        valid = indices(fold.get("validation_relative_to_training"), len(train), "CV validation")
        require(fit and valid and len(fit) + len(valid) == len(train) and set(fit).isdisjoint(valid),
                "CV fold is not a complete disjoint training-only partition")
        require(set(train_y[i] for i in fit) == {0, 1} and set(train_y[i] for i in valid) == {0, 1},
                "CV fold lacks both classes")
        require(seen_validation.isdisjoint(valid), "CV validation membership repeats across folds")
        seen_validation.update(valid)
    require(seen_validation == set(range(len(train))), "CV validation does not cover all training examples")
    cv = records["training_cv_scores"][0].get("scores")
    require(isinstance(cv, list) and len(cv) == 5, "five observed training-CV scores required")
    cv = [score(x, "training-CV AUC") for x in cv]

    probabilities = records["heldout_probabilities"][0]
    require(probabilities.get("source_column_used") == 1 and type(probabilities.get("source_column_used")) is int,
            "wrong source probability column")
    require(probabilities.get("class_order") == {"status": "observed", "values": [0, 1]},
            "source probability class order is not observed encoded [0,1]")
    require(all(type(x) is int for x in probabilities["class_order"]["values"]),
            "encoded probability classes must be integers, not booleans")
    rows = probabilities.get("probabilities")
    require(isinstance(rows, list) and len(rows) == len(test), "held-out probability count differs")
    column = []
    for row in rows:
        require(isinstance(row, list) and len(row) == 2, "binary probability row required")
        p0, p1 = [score(x, "class probability") for x in row]
        require(abs(math.fsum((p0, p1)) - 1) <= NUMERICAL_ATOL, "class probability row does not sum to one")
        column.append(p1)
    held_out_auc = rank_auc(test_y, column)
    cv_mean = math.fsum(cv) / 5
    result = records["window_result"][0]
    require(result.get("status") == "observed" and result.get("unavailable_observations") == [],
            "window result or required observations unavailable")
    counts = {name: len(values) for name, values in records.items() if name != "window_result"}
    require(result.get("observation_counts") == counts, "window observation receipt disagrees with actual event counts")
    observed = _score_object(result.get("scores"))
    require(observed == _score_object(saved), "saved score artifact differs from observed return")
    test_error = abs(held_out_auc - observed["test_score"])
    cv_error = abs(cv_mean - observed["cv_score"])
    require(test_error <= NUMERICAL_ATOL, "observed held-out probabilities do not reproduce source test AUC")
    require(cv_error <= NUMERICAL_ATOL, "observed five-CV mean differs from source CV score")
    return test_error, cv_error, len(test)


def verify(events, prepared, windows, saved_scores, *, max_examples_per_window, max_events):
    """Verify a single complete source observation stream; never return targets."""
    require(type(max_examples_per_window) is int and max_examples_per_window > 0, "positive example budget required")
    require(type(max_events) is int and max_events > 0, "positive event budget required")
    eligibility, keys = _support(prepared, windows, saved_scores)
    expected_count = sum(len(x) for x in eligibility.values()) * len(windows)
    require(expected_count * 10 + 2 <= max_events, "event allocation cannot contain complete declared support")
    seen = set()
    active = None
    records = {name: [] for name in WINDOW_EVENTS}
    event_counts = Counter()
    started = finished = False
    maximum_test_error = maximum_cv_error = 0.0
    test_rows = disagreements = 0
    for count, event in enumerate(events, 1):
        require(count <= max_events, "event budget exceeded")
        require(isinstance(event, dict), "observation event must be an object")
        kind = event.get("event")
        require(isinstance(kind, str), "observation event kind must be a string")
        require(not finished, "event after source observation completion")
        if kind == "observation_started":
            require(count == 1 and not started and not event.get("unavailable_hooks"), "invalid/incomplete observation start")
            started = True
        elif kind == "observation_finished":
            require(started and active is None, "incomplete window at observation finish")
            require(event.get("status") == "observed_not_scientifically_qualified" and
                    event.get("observer_failure") is None and not event.get("unavailable_hooks") and
                    event.get("windows_with_unavailable_observations") == 0 and
                    event.get("completed_window_calls") == expected_count,
                    "source observer did not completely finish")
            # Disagreement records are emitted by SupportChecks, outside SourceObserver.
            observer_counts = {key: value for key, value in event_counts.items() if key != "source_support_disagreement"}
            require(event.get("event_counts") == observer_counts, "source observer total counts disagree with stream")
            finished = True
        elif kind in WINDOW_EVENTS:
            require(started, "window event before observation start")
            key = _context(event, eligibility, windows)
            require(key not in seen, "duplicate already-completed source window")
            if active is None:
                require(kind == "split", "window must begin with observed source split")
                active = key
            require(key == active, "interleaved or incomplete source windows")
            records[kind].append(event)
            require(len(records[kind]) <= (5 if kind == "training_cv_fold" else 1), "excess duplicate window observations")
            if kind == "window_result":
                errors = _check_window(records, max_examples_per_window, saved_scores[key[0]][key[1]][keys[key[2]]])
                maximum_test_error = max(maximum_test_error, errors[0])
                maximum_cv_error = max(maximum_cv_error, errors[1])
                test_rows += errors[2]
                seen.add(key)
                active = None
                records = {name: [] for name in WINDOW_EVENTS}
        elif kind in OTHER_EVENTS:
            require(started, "support event before observation start")
            if kind == "source_support_disagreement":
                disagreements += 1
            # Sampling and source-identity consistency are verified separately
            # by the existing SupportChecks; do not silently claim them here.
        else:
            raise VerificationError("unknown observation event kind")
        event_counts[kind] += 1
    require(started and finished and active is None and len(seen) == expected_count,
            "missing observation lifecycle or declared contact/window coverage")
    return {"schema": "treebank-observation-score-verification/v1", "task_id": TASK_ID,
            "status": "verified_score_arithmetic_for_complete_supplied_support",
            "window_calls_verified": len(seen), "heldout_prediction_rows_verified": test_rows,
            "heldout_auc": "independent_rank_pair_count_from_observed_binary_labels_and_column1",
            "cv_check": "five_training_only_fold_partitions_and_mean_of_observed_cv_auc_only",
            "cv_prediction_level_auc_recomputed": False,
            "maximum_heldout_auc_absolute_error": maximum_test_error,
            "maximum_cv_mean_absolute_error": maximum_cv_error,
            "arithmetic_absolute_tolerance": NUMERICAL_ATOL,
            "source_support_disagreements_observed": disagreements,
            "same_case_claim": "not_admitted_by_this_verifier",
            "original_support_authenticated": False, "training_provenance_authenticated": False,
            "full_primary_reproduction": "unavailable", "candidate_improvement": "not_assessed",
            "benchmark_readiness": "not_qualified"}


def read_json(path, maximum):
    with Path(path).open("rb") as handle:
        raw = handle.read(maximum + 1)
    require(len(raw) <= maximum, "JSON input byte budget exceeded")
    return strict_loads(raw), hashlib.sha256(raw).hexdigest()


def event_stream(path, *, compressed, maximum_bytes,
                 maximum_line_bytes=MAXIMUM_EVENT_JSON_BYTES + 1, identity=None):
    opener = gzip.open if compressed else open
    observed_hash = hashlib.sha256()
    with opener(path, "rb") as stream:
        consumed = 0
        while True:
            line = stream.readline(maximum_line_bytes + 1)
            if not line:
                break
            consumed += len(line)
            require(consumed <= maximum_bytes and len(line) <= maximum_line_bytes, "observation byte/line budget exceeded")
            require(line.endswith(b"\n") and line.strip(), "incomplete/empty observation line")
            observed_hash.update(line)
            yield strict_loads(line)
    if identity is not None:
        identity.update(bytes=consumed, sha256=observed_hash.hexdigest(),
                        representation="complete decompressed JSONL bytes, not gzip container bytes")


def positive(text):
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("positive integer required") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("positive integer required")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("prepared", "windows", "scores", "observations", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--gzip", action="store_true", help="observations use the producer's gzip JSONL format")
    for key in ("max-events", "max-observation-bytes", "max-examples-per-window"):
        parser.add_argument("--" + key, type=positive, required=True)
    args = parser.parse_args()
    prepared, prep_hash = read_json(args.prepared, 16 * 1024 * 1024)
    windows, window_hash = read_json(args.windows, 65536)
    scores, score_hash = read_json(args.scores, 32 * 1024 * 1024)
    stream_identity = {}
    events = event_stream(args.observations, compressed=args.gzip,
                          maximum_bytes=args.max_observation_bytes,
                          identity=stream_identity)
    result = verify(events, prepared, windows, scores,
                    max_examples_per_window=args.max_examples_per_window, max_events=args.max_events)
    result["input_byte_hashes"] = {"prepared": prep_hash, "windows": window_hash, "scores": score_hash}
    result["observations"] = stream_identity
    result["identity_limit"] = "Observed byte identities are not authenticated recording/fit provenance."
    raw = (json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    with args.output.open("xb") as stream:
        stream.write(raw)


if __name__ == "__main__":
    main()
