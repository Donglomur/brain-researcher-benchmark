"""Prepare common sentence/training inputs from the authenticated original release.

Operator-only: the source CSV contains final targets. Never expose the source
archive to a participant. No author model, representation, or fit is executed.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

_spec = importlib.util.spec_from_file_location("fig3_inputs_endpoint", Path(__file__).with_name("endpoint.py"))
e = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = e
_spec.loader.exec_module(e)


TRAIN_PARTICIPANTS = (848, 853, 865, 875, 876)
TRAIN_ITEMS = tuple(range(1, 1001))


@dataclass(frozen=True)
class CommonInputs:
    sentences: tuple[str, ...]
    training_responses: tuple[tuple[float, ...], ...]


def _inputs_from_rows(rows):
    """Validate full original support without converting any evaluation outcome."""
    training, evaluation, metadata = {}, set(), {}
    for row in rows:
        uid = e.integer(row["target_UID"])
        if uid not in TRAIN_PARTICIPANTS + e.PARTICIPANTS or row["roi"] != e.ROI:
            continue
        item = e.integer(row["item_id"])
        is_train = uid in TRAIN_PARTICIPANTS
        e.require(item in (TRAIN_ITEMS if is_train else e.ITEMS), "unexpected original input item")
        condition = row["cond"]
        e.require(condition in e.CONDITION_COUNTS, "unknown source condition")
        e.require((condition == "B") == (item <= 1000), "original baseline identity changed")
        e.require(row["cond_approach"] == ("B" if condition == "B" else condition + "_search"),
                  "modify and search inputs cannot be exchanged")
        value = (row["sentence"], condition, row["cond_approach"])
        e.require(type(value[0]) is str and bool(value[0]), "sentence identity required")
        e.require(item not in metadata or metadata[item] == value,
                  "sentence/condition identity differs across source participants")
        metadata[item] = value
        key = (uid, item)
        if is_train:
            e.require(key not in training, "duplicate training participant/item")
            training[key] = e.finite(row["response_target"])
        else:
            e.require(key not in evaluation, "duplicate evaluation participant/item identity")
            evaluation.add(key)
    e.require(set(training) == {(u, i) for u in TRAIN_PARTICIPANTS for i in TRAIN_ITEMS},
              "all 5000 original training participant/item observations required")
    e.require(evaluation == {(u, i) for u in e.PARTICIPANTS for i in e.ITEMS},
              "all 4500 original evaluation participant/item identities required")
    conditions = [metadata[i][1] for i in e.ITEMS]
    e.require({c: conditions.count(c) for c in e.CONDITION_COUNTS} == e.CONDITION_COUNTS,
              "original 1000/250/250 source condition allocation required")
    return CommonInputs(tuple(metadata[i][0] for i in e.ITEMS),
                        tuple(tuple(training[u, i] for i in TRAIN_ITEMS) for u in TRAIN_PARTICIPANTS))


def load_original_inputs(path):
    with e.original_rows(path) as rows:
        return _inputs_from_rows(rows)


def write_inputs(inputs, directory):
    """Create a new common-input directory; existing output is never overwritten."""
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    sentences = directory / "sentences.csv"
    responses = directory / "training_responses.csv"
    with sentences.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item_id", "sentence"])
        writer.writerows(zip(e.ITEMS, inputs.sentences))
    with responses.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["target_UID", "item_id", "response_target"])
        for uid, values in zip(TRAIN_PARTICIPANTS, inputs.training_responses):
            writer.writerows((uid, item, value) for item, value in zip(TRAIN_ITEMS, values))
    files = []
    for path in (sentences, responses):
        data = path.read_bytes()
        files.append({"path": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest = {
        "schema": "original_fig3_common_inputs_v1",
        "source_archive_sha256": e.ARCHIVE_SHA256,
        "source_member": e.MEMBER,
        "roi": e.ROI,
        "train_participants": list(TRAIN_PARTICIPANTS),
        "train_items": 1000,
        "train_observations": 5000,
        "prediction_items": 1500,
        "training_response_units": "source bySessVoxZ: voxel/session z before ROI averaging",
        "training_reduction": "Per-participant source cells retained; author fit averages five people within item.",
        "common_access_conditions": ["paper_data", "paper_data_author_code"],
        "files": files,
        "excluded_columns": ["cond", "cond_approach", "encoding_model_pred", "response_target_non_norm"],
        "evaluation_responses_exported": False,
        "scientific_qualification": False,
        "limits": [
            "Text and original training responses only; no representation, model weights or author code supplied.",
            "Item IDs are joining keys, not model covariates or condition proxies.",
            "Final targets and saved predictions remain operator-owned; historical public exposure is unchanged.",
            "Operator isolation, candidate freeze, paired budgets and author-code-only assistance remain external obligations.",
            "Preparing inputs does not establish original reproduction or improvement."
        ],
    }
    with (directory / "manifest.json").open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    inputs = load_original_inputs(args.archive)
    write_inputs(inputs, args.output_dir)


if __name__ == "__main__":
    main()
