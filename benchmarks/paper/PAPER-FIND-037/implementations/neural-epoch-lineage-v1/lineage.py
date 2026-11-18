"""Audit declared epoch/regressor identities for FreeEnergyEEG source regressions.

Metadata only: this neither reads EEG nor authenticates the operator's mapping.
The original notebook uses positional arrays; equal lengths do not establish
that a source-response epoch and behavioral regressor describe the same trial.
"""

import argparse
import hashlib
import json
from pathlib import Path


TASK_ID = "PAPER-FIND-037"
SOURCE_COMMIT = "80418e5d1949631b0e2b54432e6b6956773c43da"
PARTICIPANTS = (1, *range(4, 26))
TRIALS_PER_PERSON = 120
ORIGINAL_KEYS = tuple((person, trial) for person in PARTICIPANTS
                      for trial in range(TRIALS_PER_PERSON))
ORIGINAL_KEY_SET = frozenset(ORIGINAL_KEYS)
STAGE_CODES = {
    "first_choice": frozenset({"0024"}),
    "first_result": frozenset({"0003", "0004", "0005"}),
    "second_choice": frozenset({"0025"}),
    "second_result": frozenset(f"{value:04d}" for value in range(6, 24)),
}
REASONS = frozenset({"source_stage_selection", "epoch_rejection",
                     "source_literal_719"})
MAX_BYTES = 2 * 1024 * 1024


def need(condition, message):
    if not condition:
        raise ValueError(message)


def exact_keys(value, keys, label):
    need(type(value) is dict and set(value) == set(keys),
         f"{label}: exact fields required")


def integer(value, low, high, label):
    need(type(value) is int and low <= value <= high, f"Invalid {label}")
    return value


def sha256(value):
    need(type(value) is str and len(value) == 64
         and all(c in "0123456789abcdef" for c in value),
         "Evidence requires a lowercase SHA-256 identity")
    return value


def behavior_key(row):
    exact_keys(row, ("participant_id", "trial_index"), "Behavior row")
    person = integer(row["participant_id"], 1, 25, "participant ID")
    trial = integer(row["trial_index"], 0, 119, "zero-based trial index")
    return person, trial


def events(rows, stage, label):
    need(type(rows) is list and 0 < len(rows) <= len(ORIGINAL_KEYS),
         f"{label}: nonempty bounded event list required")
    result = []
    last_index = -1
    for row in rows:
        exact_keys(row, ("participant_id", "trial_index", "event_index",
                         "event_code"), label)
        key = behavior_key({name: row[name]
                            for name in ("participant_id", "trial_index")})
        need(key in ORIGINAL_KEY_SET, f"{label}: event is outside source cohort")
        index = integer(row["event_index"], 0, 2**53 - 1,
                        "original annotation index")
        need(index > last_index, f"{label}: original event indices must increase")
        last_index = index
        need(type(row["event_code"]) is str
             and row["event_code"] in STAGE_CODES[stage],
             f"{label}: event code is outside the declared source stage")
        result.append((key, index, row["event_code"]))
    return result


def audit_lineage(document):
    """Verify declared ordering/coverage, never repair or reorder mismatches.

All 23 x 120 behavioral identities are present even when a stage omits trials.
Each omission needs an explicit source reason and an evidence identity. The
caller must independently establish those declarations from native records.
"""
    exact_keys(document, ("schema_version", "task_id", "source_commit", "stage",
                          "behavior_rows", "selected_behavior_indices",
                          "response_events", "covariance_events", "omissions"),
               "Lineage document")
    need(document["schema_version"] == "freeenergy-neural-lineage/v1",
         "Unsupported lineage schema")
    need(document["task_id"] == TASK_ID, "Wrong task")
    need(document["source_commit"] == SOURCE_COMMIT, "Wrong source-code version")
    stage = document["stage"]
    need(type(stage) is str and stage in STAGE_CODES, "Unknown source stage")
    rows = document["behavior_rows"]
    need(type(rows) is list and len(rows) == len(ORIGINAL_KEYS),
         "Complete declared 23-person/120-trial behavior reference required")
    keys = tuple(behavior_key(row) for row in rows)
    need(keys == ORIGINAL_KEYS,
         "Behavior rows must preserve the literal Design participant/trial order")

    selected = document["selected_behavior_indices"]
    need(type(selected) is list and 0 < len(selected) <= len(keys),
         "Nonempty bounded selected behavior indices required")
    for index in selected:
        integer(index, 0, len(keys) - 1, "selected behavior index")
    need(selected == sorted(set(selected)),
         "Selected indices must be unique and in original order")
    expected_keys = [keys[index] for index in selected]
    response = events(document["response_events"], stage, "Response events")
    covariance = events(document["covariance_events"], stage, "Covariance events")
    need([row[0] for row in response] == expected_keys,
         "Response epochs do not match the declared regressor rows exactly")
    # Covariance is estimated from independently selected negative-time windows.
    # Different support is an observation, not permission to discard trials or
    # an established violation of the source recipe. A shared original index,
    # however, must identify the same annotation in both window sets.
    response_by_event = {index: (key, code) for key, index, code in response}
    covariance_by_event = {index: (key, code) for key, index, code in covariance}
    common_events = response_by_event.keys() & covariance_by_event.keys()
    need(all(response_by_event[index] == covariance_by_event[index]
             for index in common_events),
         "A shared original event index has inconsistent trial/code identity")

    omissions = document["omissions"]
    need(type(omissions) is list and len(omissions) <= len(keys),
         "Bounded omission records required")
    omitted = set()
    literal_deletions = []
    reasons = {}
    for row in omissions:
        exact_keys(row, ("behavior_index", "participant_id", "trial_index",
                         "reason", "evidence_sha256"), "Omission")
        index = integer(row["behavior_index"], 0, len(keys) - 1,
                        "omitted behavior index")
        need(index not in omitted, "Duplicate omission")
        omitted.add(index)
        need(behavior_key({name: row[name] for name in
                           ("participant_id", "trial_index")}) == keys[index],
             "Omission has the wrong participant/trial identity")
        reason = row["reason"]
        need(type(reason) is str and reason in REASONS, "Unknown omission reason")
        sha256(row["evidence_sha256"])
        if reason == "source_literal_719":
            need(stage == "second_result" and index == 719,
                 "Literal 719 deletion is only a second-result source operation")
            literal_deletions.append({"behavior_index": index,
                                      "participant_id": keys[index][0],
                                      "trial_index": keys[index][1]})
        reasons[reason] = reasons.get(reason, 0) + 1
    need(omitted == set(range(len(keys))) - set(selected),
         "Every unselected original row needs exactly one explicit omission")

    return {
        "schema_version": "freeenergy-neural-lineage-audit/v1",
        "task_id": TASK_ID,
        "stage": stage,
        "status": "declared_metadata_alignment_verified",
        "reference_participants": list(PARTICIPANTS),
        "reference_trials": len(keys),
        "aligned_response_events": len(response),
        "covariance_events": len(covariance),
        "windows_have_identical_event_support": response == covariance,
        "response_only_event_count": len(response_by_event.keys()
                                          - covariance_by_event.keys()),
        "covariance_only_event_count": len(covariance_by_event.keys()
                                            - response_by_event.keys()),
        "omission_counts": reasons,
        "literal_source_deletion_identities": literal_deletions,
        "authentic_data_identity_verified": False,
        "publication_cohort_or_trial_selection_verified": False,
        "omission_reasons_independently_verified": False,
        "scientific_reproduction_verified": False,
        "readiness_promoted": False,
        "scope": "metadata consistency prerequisite; no signals, regressions or scores",
    }


def read_document(body):
    need(type(body) is bytes and len(body) <= MAX_BYTES, "Bounded JSON required")

    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Nonfinite JSON token: " + value)

    return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    with args.input.open("rb") as stream:
        body = stream.read(MAX_BYTES + 1)
    result = audit_lineage(read_document(body))
    result["input_sha256"] = hashlib.sha256(body).hexdigest()
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
