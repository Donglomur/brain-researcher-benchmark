"""Compare complete restricted-observation and frozen-program submissions.

Matching declared information hashes are required, but do not establish actual
delivery, access enforcement, authentic preparation, or programme qualification.
"""
import argparse
import hashlib
from pathlib import Path
import re

from io_contract import TASK, fields, need, panel_ids, read, strict, write
from scorer import labels, metrics, predictions, validate_role_paths

ROLES = ("restricted_observation", "frozen_program")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
LIMITS = [
    "Information equality is an operator declaration, not verified delivery.",
    "Access restrictions, source freezing and programme closure are not verified.",
    "Panel completeness is relative to the supplied panel; authentic full90 preparation remains required.",
    "One person and one held recording; overlapping event windows are not independent replication.",
    "No neural information, competence, generalization or scientific success claim follows from this score.",
]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def information_records(value, panel_sha256):
    """Admit exactly two operator declarations about the common information."""
    fields(value, ["schema_version", "task_id", "panel_sha256", "conditions"])
    need(type(value["schema_version"]) is int and value["schema_version"] == 1
         and value["task_id"] == TASK and value["panel_sha256"] == panel_sha256,
         "comparison task/schema/panel binding")
    rows = value["conditions"]
    need(type(rows) is list and len(rows) == 2, "exactly two information declarations")
    admitted = {}
    for row in rows:
        fields(row, ["access_condition", "submission_sha256", "query_observations_sha256",
                     "labeled_calibration_sha256"])
        role = row["access_condition"]
        need(type(role) is str and role in ROLES and role not in admitted,
             "unique restricted-observation and frozen-program declarations")
        for field in ("submission_sha256", "query_observations_sha256", "labeled_calibration_sha256"):
            need(type(row[field]) is str and SHA256.fullmatch(row[field]), "exact lowercase SHA256: " + field)
        admitted[role] = row
    for field in ("query_observations_sha256", "labeled_calibration_sha256"):
        need(admitted[ROLES[0]][field] == admitted[ROLES[1]][field],
             "unequal declared information: " + field)
    return admitted


def paired_statistics(restricted, program, truth, ids):
    """Descriptive finite-panel differences; no trial-independence assumption."""
    counts = {"both_correct": 0, "restricted_only_correct": 0,
              "program_only_correct": 0, "neither_correct": 0}
    for query in ids:
        left, right = restricted[query] == truth[query], program[query] == truth[query]
        key = ("both_correct" if left and right else "restricted_only_correct" if left
               else "program_only_correct" if right else "neither_correct")
        counts[key] += 1
    return counts


def score_pair(restricted_path, program_path, panel_path, comparison_path,
               targets_path, targets_sha256):
    private_read = False
    private_attempted = False
    try:
        # All public/private aliases are rejected before any input body opens.
        # As in the inherited scorer, the operator must keep paths stable.
        for path in (restricted_path, program_path, comparison_path):
            validate_role_paths(path, panel_path, targets_path)
        need(type(targets_sha256) is str and SHA256.fullmatch(targets_sha256),
             "exact private target SHA256 required")
        panel_raw = read(panel_path)
        panel = strict(panel_raw)
        ids = panel_ids(panel)
        comparison_raw = read(comparison_path)
        declarations = information_records(strict(comparison_raw), digest(panel_raw))
        admitted = {}
        for role, path in zip(ROLES, (restricted_path, program_path)):
            try:
                raw = read(path)
                need(digest(raw) == declarations[role]["submission_sha256"],
                     "submission SHA256 differs from comparison declaration")
                admitted[role] = predictions(strict(raw), panel)
            except (ValueError, OSError, OverflowError) as error:
                return {"status": "invalid_submission", "invalid_condition": role,
                        "metrics": None, "private_targets_read": False,
                        "private_targets_open_attempted": False, "reason": str(error)[:300]}
        # Neither partial success nor one malformed arm can expose private truth.
        private_attempted = True
        target_raw = read(targets_path)
        private_read = True
        need(digest(target_raw) == targets_sha256, "private target SHA256 mismatch")
        truth = labels(strict(target_raw), panel, digest(panel_raw))
        scored = {role: metrics(admitted[role], truth, ids) for role in ROLES}
        left, right = (scored[role] for role in ROLES)
        return {
            "status": "scored", "task_id": TASK, "query_count": len(ids),
            "primary": "macro_f1_39", "direction": "higher", "metrics": scored,
            "restricted_minus_program": {
                "macro_f1_39": left["macro_f1_39"] - right["macro_f1_39"],
                "accuracy": left["accuracy"] - right["accuracy"],
                "per_class_f1": [a["f1"] - b["f1"]
                                 for a, b in zip(left["per_class"], right["per_class"])],
            },
            "paired_correctness": paired_statistics(admitted[ROLES[0]], admitted[ROLES[1]], truth, ids),
            "bindings": {"panel_sha256": digest(panel_raw), "comparison_sha256": digest(comparison_raw)},
            "declared_conditions": declarations,
            "private_targets_read": private_read, "private_targets_open_attempted": private_attempted,
            "candidate_executed": False, "access_enforcement_verified": False,
            "same_information_delivery_verified": False, "confidence_interval": None,
            "scientific_success": None, "limitations": LIMITS,
        }
    except (ValueError, OSError) as error:
        return {"status": "operator_error", "metrics": None,
                "private_targets_read": private_read, "private_targets_open_attempted": private_attempted,
                "reason": str(error)[:300]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("restricted", "program", "panel", "comparison", "targets", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--targets-sha256", required=True)
    args = parser.parse_args(argv)
    result = score_pair(args.restricted, args.program, args.panel, args.comparison,
                        args.targets, args.targets_sha256)
    write(args.output, result)
    return {"scored": 0, "invalid_submission": 2, "operator_error": 1}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
