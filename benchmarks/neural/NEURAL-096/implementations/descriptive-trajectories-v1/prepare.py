#!/usr/bin/env python3
"""Operator preparation and grading for the scoped descriptive outcome.

This provides no arbitrary participant executor, provider connection or isolation
qualification. The private directory must remain outside participant delivery.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np

from packet import (RECEIPT_SHA256, SOURCE_SHA256, bounded_file,
                    load_original_packet, strict_json)
from score import expected_answer, grade
from trajectory import METHOD, build_reference, matched_observation, require


MAX_DELIVERY_BYTES = 16 * 1024 * 1024
MAX_SUBMISSION_BYTES = 128 * 1024
SOURCE_FILES = ("packet.py", "support.py", "trajectory.py", "score.py", "view.py",
                "prepare.py", "CONTRACT.json", "ROOT_SELECTION.json")


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf8")


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def source_pins():
    folder = Path(__file__).resolve().parent
    return {name: pin(bounded_file(folder / name, 256 * 1024)) for name in SOURCE_FILES}


def exclusive_write(path, body):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def validate_inventory(directory, *, complete):
    """Refuse extra delivery files and indirect directory/file entries.

    This is an integrity check inside an operator-owned directory, not a claim
    of race-free protection against a hostile process with the same privileges.
    """
    directory = Path(directory)
    layout = {
        "": {"participant", "private"} | ({"COMPLETE.json"} if complete else set()),
        "participant": {"observations.json", "MANIFEST.json"},
        "private": {"reference.json", "expected-answer.json", "RECEIPT.json"},
    }
    for relative, expected in layout.items():
        folder = directory / relative
        require(not folder.is_symlink() and folder.is_dir(), "ordinary delivery directory required")
        found = set()
        for child in folder.iterdir():
            require(len(found) < len(expected), "unlisted delivery entry")
            require(child.name in expected and not child.is_symlink(),
                    "unlisted or indirect delivery entry")
            if relative == "" and child.name in ("participant", "private"):
                require(child.is_dir(), "delivery subdirectory required")
            else:
                require(child.is_file(), "ordinary delivery file required")
            found.add(child.name)
        require(found == expected, "incomplete delivery inventory")


def prepare(packet, output):
    output = Path(output)
    require(not output.exists() and not output.is_symlink(), "fresh output directory required")
    require(output.parent.is_dir(), "existing output parent required")
    require(not any((parent / ".git").exists() for parent in (output.parent, *output.parent.parents)),
            "answer-bearing preparation must remain outside Git worktrees")
    before = source_pins()
    metadata, arrays, binding = load_original_packet(packet)
    require(binding["receipt_sha256"] == RECEIPT_SHA256
            and binding["source_sha256"] == SOURCE_SHA256, "original input binding required")
    reference = build_reference(metadata, arrays)
    observation = matched_observation(reference)
    answer = expected_answer(reference)
    payloads = {
        "participant/observations.json": encoded(observation),
        "private/reference.json": encoded(reference),
        "private/expected-answer.json": encoded(answer),
    }
    inventory = {name: pin(body) for name, body in payloads.items()}
    participant_manifest = {
        "schema": "neural096-matched-participant-delivery/v1", "method": METHOD,
        "files": {"observations.json": inventory["participant/observations.json"]},
        "access": "Same aggregate observation in typed viewer and numerical programme conditions.",
        "private_files_delivered": False,
        "runtime_or_model_delivery_qualified": False,
    }
    payloads["participant/MANIFEST.json"] = encoded(participant_manifest)
    inventory["participant/MANIFEST.json"] = pin(payloads["participant/MANIFEST.json"])
    receipt = {
        "schema": "neural096-descriptive-operator-preparation/v1", "method": METHOD,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "original_preparation": binding, "producer": before,
        "files": inventory, "python": sys.version.split()[0], "numpy": np.__version__,
        "limits": {
            "new_NWB_spike_reread": False,
            "additional_14_unit_identity_independently_recovered": False,
            "uncertainty_qualified": False,
            "participant_runtime_qualified": False,
            "full_task_completed": False,
            "new_model_trials": 0,
        },
        "scope": "Operator-derived descriptive reference from the exact saved preparation; no AI performance or calibrated statistical inference.",
    }
    payloads["private/RECEIPT.json"] = encoded(receipt)
    complete_body = encoded({
        "schema": "neural096-preparation-completion/v1",
        "receipt": pin(payloads["private/RECEIPT.json"]),
        "total_payload_bytes": sum(map(len, payloads.values())),
    })
    require(sum(map(len, payloads.values())) + len(complete_body) <= MAX_DELIVERY_BYTES,
            "output exceeds finite byte cap")
    require(source_pins() == before, "producer changed during preparation")
    output.mkdir(mode=0o700)
    (output / "participant").mkdir(mode=0o700)
    (output / "private").mkdir(mode=0o700)
    try:
        for name, body in payloads.items():
            exclusive_write(output / name, body)
        validate_inventory(output, complete=False)
        exclusive_write(output / "COMPLETE.json", complete_body)
    except BaseException:
        # Preserve partial output for diagnosis and accounting; never reuse it.
        raise
    return {"method": METHOD, "files_written": len(payloads) + 1,
            "bytes_written": sum(path.stat().st_size for path in output.rglob("*") if path.is_file()),
            "completion": pin(complete_body),
            "scientific_inference_qualified": False, "full_task_completed": False}


def load_reference(delivery, completion_sha256):
    """Authenticate the closed operator bundle before opening its answer."""
    delivery = Path(delivery)
    validate_inventory(delivery, complete=True)
    require(type(completion_sha256) is str and len(completion_sha256) == 64
            and all(char in "0123456789abcdef" for char in completion_sha256),
            "operator-frozen completion hash required")
    complete_body = bounded_file(delivery / "COMPLETE.json", 4096)
    require(pin(complete_body)["sha256"] == completion_sha256,
            "completion differs from operator-frozen identity")
    complete = strict_json(complete_body)
    require(complete.get("schema") == "neural096-preparation-completion/v1",
            "closed operator preparation required")
    receipt_body = bounded_file(delivery / "private/RECEIPT.json", 128 * 1024)
    require(pin(receipt_body) == complete.get("receipt"), "operator receipt changed")
    receipt = strict_json(receipt_body)
    require(receipt.get("schema") == "neural096-descriptive-operator-preparation/v1"
            and receipt.get("method") == METHOD
            and receipt.get("producer") == source_pins(), "producer/method binding changed")
    original = receipt.get("original_preparation", {})
    require(original.get("receipt_sha256") == RECEIPT_SHA256
            and original.get("source_sha256") == SOURCE_SHA256,
            "original source preparation binding changed")
    files = receipt.get("files")
    require(type(files) is dict and set(files) == {
        "participant/observations.json", "participant/MANIFEST.json",
        "private/reference.json", "private/expected-answer.json"}, "complete operator inventory required")
    require(sum(item["bytes"] for item in files.values()) + len(receipt_body) <= MAX_DELIVERY_BYTES,
            "operator inventory exceeds byte cap")
    bodies = {}
    for name, expected in files.items():
        body = bounded_file(delivery / name, MAX_DELIVERY_BYTES)
        require(pin(body) == expected, "operator artifact changed: " + name)
        bodies[name] = body
    reference = strict_json(bodies["private/reference.json"])
    require(expected_answer(reference) == strict_json(bodies["private/expected-answer.json"]),
            "expected answer does not match private reference")
    require(matched_observation(reference) == strict_json(bodies["participant/observations.json"]),
            "participant observation does not match private prior means/support")
    return reference


def grade_submission(delivery, completion_sha256, submission, output):
    reference = load_reference(delivery, completion_sha256)
    answer_body = bounded_file(submission, MAX_SUBMISSION_BYTES)
    result = grade(reference, strict_json(answer_body))
    result["submission"] = pin(answer_body)
    exclusive_write(Path(output), encoded(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("--packet", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    evaluate = commands.add_parser("grade")
    evaluate.add_argument("--delivery", type=Path, required=True)
    evaluate.add_argument("--completion-sha256", required=True,
                          help="Operator-frozen COMPLETE.json hash, recorded before participant exposure")
    evaluate.add_argument("--submission", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (prepare(args.packet, args.output) if args.action == "prepare" else
              grade_submission(args.delivery, args.completion_sha256, args.submission, args.output))
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
