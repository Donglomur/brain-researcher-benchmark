"""Fixed GCaMP8 daemon retirement child. No scientific operation is available."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).absolute().parent


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def read_request(fd):
    raw = bytearray()
    try:
        while len(raw) <= 4096:
            part = os.read(fd, 4097 - len(raw))
            if not part:
                break
            raw.extend(part)
        need(0 < len(raw) <= 4096, "one-bounded-original-recovery-request")
        def pairs(rows):
            result = {}
            for key, value in rows:
                need(key not in result, "duplicate-recovery-key")
                result[key] = value
            return result
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: need(False, "finite-recovery-json"))
    finally:
        os.close(fd)


def recover(request):
    need(type(request) is dict and set(request) == {
        "schema", "rows", "docker", "socket", "docker_pin", "executor_pin", "deadline",
        "failure_source_pin", "failure_directory", "failure_byte_cap"},
        "fixed-recovery-request")
    need(request["schema"] == "gcamp8_original_daemon_recovery_v1" and
         type(request["rows"]) is list and len(request["rows"]) <= 6 and
         type(request["deadline"]) in (int, float) and
         time.monotonic() < request["deadline"], "original-recovery-interval")
    rows = request["rows"]
    need(all(type(row) is dict for row in rows) and
         len({row["name"] for row in rows}) == len(rows),
         "known-unique-original-resource-rows")
    source = HERE / "backend/executor.py"
    raw = source.read_bytes()
    need({"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} ==
         request["executor_pin"], "exact-original-retirement-source")
    specification = importlib.util.spec_from_file_location("_gcamp8_recovery_executor", source)
    module = importlib.util.module_from_spec(specification)
    # Execute the exact already-captured body, without a second import read.
    exec(compile(raw, str(source), "exec"), module.__dict__)
    failure_source = HERE / "failure_evidence.py"
    failure_raw = failure_source.read_bytes()
    need({"bytes": len(failure_raw), "sha256": hashlib.sha256(failure_raw).hexdigest()} ==
         request["failure_source_pin"], "exact-original-failure-evidence-source")
    specification = importlib.util.spec_from_file_location("_gcamp8_recovery_failure", failure_source)
    failure_module = importlib.util.module_from_spec(specification)
    exec(compile(failure_raw, str(failure_source), "exec"), failure_module.__dict__)
    need(request["failure_byte_cap"] == 1048576, "precharged-original-recovery-evidence")
    if rows:
        module.opaque_pin(request["docker"], request["docker_pin"], 268435456)
    docker = module.Docker(request["docker"], request["socket"]) if rows else None
    results, original_errors = [], []
    # Exactly one independent retirement per known obligation; containers first.
    ordered = sorted(enumerate(rows), key=lambda item:
                     (item[1]["kind"] == "volume", -item[0]))
    for original_index, row in ordered:
        try:
            need(time.monotonic() < request["deadline"], "same-original-recovery-cutoff")
            result = module.retire(docker, row, request["deadline"])
        except BaseException as error:
            original_errors.append(error)  # Keep raw objects through all independent cleanup.
            result = {"kind": row["kind"], "name": row["name"], "closed": False,
                      "error_type": type(error).__name__}
        results.append({"original_index": original_index, "resource": row, "result": result})
    retirement_error_evidence = None
    try:
        retirement_error_evidence = failure_module.describe_original_errors(original_errors)
    except BaseException as error:
        original_errors.append(error)
    original_evidence = None
    if docker is not None and docker.original_failures:
        try:
            original_evidence = failure_module.persist(request["failure_directory"],
                docker.original_failures, request["failure_byte_cap"], request["deadline"])
            original_errors.extend(original_evidence["publication_errors"])
        except BaseException as error:
            original_errors.append(error)
    summary = {"schema": "gcamp8_original_daemon_recovery_result_v1",
            "results": results, "commands": [] if docker is None else docker.records,
            "cli_groups_closed": True if docker is None else docker.reaped,
            "original_error_types": [type(x).__name__ for x in original_errors],
            "original_command_evidence": (None if original_evidence is None else
                                          original_evidence["summary"]),
            "original_retirement_error_evidence": retirement_error_evidence,
            "study_failure_unchanged": True, "automatic_retry": False,
            "runtime_or_scientific_qualification_added": False}
    # Retain these originals through serialization/flushing in main. Only the
    # bounded summary crosses the process boundary.
    return {"summary": summary, "original_errors": tuple(original_errors),
            "original_evidence": original_evidence, "docker": docker}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-fd", type=int, required=True)
    args = parser.parse_args()
    held = recover(read_request(args.request_fd))
    raw = (json.dumps(held["summary"], sort_keys=True, separators=(",", ":"),
                      allow_nan=False) + "\n").encode()
    need(len(raw) <= 65536, "original-recovery-result-cap")
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()

