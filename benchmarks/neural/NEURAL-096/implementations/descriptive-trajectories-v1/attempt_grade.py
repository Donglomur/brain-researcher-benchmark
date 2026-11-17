"""Operator-only bridge from a sealed participant answer to the existing grader.

This module is not a participant tool. It does not change the descriptive
estimand, numerical scoring or uncertainty rules. Source-level binding checks
do not establish provider or operating-system isolation. Importing this module
does not load scientific dependencies or read data.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import stat


MAX_MANIFEST_BYTES = 64 * 1024
MAX_ANSWER_BYTES = 128 * 1024
MAX_GRADE_BYTES = 512 * 1024
MAX_RECEIPT_BYTES = 16 * 1024


class AttemptGradeError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AttemptGradeError(message)


def pin(body):
    require(type(body) is bytes, "bytes required")
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def digest(value):
    require(type(value) is str and len(value) == 64
            and all(c in "0123456789abcdef" for c in value), "frozen SHA256 required")
    return value


def commitment(value, cap):
    require(type(value) is dict and set(value) == {"bytes", "sha256"}, "exact commitment required")
    require(type(value["bytes"]) is int and 0 < value["bytes"] <= cap, "commitment size bound")
    digest(value["sha256"])
    return value


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def strict_json(body):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out

    def nonfinite(_):
        raise AttemptGradeError("nonfinite JSON constant")

    def finite_float(text):
        value = float(text)
        require(math.isfinite(value), "nonfinite JSON number")
        return value

    try:
        return json.loads(body, object_pairs_hook=pairs, parse_constant=nonfinite,
                          parse_float=finite_float)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise AttemptGradeError("bounded valid JSON required") from error


def same(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(same(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    if type(left) is float:
        return math.isfinite(left) and math.isfinite(right) and left == right
    return left == right


def ordinary_path(value, *, existing=True, directory=False):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "absolute ordinary path required")
    for ancestor in reversed(path.parents):
        info = ancestor.lstat()
        require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),
                "ordinary directory ancestors required")
    if existing:
        info = path.lstat()
        expected = stat.S_ISDIR if directory else stat.S_ISREG
        require(expected(info.st_mode) and not stat.S_ISLNK(info.st_mode), "ordinary path required")
    else:
        require(not os.path.lexists(path), "fresh output required")
    return path


def bounded_file(value, cap):
    path = ordinary_path(value)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= cap, "bounded regular file required")
        body = handle.read(cap + 1)
        after = os.fstat(handle.fileno())
    require(len(body) == before.st_size <= cap and (before.st_dev, before.st_ino,
            before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino,
            after.st_size, after.st_mtime_ns), "input changed while reading")
    return body


def write_fresh(path, body, cap):
    require(type(body) is bytes and 0 < len(body) <= cap, "bounded output bytes required")
    ordinary_path(path, existing=False)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())


def _attempt_module():
    return importlib.import_module("attempt")


def _grader_module():
    # The operator launcher must authenticate trusted source/import locations.
    return importlib.import_module("prepare")


def grade_attempt(prepared_directory, completion_sha256, observation_manifest,
                  observation_manifest_sha256, attempt_directory,
                  attempt_manifest_sha256, final_receipt_sha256, output_directory,
                  participant_material_roots):
    """Grade one sealed answer into a fresh private operator-only directory.

    The caller supplies independently frozen commitments, including the final
    receipt hash returned at capture time and retained in operator custody.
    Re-deriving that expected hash from the current FINAL file defeats the
    cross-time mutation check. The observation
    manifest is operator metadata, never an additional participant response.
    Its containing directory is treated as the dedicated protected observation
    bundle; callers must not supply an unrelated broad parent via a detached
    metadata copy and expect grading output within that protected directory.
    All source/grader code must be loaded from trusted operator paths. A failed
    output directory is retained and cannot be reused for an automatic retry.
    The operator must supply both actual participant material roots. Lexical
    placement checks prevent accidental mixing/publication; they do not create
    an OS access boundary or prove that the caller declared every exposed path.
    """
    for value in (completion_sha256, observation_manifest_sha256,
                  attempt_manifest_sha256, final_receipt_sha256):
        digest(value)
    manifest_body = bounded_file(observation_manifest, MAX_MANIFEST_BYTES)
    require(pin(manifest_body)["sha256"] == observation_manifest_sha256,
            "operator observation manifest differs from frozen identity")
    observation = strict_json(manifest_body)
    require(type(observation) is dict
            and observation.get("schema") == "neural096-observation-delivery-manifest/v1",
            "observation delivery manifest required")
    binding = observation.get("source_binding")
    require(type(binding) is dict and set(binding) == {
        "preparation_completion_sha256", "preparation_receipt", "observation"},
        "exact preparation-to-observation binding required")
    require(binding["preparation_completion_sha256"] == completion_sha256,
            "observation manifest belongs to another preparation")
    commitment(binding["preparation_receipt"], 128 * 1024)
    commitment(binding["observation"], 4 * 1024 * 1024)
    files = observation.get("files")
    require(type(files) is dict and same(files.get("programme/observations.json"), binding["observation"]),
            "programme observation commitment changed")

    attempt = _attempt_module()
    final = attempt.verify_final(Path(attempt_directory), attempt_manifest_sha256, final_receipt_sha256)
    require(type(final) is dict and {"manifest", "receipt", "receipt_pin", "answer_bytes", "log"} <= set(final),
            "verified final-capture result required")
    attempt_manifest, answer = final["manifest"], final["answer_bytes"]
    require(type(attempt_manifest) is dict, "attempt manifest required")
    for field, expected in {
        "observation_manifest_sha256": observation_manifest_sha256,
        "observation_sha256": binding["observation"]["sha256"],
        "preparation_completion_sha256": completion_sha256,
    }.items():
        require(attempt_manifest.get(field) == expected, "attempt condition differs: " + field)
    require(attempt_manifest.get("arm") in ("native", "programme"), "declared attempt arm required")
    require(type(answer) is bytes and 0 < len(answer) <= MAX_ANSWER_BYTES, "bounded captured answer required")
    commitment(final["receipt_pin"], MAX_RECEIPT_BYTES)
    require(final["receipt_pin"]["sha256"] == final_receipt_sha256,
            "verified final capture differs from independently frozen final identity")
    answer_pin = pin(answer)

    output = ordinary_path(output_directory, existing=False)
    require(type(participant_material_roots) in (tuple, list) and len(participant_material_roots) == 2,
            "both participant material roots required")
    materials = [ordinary_path(p, directory=True) for p in participant_material_roots]
    require(materials[0] != materials[1], "distinct participant material roots required")
    protected = materials + [ordinary_path(attempt_directory, directory=True),
                             ordinary_path(prepared_directory, directory=True),
                             ordinary_path(Path(observation_manifest).parent, directory=True)]
    require(all(output != root and output not in root.parents and root not in output.parents
                for root in protected), "private grading output overlaps protected input or participant material")
    require(not any(os.path.lexists(parent / ".git") for parent in output.parents),
            "private grading output must be outside Git repositories")
    output.mkdir(mode=0o700)
    write_fresh(output / "SUBMISSION.json", answer, MAX_ANSWER_BYTES)
    try:
        grader = _grader_module()
        result = grader.grade_submission(Path(prepared_directory), completion_sha256,
                                         output / "SUBMISSION.json", output / "GRADE.json")
        grade_body = bounded_file(output / "GRADE.json", MAX_GRADE_BYTES)
        saved_grade = strict_json(grade_body)
        require(same(saved_grade, result), "saved grade differs from returned grade")
        require(type(result) is dict and same(result.get("submission"), answer_pin),
                "grade is not bound to captured answer bytes")
        require(bounded_file(output / "SUBMISSION.json", MAX_ANSWER_BYTES) == answer,
                "captured submission copy changed during grading")
        final_after = attempt.verify_final(Path(attempt_directory), attempt_manifest_sha256, final_receipt_sha256)
        require(same(final_after, final), "sealed attempt changed during grading")
        require({p.name for p in output.iterdir()} == {"SUBMISSION.json", "GRADE.json"},
                "unlisted private grading output before success receipt")
        receipt = {
            "schema": "neural096-operator-attempt-grade/v1", "status": "graded",
            "attempt_manifest_sha256": attempt_manifest_sha256,
            "frozen_final_receipt_sha256": final_receipt_sha256,
            "final_receipt": final["receipt_pin"], "arm": attempt_manifest["arm"],
            "observation_manifest": pin(manifest_body), "observation": binding["observation"],
            "preparation_completion_sha256": completion_sha256,
            "submission": answer_pin, "grade": pin(grade_body),
            "scoring": "Existing prepare.grade_submission unchanged; continuous errors and separate support/uncertainty conclusions.",
            "native_tolerance_relaxed": False, "participant_feedback_delivered": False,
            "placement": "Outside declared participant material, sealed attempt, preparation, observation bundle and Git paths; caller declarations remain trusted.",
            "provider_transport_qualified": False, "OS_isolation_qualified": False,
            "scientific_inference_qualified": False, "learned_neural_understanding_established": False,
            "full_task_completed": False,
        }
        write_fresh(output / "RECEIPT.json", encoded(receipt), MAX_RECEIPT_BYTES)
        require({p.name for p in output.iterdir()} == {"SUBMISSION.json", "GRADE.json", "RECEIPT.json"},
                "unlisted private grading output")
        return {"status": "graded", "receipt": pin(encoded(receipt)), "arm": attempt_manifest["arm"],
                "files_written": 3, "participant_feedback_delivered": False,
                "provider_transport_qualified": False, "OS_isolation_qualified": False,
                "full_task_completed": False}
    except Exception as error:
        failure = {"schema": "neural096-operator-attempt-grade-failure/v1", "status": "failed",
                   "attempt_manifest_sha256": attempt_manifest_sha256, "submission": answer_pin,
                   "frozen_final_receipt_sha256": final_receipt_sha256,
                   "error_type": type(error).__name__, "error": str(error)[:1024],
                   "automatic_retry": False, "participant_feedback_delivered": False}
        write_fresh(output / "FAILURE.json", encoded(failure), MAX_RECEIPT_BYTES)
        raise
