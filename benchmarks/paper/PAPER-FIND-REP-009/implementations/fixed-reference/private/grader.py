#!/usr/bin/env python3
"""Portable all-17 artifact adapter; unchanged numeric core and R diagnostics."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from asset_io import read_regular

PINS = {
    "scorer_core.py": {"bytes": 16610, "sha256": "3757b56f8dd73cf11339db9482c6d5cb5cac25bb66a08fd0a89695b908dd6734"},
    "grader.py": {"bytes": 15209, "sha256": "c02b8121e6857cf604ef6be2e415dbf408b2bab98a50723ba3c8f7eedd34da43"},
    "paired_diagnostics.R": {"bytes": 7721, "sha256": "d8d162bab40706a7c6a591039ab961659d4412f7ed5ab3313f44ddb0f00ff506"},
    "REFERENCE_EXPECTATIONS.json": {"bytes": 22002, "sha256": "22d7b72f971529951f6f13e0f6687f0c57d140c2aebf21a938ec4399fb3b298b"},
}
MANIFEST_PIN = {"bytes": 23807, "sha256": "68488edb56d02f2dcaca8fe3007d7ca7f0c391842a1e1cd521affba3dd160687"}
PAIR_NAMES = ["pair%03d.json" % i for i in range(1, 18)]

def source_module(name, filename):
    path = HERE / "core" / filename
    body = read_regular(path, 100000, PINS[filename])
    # Load only captured, pinned trusted bytes; never candidate source.
    import types
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module

def load_core():
    return source_module("_thalamus_portable_core", "scorer_core.py")

def capture_pairs(directory, core):
    directory = Path(directory)
    core.public(not directory.is_symlink() and directory.is_dir(), "Ordinary submission directory")
    core.public({p.name for p in directory.iterdir()} == set(PAIR_NAMES), "Exactly seventeen pairNNN.json files")
    result = []
    for name in PAIR_NAMES:
        try:
            result.append(read_regular(directory / name, core.PAIR_CAP))
        except (OSError, ValueError) as error:
            raise core.InvalidSubmission("Candidate capture: " + type(error).__name__) from error
    return result

def grade_directory(directory):
    core = load_core()
    worker = source_module("_thalamus_portable_worker", "grader.py")
    worker.START = time.monotonic()
    manifest = core.strict_json(read_regular(HERE.parent / "public/SESSION_MANIFEST.json", 100000, MANIFEST_PIN))
    expected = core.strict_json(read_regular(HERE / "core/REFERENCE_EXPECTATIONS.json", 100000, PINS["REFERENCE_EXPECTATIONS.json"]))
    reads = attempts = 0
    def load_reference():
        nonlocal reads, attempts
        attempts += 1
        pin = json.loads(read_regular(HERE / "reference_pin.json", 16384))
        body = read_regular(HERE / "fixed_reference.json", core.REFERENCE_CAP, pin)
        reads += 1
        return core.strict_json(body)
    try:
        raw = capture_pairs(directory, core)
    except (OSError, core.InvalidSubmission) as error:
        return {"schema": "thalamus_figure3C_score_v1", "status": "invalid_submission",
                "reason": str(error)[:400], "primary_metric": None, "private_loader_calls": 0,
                "private_reference_reads": 0, "private_reference_read_attempts": 0,
                "scientific_success": None, "research_qualified": False, "full_paper_complete": False}, 2
    result = core.score(raw, manifest, expected, load_reference)
    core.need(result["private_loader_calls"] == attempts and result["private_reference_reads"] == reads,
              "Actual lazy reference counts")
    if result["status"] == "scored" and "_statistics_input" in result:
        values = result.pop("_statistics_input")
        script = read_regular(HERE / "core/paired_diagnostics.R", 20000, PINS["paired_diagnostics.R"])
        state = {"started": False}
        result["statistics"] = worker.r_diagnostics(values, script, core, state)
        result["R_diagnostic_process"] = state
        result["whole17_statistics_status"] = "computed_R431_full17_candidate_and_reference"
    result.update(private_reference_read_attempts=attempts, model_fits=0,
                  candidate_program_executed=False, candidate_chronology_verified=False,
                  portable_adapter="artifact paths and IO; frozen scorer_core.py and paired_diagnostics.R unchanged")
    return result, 0 if result["status"] == "scored" else 2

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="Fresh complete score JSON")
    args = parser.parse_args(argv)
    output = args.output.absolute()
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        parser.error("Fresh output in an existing directory required")
    try:
        result, code = grade_directory(args.submission_dir)
    except Exception as error:
        result = {"schema": "thalamus_figure3C_score_v1", "status": "operator_error",
                  "reason": type(error).__name__ + ": " + str(error)[:512],
                  "primary_metric": None, "scientific_success": None,
                  "private_reference_reads": None, "full_paper_complete": False}
        code = 3
    result["candidate_id"] = "PAPER-FIND-REP-009"
    body = (json.dumps(result, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n").encode()
    if len(body) > 1000000: raise RuntimeError("Complete score exceeds one-million-byte bound")
    with output.open("xb") as stream: stream.write(body)
    print(json.dumps({"status": result["status"], "output": str(output)}))
    return code

if __name__ == "__main__": raise SystemExit(main())
