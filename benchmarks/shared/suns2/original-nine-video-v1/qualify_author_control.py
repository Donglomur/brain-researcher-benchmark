"""One separately admitted saved-author replay through the new grading path.

No model runs. Copy nine already authenticated author masks into a protected
numeric submission, then grade against the same source reference. Authentic
execution requires an exact root-admitted protocol; generated tests use fixtures.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


def _copy_pinned(record, target):
    source = Path(record["path"])
    _need(source == source.resolve(strict=True), "Source alias refused")
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
              before.st_size == record["bytes"], "Source identity/size refused")
        _need(128 <= before.st_size <= 16777216, "Source byte limit")
        chunks, remaining = [], before.st_size + 1
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        _need(_identity(before) == _identity(os.fstat(fd)) ==
              _identity(os.stat(source, follow_symlinks=False)),
              "Source changed while copying")
        _need(len(raw) == record["bytes"] and
              hashlib.sha256(raw).hexdigest() == record["sha256"],
              "Source bytes do not match trusted pin")
    finally:
        os.close(fd)
    output = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(output, view)
            _need(written > 0, "Copy write made no progress")
            view = view[written:]
    finally:
        os.close(output)
    return len(raw)


def execute_control(reference_spec, reference_sha256, destination, output,
                    expected_copy_bytes, procedure_digest):
    from suns2_benchmark.constants import VIDEO_IDS
    from suns2_benchmark.grade import (
        validate_reference_spec, grade_submission, _write_report,
    )
    destination, output = Path(destination), Path(output)
    _need(not destination.exists() and not destination.is_symlink(),
          "Control destination already exists; no retry")
    _need(not output.exists() and not output.is_symlink(),
          "Control report already exists; no retry")
    _need(destination.parent == destination.parent.resolve(strict=True),
          "Control parent is an alias")
    destination.mkdir(mode=0o700)
    (destination / "masks").mkdir(mode=0o700)
    spec = validate_reference_spec(reference_spec, reference_sha256, destination)
    by_id = {row["video_id"]: row for row in spec["cases"]}
    total = sum(row["author_prediction"]["bytes"] for row in spec["cases"])
    _need(type(expected_copy_bytes) is int and total == expected_copy_bytes,
          "Exact copied-source byte total differs")
    copied, records = 0, []
    for video in VIDEO_IDS:
        source = by_id[video]["author_prediction"]
        relative = f"masks/{video}.mat"
        copied += _copy_pinned(source, destination / relative)
        records.append({"video_id": video, "path": relative,
                        "bytes": source["bytes"], "sha256": source["sha256"]})
    _need(copied == expected_copy_bytes, "Incomplete author-control copy")
    manifest = {"schema": "suns2-candidate-submission/v1", "condition": "paper_data",
                "procedure_digest": procedure_digest, "cases": records}
    _need(len((json.dumps(manifest, indent=2) + "\n").encode()) <= 4096,
          "Fixed control manifest exceeds4096B")
    _write_report(destination / "submission.json", manifest)
    report = grade_submission(reference_spec, reference_sha256, destination,
                              "paper_data", procedure_digest)
    outcome = report["scores"]["descriptive_outcome"]
    _need(report["status"] == "scored_complete_panel", "Reference control undefined")
    _need(outcome["same_panel_geometry_improvement"] is False and
          outcome["geometry_changed_video_ids"] == [] and
          outcome["original_mean_delta_exact"]["numerator"] == "0" and
          outcome["audit_mean_delta_exact"]["numerator"] == "0",
          "Identical author-control masks produced a spurious improvement")
    _need([row["video_id"] for row in report["scores"]["cases"]] == list(VIDEO_IDS),
          "Control row support/order changed")
    for row in report["scores"]["cases"]:
        _need(row["geometry"]["raw_instance_order_equal"] is True,
              "Control per-video raw mask order differs")
        for field, keys in (
            ("original", ("matches", "ground_truth_instances", "prediction_instances",
                          "recall", "precision", "f1", "status", "f1_exact")),
            ("declared_order_invariant_audit", (
                "matches", "ground_truth_instances", "unique_prediction_instances",
                "raw_prediction_instances", "duplicate_prediction_instances_removed_for_audit_only",
                "f1", "f1_exact")),
        ):
            comparison = row[field]
            _need(comparison["candidate_minus_author_f1_exact"]["numerator"] == "0"
                  and comparison["candidate_minus_author_f1_float"] == 0,
                  "Control per-video score delta is not zero")
            _need(all(comparison["author"][key] == comparison["candidate"][key]
                      for key in keys), "Control per-video metric/count mismatch")
    report["fixed_control"] = {
        "kind": "saved_author_prediction_replay",
        "source_MAT_bytes_copied": copied,
        "procedure_digest": procedure_digest,
        "reference_reconstruction": "All original primary values and mean checked",
        "new_quantity": "Symmetric declared unique-geometry audit on the author outputs",
        "not_a_candidate_method_or_training_reproduction": True,
        "no_AI_or_model_execution": True,
        "condition_tag": "paper_data is a schema-control tag here; copying protected author answers is not an eligible assistance-arm trial",
    }
    _need(len((json.dumps(report, indent=2, allow_nan=False) + "\n").encode()) <= 65536,
          "Fixed replay report exceeds65536B")
    _write_report(output, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--site-packages", required=True)
    parser.add_argument("--reference-spec", required=True)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-copy-bytes", type=int, required=True)
    parser.add_argument("--procedure-digest", required=True)
    args = parser.parse_args(argv)
    _need(not any(x in sys.modules for x in ("numpy", "scipy")),
          "Scientific modules imported before controlled path initialization")
    for value in (args.source_root, args.site_packages):
        p = Path(value)
        _need(p.is_dir() and p == p.resolve(strict=True), "Noncanonical import root")
    sys.path[:0] = [args.source_root, args.site_packages]
    import numpy
    import scipy
    _need(numpy.__version__ == "2.4.6" and scipy.__version__ == "1.17.1",
          "Numerical runtime version changed")
    result = execute_control(args.reference_spec, args.reference_sha256,
                             args.destination, args.output,
                             args.expected_copy_bytes, args.procedure_digest)
    print(json.dumps({"status": result["status"], "control": "saved_author_replay",
                      "original_mean_F1": result["scores"]["original_summary"][
                          "author_mean_float"],
                      "declared_audit_mean_F1": result["scores"]["declared_audit_summary"][
                          "author_mean_float"],
                      "same_panel_geometry_improvement": False}))


if __name__ == "__main__":
    main()
