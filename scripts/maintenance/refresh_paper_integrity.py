#!/usr/bin/env python3
"""Bind reviewed paper revisions without replacing historical calibration bytes.

Run after bind_paper_improvement.py, before check_repository.py --write. Only
current integrity metadata and exact workflow pins for changed descriptors are
written. Implementation source, predecessor pins and historical inventories are
never rewritten. The default is a read-only freshness check.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("_paper_source_integrity", ROOT / "src/neurobench/source_integrity.py")
integrity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integrity)
CURRENT = "benchmarks/integrity/current.json"
CLOSURES = "benchmarks/integrity/current-closures"
WORKFLOWS = (".github/workflows/construction-benchmark-components.yml",
             ".github/workflows/neuroscience-source-integrity.yml")
REVISION_FIELD = "paper_specification_revisions"


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def pin(path, body):
    return {"path": path, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def revision_pin(reader, row):
    """Authenticate both revisions against the existing registry original pin."""
    integrity.require(row.get("track") == "paper", "Revision cannot change neural integrity bindings")
    specification, original = row["specification"], row["original_specification"]
    task_pin = {**specification, "original_path": original["path"],
                "predecessor": {key: original[key] for key in ("bytes", "sha256")},
                "specification_revision": row["specification_revision"]}
    document = integrity.strict_json(reader.checked(specification["path"], specification))
    integrity.require(type(document) is dict
                      and document.get("id") == row.get("specification_id", row["id"])
                      and document.get("track") == "paper", "Current paper task identity mismatch")
    integrity.checked_paper_revision(reader, row["id"], task_pin, document, row)
    return task_pin


def refresh_workflow(body, path, old, new):
    """Replace exactly one complete literal descriptor pin, with stale checks."""
    text = body.decode("utf-8")
    pattern = re.compile(
        r'(?P<head>"path"\s*:\s*"' + re.escape(path)
        + r'"\s*,\s*"bytes"\s*:\s*)(?P<bytes>[0-9]+)'
        + r'(?P<middle>\s*,\s*"sha256"\s*:\s*")(?P<sha>[0-9a-f]{64})(?P<tail>")')
    matches = list(pattern.finditer(text))
    integrity.require(len(matches) == 1, "Expected exactly one workflow descriptor pin: " + path)
    match = matches[0]
    observed = {"bytes": int(match["bytes"]), "sha256": match["sha"]}
    integrity.require(integrity.same_pin(observed, old), "Stale workflow descriptor pin: " + path)
    return (text[:match.start()] + match["head"] + str(new["bytes"]) + match["middle"]
            + new["sha256"] + match["tail"] + text[match.end():]).encode("utf-8")


def build_outputs(root):
    reader = integrity.Reader(root)
    registered = integrity.task_registry(reader)
    validated = {}

    def revised(identifier):
        row = registered.get(identifier)
        integrity.require(type(row) is dict, "Unregistered paper closure task: " + identifier)
        if "specification_revision" not in row:
            return None
        if identifier not in validated:
            validated[identifier] = revision_pin(reader, row)
        return validated[identifier]

    old_current = reader.read(CURRENT)
    current = integrity.strict_json(old_current)
    updated = copy.deepcopy(current)
    for package in updated["packages"]:
        if package["track"] != "paper":
            continue
        task_pin = revised(package["task_id"])
        if task_pin is None:
            continue
        existing = package["registered_task"]
        integrity.require(existing["original_path"] == task_pin["original_path"]
                          and existing["predecessor"] == task_pin["predecessor"],
                          "Refusing to rewrite registered task predecessor")
        if "specification_revision" not in existing:
            integrity.require(integrity.same_pin(existing, existing["predecessor"]),
                              "Unversioned registered task already changed")
        else:
            integrity.require(existing["specification_revision"]["previous_specification"]
                              == task_pin["specification_revision"]["previous_specification"],
                              "Refusing to replace previously preserved paper history")
        package["registered_task"] = copy.deepcopy(task_pin)
    # This also authenticates every original implementation inventory and neural task.
    integrity.check_configuration(reader, updated)
    outputs = {}
    changes = []
    if updated != current:
        outputs[CURRENT] = encoded(updated)

    base = Path(root) / CLOSURES
    if base.exists():
        names = sorted(integrity.physical_members(reader.root, CLOSURES))
    else:
        names = []
    for name in names:
        if not name.endswith(".json"):
            continue
        original_body = reader.read(name)
        document = integrity.strict_json(original_body)
        integrity.require(type(document) is dict, "Closure metadata must be an object: " + name)
        result = copy.deepcopy(document)
        lineage = {}

        def visit(value):
            if type(value) is dict:
                path = value.get("path")
                if type(path) is str and path.startswith("benchmarks/paper/"):
                    parts = path.split("/")
                    if len(parts) >= 4 and "/".join(parts[3:]) in ("task.json", integrity.PAPER_HISTORY):
                        task_pin = revised(parts[2])
                        if task_pin is not None:
                            revision = task_pin["specification_revision"]
                            previous = revision["previous_specification"]
                            integrity.descriptor(value)
                            integrity.require(integrity.same_pin(value, previous),
                                              "Closure paper pin does not authenticate historical bytes: " + path)
                            value["path"] = previous["path"]
                            lineage[parts[2]] = {"task_id": parts[2], "version": integrity.PAPER_REVISION,
                                "role": "calibration_only", "historical_specification": previous,
                                "current_specification": {key: task_pin[key] for key in ("path", "bytes", "sha256")},
                                "improvement_contract": revision["improvement_contract"]}
                for key, child in value.items():
                    if key != REVISION_FIELD:
                        visit(child)
            elif type(value) is list:
                for child in value:
                    visit(child)

        visit(result)
        if lineage:
            expected = [lineage[key] for key in sorted(lineage)]
            old_lineage = document.get(REVISION_FIELD)
            if old_lineage is not None:
                integrity.require(type(old_lineage) is list
                                  and {item["task_id"] for item in old_lineage} == set(lineage),
                                  "Unexpected existing paper closure revision roster")
                for item in old_lineage:
                    integrity.require(item["version"] == integrity.PAPER_REVISION
                                      and item["role"] == "calibration_only"
                                      and item["historical_specification"] == lineage[item["task_id"]]["historical_specification"],
                                      "Refusing to replace existing closure history")
            result[REVISION_FIELD] = expected
        if result != document:
            body = encoded(result)
            outputs[name] = body
            changes.append({"path": name, "previous": pin(name, original_body), "current": pin(name, body),
                            "paper_tasks": sorted(lineage)})

    # Only the two reviewed workflows embed pins for these closure descriptors.
    # Each replacement is keyed by its full path and authenticated old hash/size.
    for name in WORKFLOWS:
        path = Path(root) / name
        if not path.exists():
            continue
        original_body = reader.read(name)
        body = original_body
        for change in changes:
            if change["path"].encode("utf-8") in body:
                body = refresh_workflow(body, change["path"], change["previous"], change["current"])
        if body != original_body:
            outputs[name] = body
    return outputs, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        outputs, changes = build_outputs(args.root)
        if args.write:
            for name, body in outputs.items():
                destination = args.root / name
                mode = destination.stat().st_mode & 0o777
                with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".paper-integrity-", delete=False) as handle:
                    temporary = Path(handle.name)
                    try:
                        handle.write(body)
                        handle.flush()
                        os.fchmod(handle.fileno(), mode)
                    except BaseException:
                        temporary.unlink(missing_ok=True)
                        raise
                try:
                    temporary.replace(destination)
                finally:
                    temporary.unlink(missing_ok=True)
        print(json.dumps({"status": "written" if args.write else "stale" if outputs else "current",
                          "files": sorted(outputs), "closure_pin_changes": changes,
                          "implementation_source_changed": False, "benchmark_execution": False}, indent=2))
        if outputs and not args.write:
            parser.exit(1)
    except (integrity.InvalidSource, OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, "Paper integrity refresh failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()
