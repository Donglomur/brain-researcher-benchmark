"""Trusted offline grading coordinator; never executes participant code.

The operator supplies the reference-spec digest, condition and frozen procedure
digest independently. A submission's matching digest does not prove that the
procedure produced its masks. Authentic execution requires the separate approved
native protocol; construction controls use generated references only.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

from .constants import VIDEO_IDS, ASSISTANCE_CONDITIONS, TASK_SLUG
from .candidate_io import load_candidate_submission, load_trusted_mask
from .scoring import score_panel, AUDIT_NAME

SPEC_LIMIT = 131072
REPORT_LIMIT = 1048576
REFERENCE_AGREEMENT_ATOL = 1e-12


class GradingError(ValueError):
    """An operator reference or complete submission failed admission."""


def _require(condition, message):
    if not condition:
        raise GradingError(message)


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def _keys(value, expected, label):
    _require(type(value) is dict and set(value) == set(expected),
             f"{label}: exact keys required")


def _read_spec(path, expected_sha256):
    _require(_digest(expected_sha256), "Trusted reference digest is required")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                 "Reference specification must be one regular file")
        _require(0 < before.st_size <= SPEC_LIMIT, "Reference specification size")
        chunks, remaining = [], before.st_size + 1
        while remaining:
            piece = os.read(fd, min(65536, remaining))
            if not piece:
                break
            chunks.append(piece)
            remaining -= len(piece)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        _require((before.st_dev, before.st_ino, before.st_size,
                  before.st_mtime_ns, before.st_ctime_ns) ==
                 (after.st_dev, after.st_ino, after.st_size,
                  after.st_mtime_ns, after.st_ctime_ns), "Reference spec changed")
        _require(len(raw) == before.st_size, "Reference spec changed length")
        _require(hashlib.sha256(raw).hexdigest() == expected_sha256,
                 "Reference specification digest mismatch")
    finally:
        os.close(fd)
    try:
        return json.loads(raw, object_pairs_hook=_unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              GradingError("Non-finite JSON number")))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise GradingError("Invalid reference JSON") from exc


def validate_reference_spec(path, expected_sha256, submission_directory):
    """Validate all reference metadata before opening any mask member."""
    submission_root = Path(submission_directory).resolve(strict=True)
    _require(not Path(path).resolve(strict=True).is_relative_to(submission_root),
             "Operator specification cannot be inside participant submission")
    spec = _read_spec(path, expected_sha256)
    _keys(spec, {"schema", "task", "cases", "expected_reference", "provenance"},
          "Operator reference")
    _require(spec["schema"] == "suns2-operator-reference/v1" and
             spec["task"] == TASK_SLUG, "Wrong reference schema/task")
    _keys(spec["provenance"], {"input_manifest_sha256", "saved_result_sha256"},
          "Reference provenance")
    _require(all(_digest(v) for v in spec["provenance"].values()),
             "Invalid reference provenance digest")
    cases = spec["cases"]
    _require(type(cases) is list and len(cases) == len(VIDEO_IDS),
             "All nine reference cases required")
    seen, paths = set(), set()
    for case in cases:
        _keys(case, {"video_id", "ground_truth", "author_prediction"},
              "Reference case")
        video = case["video_id"]
        _require(video in VIDEO_IDS and video not in seen,
                 "Wrong/duplicate reference video")
        seen.add(video)
        for role, variable in (("ground_truth", "FinalMasks"),
                               ("author_prediction", "Masks")):
            record = case[role]
            _keys(record, {"path", "bytes", "sha256", "variable"}, role)
            _require(type(record["path"]) is str and Path(record["path"]).is_absolute(),
                     "Reference path must be operator-supplied absolute path")
            resolved = Path(record["path"]).resolve(strict=True)
            _require(not resolved.is_relative_to(submission_root),
                     "Reference masks cannot be participant submission files")
            _require(resolved not in paths, "Duplicate reference path")
            paths.add(resolved)
            _require(type(record["bytes"]) is int and 128 <= record["bytes"] <= 16777216,
                     "Reference source-byte bound")
            _require(_digest(record["sha256"]) and record["variable"] == variable,
                     "Reference hash/variable mismatch")
    _require(seen == set(VIDEO_IDS), "Incomplete reference support")
    expected = spec["expected_reference"]
    _keys(expected, {"cases", "mean_f1"}, "Expected reference")
    _require(type(expected["cases"]) is dict and
             set(expected["cases"]) == set(VIDEO_IDS), "Expected-score support")
    values = [expected["mean_f1"]]
    for row in expected["cases"].values():
        _keys(row, {"recall", "precision", "f1"}, "Expected reference row")
        values.extend(row.values())
    _require(all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1
                 for x in values), "Invalid expected reference score")
    return spec


def _original_reference_control(score, expected):
    for row in score["cases"]:
        author = row["original"]["author"]
        for name in ("recall", "precision", "f1"):
            value = author[name]
            _require(value is not None and math.isclose(
                value, expected["cases"][row["video_id"]][name],
                rel_tol=0, abs_tol=REFERENCE_AGREEMENT_ATOL),
                "Original author-reference reconstruction mismatch")
    _require(math.isclose(score["original_summary"]["author_mean_float"],
                         expected["mean_f1"], rel_tol=0,
                         abs_tol=REFERENCE_AGREEMENT_ATOL),
             "Original author-reference mean mismatch")
    return {"status": "all_27_primary_values_and_mean_agree",
            "absolute_tolerance": REFERENCE_AGREEMENT_ATOL,
            "tolerance_role": "Numerical reconstruction agreement only; not improvement margin"}


def grade_submission(reference_spec_path, reference_spec_sha256,
                     submission_directory, expected_condition,
                     expected_procedure_digest):
    """Grade numeric artifacts on all nine cases with independent operator pins.

    This callable does not launch a candidate or prove where its masks came from.
    No partial-panel score or hidden feedback is emitted before complete admission.
    """
    _require(expected_condition in ASSISTANCE_CONDITIONS,
             "A trusted assistance condition is required")
    _require(_digest(expected_procedure_digest), "Trusted procedure digest required")
    spec = validate_reference_spec(reference_spec_path, reference_spec_sha256,
                                   submission_directory)
    # Admit the complete candidate set before decoding any protected reference.
    candidate, submission = load_candidate_submission(
        submission_directory, expected_condition, expected_procedure_digest)
    gt, author, references = {}, {}, []
    by_video = {row["video_id"]: row for row in spec["cases"]}
    for video in VIDEO_IDS:
        case = by_video[video]
        for role, output in (("ground_truth", gt), ("author_prediction", author)):
            record = case[role]
            value, metadata = load_trusted_mask(
                record["path"], record["variable"], record["sha256"], record["bytes"])
            output[video] = value
            # Do not include protected filesystem paths or mask contents in report.
            references.append({"video_id": video, "role": role,
                               "bytes": record["bytes"], "sha256": record["sha256"]})
    score = score_panel(gt, author, candidate)
    control = _original_reference_control(score, spec["expected_reference"])
    return {"schema": "suns2-trusted-offline-grading/v1",
            "status": score["status"], "task": TASK_SLUG,
            "condition": expected_condition,
            "procedure_digest": expected_procedure_digest,
            "reference_spec_sha256": reference_spec_sha256,
            "reference_original_control": control,
            "reference_members": references,
            "submission": submission, "scores": score,
            "declared_audit": AUDIT_NAME,
            "execution_scope": {
                "participant_code_executed": False,
                "candidate_production_attested": False,
                "native_admission_attested_by_this_function": False,
                "scope": "Trusted complete-panel numeric artifact grading only",
                "not_proved": "Procedure execution, held-label isolation of that execution, fresh training, population inference, global SOTA or benchmark readiness"}}


def _write_report(path, report):
    raw = (json.dumps(report, indent=2, allow_nan=False) + "\n").encode()
    _require(len(raw) <= REPORT_LIMIT, "Grading report size bound")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            _require(written > 0, "Grading report write made no progress")
            view = view[written:]
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-spec", required=True)
    parser.add_argument("--reference-spec-sha256", required=True)
    parser.add_argument("--submission", required=True)
    parser.add_argument("--condition", choices=ASSISTANCE_CONDITIONS, required=True)
    parser.add_argument("--procedure-digest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = grade_submission(args.reference_spec, args.reference_spec_sha256,
                              args.submission, args.condition, args.procedure_digest)
    _write_report(args.output, report)
    print(json.dumps({"status": report["status"],
                      "same_panel_geometry_improvement": report["scores"][
                          "descriptive_outcome"]["same_panel_geometry_improvement"]}))


if __name__ == "__main__":
    main()
