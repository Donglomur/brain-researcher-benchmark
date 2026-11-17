"""MARBLE improvement preparation and post-grader diagnostics; no model/data runner.

Only public source descriptors and explicitly supplied grader JSON are read.
No command accepts a label, pickle, checkpoint, neural-data or executable input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
TASK = HERE.parents[1]
RATS = ("achilles", "buddy", "cicero", "gatsby")
METHODS = ("candidate", "marble", "cebra-time", "cebra-behavior")
CONDITIONS = ("clean", "half")
MAX_JSON_BYTES = 1_048_576


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def encode(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def parse(body):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, "nonfinite JSON"))


def capture(path, limit=MAX_JSON_BYTES, expected=None):
    path = Path(path).absolute()
    need(".." not in path.parts, "canonical path required")
    need(all(not p.is_symlink() for p in (path, *path.parents)), "linked path refused")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= limit, "bounded ordinary file required")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            body = handle.read(limit + 1)
        after = os.fstat(fd)
        named = path.lstat()
        fields = ("st_ino", "st_dev", "st_size", "st_nlink", "st_mtime_ns", "st_ctime_ns")
        need(len(body) == before.st_size and all(
            getattr(before, key) == getattr(after, key) == getattr(named, key)
            for key in fields), "file changed during capture")
        need(expected is None or pin(body) == expected, "source or report pin mismatch")
        return body
    finally:
        os.close(fd)


def load_contract():
    raw = capture(HERE / "EPISODE.json")
    episode = parse(raw)
    for relative, identity in episode["existing_dependencies"].items():
        path = Path(relative)
        need(not path.is_absolute() and ".." not in path.parts, "relative dependency")
        capture(TASK / path, expected=identity)
    baseline = parse(capture(HERE / "BASELINE_MANIFEST.json"))
    current = parse(capture(HERE / "CURRENT_COMPARATOR.json"))
    need(episode["task_id"] == "PAPER-paper-method-034", "existing task identity")
    need(tuple(row["rat"] for row in episode["support"]) == RATS, "complete rat roster")
    return episode, baseline, current, pin(raw)


def readiness(episode, baseline, current):
    # This release provides preparation, not a Boolean-attestation admission path.
    # Closing these scientific gates requires a separately reviewed evidence update.
    return {
        "schema": "marble_improvement_readiness_v1",
        "task_id": episode["task_id"],
        "preparation_available": True,
        "diagnostic_report_comparison_available": True,
        "author_baseline_admitted": baseline["baseline_admitted"],
        "execution_ready": False,
        "historical_paper_comparison_ready": False,
        "current_sota_comparison_ready": False,
        "current_best_status": current["current_best_status"],
        "open_gates": episode["readiness_gates"],
        "baseline_blockers": baseline["blocking_source_findings"],
        "models_fitted": 0,
        "labels_read": False,
    }


def support_manifest(episode):
    result = []
    source = episode["dataset"]["content_sha256_explicit"]
    for condition in CONDITIONS:
        for rat in episode["support"]:
            for phase, field in (("train", "final_fit_rows_zero_based_half_open"),
                                 ("test", "query_rows_zero_based_half_open")):
                start, stop = rat[field]
                # IDs bind original row order; they contain no target values.
                identities = "".join(f"{source}/{rat['rat']}/{i}\n"
                                     for i in range(start, stop)).encode()
                for dimension in (3, 32):
                    result.append({
                        "filename": f"{condition}-{rat['rat']}-{phase}-d{dimension}.npy",
                        "shape": [stop - start, dimension],
                        "source_rows_zero_based_half_open": [start, stop],
                        "ordered_row_identity_stream": pin(identities),
                        "row_identity_format": "source_sha256/rat/zero_based_row followed by LF",
                        "condition": condition,
                        "rat": rat["rat"],
                    })
    return {"schema": "marble_improvement_output_support_v1",
            "task_id": episode["task_id"],
            "protocol_id": episode["existing_protocol_id"],
            "source_sha256": source, "files": result,
            "query_targets_included": False, "neural_data_included": False}


def prepare(destination, episode, episode_pin):
    destination = Path(destination).absolute()
    need(not destination.exists() and not destination.is_symlink(), "fresh destination required")
    need(destination.parent.is_dir() and all(not p.is_symlink() for p in destination.parents),
         "ordinary existing destination parent required")
    support = support_manifest(episode)
    interface = {
        "schema": "marble_improvement_candidate_interface_v1",
        "episode": episode_pin,
        "status": "metadata_preparation_only_not_a_runnable_input_packet",
        "command": ["python", "-I", "-B", "/program/candidate.py",
                    "--input", "/input", "--output", "/output"],
        "input_requires": ["admitted neural training/query arrays", "training labels only",
                           "fixed public support", "paper", "official code in B only"],
        "output_contract": "Existing sibling fit-closed-comparator interface.py: all32 NPY embeddings plus its manifest; no new prediction format.",
        "support": pin(encode(support)),
        "budget": episode["budget"],
        "launch_permitted_by_this_component": False,
    }
    destination.mkdir(mode=0o700)
    for name, value in (("OUTPUT_SUPPORT.json", support), ("INTERFACE.json", interface)):
        with (destination / name).open("xb") as handle:
            handle.write(encode(value))
    return {"prepared": str(destination), "files": ["OUTPUT_SUPPORT.json", "INTERFACE.json"],
            "execution_ready": False, "labels_read": False}


def audit_author(root, baseline):
    """Admit exact source bytes already selected by the original public package."""
    root = Path(root).absolute()
    observations = []
    for member in baseline["official_source_required"]:
        path = root / member["relative"]
        try:
            body = capture(path, expected={k: member[k] for k in ("bytes", "sha256")})
            observations.append({"relative": member["relative"], "state": "exact",
                                 "identity": pin(body)})
        except (OSError, ValueError) as error:
            observations.append({"relative": member["relative"], "state": "not_admitted",
                                 "reason": str(error)})
    return {"schema": "marble_author_source_admission_v1",
            "author_revision": baseline["author_revision"],
            "files": observations,
            "all_selected_source_exact": all(r["state"] == "exact" for r in observations),
            "source_executed": False, "checkpoint_loaded": False,
            "baseline_admitted": False,
            "limitation": "Exact source is necessary but does not close training provenance, historical recipe or numerical reference gates."}


def numeric(value, label, nonnegative=False):
    need(type(value) in (int, float) and math.isfinite(value), label + " must be finite")
    need(not nonnegative or value >= 0, label + " must be nonnegative")
    return float(value)


def digest(value):
    need(type(value) is str and len(value) == 64
         and all(c in "0123456789abcdef" for c in value), "SHA256 required")


def report_check(report, arm, episode):
    need(report["schema"] == "marble_fit_closed_grade_v1", "fit-closed grader report required")
    need(report["protocol_id"] == episode["existing_protocol_id"], "fixed original split required")
    need(report["access_view"] == arm, "paired access arm mismatch")
    need(report["complete_native_provenance_admitted"] is True, "complete captured provenance required")
    # A report is still not proof that native execution or scientific parity occurred.
    need(set(report["scores"]) == set(METHODS), "all candidate and three comparator scores required")
    expected_files = {r["filename"] for r in support_manifest(episode)["files"]}
    need(set(report["captured_artifact_hashes"]) == set(METHODS), "complete artifact methods")
    for method in METHODS:
        artifacts = report["captured_artifact_hashes"][method]
        need(set(artifacts) == expected_files, "complete fixed32 artifact roster")
        for value in artifacts.values():
            digest(value)
        scores = report["scores"][method]
        need(set(scores) == set(CONDITIONS), "both fixed conditions required")
        for condition in CONDITIONS:
            score = scores[condition]
            rows = score["decoding_per_rat"]
            need(tuple(r["rat"] for r in rows) == RATS, "complete ordered rat roster")
            for row, support in zip(rows, episode["support"]):
                start, stop = support["query_rows_zero_based_half_open"]
                need(type(row["samples"]) is int and row["samples"] == stop - start,
                     "exact query row count required")
                numeric(row["mae_m"], "mean error", True)
                numeric(row["median_absolute_error_m"], "median error", True)
            aggregate = sum(row["mae_m"] for row in rows) / len(rows)
            need(math.isclose(numeric(score["equal_rat_mae_m"], "equal-rat mean", True),
                              aggregate, rel_tol=1e-12, abs_tol=1e-12),
                 "mean aggregation mismatch")
            consistency = score["consistency_12_directions"]
            if score["mean_consistency_r2"] is None:
                need(consistency == [] and bool(score["undefined_consistency_reason"]),
                     "undefined consistency requires explicit cause")
            else:
                need([(r["source"], r["target"]) for r in consistency] ==
                     [(a, b) for a in RATS for b in RATS if a != b],
                     "all12 directed consistency values required")
                values = [numeric(r["r2"], "consistency") for r in consistency]
                need(all(value <= 1.0 + 1e-12 for value in values),
                     "consistency R2 cannot exceed one")
                need(score["undefined_consistency_reason"] is None and
                     math.isclose(numeric(score["mean_consistency_r2"], "mean consistency"),
                                  sum(values) / 12, rel_tol=1e-12, abs_tol=1e-12),
                     "consistency aggregation mismatch")
    bank = report["protected_comparator_bank"]
    need(set(bank) == {"bytes", "sha256"} and type(bank["bytes"]) is int
         and bank["bytes"] > 0, "external comparator bank pin required")
    digest(bank["sha256"])


def compare_reports(a, b, episode, episode_pin, report_pins):
    for arm, report in (("A", a), ("B", b)):
        report_check(report, arm, episode)
    need(a["protected_comparator_bank"] == b["protected_comparator_bank"], "same comparator bank required")
    for method in METHODS[1:]:
        need(a["captured_artifact_hashes"][method] == b["captured_artifact_hashes"][method]
             and a["scores"][method] == b["scores"][method], "paired baselines must be identical")
    scorer_path = TASK / "implementations/fit-closed-comparator/dependencies/score_core.py"
    expected = episode["existing_dependencies"][str(scorer_path.relative_to(TASK))]
    namespace = {"__name__": "authenticated_marble_score_core"}
    # Definitions only: score() and its KNN fit are never invoked here.
    exec(compile(capture(scorer_path, expected=expected), str(scorer_path), "exec"), namespace)
    comparisons = {}
    for arm, report in (("A", a), ("B", b)):
        candidate = report["scores"]["candidate"]
        comparisons[arm] = {}
        for method in METHODS[1:]:
            baseline = report["scores"][method]
            rows = []
            for condition in CONDITIONS:
                for c, ref in zip(candidate[condition]["decoding_per_rat"],
                                  baseline[condition]["decoding_per_rat"]):
                    rows.append({"condition": condition, "rat": c["rat"],
                                 "candidate_mae_m": c["mae_m"], "baseline_mae_m": ref["mae_m"],
                                 "candidate_minus_baseline_mae_m": c["mae_m"] - ref["mae_m"]})
            comparisons[arm][method] = {
                "per_rat_effects": rows,
                "existing_scorer_diagnostic": namespace["improvement"](candidate, baseline),
            }
    return {"schema": "marble_improvement_diagnostic_comparison_v1",
            "task_id": episode["task_id"], "episode": episode_pin,
            "input_reports": report_pins, "comparisons": comparisons,
            "interpretation": "Negative delta is lower error on the declared support. Existing Boolean diagnostics are conditional on unqualified native comparator reports; they are not an awarded scientific improvement.",
            "scientific_improvement_awarded": None,
            "historical_paper_improvement": None, "current_sota_improvement": None,
            "execution_ready": False, "labels_read": False,
            "open_gates": episode["readiness_gates"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect")
    commands.add_parser("require-ready")
    prep = commands.add_parser("prepare-interface")
    prep.add_argument("--destination", required=True, type=Path)
    audit = commands.add_parser("audit-author-source")
    audit.add_argument("--author-root", required=True, type=Path)
    comparison = commands.add_parser("compare-grades")
    for arm in ("a", "b"):
        comparison.add_argument("--grade-" + arm, type=Path, required=True)
        comparison.add_argument("--grade-" + arm + "-sha256", required=True)
        comparison.add_argument("--grade-" + arm + "-bytes", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        episode, baseline, current, episode_pin = load_contract()
        if args.command in ("inspect", "require-ready"):
            result = readiness(episode, baseline, current)
        elif args.command == "prepare-interface":
            result = prepare(args.destination, episode, episode_pin)
        elif args.command == "audit-author-source":
            result = audit_author(args.author_root, baseline)
        else:
            reports, pins = {}, {}
            for arm in ("a", "b"):
                identity = {"bytes": getattr(args, "grade_" + arm + "_bytes"),
                            "sha256": getattr(args, "grade_" + arm + "_sha256")}
                digest(identity["sha256"])
                need(type(identity["bytes"]) is int and 0 < identity["bytes"] <= MAX_JSON_BYTES,
                     "bounded report extent")
                reports[arm] = parse(capture(getattr(args, "grade_" + arm), expected=identity))
                pins[arm.upper()] = identity
            result = compare_reports(reports["a"], reports["b"], episode, episode_pin, pins)
        print(encode(result).decode(), end="")
        return 2 if args.command == "require-ready" else 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error), "execution_ready": False}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
