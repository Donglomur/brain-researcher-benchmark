#!/usr/bin/env python3
"""Capture actual local Harbor oracle/nop evidence without asserting qualification.

Pass one finished trial directory, never a job aggregate. The caller records the
task fingerprint before execution and supplies it here; edits during a run are
rejected. Failed runs remain useful evidence, but cannot satisfy the validator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from validate_neuro_tasks import Audit


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(task: Path, authoring: Path, trial: Path, kind: str,
            expected_fingerprint: str, command: list[str], harbor_version: str,
            run_id: str) -> dict:
    if kind not in {"oracle", "nop"}:
        raise ValueError("Only local oracle/nop evidence is supported")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", run_id):
        raise ValueError("run_id must be a simple directory name")
    if not command or any(not isinstance(x, str) or not x for x in command):
        raise ValueError("Record the actual nonempty command as an array of strings")
    task, authoring, trial = task.resolve(), authoring.resolve(), trial.resolve()
    audit = Audit(task, authoring)
    audit.input_lock()
    fingerprint = audit.fingerprint()
    if fingerprint != expected_fingerprint:
        raise ValueError("Task changed since the supplied pre-run fingerprint")
    result_path = trial / "result.json"
    result = json.loads(result_path.read_text())
    if not isinstance(result.get("agent_info"), dict) or result["agent_info"].get("name") != kind:
        raise ValueError("This is not a single trial result for the selected agent")
    if not result.get("finished_at") or not result.get("task_checksum"):
        raise ValueError("Trial is unfinished or lacks its native task checksum")
    if result.get("task_name") not in {task.name, "terminal-bench-science/" + task.name}:
        raise ValueError("Trial identifies a different task")
    required = {
        "result": result_path,
        "reward": trial / "verifier/reward.txt",
        "ctrf": trial / "verifier/ctrf.json",
    }
    if not required["reward"].is_file():
        required["reward"] = trial / "verifier/reward.json"
    for name, path in required.items():
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing regular {name} evidence: {path}")
    destination = authoring / "evidence/harbor" / run_id
    if destination.exists():
        raise ValueError("Never overwrite an existing captured trial")
    qualification_path = authoring / "evidence/qualification.json"
    qualification = json.loads(qualification_path.read_text())
    destination.mkdir(parents=True)
    record = {
        "status": "recorded", "task_fingerprint": fingerprint,
        "command": command, "harbor_version": harbor_version,
        "completed_at": result["finished_at"],
    }
    for name, source in required.items():
        target = destination / source.name
        shutil.copyfile(source, target)
        record[name + "_path"] = target.relative_to(authoring).as_posix()
        record[name + "_sha256"] = digest(target)
    # Keep the behavioral test failure and oracle execution output for diagnosis.
    for relative in ("trial.log", "verifier/test-stdout.txt", "agent/oracle.txt"):
        source = trial / relative
        if source.is_file() and not source.is_symlink():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    (destination / "capture.json").write_text(json.dumps(record, indent=2) + "\n")
    qualification.setdefault("runs", {})[kind] = record
    qualification_path.write_text(json.dumps(qualification, indent=2, allow_nan=False) + "\n")
    return {"captured": str(destination), "agent": kind,
            "reward": result.get("verifier_result"),
            "exception": result.get("exception_info"),
            "qualification": "Not inferred; run validate_neuro_tasks.py with runtime evidence"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("task", "authoring", "trial"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--kind", choices=("oracle", "nop"), required=True)
    parser.add_argument("--expected-fingerprint", required=True)
    parser.add_argument("--command-json", required=True)
    parser.add_argument("--harbor-version", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(json.dumps(capture(args.task, args.authoring, args.trial, args.kind,
                             args.expected_fingerprint, json.loads(args.command_json),
                             args.harbor_version, args.run_id), indent=2))


if __name__ == "__main__":
    main()
