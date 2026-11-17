"""Operator packet construction, independent-reference freeze and submission grading."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from contract import (COMPONENT, DATA_SHA, REVISION, TASK, ContractError, compare,
                      digest, index_trials, read_json, reconstruct, require,
                      validate_submission, verify_independent, write_json)

HERE = Path(__file__).resolve().parent
CONDITIONS = ("paper_and_data", "paper_data_official_code")


def pin(path, entry):
    require(Path(path).is_file() and not Path(path).is_symlink(), f"ordinary file required: {path}")
    require(Path(path).stat().st_size == entry["bytes"] and digest(path) == entry["sha256"], f"source pin mismatch: {path}")


def verify_packet(packet):
    """Authenticate against this source package, never a self-authored manifest alone."""
    packet = Path(packet)
    manifest = read_json(packet / "packet.json")
    require(manifest["schema"] == "opto-candidate-packet-v1" and manifest["task_id"] == TASK and
            manifest["component"] == COMPONENT, "candidate packet identity mismatch")
    require(manifest["condition"] in CONDITIONS, "candidate condition mismatch")
    require((manifest["trials"], manifest["animals"], manifest["sessions"]) == (3304, 2, 8), "packet population mismatch")
    pins = read_json(HERE / "source-pins.json")
    sources = {s["source_path"]: s for s in pins["sources"]}
    expected = {"optoData.mat": pins["data"], "article.xml": sources["primary_article_xml"],
                "trial-roster.json": pins["trial_roster"]}
    for name in ("TASK.md", "submission-schema.json", "source-pins.json"):
        expected[name] = {"bytes": (HERE / name).stat().st_size, "sha256": digest(HERE / name)}
    if manifest["condition"] == "paper_data_official_code":
        expected.update({"official-code/" + name: row for name,row in sources.items() if name != "primary_article_xml"})
    require(set(manifest["files"]) == set(expected), "condition-specific file inventory mismatch")
    actual_paths = {p.relative_to(packet).as_posix() for p in packet.rglob("*") if p.is_file()}
    require(actual_paths == set(expected) | {"packet.json"}, "candidate packet inventory mismatch")
    require(not any(p.is_symlink() for p in packet.rglob("*")), "candidate packet symlink forbidden")
    for name, entry in expected.items():
        pin(packet / name, entry)
        require(manifest["files"][name] == {"bytes": entry["bytes"], "sha256": entry["sha256"]}, "packet manifest pin mismatch")
    return manifest


def verify_reference_population(reference):
    rows = sorted(reference["trials"], key=lambda r: (r["mouse"], r["session"], r["trial_number"]))
    roster = {"task_id": TASK, "input_sha256": DATA_SHA,
              "trials": [{k: r[k] for k in ("mouse", "session", "trial_number")} for r in rows]}
    raw = (json.dumps(roster, indent=2, allow_nan=False) + "\n").encode()
    pin = read_json(HERE / "source-pins.json")["trial_roster"]
    require(len(raw) == pin["bytes"] and hashlib.sha256(raw).hexdigest() == pin["sha256"],
            "reference must contain the complete authentic identity roster")


def prepare(mat, paper, code_root, output):
    """Construct both candidate arms and a separate unapproved operator draft."""
    from native import extract
    pins = read_json(HERE / "source-pins.json")
    pin(mat, pins["data"])
    sources = {s["source_path"]: s for s in pins["sources"]}
    pin(paper, sources["primary_article_xml"])
    for relative, entry in sources.items():
        if relative != "primary_article_xml":
            pin(Path(code_root) / relative, entry)
    rows = extract(mat)
    reference = reconstruct(rows)
    require(not Path(output).exists(), "output exists; preserve previous preparation")
    root = Path(output)
    root.mkdir(parents=True)
    operator = root / "operator"
    operator.mkdir()
    write_json(operator / "draft-reference.json", reference)
    write_json(operator / "native-bridge.json", {"task_id": TASK, "input_sha256": DATA_SHA, "rows": rows})
    roster = [{k: row[k] for k in ("mouse", "session", "trial_number")} for row in reference["trials"]]
    packets = {}
    for condition in CONDITIONS:
        packet = root / "candidates" / condition
        packet.mkdir(parents=True)
        shutil.copyfile(mat, packet / "optoData.mat")
        shutil.copyfile(paper, packet / "article.xml")
        shutil.copyfile(HERE / "TASK.md", packet / "TASK.md")
        shutil.copyfile(HERE / "submission-schema.json", packet / "submission-schema.json")
        write_json(packet / "trial-roster.json", {"task_id": TASK, "input_sha256": DATA_SHA, "trials": roster})
        shutil.copyfile(HERE / "source-pins.json", packet / "source-pins.json")
        if condition == "paper_data_official_code":
            for relative in sources:
                if relative == "primary_article_xml":
                    continue
                destination = packet / "official-code" / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(Path(code_root) / relative, destination)
        inventory = {p.relative_to(packet).as_posix(): {"bytes": p.stat().st_size, "sha256": digest(p)}
                     for p in sorted(packet.rglob("*")) if p.is_file()}
        manifest = {"schema": "opto-candidate-packet-v1", "task_id": TASK, "component": COMPONENT,
                    "condition": condition, "files": inventory, "trials": len(roster), "animals": 2, "sessions": 8,
                    "official_code_scope": "selected Figure1H calculation and parent figure script; not the whole repository",
                    "reference_included": False, "boundary": "candidate-only delivery; shared host access is policy-only",
                    "scientifically_qualified": False, "article_quantitative_reproduction": "unresolved_cue_origin_and_article_percentage_reconciliation", "time_origin_validated": False}
        write_json(packet / "packet.json", manifest)
        verify_packet(packet)
        packets[condition] = digest(packet / "packet.json")
    write_json(root / "preparation.json", {"schema": "opto-preparation-v1", "task_id": TASK,
               "input_sha256": DATA_SHA, "reference_sha256": digest(operator / "draft-reference.json"),
               "packets": packets, "trials": 3304, "animals": 2, "sessions": 8,
               "reference_state": "draft_requires_independent_check", "solver_trials": 0,
               "scientifically_qualified": False, "native_matlab_execution": False})


def freeze_reference(draft, independent, output):
    reference, check = read_json(draft), read_json(independent)
    verify_reference_population(reference)
    verify_independent(reference, check)
    require(len(reference["trials"]) == 3304, "complete authentic reference required")
    require(not Path(output).exists(), "reference output exists")
    root = Path(output)
    root.mkdir(parents=True)
    shutil.copyfile(draft, root / "reference.json")
    shutil.copyfile(independent, root / "independent-reference.json")
    write_json(root / "freeze.json", {"schema": "opto-reference-freeze-v1", "task_id": TASK,
               "reference_sha256": digest(root / "reference.json"), "independent_sha256": digest(root / "independent-reference.json"),
               "official_code_revision": REVISION, "independent_numerical_agreement": True,
               "native_matlab_execution": False, "scientifically_qualified": False,
               "article_quantitative_reproduction": "unresolved_cue_origin_and_article_percentage_reconciliation", "time_origin_validated": False})


def freeze_submission(submission, packet, attempt, output):
    require(type(attempt) is str and 1 <= len(attempt) <= 120 and attempt.isascii() and
            all(c.isalnum() or c in "-_." for c in attempt), "safe nonempty attempt ID required")
    packet = Path(packet)
    manifest = verify_packet(packet)
    suffix = Path(submission).suffix.lower()
    require(suffix in (".json", ".mat"), "submission must be JSON or MATLAB MAT")
    require(Path(submission).is_file() and not Path(submission).is_symlink(), "ordinary submission file required")
    require(Path(submission).stat().st_size <= 32*1024*1024, "submission exceeds32MiB")
    require(not Path(output).exists(), "submission freeze exists; no revision permitted")
    root = Path(output)
    root.mkdir(parents=True)
    shutil.copyfile(submission, root / ("submission" + suffix))
    # Freeze every attempt, including malformed ones, before parsing any numerical fields.
    write_json(root / "freeze.json", {"schema": "opto-submission-freeze-v1", "task_id": TASK,
               "attempt_id": attempt, "condition": manifest["condition"],
               "packet_sha256": digest(packet / "packet.json"), "input_sha256": DATA_SHA,
               "submission_file": "submission" + suffix, "submission_sha256": digest(root / ("submission" + suffix))})


def grade(reference_dir, submission_dir):
    root, candidate = Path(reference_dir), Path(submission_dir)
    freeze = read_json(root / "freeze.json")
    require(freeze["schema"] == "opto-reference-freeze-v1" and freeze["task_id"] == TASK, "reference freeze identity")
    require(digest(root / "reference.json") == freeze["reference_sha256"], "reference tampering")
    require(digest(root / "independent-reference.json") == freeze["independent_sha256"], "independent reference tampering")
    reference = read_json(root / "reference.json")
    verify_reference_population(reference)
    verify_independent(reference, read_json(root / "independent-reference.json"))
    frozen = read_json(candidate / "freeze.json")
    require(frozen["schema"] == "opto-submission-freeze-v1" and frozen["task_id"] == TASK and frozen["input_sha256"] == DATA_SHA,
            "submission freeze identity")
    require(frozen["condition"] in CONDITIONS and frozen["submission_file"] in ("submission.json", "submission.mat"), "submission freeze format")
    path = candidate / frozen["submission_file"]
    require(digest(path) == frozen["submission_sha256"], "submission changed after freeze")
    if path.suffix == ".mat":
        from native import read_submission
        submission = read_submission(path)
    else:
        submission = read_json(path)
    result = compare(reference, submission)
    result.update(attempt_id=frozen["attempt_id"], condition=frozen["condition"],
                  reference_sha256=freeze["reference_sha256"], submission_sha256=frozen["submission_sha256"],
                  packet_sha256=frozen["packet_sha256"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    for name in ("mat", "paper", "code-root", "output"):
        p.add_argument("--" + name, required=True)
    p = sub.add_parser("freeze-reference")
    for name in ("draft", "independent", "output"):
        p.add_argument("--" + name, required=True)
    p = sub.add_parser("freeze-submission")
    for name in ("submission", "packet", "attempt", "output"):
        p.add_argument("--" + name, required=True)
    p = sub.add_parser("grade")
    for name in ("reference-dir", "submission-dir", "output"):
        p.add_argument("--" + name, required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    if command == "grade":
        output = args.pop("output")
        require(not Path(output).exists(), "grade receipt exists; preserve earlier result")
        try:
            result = grade(**args)
        except (ContractError, KeyError, TypeError, ValueError, OSError) as error:
            write_json(output, {"task_id": TASK, "admissible": False, "error_type": type(error).__name__,
                               "error": str(error), "scientifically_qualified": False})
            raise SystemExit(2)
        write_json(output, result)
    else:
        globals()[command.replace("-", "_")](**args)


if __name__ == "__main__":
    main()
