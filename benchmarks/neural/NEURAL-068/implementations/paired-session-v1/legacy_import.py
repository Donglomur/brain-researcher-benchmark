"""Import complete legacy NEURAL-068 predictions into the paired-session scorer.

Trusted operator transformation only. It imports the sibling scorer module,
but opens no target/data operand files, participant programs, or historical
score files. The caller must freeze the expected legacy packet ID outside
participant control.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


_spec = importlib.util.spec_from_file_location(
    "_neural068_paired_import_scorer", Path(__file__).with_name("scorer.py"))
scorer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scorer)

LEGACY_SCHEMA = "neural068-prefix-5-10-third-segment-v1"
LABELS = ("tx", "ty", "tz", "rx", "g1", "g2", "g3")
TRAIN = (
    "19250101T111740", "19250101T112404", "19250108T110520",
    "19250108T111022", "19250108T111455", "19250113T120811",
    "19250113T121303", "19250115T110633", "19250115T111328",
    "19250119T113543", "19250119T114045", "19250120T115044",
    "19250120T115537",
)


def legacy_packet_id(pool):
    """Reproduce the retained public/io_utils.py canonical-pool digest."""
    scorer.require(type(pool) is dict and "packet_id" in pool, "Legacy pool object")
    body = {key: value for key, value in pool.items() if key != "packet_id"}
    try:
        raw = (json.dumps(body, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
    except (TypeError, ValueError, OverflowError) as error:
        raise scorer.ContractError("Finite canonical legacy pool") from error
    return hashlib.sha256(raw).hexdigest()


def _integer(value, lower, upper, label):
    scorer.require(type(value) is int and lower <= value <= upper, label)


def _admit_source_join(layout, pool, expected_legacy_packet_id):
    scorer.validate_layout(layout)
    scorer.exact(pool, ("schema", "packet_id", "labels", "runs", "scope",
                        "shared_preparation", "performance_inspected",
                        "scientific_computation"), "Legacy pool")
    scorer.require(scorer.sha256(expected_legacy_packet_id), "Externally frozen legacy packet ID")
    scorer.require(pool["schema"] == LEGACY_SCHEMA
                   and pool["packet_id"] == expected_legacy_packet_id
                   and legacy_packet_id(pool) == expected_legacy_packet_id,
                   "Exact externally selected legacy pool generation")
    scorer.require(pool["labels"] == list(LABELS), "Exact seven-channel order")
    rows = pool["runs"]
    expected = list(TRAIN) + [run for run, _ in scorer.RUNS]
    scorer.require(type(rows) is list and len(rows) == len(expected), "Complete 27-run legacy pool")
    scorer.require(all(type(row) is dict and row.get("run") == run
                       for row, run in zip(rows, expected)), "Exact legacy run order")
    scorer.require(all(row.get("role") == "train" for row in rows[:len(TRAIN)]),
                   "Exact training/query partition")
    for old, current in zip(rows[len(TRAIN):], layout["runs"]):
        scorer.require(old.get("role") == "query", "Exact training/query partition")
        source = old.get("source")
        scorer.require(type(source) is dict
                       and source.get("sha256") == current["source_sha256"],
                       "Same original NWB source hash")
        split = old.get("split")
        scorer.require(type(split) is dict, "Recorded legacy split")
        start, stop = current["query_start_bin"], current["query_stop_bin"]
        for key, expected_value in (("query_start", start), ("query_stop", stop),
                                    ("query_rows", stop - start),
                                    ("query_scored_rows", sum(current["eval_mask"]))):
            value = split.get(key)
            scorer.require(type(value) is int and value == expected_value,
                           "Exact recorded query support: " + key)
        scorer.require(type(old.get("n_rows")) is int and old["n_rows"] == stop,
                       "Complete third-segment suffix")
        segments = split.get("segments")
        scorer.require(type(segments) is list and len(segments) == 3
                       and all(type(segment) is list and len(segment) == 2
                               and all(type(x) is int for x in segment)
                               for segment in segments), "Three recorded integer segments")
        scorer.require(segments[0][0] == 0 and 500 <= segments[0][1] < start
                       and segments[1] == [segments[0][1], start]
                       and segments[2] == [start, stop], "Same recorded first-prefix/third-segment split")
        prefixes = split.get("prefixes")
        scorer.exact(prefixes, ("0", "5", "10"), "Legacy prefixes")
        for budget in scorer.BUDGETS:
            prefix = prefixes[str(budget)]
            scorer.exact(prefix, ("elapsed_seconds", "rows", "labeled_rows"), "Legacy prefix")
            _integer(prefix["elapsed_seconds"], budget, budget, "Exact elapsed calibration budget")
            _integer(prefix["rows"], budget * 50, budget * 50, "Exact prefix row support")
            count = current["calibration_labeled_rows"][str(budget)]
            _integer(prefix["labeled_rows"], count, count, "Same calibration label support")


def convert(layout, pool, answers, *, expected_legacy_packet_id):
    """Convert all 84 captured context answers without fitting, scoring or gold reads.

    A trusted operator supplies both the current authenticated layout and the
    externally selected legacy pool generation. Per-context legacy arrays are
    already ordered by query_start:query_stop; matching that exact interval is
    required before supplying explicit current row IDs. Inputs are not mutated.
    """
    _admit_source_join(layout, pool, expected_legacy_packet_id)
    expected = {scorer.context_id(run, arm, budget)
                for run, _ in scorer.RUNS
                for arm in scorer.ARMS for budget in scorer.BUDGETS}
    scorer.require(type(answers) is dict and set(answers) == expected,
                   "Exact complete 84 legacy answers")
    contexts = {}
    for row in layout["runs"]:
        for arm in scorer.ARMS:
            for budget in scorer.BUDGETS:
                key = scorer.context_id(row["run"], arm, budget)
                answer = answers[key]
                scorer.exact(answer, ("schema", "packet_id", "context_id", "predictions"),
                             "Legacy answer")
                scorer.require(answer["schema"] == LEGACY_SCHEMA
                               and answer["packet_id"] == expected_legacy_packet_id
                               and answer["context_id"] == key,
                               "Exact legacy generation/context join")
                scorer.matrix(answer["predictions"], len(row["row_ids"]), "Legacy predictions")
                contexts[key] = {"row_ids": list(row["row_ids"]),
                                 "predictions": [list(values) for values in answer["predictions"]]}
    submission = {"schema": scorer.VERSION, "packet_id": layout["packet_id"], "contexts": contexts}
    scorer.validate_submission(layout, submission)
    return submission
