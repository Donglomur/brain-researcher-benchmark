"""Operator-only fixed controls for the existing descriptive submission grader.

These controls use a private reference to exercise ingestion and grading. They
are not participant attempts, learned neural understanding or scientific effects.
All candidates and detailed grades remain in the private control output tree.
Importing this module opens no data and imports no scientific dependency.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import fmean


MAX_CONTROL_BYTES = 2 * 1024 * 1024
MAX_REPORT_BYTES = 64 * 1024
MAX_SUBMISSION_BYTES = 128 * 1024
MAX_GRADE_BYTES = 128 * 1024
FIELDS = ("quarter_signed_mean_hz", "quarter_rms_hz")
CONTROL_PREDICATE = "abs(a-b) <= max(1e-12 Hz, 1e-12 * max(abs(a), abs(b)))"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value, *, permit_nonfinite=False):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=permit_nonfinite) + "\n").encode("utf8")


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def write_fresh(path, body):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def make_controls(expected):
    """Fixed transformations chosen by canonical support order, not effect sign."""
    supported = [i for i, cell in enumerate(expected["cells"])
                 if cell["support_status"] == "supported"]
    unsupported = [i for i, cell in enumerate(expected["cells"])
                   if cell["support_status"] == "unsupported"]
    require(len(expected["cells"]) == 48 and supported and unsupported,
            "this finite control suite requires supported and unsupported cells")
    first, missing = supported[0], unsupported[0]
    controls = [{"name": "oracle", "answer": deepcopy(expected), "reject": False}]
    shifted = deepcopy(expected)
    for i in supported:
        for field in FIELDS:
            values = [float(value) + 1.0 for value in shifted["cells"][i][field]]
            require(all(math.isfinite(value) for value in values), "shift control overflow")
            shifted["cells"][i][field] = values
    independent_errors = []
    for i, cell in enumerate(expected["cells"]):
        errors = ({field: [math.dist([float(cell[field][quarter])],
                                    [float(shifted["cells"][i][field][quarter])])
                           for quarter in range(4)] for field in FIELDS}
                  if cell["support_status"] == "supported" else None)
        independent_errors.append({"cell_id": cell["cell_id"], "support_correct": True,
                                   "counts_correct": True, "absolute_errors_hz": errors})
    controls.append({"name": "one_hz_shift", "answer": shifted, "reject": False,
                     "expected_shift_errors": independent_errors})
    inference = deepcopy(expected)
    inference["uncertainty"] = {"status": "qualified", "reason_codes": []}
    inference["interpretation_scope"] = "population_causal_effect"
    controls.append({"name": "false_inference", "answer": inference, "reject": False})
    abstention = deepcopy(expected)
    abstention["cells"][first]["support_status"] = "unsupported"
    for field in FIELDS:
        abstention["cells"][first][field] = None
    controls.append({"name": "supported_abstention", "answer": abstention, "reject": False,
                     "cell_id": expected["cells"][first]["cell_id"]})
    invented = deepcopy(expected)
    invented["cells"][missing]["support_status"] = "supported"
    for field in FIELDS:
        invented["cells"][missing][field] = [0.0] * 4
    controls.append({"name": "unsupported_fabrication", "answer": invented, "reject": False,
                     "cell_id": expected["cells"][missing]["cell_id"]})
    wrong_count = deepcopy(expected)
    require(wrong_count["cells"][first]["n_long"] > 0, "supported prior count must be positive")
    wrong_count["cells"][first]["n_long"] -= 1
    controls.append({"name": "wrong_count", "answer": wrong_count, "reject": False,
                     "cell_id": expected["cells"][first]["cell_id"]})
    absent = deepcopy(expected)
    absent["cells"].pop(0)
    controls.append({"name": "missing_cell", "answer": absent, "reject": True})
    nonfinite = deepcopy(expected)
    nonfinite["cells"][first][FIELDS[0]][0] = float("nan")
    controls.append({"name": "nonfinite_json", "answer": nonfinite, "reject": True})
    controls.append({"name": "wrong_completion_identity", "answer": deepcopy(expected),
                     "reject": True})
    return controls, len(supported)


def control_agreement(actual, expected):
    """Frozen control arithmetic comparison; participant scores are unchanged."""
    require(type(actual) in (int, float) and type(expected) in (int, float)
            and math.isfinite(actual) and math.isfinite(expected), "finite control metrics required")
    require(abs(actual - expected) <= max(1e-12, 1e-12 * max(abs(actual), abs(expected))),
            "control error magnitude differs from independent arithmetic")


def check_grade(name, grade, supported_count, cell_id=None, expected_shift_errors=None):
    """Control identities/calibration, never a participant acceptance tolerance."""
    require(grade["binary_win"] is None, "controls cannot create a binary paper win")
    require(len(grade["per_cell"]) == 48, "complete grade roster required")
    if name == "supported_abstention":
        require(grade["numeric_status"] == "missing_supported_cell_estimates"
                and grade["missing_numeric_cells"] == [cell_id]
                and grade["support_error_cells"] == [cell_id]
                and all(grade["numeric_errors"][field] is None for field in FIELDS),
                "abstention must not manufacture a complete numeric aggregate")
        return
    require(grade["numeric_status"] == "complete", "complete numeric grade required")
    if name == "one_hz_shift":
        require(type(expected_shift_errors) is list and len(expected_shift_errors) == 48,
                "all independently identified shift-control cells required")
        require(len({row["cell_id"] for row in expected_shift_errors}) == 48,
                "independent control cell identities must be unique")
        for actual, expected in zip(grade["per_cell"], expected_shift_errors):
            require(type(actual) is dict and set(actual) == set(expected)
                    and actual["cell_id"] == expected["cell_id"]
                    and actual["support_correct"] is True and actual["counts_correct"] is True,
                    "shift-control cell identity/support/count metadata changed")
            target = expected["absolute_errors_hz"]
            observed = actual["absolute_errors_hz"]
            if target is None:
                require(observed is None, "unsupported shift-control errors must stay null")
                continue
            require(type(observed) is dict and set(observed) == set(FIELDS)
                    and type(target) is dict and set(target) == set(FIELDS),
                    "exact error fields required per supported control cell")
            for field in FIELDS:
                require(type(observed[field]) is list and len(observed[field]) == 4
                        and type(target[field]) is list and len(target[field]) == 4,
                        "four control error quarters required per supported cell")
                for value, intended in zip(observed[field], target[field]):
                    control_agreement(value, intended)
    for field in FIELDS:
        error = grade["numeric_errors"][field]
        require(error["scored_values"] == 4 * supported_count, "all supported quarters must be scored")
        if name == "one_hz_shift":
            values = [value for row in expected_shift_errors
                      if row["absolute_errors_hz"] is not None
                      for value in row["absolute_errors_hz"][field]]
            require(len(values) == 4 * supported_count
                    and all(math.isfinite(value) and value > 0 for value in values),
                    "fixed shift must be representably nonzero for every supported coordinate")
            # Independent fmean aggregation differs from the producer's
            # fsum(error / count); the frozen rule permits only FP roundoff.
            control_agreement(error["mean_absolute_error_hz"], fmean(values))
            control_agreement(error["max_absolute_error_hz"], max(values))
        else:
            require(error["mean_absolute_error_hz"] == 0
                    and error["max_absolute_error_hz"] == 0, "oracle coordinates must have zero error")
    if name == "false_inference":
        require(grade["uncertainty_qualification_correct"] is False
                and grade["interpretation_scope_correct"] is False,
                "zero error must not certify invented inference")
    else:
        require(grade["uncertainty_qualification_correct"] is True
                and grade["interpretation_scope_correct"] is True, "declared descriptive scope required")
    if name == "unsupported_fabrication":
        require(grade["support_error_cells"] == [cell_id]
                and grade["unsupported_cells_given_numbers"] == [cell_id],
                "fabricated unsupported estimates must be flagged")
    else:
        require(grade["support_error_cells"] == [] and grade["unsupported_cells_given_numbers"] == [],
                "unexpected support error")
    require(grade["count_error_cells"] == ([cell_id] if name == "wrong_count" else []),
            "count differences must remain separate from numeric error")
    require(grade["support_conclusion_correct"] is True, "support conclusion drift")


def check_refusal(name, error):
    """A different validation failure must not masquerade as the intended control."""
    from packet import PacketError
    from trajectory import TrajectoryError
    expected = {
        "missing_cell": (TrajectoryError, "complete cell roster required"),
        "nonfinite_json": (PacketError, "nonfinite JSON constant: NaN"),
        "wrong_completion_identity": (TrajectoryError, "completion differs from operator-frozen identity"),
    }
    require(name in expected, "undeclared refusal control")
    exception_type, message = expected[name]
    require(type(error) is exception_type and str(error) == message,
            "refusal did not reach the intended validation boundary")


def check_saved_grade(body, returned, submission_pin):
    """Verify the persisted result, including JSON types and finite values."""
    from packet import strict_json
    saved = strict_json(body)
    require(encoded(saved) == encoded(returned), "persisted grade differs from returned result")
    require(type(saved) is dict and "submission" in saved
            and encoded(saved["submission"]) == encoded(submission_pin),
            "grade is not bound to the exact submitted candidate")


def validate_control_inventory(output, files, *, complete=False):
    """Check every entry, including empty directories and dangling symlinks."""
    layout = {"": {"submissions", "grades"} | ({"REPORT.json"} if complete else set()),
              "submissions": {Path(name).name for name in files if name.startswith("submissions/")},
              "grades": {Path(name).name for name in files if name.startswith("grades/")}}
    require(set(files) == {folder + "/" + name for folder in ("submissions", "grades")
                          for name in layout[folder]}, "unexpected control inventory path")
    for relative, expected in layout.items():
        folder = Path(output) / relative
        require(folder.is_dir() and not folder.is_symlink(), "ordinary control directory required")
        entries = list(folder.iterdir())
        require({entry.name for entry in entries} == expected, "unlisted control entry")
        for entry in entries:
            require(not entry.is_symlink(), "indirect control entry")
            if relative == "" and entry.name in ("submissions", "grades"):
                require(entry.is_dir(), "control subdirectory required")
            else:
                require(entry.is_file(), "ordinary control file required")


def exercise_grader(prepared_directory, completion_sha256, output_directory):
    """Run nine fixed controls through the actual file-based submission path.

    Requires separate operator authorization for authentic reference reads. It
    creates no participant process and does not qualify a provider or sandbox.
    """
    import prepare
    from packet import PacketError
    from score import expected_answer
    from trajectory import TrajectoryError

    output = Path(output_directory)
    require(output.is_absolute() and output.parent.is_dir()
            and not output.exists() and not output.is_symlink(), "fresh absolute output required")
    for parent in (output.parent, *output.parents):
        require(not parent.is_symlink() and not (parent / ".git").exists(),
                "private controls must remain in ordinary directories outside Git")
    reference = prepare.load_reference(Path(prepared_directory), completion_sha256)
    expected = expected_answer(reference)
    controls, supported = make_controls(expected)
    bodies = {item["name"]: encoded(item["answer"], permit_nonfinite=item["name"] == "nonfinite_json")
              for item in controls}
    require(all(len(body) <= MAX_SUBMISSION_BYTES for body in bodies.values()), "bounded control submissions required")
    # Nine bounded submissions, at most six bounded grades, and one report.
    require(sum(map(len, bodies.values())) + 6 * MAX_GRADE_BYTES + MAX_REPORT_BYTES <= MAX_CONTROL_BYTES,
            "control output upper bound exceeded")
    output.mkdir(mode=0o700)
    (output / "submissions").mkdir(mode=0o700)
    (output / "grades").mkdir(mode=0o700)
    inventory, results = {}, []
    for item in controls:
        name = item["name"]
        submission = output / "submissions" / (name + ".json")
        destination = output / "grades" / (name + ".json")
        write_fresh(submission, bodies[name])
        inventory[str(submission.relative_to(output))] = pin(bodies[name])
        frozen = ("1" if completion_sha256[0] == "0" else "0") + completion_sha256[1:] \
            if name == "wrong_completion_identity" else completion_sha256
        try:
            grade = prepare.grade_submission(Path(prepared_directory), frozen, submission, destination)
        except (PacketError, TrajectoryError) as exc:
            require(item["reject"] and not destination.exists(), "unexpected refusal or partial grade")
            check_refusal(name, exc)
            results.append({"name": name, "expected_refusal_observed": True,
                            "error_type": type(exc).__name__})
            continue
        require(not item["reject"], "invalid submission was accepted")
        check_grade(name, grade, supported, item.get("cell_id"), item.get("expected_shift_errors"))
        require(destination.is_file() and not destination.is_symlink()
                and 0 < destination.stat().st_size <= MAX_GRADE_BYTES, "bounded ordinary grade required")
        with destination.open("rb") as handle:
            grade_body = handle.read(MAX_GRADE_BYTES + 1)
        require(len(grade_body) <= MAX_GRADE_BYTES, "grade grew beyond bound")
        check_saved_grade(grade_body, grade, pin(bodies[name]))
        inventory[str(destination.relative_to(output))] = pin(grade_body)
        results.append({"name": name, "expected_behavior_observed": True,
                        "numeric_status": grade["numeric_status"]})
        if name == "one_hz_shift":
            results[-1]["independent_magnitude_calibration"] = {
                "coordinate_comparisons": 8 * supported, "aggregate_comparisons": 4,
                "cell_id_support_count_and_null_layout_checks": 48,
                "predicate": CONTROL_PREDICATE,
                "participant_scoring_or_native_tolerance_changed": False}
    require(len(results) == 9 and sum("expected_refusal_observed" in row for row in results) == 3,
            "all nine fixed controls required")
    validate_control_inventory(output, inventory)
    report = {"schema": "neural096-fixed-submission-controls/v1", "status": "passed",
              "controls": results, "files": inventory, "supported_cells": supported,
              "unsupported_cells": 48 - supported, "completion_sha256": completion_sha256,
              "model_trials": 0, "participant_attempts": 0, "scientific_inference_qualified": False,
              "full_task_completed": False,
              "scope": "Operator file-ingestion and grader controls only; programmed arithmetic is not learned neural understanding."}
    body = encoded(report)
    require(len(body) <= MAX_REPORT_BYTES
            and sum(item["bytes"] for item in inventory.values()) + len(body) <= MAX_CONTROL_BYTES,
            "control report or total exceeds cap")
    write_fresh(output / "REPORT.json", body)
    validate_control_inventory(output, inventory, complete=True)
    return {"status": "passed", "controls": 9, "accepted_grades": 6,
            "expected_refusals": 3, "report": pin(body),
            "bytes_written": sum(item["bytes"] for item in inventory.values()) + len(body),
            "files_written": len(inventory) + 1, "model_trials": 0,
            "scientific_inference_qualified": False, "full_task_completed": False}
