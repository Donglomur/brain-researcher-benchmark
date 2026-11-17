"""Operator-only central source routes for the adopted NEURAL-029 method.

This module grants no scientific execution authority. Its default inspect and
plan paths read ordinary source/command metadata only. Actual preparation and
grading remain trusted-operator calls; no candidate executor is supplied.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import subprocess
import sys
import time

SOURCE_FREEZE_BYTES = 11628
SOURCE_FREEZE_SHA256 = "de3b5c4ffc0bc5c5dba00febaa174c720b5b1d084dbb8248b3e18ff81b2c8673"
SOURCE_ROLE_COUNT = 24
SOURCE_TOTAL_BYTES = 201227
PRIMARY_WEIGHTING = "pair sqrt(pooled MSE / pooled training variance); equal pairs within mouse; equal mice"

def need(ok, reason):
    if not ok:
        raise ValueError(reason)

def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, "nonfinite JSON"))

def capture(path, cap, pin=None):
    path = Path(path).absolute()
    need(".." not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)),
         "ordinary source/metadata path without symlink ancestors")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             0 < before.st_size <= cap, "bounded regular source/metadata file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(cap + 1)
        after, linked = os.fstat(fd), path.lstat()
        attrs = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size",
                 "st_mtime_ns", "st_ctime_ns")
        need(len(raw) == before.st_size and
             all(getattr(before, a) == getattr(after, a) == getattr(linked, a) for a in attrs),
             "stable complete source/metadata read")
    finally:
        os.close(fd)
    if pin is not None:
        need(len(raw) == pin["bytes"] and hashlib.sha256(raw).hexdigest() == pin["sha256"],
             "source/metadata identity")
    return raw

def absolute_name(value):
    need(type(value) is str and value and all(ord(c) >= 32 and ord(c) != 127 for c in value),
         "plain operator path")
    p = PurePosixPath(value)
    need(p.is_absolute() and p.as_posix() == value and ".." not in p.parts,
         "canonical absolute operator path")
    return value

class HostRuntime:
    """Trusted operator bridge; source authentication is not target authority."""
    def __init__(self, root=None):
        self.root = Path(root if root is not None else Path(__file__).parent).absolute()
        self.last_failure = None

    def verify_source(self):
        raw = capture(self.root / "SOURCE_FREEZE.json", 65536,
                      {"bytes": SOURCE_FREEZE_BYTES, "sha256": SOURCE_FREEZE_SHA256})
        freeze = strict(raw)
        rows = freeze["roles"]
        need(freeze["schema"] == "neural029_public_source_freeze_v1" and
             freeze["task_id"] == "NEURAL-029" and
             freeze["role_count"] == len(rows) == SOURCE_ROLE_COUNT and
             freeze["all_original_bodies_unchanged"] is False and
             freeze["all_scientific_implementation_bodies_unchanged"] is True and
             freeze["provenance_metadata_projection"] is True, "complete inherited source contract")
        names = [r["path"] for r in rows]
        need(len(set(names)) == SOURCE_ROLE_COUNT and
             sum(r["bytes"] for r in rows) == SOURCE_TOTAL_BYTES, "complete inherited role census")
        bodies = {}
        for row in rows:
            p = PurePosixPath(row["path"])
            need(p.as_posix() == row["path"] and not p.is_absolute() and
                 ".." not in p.parts and p.parts[:2] == ("runtime", "source"),
                 "inherited source-relative path")
            bodies[row["path"]] = capture(self.root / row["path"], 1048576, row)
        source_names = {PurePosixPath(n).relative_to("runtime/source") for n in names}
        dirs = {PurePosixPath(".")}
        for p in source_names:
            dirs.update(p.parents)
        for rel in dirs:
            expected = {p.relative_to(rel).parts[0] for p in source_names if p.is_relative_to(rel)}
            directory = self.root / "runtime/source" / rel
            actual = set()
            for entry in directory.iterdir():
                need(entry.name in expected and entry.name not in actual and not entry.is_symlink(),
                     "unexpected inherited-source entry")
                actual.add(entry.name)
            need(actual == expected, "complete inherited-source directory")
        return freeze, bodies

    def inspect(self):
        _, bodies = self.verify_source()
        protocol = strict(bodies["runtime/source/PROTOCOL.json"])
        return {
            "schema": "neural029_central_source_inspection_v1", "id": "NEURAL-029",
            "inherited_source_roles": SOURCE_ROLE_COUNT,
            "source_freeze_sha256": SOURCE_FREEZE_SHA256,
            "operator_routes": ["prepare", "grade"],
            "candidate_executor": None, "program_execution": None,
            "primary": protocol["primary"], "primary_weighting": PRIMARY_WEIGHTING,
            "cohort": protocol["cohort"], "trials": protocol["trials"],
            "public_submission_schemas_unchanged": True,
            "qualification": {"runnable": False, "research_qualified": False,
                              "submission_ready": False, "authentic_inputs_verified": False},
            "interpretation": "Source-only operator integration; no data, target or model inspected."
        }

    def _request(self, request, operation):
        fields = {"schema", "wall_time_seconds", "cleanup_wall_time_seconds", "output"}
        fields |= ({"source_root", "index_sha256"} if operation == "prepare"
                   else {"prepared_root", "binding", "submission"})
        need(type(request) is dict and set(request) == fields and
             request["schema"] == "neural029-central-" + operation + "-request-v2",
             "exact operator request")
        seconds = request["wall_time_seconds"]
        need(type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0,
             "explicit positive operator wall-time allocation")
        cleanup_seconds = request["cleanup_wall_time_seconds"]
        need(type(cleanup_seconds) in (int, float) and math.isfinite(cleanup_seconds) and cleanup_seconds > 0,
             "explicit positive cleanup wait allocation")
        need(math.isfinite(seconds + cleanup_seconds), "finite total operation and cleanup allocation")
        for key in fields - {"schema", "wall_time_seconds", "cleanup_wall_time_seconds", "index_sha256"}:
            absolute_name(request[key])
        if operation == "prepare":
            need(type(request["index_sha256"]) is str and
                 re.fullmatch("[0-9a-f]{64}", request["index_sha256"]) is not None,
                 "operator-selected complete INDEX identity")
            need(request["source_root"] != request["output"], "distinct input/output roots")
        else:
            need(request["output"] not in {request["binding"], request["submission"]},
                 "fresh grade output distinct from request inputs")
        return seconds, cleanup_seconds

    def _plan(self, request, operation):
        seconds, cleanup_seconds = self._request(request, operation)
        self.verify_source()
        argv = [sys.executable, "-I", "-B",
                str(self.root / "runtime/source" / (operation + ".py"))]
        if operation == "prepare":
            argv += ["--source-root", request["source_root"], "--index-sha256",
                     request["index_sha256"], "--output", request["output"]]
        else:
            argv += ["--root", request["prepared_root"], "--binding", request["binding"],
                     "--submission", request["submission"], "--output", request["output"]]
        return {"schema": "neural029-operator-command-plan-v2", "operation": operation,
                "argv": argv, "cwd": str(self.root), "wall_time_seconds": seconds,
                "cleanup_wall_time_seconds": cleanup_seconds,
                "requested_operation_plus_cleanup_seconds": seconds + cleanup_seconds,
                "source_freeze_sha256": SOURCE_FREEZE_SHA256,
                "payload_read_by_planner": False, "scientific_execution_authority_issued": False}

    def plan_prepare(self, request):
        return self._plan(request, "prepare")

    def plan_grade(self, request):
        return self._plan(request, "grade")

    def _invoke(self, plan):
        # Only plans just built by prepare()/grade() reach this private method.
        # Source auth does not qualify the external environment or immutable mounts.
        start = time.monotonic()
        proc = subprocess.Popen(plan["argv"], cwd=plan["cwd"], stdin=subprocess.DEVNULL,
                                close_fds=True, start_new_session=True)
        try:
            code = proc.wait(timeout=plan["wall_time_seconds"])
        except BaseException as primary:
            # Preserve the exact first exception. Signal and reap are independent
            # attempts; neither is allowed to mask that original failure.
            secondary = []
            reap_returncode = None
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except BaseException as error:
                secondary.append(("signal_group", error))
            try:
                reap_returncode = proc.wait(timeout=plan["cleanup_wall_time_seconds"])
            except BaseException as error:
                secondary.append(("reap_leader", error))
            self.last_failure = {"primary": primary, "cleanup_errors": tuple(secondary),
                                 "reap_returncode": reap_returncode,
                                 "group_completion_claimed": False}
            BaseException.add_note(primary,
                "NEURAL029 cleanup observations retained on HostRuntime.last_failure; "
                "no group-completion certification. Secondary errors: " +
                (", ".join(phase + ":" + type(error).__name__ for phase, error in secondary)
                 if secondary else "none"))
            raise
        if code:
            raise subprocess.CalledProcessError(code, plan["argv"])
        return {"schema": "neural029-operator-process-observation-v2",
                "operation": plan["operation"], "returncode": code,
                "observed_wall_seconds": time.monotonic() - start,
                "source_freeze_sha256": SOURCE_FREEZE_SHA256,
                "scientific_qualification": False,
                "interpretation": "Leader observation only; not complete resource, descendant, target or numerical qualification."}

    def prepare(self, request):
        return self._invoke(self.plan_prepare(request))

    def grade(self, request):
        return self._invoke(self.plan_grade(request))

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("operation", choices=("inspect", "prepare", "grade"))
    ap.add_argument("--request")
    ap.add_argument("--plan", action="store_true", help="Construct command only; open no payload.")
    args = ap.parse_args(argv)
    host = HostRuntime()
    if args.operation == "inspect":
        need(args.request is None and not args.plan, "inspect accepts no payload request")
        result = host.inspect()
    else:
        need(args.request is not None, "explicit trusted-operator request required")
        request = strict(capture(args.request, 65536))
        method = ("plan_" if args.plan else "") + args.operation
        result = getattr(host, method)(request)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))

if __name__ == "__main__":
    main()
