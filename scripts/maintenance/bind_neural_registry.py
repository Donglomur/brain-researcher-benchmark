#!/usr/bin/env python3
"""Bind revised neural definitions without rewriting their preserved predecessors.

The neural definition builder owns task.json, understanding.v1.json and exact
historical task bytes. This command writes only the current registry and its
immutable pre-understanding snapshot. The default is a read-only freshness check.
No implementation, recording, candidate or private source locator is executed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = "benchmarks/registry.json"
SNAPSHOT = "docs/provenance/registrations/neural-pre-understanding-v1.json"
HISTORY = "historical/task.pre-understanding.v1.json"
VERSION = "neural-understanding/v1"
OBJECTIVE = "infer_neural_or_behavioral_targets_from_permitted_observations"
MEMBER_LIMIT = 4 * 1024 * 1024
TOTAL_LIMIT = 32 * 1024 * 1024
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def strict_json(body, name):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key in " + name + ": " + key)
            result[key] = value
        return result

    def constant(value):
        raise ValueError("nonfinite JSON in " + name + ": " + value)

    document = json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
    require(type(document) is dict, "metadata object required: " + name)
    # JSON exponent overflow must be refused as well as literal Infinity/NaN.
    encode(document)
    return document


def relative(value):
    require(type(value) is str and value and "\\" not in value
            and not any(ord(char) < 32 or ord(char) == 127 for char in value),
            "ordinary relative source path required")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value
            and all(part not in ("", ".", "..", ".git") for part in value.split("/")),
            "normalized repository-relative source path required: " + value)
    return value


def safe_path(root, name):
    path = root / relative(name)
    for current in (*reversed(path.parents), path):
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if current == path:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                    "ordinary single-link source file required: " + name)
        else:
            require(stat.S_ISDIR(info.st_mode), "ordinary source directory required: " + name)
    return path


def stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


class Reader:
    def __init__(self, root):
        self.root = Path(root).absolute()
        require(self.root.is_dir(), "repository root is missing")
        require(all(not value.is_symlink() for value in (self.root, *self.root.parents)),
                "repository root must have ordinary directory ancestors")
        self.total = 0
        self.captured = {}

    def read(self, name):
        path = safe_path(self.root, name)
        before = path.stat()
        require(0 < before.st_size <= MEMBER_LIMIT, "metadata member exceeds byte limit: " + name)
        if name in self.captured:
            old, raw = self.captured[name]
            require(stamp(before) == old, "metadata changed during preflight: " + name)
            return raw
        require(self.total + before.st_size <= TOTAL_LIMIT, "metadata read budget exceeded")
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            require(stamp(opened) == stamp(before), "metadata changed before capture: " + name)
            raw = handle.read(before.st_size + 1)
            require(stamp(os.fstat(handle.fileno())) == stamp(before) == stamp(path.stat()),
                    "metadata changed during capture: " + name)
        require(len(raw) == before.st_size, "metadata extent changed: " + name)
        self.total += len(raw)
        self.captured[name] = (stamp(before), raw)
        return raw

    def document(self, name):
        return strict_json(self.read(name), name)


def pin(name, body):
    return {"path": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def descriptor(value, label):
    require(type(value) is dict and set(value) == {"path", "bytes", "sha256"},
            "closed descriptor required: " + label)
    relative(value["path"])
    require(type(value["bytes"]) is int and 0 < value["bytes"] <= MEMBER_LIMIT
            and type(value["sha256"]) is str and SHA256.fullmatch(value["sha256"]),
            "invalid descriptor: " + label)


def checked_pin(value, name, body, label):
    descriptor(value, label)
    require(value == pin(name, body), "pin mismatch: " + label)


def task_rows(document):
    require(type(document.get("schema_version")) is int and document["schema_version"] == 1
            and document.get("kind") == "neuroscience_benchmark_registry",
            "unsupported benchmark registry")
    rows = document.get("tasks")
    require(type(rows) is list and 0 < len(rows) <= 1000, "bounded registry roster required")
    identifiers = set()
    neural = {}
    for row in rows:
        require(type(row) is dict and type(row.get("id")) is str
                and SAFE_ID.fullmatch(row["id"]) and row["id"].casefold() not in identifiers,
                "unsafe or duplicate registered identity")
        identifiers.add(row["id"].casefold())
        require(row.get("track") in ("paper", "neural"), "unknown registered track")
        if row["track"] != "neural":
            continue
        identifier = row["id"]
        home = "benchmarks/neural/" + identifier
        require(row.get("task_directory") == home, "neural task directory mismatch: " + identifier)
        descriptor(row.get("specification"), "neural specification")
        require(row["specification"]["path"] == home + "/task.json", "neural specification location mismatch")
        descriptor(row.get("original_specification"), "original neural specification")
        require(type(row.get("specification_id")) is str and SAFE_ID.fullmatch(row["specification_id"])
                and type(row.get("specification_alias")) is bool
                and row["specification_alias"] == (row["specification_id"] != identifier),
                "neural specification identity/alias mismatch")
        neural[identifier] = row
    require(neural, "neural registry roster is empty")
    return neural


def identity(row, document, label):
    observed = document.get("id", document.get("candidate_id", document.get("task_id")))
    require(observed == row["specification_id"] and document.get("track", "neural") == "neural",
            label + " identity/track mismatch: " + row["id"])


def load_engine(reader):
    name = "src/neurobench/neural_understanding.py"
    source = reader.read(name)
    path = reader.root / name
    spec = importlib.util.spec_from_file_location("_neural_registry_binding_engine", path)
    require(spec is not None and spec.loader is not None, "cannot load neural understanding validator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    exec(compile(source, str(path), "exec"), module.__dict__)
    require(callable(getattr(module, "validate_contract", None))
            and callable(getattr(module, "summary", None)), "neural contract validation/summary API required")
    return module


def build_outputs(root=ROOT, *, engine=None):
    """Validate all neural source/history bindings, then return registry output bytes.

    A test engine may be supplied for compact lineage fixtures. CLI execution
    always loads the reviewed neural_understanding.py beside the other framework.
    """
    reader = Reader(root)
    current_body = reader.read(REGISTRY)
    current = strict_json(current_body, REGISTRY)
    current_rows = task_rows(current)
    metadata = current.get("neural_understanding")
    snapshot_path = safe_path(reader.root, SNAPSHOT)
    snapshot_body = reader.read(SNAPSHOT) if snapshot_path.exists() else current_body
    previous = strict_json(snapshot_body, SNAPSHOT)
    previous_rows = task_rows(previous)
    require("neural_understanding" not in previous
            and all("specification_revision" not in row for row in previous_rows.values()),
            "historical registry must precede the neural revision")
    require(set(current_rows) == set(previous_rows), "neural historical roster mismatch")
    require({row["id"] for row in previous["tasks"]} <= {row["id"] for row in current["tasks"]},
            "historical registration removed from current roster")
    expected_meta = {"schema_version": VERSION, "objective": OBJECTIVE, "coverage_required": True,
                     "registered_count": len(current_rows), "pre_understanding_registry": pin(SNAPSHOT, snapshot_body)}
    if metadata is None:
        require(all("specification_revision" not in row for row in current_rows.values()),
                "neural revisions require their coverage metadata")
    else:
        require(snapshot_path.exists(), "historical registry snapshot missing")
        require(type(metadata) is dict and type(metadata.get("registered_count")) is int
                and metadata.get("coverage_required") is True
                and metadata == expected_meta, "neural coverage metadata or historical snapshot mismatch")
    engine = engine if engine is not None else load_engine(reader)
    result = copy.deepcopy(current)
    result_rows = {row["id"]: row for row in result["tasks"]}
    for identifier, row in current_rows.items():
        old = previous_rows[identifier]
        for field in ("id", "track", "task_directory", "original_specification", "specification_id", "specification_alias"):
            require(row.get(field) == old.get(field), "original neural registration drift: " + field + ": " + identifier)
        home = row["task_directory"]
        history_path = home + "/" + HISTORY
        historical_body = reader.read(history_path)
        historical = strict_json(historical_body, history_path)
        checked_pin(old["specification"], home + "/task.json", historical_body, "historical neural bytes")
        require(all(old["original_specification"][key] == old["specification"][key] for key in ("bytes", "sha256")),
                "historical neural original identity mismatch")
        identity(old, historical, "historical neural definition")
        require(historical.get("objective") != OBJECTIVE, "historical neural task is already revised")
        history_pin = pin(history_path, historical_body)
        revision = row.get("specification_revision")
        if metadata is None:
            require(row["specification"] == old["specification"], "unbound original specification pin drift")
        else:
            require(type(revision) is dict and set(revision) ==
                    {"version", "previous_specification", "understanding_contract"}
                    and revision.get("version") == VERSION and revision.get("previous_specification") == history_pin,
                    "existing neural revision history mismatch")
            descriptor(revision["understanding_contract"], "existing neural understanding contract")
            require(revision["understanding_contract"]["path"] == home + "/understanding.v1.json",
                    "existing neural contract location mismatch")
        contract_path = home + "/understanding.v1.json"
        contract_body = reader.read(contract_path)
        contract = strict_json(contract_body, contract_path)
        require(contract.get("schema_version") == VERSION and contract.get("task_id") == identifier
                and contract.get("objective") == OBJECTIVE, "neural contract identity mismatch")
        errors = engine.validate_contract(contract, task_id=identifier)
        require(type(errors) is list and not errors, "invalid neural contract: " + identifier + ": " + str(errors))
        contract_pin = pin(contract_path, contract_body)
        task_path = home + "/task.json"
        task_body = reader.read(task_path)
        task = strict_json(task_body, task_path)
        identity(row, task, "current neural definition")
        expected_binding = {"schema_version": VERSION, "objective": OBJECTIVE,
                            "contract_path": "understanding.v1.json", "contract_sha256": contract_pin["sha256"],
                            "original_definition_path": HISTORY, "original_definition_sha256": history_pin["sha256"]}
        require(task.get("objective") == OBJECTIVE and type(task.get("evaluation")) is dict
                and task["evaluation"].get("neural_understanding") == expected_binding,
                "current neural definition contract/history binding mismatch")
        admission = task.get("admission")
        require(type(admission) is dict and admission.get("runnable") is False
                and admission.get("research_qualified") is False,
                "neural source binding cannot promote runtime or scientific admission")
        require(type(task.get("title")) is str and bool(task["title"].strip()), "current neural title required")
        summary = engine.summary(contract)
        require(type(summary) is dict and summary.get("schema_version") == VERSION
                and summary.get("objective") == OBJECTIVE, "invalid neural contract summary")
        result_rows[identifier].update(
            title=task["title"], declared_specification_status=task.get("status", task.get("state")),
            specification=pin(task_path, task_body),
            specification_revision={"version": VERSION, "previous_specification": history_pin,
                                    "understanding_contract": contract_pin},
            neural_understanding=summary, scientific_readiness="unknown", submission_readiness="not_qualified_by_binding")
    result["neural_understanding"] = expected_meta
    outputs = {SNAPSHOT: snapshot_body, REGISTRY: encode(result)}
    for name in outputs:
        safe_path(reader.root, name)
    return outputs


def write_or_check(root=ROOT, *, write=False, engine=None):
    root = Path(root).absolute()
    outputs = build_outputs(root, engine=engine)
    before = {name: safe_path(root, name).read_bytes() if safe_path(root, name).exists() else None for name in outputs}
    stale = [name for name, body in outputs.items() if before[name] != body]
    if write and stale:
        require(outputs == build_outputs(root, engine=engine), "binding inputs changed during preflight")
        for name, expected in before.items():
            path = safe_path(root, name)
            require((path.read_bytes() if path.exists() else None) == expected,
                    "binding output changed during preflight: " + name)
        for name in stale:
            path, body = safe_path(root, name), outputs[name]
            path.parent.mkdir(parents=True, exist_ok=True)
            if name == SNAPSHOT:
                # Historical bytes are never replaced, even if a concurrent writer
                # appears after preflight. A failed later replace is retryable.
                with path.open("xb") as handle:
                    handle.write(body)
                    handle.flush()
                    os.fsync(handle.fileno())
            else:
                mode = path.stat().st_mode & 0o777
                descriptor_number, temporary = tempfile.mkstemp(prefix=".neural-registry-", dir=path.parent)
                try:
                    with os.fdopen(descriptor_number, "wb") as handle:
                        os.fchmod(handle.fileno(), mode)
                        handle.write(body)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temporary, path)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
    registry = strict_json(outputs[REGISTRY], REGISTRY)
    return {"status": "written" if write and stale else "stale" if stale else "current",
            "changed_files": stale, "neural_registrations": registry["neural_understanding"]["registered_count"],
            "pre_understanding_registry": registry["neural_understanding"]["pre_understanding_registry"],
            "scientific_qualification": "not_established_by_binding", "benchmark_execution": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--write", action="store_true", help="bind current source after full validation")
    modes.add_argument("--check", action="store_true", help="read-only freshness check (the default)")
    args = parser.parse_args(argv)
    try:
        result = write_or_check(args.root, write=args.write)
        print(json.dumps(result, indent=2))
        return 1 if result["status"] == "stale" else 0
    except (ValueError, KeyError, TypeError, OSError, ImportError) as error:
        print("neural registry binding failed: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
