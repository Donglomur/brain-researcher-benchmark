#!/usr/bin/env python3
"""Audit positional source traversal against keyed UMBRAE query identities.

This inspects operator files, never generates a score or runs the author model.
An aligned traversal is necessary but insufficient for numerical source parity.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys

CORE_PATH = Path(__file__).resolve().parents[1] / "initial-evaluator-v1" / "grounding.py"
CORE_SHA256 = "14c7ba38ca656e7e5e1f8db11d6eb3ecc2e4dd06848aeb07c2e1212ccb1afa1d"
if hashlib.sha256(CORE_PATH.read_bytes()).hexdigest() != CORE_SHA256:
    raise RuntimeError("reviewed grounding dependency changed")
_spec = importlib.util.spec_from_file_location("umbrae_alignment_grounding", CORE_PATH)
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)

GROUP_NAMES = {
    "coco_cats": "All", "salient": "Salient",
    "salient_creatures": "Salient Creatures",
    "salient_objects": "Salient Objects",
    "inconspicuous_objects": "Inconspicuous",
}
MAX_INPUT_BYTES = 16 * 1024 * 1024


def read_input(path: Path) -> tuple[object, dict]:
    """Parse and fingerprint the same byte snapshot; retain JSON insertion order."""
    with path.open("rb") as stream:
        body = stream.read(MAX_INPUT_BYTES + 1)
    g._require(len(body) <= MAX_INPUT_BYTES, "input exceeds 16 MiB engineering limit")

    def invalid(value):
        raise g.ContractError("nonfinite JSON constant: " + value)

    value = json.loads(body.decode("utf-8"), object_pairs_hook=g._pairs,
                       parse_constant=invalid)
    return value, {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def validate_categories(groups: object) -> dict:
    """Keep source list order, while checking its fixed source group membership."""
    g._require(isinstance(groups, dict) and set(groups) == set(GROUP_NAMES),
               "the five original category groups are required")
    for source_name, local_name in GROUP_NAMES.items():
        categories = groups[source_name]
        g._require(isinstance(categories, list)
                   and all(isinstance(c, str) for c in categories),
                   "category groups must contain lists of strings")
        g._require(len(categories) == len(set(categories))
                   and set(categories) == set(g.GROUPS[local_name]),
                   f"{source_name}: category membership differs from source")
    return groups


def traversal(images: dict, categories: list[str]) -> list[tuple[str, str]]:
    """Mirror the source's independent dict traversal and keys & list operation.

    Do not sort here. The set-intersection iteration order is part of the
    currently observed source path, and can differ across Python processes.
    """
    return [(image, category) for image, values in images.items()
            for category in values.keys() & categories]


def audit_subject(annotations: dict, responses: object, groups: dict) -> dict:
    g._require(isinstance(responses, dict), "responses must be an image object")
    for image, values in responses.items():
        g._require(isinstance(image, str) and isinstance(values, dict)
                   and all(isinstance(c, str) for c in values),
                   "response images must map category strings to extracted values")
    image_count_matches = len(annotations) == len(responses)
    image_membership_matches = set(annotations) == set(responses)
    image_order_matches = list(annotations) == list(responses)
    result = {}
    for source_name, local_name in GROUP_NAMES.items():
        categories = groups[source_name]
        expected = traversal(annotations, categories)
        actual = traversal(responses, categories)
        expected_set, actual_set = set(expected), set(actual)
        pairs = list(zip(expected, actual))
        extraction_errors = 0
        for image, category in actual:
            value = responses[image][category]
            # The source tests len(value), then indexes value[0][0]. A JSON
            # null accepted by the keyed scorer would instead raise there.
            try:
                if len(value):
                    value[0][0]
            except (TypeError, IndexError, KeyError):
                extraction_errors += 1
        mismatches = sum(left != right for left, right in pairs)
        query_alignment = expected == actual
        result[local_name] = {
            "reference_queries": len(expected), "response_queries": len(actual),
            "positional_pairs": len(pairs), "mispaired_queries": mismatches,
            "same_image_wrong_category_pairs": sum(a[0] == b[0] and a[1] != b[1] for a, b in pairs),
            "wrong_image_pairs": sum(a[0] != b[0] for a, b in pairs),
            "unpaired_reference_tail": max(0, len(expected) - len(actual)),
            "unpaired_response_tail": max(0, len(actual) - len(expected)),
            "missing_query_identities": len(expected_set - actual_set),
            "unexpected_query_identities": len(actual_set - expected_set),
            "same_query_membership": expected_set == actual_set,
            "same_query_sequence": query_alignment,
            "source_extraction_index_errors": extraction_errors,
            "source_pairing_compatible_in_this_process": (
                image_count_matches and image_membership_matches and query_alignment
                and not extraction_errors and bool(expected)),
            "reference_traversal_sha256": hashlib.sha256(json.dumps(expected).encode()).hexdigest(),
            "response_traversal_sha256": hashlib.sha256(json.dumps(actual).encode()).hexdigest(),
        }
    return {
        "source_image_count_assertion_passes": image_count_matches,
        "same_image_membership": image_membership_matches,
        "same_image_insertion_order": image_order_matches,
        "groups": result,
    }


def audit(contract_path: Path, annotations_path: Path, image_order_path: Path,
          category_groups_path: Path) -> dict:
    contract, contract_pin = read_input(contract_path)
    annotations, annotation_pin = read_input(annotations_path)
    image_order, order_pin = read_input(image_order_path)
    groups, groups_pin = read_input(category_groups_path)
    g._require(isinstance(contract, dict), "contract must be an object")
    g.prepare_reference(annotations, image_order, contract.get("profile"))
    g.validate_design(contract, image_order)
    g._require(contract["annotations_sha256"] == annotation_pin["sha256"], "annotation pin mismatch")
    g._require(contract["image_order_sha256"] == order_pin["sha256"], "image order pin mismatch")
    validate_categories(groups)
    panel, response_pins = {}, {}
    for role in g.ROLES:
        panel[role], response_pins[role] = {}, {}
        for subject in g.SUBJECTS:
            response, pin = read_input(contract_path.parent / contract["runs"][role]["responses"][subject])
            panel[role][subject] = audit_subject(annotations, response, groups)
            response_pins[role][subject] = pin
    return {
        "schema": "umbrae-source-traversal-audit/v1", "task_id": g.TASK,
        "profile": contract["profile"], "subject_order": list(g.SUBJECTS),
        "primary_all_category_alignment": {
            role: {subject: panel[role][subject]["groups"]["All"]["source_pairing_compatible_in_this_process"]
                   for subject in g.SUBJECTS} for role in g.ROLES},
        "panel": panel,
        "input_pins": {"contract": contract_pin, "annotations": annotation_pin,
                       "image_order": order_pin, "category_groups": groups_pin,
                       "responses": response_pins},
        "current_runtime": {"implementation": platform.python_implementation(),
                            "version": platform.python_version(),
                            "hash_randomization_enabled": bool(sys.flags.hash_randomization)},
        "native_numerical_parity": "not_established",
        "scientific_qualification": "not_established",
        "limits": [
            "Traversal diagnostics only; no IoU, accuracy, author module, model or scientific decision is executed.",
            "Source set traversal is observed in this Python process; the historical author process is not recovered.",
            "Matching query positions does not qualify float32 arithmetic, box geometry, parser parity or source data identity.",
            "Group membership is checked; the supplied category-list byte snapshot is recorded but not independently authenticated.",
            "Input pins identify consumed snapshots; they do not attest response production or protected evaluation.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--image-order", type=Path, required=True)
    parser.add_argument("--category-groups", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args.contract, args.annotations, args.image_order, args.category_groups)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except (g.ContractError, OSError, UnicodeError, ValueError, RecursionError) as exc:
        parser.exit(2, f"source traversal audit rejected: {exc}\n")


if __name__ == "__main__":
    main()
