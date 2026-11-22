"""Private original-packet initial-image census; invocation needs separate selection.

One Session/render per query supplies both existing local projections. This is
not a participant executor, scorer, independent-render comparison or model run.
No production function is replaced. Successful scratch is deleted only after
its census commitment is fsynced. Deleted bytes remain cumulatively charged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time
import types

PROFILE = "erp-full32-visual-v1"
PREFIX = "benchmarks/neural/NEURAL-077/implementations/"
COUNT = 6400
MANIFEST = {"bytes": 5428, "sha256": "241870678fed37fca67cc9c64e2e3a0830e0a97f9815332e27fa3018ed6c9f3f"}
PUBLIC_BYTES = 235921250
SHARD_BYTES = 234460034
PNG_CAP = 4 * 1024**2
CASE_METADATA_CAP = 65536
CASE_RESERVE = PNG_CAP + CASE_METADATA_CAP
FINAL_RESERVE = 2 * 1024**2
ROW_CAP = 4096
DEPENDENCY_READ_RESERVE = 128 * 1024**2
ID = re.compile(r"q-[0-9a-f]{32}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
CASE_FILES = {"SESSION.json", "prompt.txt", "action-0000.json", "frames/0000.png"}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def decode(body):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, "Duplicate JSON key")
            value[key] = item
        return value
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def integer(value, low, high, name):
    need(type(value) is int and low <= value <= high, "Bounded integer: " + name)


def check_pin(value, maximum):
    need(type(value) is dict and set(value) == {"bytes", "sha256"}, "Exact content pin")
    integer(value["bytes"], 1, maximum, "pin bytes")
    need(type(value["sha256"]) is str and SHA.fullmatch(value["sha256"]), "SHA256")


def ordinary(path):
    need(type(path) in (str, type(Path())), "Path string")
    path = Path(path)
    need(path.is_absolute() and ".." not in path.parts, "Absolute ordinary path")
    need(all(not part.is_symlink() for part in (path, *path.parents)), "No symlink path components")
    return path


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_nlink)


class Budget:
    def __init__(self, reads, writes):
        self.read_limit, self.write_limit = reads, writes
        self.reads = self.writes = self.deleted_bytes = 0
        self.read_allowances = []
        self.external_cases = set()
        self.external_measured_bytes = 0
        self.accounting_unresolved = []

    def input(self, amount):
        integer(amount, 0, self.read_limit, "read request")
        need(self.reads + amount <= self.read_limit, "Cumulative read ceiling")
        self.reads += amount

    def allowance(self, amount, reason):
        self.input(amount)
        self.read_allowances.append({"bytes": amount, "reason": reason})

    def reserve(self, amount, *, final=False):
        keep = 0 if final else FINAL_RESERVE
        need(self.writes + amount + keep <= self.write_limit, "Cumulative write ceiling")

    def external(self, ordinal, amount, *, measured=True, reason=None):
        # Existing Session writes are create-only. Measure before any deletion,
        # including partial files after a failure; never refund deleted bytes.
        # No I/O while the work timer is briefly excluded from this atomic
        # counter/idempotence update. Pending signals are restored immediately.
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM, signal.SIGTERM})
        try:
            if ordinal not in self.external_cases:
                self.writes += amount
                if measured:
                    self.external_measured_bytes += amount
                else:
                    self.accounting_unresolved.append({"ordinal": ordinal, "charge_bytes": amount, "reason": reason})
                self.external_cases.add(ordinal)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
        need(self.writes <= self.write_limit, "Observed write ceiling exceeded")


def read(path, cap, budget, expected=None):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             0 < before.st_size <= cap, "Bounded single-link file")
        budget.input(before.st_size + 1)
        body = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
    need(identity(before) == identity(after) == identity(path.lstat()) and
         len(body) == before.st_size, "File changed during read")
    need(expected is None or pin(body) == expected, "Content pin mismatch")
    return body


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_fd(fd, body, budget, *, final=False):
    budget.reserve(len(body), final=final)
    # Precharge requests; interrupted short writes cannot escape accounting.
    # Retained journal extents separately disclose actual bytes and partial tails.
    budget.writes += len(body)
    remaining = memoryview(body)
    while remaining:
        count = os.write(fd, remaining)
        need(count > 0, "Short output write")
        remaining = remaining[count:]
    os.fsync(fd)


def write_new(path, value, budget, cap, *, final=False):
    body = encode(value)
    need(len(body) <= cap, "Bounded output object")
    budget.reserve(len(body), final=final)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        write_fd(fd, body, budget, final=final)
    finally:
        os.close(fd)
    fsync_directory(path.parent)
    return pin(body)


class Journal:
    def __init__(self, path, budget, row_cap):
        self.path, self.budget, self.row_cap = path, budget, row_cap
        self.fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self.previous = "0" * 64
        self.rows = self.bytes = 0
        try:
            fsync_directory(path.parent)
        except BaseException:
            fd, self.fd = self.fd, None
            os.close(fd)
            raise

    def append(self, value):
        row = dict(value, sequence=self.rows, previous_sha256=self.previous)
        body = encode(row)
        need(len(body) <= self.row_cap, "Census row cap")
        write_fd(self.fd, body, self.budget)
        self.previous = hashlib.sha256(body).hexdigest()
        self.rows += 1
        self.bytes += len(body)
        return pin(body)

    def close(self):
        if self.fd is not None:
            fd, self.fd = self.fd, None
            os.close(fd)


def module(name, path, body):
    value = types.ModuleType(name)
    value.__file__ = str(path)
    sys.modules[name] = value
    exec(compile(body, str(path), "exec"), value.__dict__)
    return value


def authenticate_sources(plan, budget):
    root = ordinary(plan["source_root"])
    descriptor = plan["source_guard"]
    body = read(descriptor["path"], 256 * 1024, budget, descriptor["pin"])
    manifest = decode(body)
    need(type(manifest) is dict and type(manifest.get("files")) is list and
         1 <= len(manifest["files"]) <= 128, "Finite source closure")
    entries, total = {}, 0
    for row in manifest["files"]:
        need(type(row) is dict and {"repository_path", "bytes", "sha256"} <= set(row), "Source member")
        relative = row["repository_path"]
        need(type(relative) is str and relative.startswith("benchmarks/") and
             not Path(relative).is_absolute() and ".." not in Path(relative).parts and
             relative not in entries, "Unique repository source member")
        expected = {key: row[key] for key in ("bytes", "sha256")}
        check_pin(expected, 131072)
        entries[relative] = read(root / relative, 131072, budget, expected)
        total += expected["bytes"]
    need(total <= 4 * 1024**2, "Source closure byte cap")
    required = ("image-matched-programme-v1/pair.py", "image-matched-programme-v1/adapters.py",
                "image-matched-programme-v1/SOURCE_BINDINGS.json", "visual-viewer-v1/viewer.py",
                "visual-viewer-v1/full32_profile.py", "visual-viewer-v1/raster.py",
                "visual-provider-pair-v1/transport.py", "visual-provider-pair-v1/transfer_png.py",
                "full32-paired-benchmark-v1/consumer.py")
    need(all(PREFIX + name in entries for name in required), "Required exact API sources")
    binding = decode(entries[PREFIX + "image-matched-programme-v1/SOURCE_BINDINGS.json"])
    need(type(binding.get("members")) is dict, "Programme dependency closure")
    for relative, expected in binding["members"].items():
        need(relative in entries and pin(entries[relative]) == expected, "Guard closes programme dependency")
    return root, entries, {"guard": pin(body), "members": len(entries), "body_bytes": total}


def runtime_identity(plan, budget):
    selected = plan["runtime"]
    need(os.path.abspath(sys.executable) == selected["invocation"] and
         list(sys.version_info[:3]) == selected["python_version"] and
         os.path.abspath(sys.prefix) == selected["prefix"], "Selected invocation/runtime drift")
    need(len(selected["bodies"]) <= 16, "Finite runtime body roster")
    for row in selected["bodies"]:
        read(row["path"], 64 * 1024**2, budget, row["pin"])
    executable = Path(sys.executable).resolve(strict=True)
    need(any(Path(row["path"]) == executable for row in selected["bodies"]), "Resolved executable body bound")
    import numpy as np
    import zlib
    need(np.__version__ == selected["numpy_version"] and
         os.path.abspath(np.__file__) == selected["numpy_origin"], "NumPy version/origin drift")
    need(any(row["path"] == selected["numpy_origin"] for row in selected["bodies"]), "NumPy source bound")
    need(zlib.ZLIB_VERSION == selected["zlib_compile_version"] and
         zlib.ZLIB_RUNTIME_VERSION == selected["zlib_runtime_version"], "Selected zlib identity")
    return {key: selected[key] for key in ("invocation", "prefix", "python_version", "numpy_version",
                                           "numpy_origin", "zlib_compile_version", "zlib_runtime_version")}


def validate_plan(plan):
    need(type(plan) is dict and set(plan) == {
        "schema", "qualification", "source_root", "source_guard", "accepted_source_commit",
        "public_root", "manifest", "output", "runtime", "limits", "hash_whole_shards"}, "Exact plan fields")
    need(plan["schema"] == "erp-initial-image-census-plan/v1" and
         plan["qualification"] == "shared_render_local_initial_projections", "Exact narrow qualification")
    need(re.fullmatch("[0-9a-f]{40}", plan["accepted_source_commit"] or ""), "Accepted source identity required")
    need(plan["manifest"] == MANIFEST, "Only the frozen original full32 public manifest")
    need(type(plan["hash_whole_shards"]) is bool, "Explicit whole-shard custody scope")
    need(set(plan["source_guard"]) == {"path", "pin"}, "Exact guard descriptor")
    check_pin(plan["source_guard"]["pin"], 256 * 1024)
    source, public, output = (ordinary(plan[key]) for key in ("source_root", "public_root", "output"))
    need(not os.path.lexists(output) and output.parent.is_dir(), "Fresh output, existing ordinary parent")
    for first, second in ((source, public), (source, output), (public, output)):
        need(not first.is_relative_to(second) and not second.is_relative_to(first), "Disjoint source/public/output")
    limits = plan["limits"]
    need(set(limits) == {"read_bytes", "write_bytes", "work_seconds", "closure_seconds"}, "Exact resource fields")
    integer(limits["read_bytes"], 256 * 1024**2, 3 * 1024**3, "read ceiling")
    integer(limits["write_bytes"], FINAL_RESERVE + CASE_RESERVE + 1024**2, 26 * 1024**3, "write ceiling")
    integer(limits["work_seconds"], 1, 3600, "work deadline")
    integer(limits["closure_seconds"], 1, 600, "closure allowance")
    runtime = plan["runtime"]
    need(type(runtime) is dict and set(runtime) == {"invocation", "prefix", "python_version", "numpy_version",
        "numpy_origin", "zlib_compile_version", "zlib_runtime_version", "bodies"}, "Exact runtime fields")
    need(type(runtime["bodies"]) is list and 1 <= len(runtime["bodies"]) <= 16, "Runtime bindings required")
    for row in runtime["bodies"]:
        need(set(row) == {"path", "pin"}, "Exact runtime body")
        ordinary(row["path"])
        check_pin(row["pin"], 64 * 1024**2)
    return source, public, output


def scratch_inventory(case):
    if not case.exists():
        return [], 0
    need(not case.is_symlink() and case.is_dir(), "Owned ordinary scratch")
    rows = []
    for parent, dirs, files in os.walk(case, followlinks=False):
        need(all(not (Path(parent) / name).is_symlink() for name in dirs), "No scratch directory links")
        for name in files:
            path = Path(parent) / name
            info = path.lstat()
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "Ordinary scratch files")
            rows.append({"path": str(path.relative_to(case)), "bytes": info.st_size})
            need(len(rows) <= 8, "Bounded scratch inventory")
    return sorted(rows, key=lambda row: row["path"]), sum(row["bytes"] for row in rows)


def delete_committed_case(case, inventory, budget):
    current, count = scratch_inventory(case)
    need(current == inventory and {row["path"] for row in current} == CASE_FILES, "Exact committed scratch only")
    for row in current:
        (case / row["path"]).unlink()
        budget.deleted_bytes += row["bytes"]
    (case / "frames").rmdir()
    case.rmdir()
    fsync_directory(case.parent)
    return count


def account_case(case, ordinal, budget):
    try:
        inventory, written = scratch_inventory(case)
    except BaseException as exc:
        # No deletion. Exact measurement is unresolved; charge the complete
        # already-reserved trusted-source case bound and preserve that limit.
        budget.external(ordinal, CASE_RESERVE, measured=False,
                        reason=type(exc).__name__ + ": " + str(exc)[:512])
        raise
    budget.external(ordinal, written)
    return inventory, written


def hash_shards(session, budget):
    result = []
    for relative in sorted(name for name in session._files if name.startswith("queries/")):
        expected = session._files[relative]
        fd = session._open(relative, expected["bytes"])
        try:
            before = identity(os.fstat(fd)); digest = hashlib.sha256(); remaining = expected["bytes"]
            while remaining:
                request = min(1024**2, remaining)
                budget.input(request)
                body = os.read(fd, request)
                need(body, "Truncated whole shard")
                digest.update(body); remaining -= len(body)
            need(identity(os.fstat(fd)) == before and digest.hexdigest() == expected["sha256"], "Whole-shard custody")
        finally:
            os.close(fd)
        result.append({"path": relative, **expected})
    need(len(result) == 32 and sum(row["bytes"] for row in result) == SHARD_BYTES, "Exact original shard bytes")
    return result


def check_images(session, direct, programme, adapter, budget):
    raw = session.handle(b'{"action":"inspect"}')
    need(session.sequence == 1 and not session.closed and session.state == direct.v.initial_state(), "One initial inspect only")
    a, png_a = direct.projection(raw)
    b, png_b = programme.projection(raw)
    need(a == b and png_a == png_b and 0 < len(png_a) <= PNG_CAP, "Exact shared-render projection equality")
    limits = direct.Limits()  # Preserve the existing interface's available limits.
    limits.validate()
    a["remaining_actions"] = b["remaining_actions"] = limits.max_actions - session.sequence
    # IDs are operator framing only; no source-person/order information is added.
    ha = direct.ready_header(session, limits, "0" * 32, budget=budget)
    hb = programme.ready_header(session, limits, "1" * 32, budget=budget)
    ha["initial"], hb["initial"] = a, b
    expected = dict(ha, episode_id=hb["episode_id"], prompt=adapter.programme_prompt(ha["prompt"]))
    need(hb == expected, "Only permission sentence and episode identity may differ")
    wa, wb = direct.wire(ha, png_a), programme.wire(hb, png_b)
    need(direct.unpack(wa) == (ha, png_a) and programme.unpack(wb) == (hb, png_b), "Framed projection round trip")
    need(ha["trial_id"] == session.query["trial_id"] and
         set(ha) == {"status", "episode_id", "trial_id", "prompt", "actions", "limits", "instructions", "profile", "profile_commitment", "initial"},
         "No operator-only metadata in participant header")
    return {"direct_png": pin(png_a), "programme_png": pin(png_b), "direct_header": pin(direct.v.encode(ha)),
            "programme_header": pin(direct.v.encode(hb)), "direct_wire": pin(wa), "programme_wire": pin(wb),
            "image_bytes_equal": True, "projection_equal": True, "normalized_headers_equal": True,
            "shared_render": True, "independent_native_deliveries": False, "encoding": session.frame_encoding}


def run(plan, plan_pin, began):
    source, public, output = validate_plan(plan)
    cap = plan["limits"]
    budget = Budget(cap["read_bytes"], cap["write_bytes"])
    work_deadline = began + cap["work_seconds"]
    whole_deadline = work_deadline + cap["closure_seconds"]
    data = None; census = starts = None; deps = None; statuses = []
    source_before = runtime_before = None; failure = None; current = None
    all_success = False; close_error = None
    budget.input(plan_pin["bytes"] + 1)
    output.mkdir(mode=0o700)
    try:
        write_new(output / "START.json", {"schema": "erp-initial-image-census-start/v1", "plan": plan_pin,
            "pid": os.getpid(), "started_monotonic": began, "work_deadline": work_deadline,
            "whole_deadline": whole_deadline, "qualification": plan["qualification"], "attempts": 1,
            "private_targets_opened": False, "predictions": 0, "scoring": False}, budget, 16384)
        budget.allowance(DEPENDENCY_READ_RESERVE, "Finite existing dependency/import loader allowance; not kernel I/O measurement")
        runtime_before = runtime_identity(plan, budget)
        root, bodies, source_before = authenticate_sources(plan, budget)
        path = root / (PREFIX + "image-matched-programme-v1/pair.py")
        pair = module("private_initial_census_pair", path, bodies[PREFIX + "image-matched-programme-v1/pair.py"])
        deps = pair.dependencies(root / PREFIX, profile=PROFILE)
        del bodies
        remaining = work_deadline - time.monotonic()
        need(remaining > 0, "Original work deadline expired during preflight")
        with pair.deadline(remaining):
            direct, programme = deps["transport"], deps["image_transport"]
            data = deps["provider"].dataset_for(deps, public, profile=PROFILE, manifest_pin=MANIFEST, budget=budget)
            session = data["_session"]
            need(MANIFEST["bytes"] + sum(row["bytes"] for row in session._files.values()) == PUBLIC_BYTES,
                 "Exact original declared public extent")
            ids = tuple(direct.v.ordered_ids(data))
            need(len(ids) == COUNT and list(ids) == sorted(set(ids)) and all(ID.fullmatch(x) for x in ids), "Complete deterministic opaque roster")
            statuses = [{"ordinal": i, "trial_id": key, "status": "unattempted"} for i, key in enumerate(ids)]
            write_new(output / "ROSTER.json", {"schema": "erp-initial-image-planned-roster/v1", "ids": ids,
                "public_manifest": MANIFEST, "source": source_before, "runtime": runtime_before,
                "accepted_source_commit": plan["accepted_source_commit"], "profile_commitment": data["profile_commitment"]}, budget, 512 * 1024)
            if plan["hash_whole_shards"]:
                write_new(output / "SHARDS.json", {"members": hash_shards(session, budget)}, budget, 16384)
            census = Journal(output / "CENSUS.jsonl", budget, ROW_CAP)
            starts = Journal(output / "ATTEMPTS.jsonl", budget, 512)
            scratch = output / "scratch"; scratch.mkdir(mode=0o700)
            for ordinal in range(COUNT):
                need(time.monotonic() < work_deadline, "Whole work deadline")
                budget.reserve(CASE_RESERVE + ROW_CAP + 512)
                current = ordinal
                starts.append({"ordinal": ordinal, "trial_id": ids[ordinal], "status": "started"})
                statuses[ordinal]["status"] = "failed"
                case = scratch / f"{ordinal:04d}"
                view = None
                try:
                    view = direct.v.Session(data, ordinal, "four_demo", case)
                    result = check_images(view, direct, programme, deps["adapter"], budget)
                    inventory, written = account_case(case, ordinal, budget)
                    need({row["path"] for row in inventory} == CASE_FILES and
                         written <= CASE_RESERVE and
                         sum(row["bytes"] for row in inventory if not row["path"].endswith(".png")) <= CASE_METADATA_CAP,
                         "Exact bounded initial-only Session inventory")
                    # Hashes refer to live returned PNG bytes. No extra disk PNG
                    # reread and no later image-body replay is claimed.
                    record = {"ordinal": ordinal, "trial_id": ids[ordinal], "status": "initial_projection_equal",
                              "input_span": {key: session._rows[ids[ordinal]][key] for key in ("bytes", "sha256")},
                              "image_comparison": result, "scratch_inventory": inventory,
                              "scratch_written_bytes": written, "cumulative_write_charge_bytes_before_row": budget.writes,
                              "cumulative_read_charge_bytes": budget.reads}
                    commitment = census.append(record)
                    statuses[ordinal].update(status="initial_projection_equal", census_row=commitment)
                    delete_committed_case(case, inventory, budget)
                finally:
                    if ordinal not in budget.external_cases:
                        account_case(case, ordinal, budget)
                    view = result = None
                current = None
            all_success = True
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)[:2048], "ordinal": current}
    finally:
        for journal in (census, starts):
            if journal is not None:
                try:
                    journal.close()
                except BaseException as exc:
                    close_error = type(exc).__name__ + ": " + str(exc)[:512]
        if data is not None:
            try:
                deps["transport"].v.close_source(data)
                need(data["_session"]._closed, "Packet source must close")
            except BaseException as exc:
                close_error = type(exc).__name__ + ": " + str(exc)[:512]
        try:
            if source_before is not None:
                _, _, after = authenticate_sources(plan, budget)
                need(after == source_before, "Source changed after work")
            if runtime_before is not None:
                need(runtime_identity(plan, budget) == runtime_before, "Runtime changed after work")
        except BaseException as exc:
            failure = failure or {"type": type(exc).__name__, "message": str(exc)[:2048], "ordinal": None}
        journal_state = {}
        for name, journal in (("census", census), ("attempts", starts)):
            if journal is not None:
                try:
                    info = journal.path.lstat()
                    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                         info.st_size >= journal.bytes, "Journal extent changed")
                    journal_state[name] = {"complete_rows": journal.rows, "complete_row_bytes": journal.bytes,
                        "file_bytes_including_partial_tail": info.st_size,
                        "uncommitted_tail_bytes": info.st_size - journal.bytes, "last_sha256": journal.previous}
                    if info.st_size != journal.bytes:
                        failure = failure or {"type": "PartialJournal", "message": "Retained incomplete row tail", "ordinal": current}
                except BaseException as exc:
                    failure = failure or {"type": type(exc).__name__, "message": str(exc)[:512], "ordinal": current}
        complete = (all_success and failure is None and close_error is None and
                    not budget.accounting_unresolved and len(statuses) == COUNT)
        elapsed = time.monotonic() - began
        if time.monotonic() > whole_deadline:
            complete = False
            failure = failure or {"type": "TimeoutError", "message": "Whole operation deadline", "ordinal": None}
        summary = {"schema": "erp-initial-image-census-result/v1", "status": "complete_initial_local_projections" if complete else "partial_or_refused",
            "qualification": plan["qualification"], "plan": plan_pin, "expected_queries": COUNT,
            "roster_authenticated": len(statuses) == COUNT,
            "statuses": statuses, "unattempted_without_authenticated_ids": COUNT if not statuses else 0,
            "failure": failure, "close_error": close_error, "elapsed_seconds_before_final_write": elapsed,
            "packet_closed": data is None or (data["_session"]._closed and close_error is None),
            "journals": journal_state,
            "cumulative_read_charge_bytes": budget.reads, "read_allowances": budget.read_allowances,
            "cumulative_write_charge_bytes_before_final": budget.writes, "deleted_bytes_still_charged": budget.deleted_bytes,
            "measured_session_written_bytes_including_deleted": budget.external_measured_bytes,
            "write_accounting_unresolved": budget.accounting_unresolved,
            "write_accounting": "Owned requests precharged; Session extents measured once or full reserved failure bound explicitly charged; deletion never refunded.",
            "outer_absolute_deadline_required": whole_deadline,
            "driver_attests_own_outer_closure": False,
            "limits": cap, "native_participant_deliveries": 0, "provider_calls": 0, "predictions": 0, "scoring": False,
            "source_drift_checked": source_before is not None and failure is None,
            "image_bodies_retained_for_successes": False,
            "limits_of_claim": ["Shared render feeding two local projections, not two independent renders or native deliveries.",
                "Initial query image only; no later actions or rendered demonstrations.",
                "Hash census cannot replay discarded image bodies and is not a complete benchmark arm capture.",
                "No physiological, scientific-performance or model claim."]}
        write_new(output / "RESULT.json", summary, budget, FINAL_RESERVE, final=True)
        # Final cumulative charge is recoverable as before_final + RESULT
        # byte extent. No recursive self-pin or speculative exact zero.
    print(json.dumps({"status": summary["status"], "read_charge_bytes": budget.reads,
                      "cumulative_write_charge_bytes": budget.writes, "output": str(output)}))
    return 0 if complete else 1


def main():
    began = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--plan-bytes", type=int, required=True)
    parser.add_argument("--plan-sha256", required=True)
    args = parser.parse_args()
    expected = {"bytes": args.plan_bytes, "sha256": args.plan_sha256}
    check_pin(expected, 65536)
    admission = Budget(65537, FINAL_RESERVE)
    plan = decode(read(args.plan, 65536, admission, expected))
    return run(plan, expected, began)


if __name__ == "__main__":
    raise SystemExit(main())
