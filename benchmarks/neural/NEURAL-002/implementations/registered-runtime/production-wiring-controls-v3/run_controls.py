"""One root-selected, source-pinned synthetic group. No automatic retries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import time
import traceback
import types

START = time.monotonic()
GROUPS = {"boundary": (8 * 2**20, 20), "full_positive": (76 * 2**20, 40),
          "full_last_failure": (76 * 2**20, 40), "storage": (24 * 2**20, 30)}


def require(value, message):
    if not value: raise AssertionError(message)


def canonical_root(value, *, absent=False):
    p = Path(value)
    require(type(value) is str and not value.startswith("//") and p.is_absolute()
            and str(p) == value and ".." not in p.parts and len(value.encode()) <= 384,
            "canonical selected control path within reviewed384-byte fixture bound")
    for parent in (p.parent, *p.parent.parents):
        require(stat.S_ISDIR(parent.lstat().st_mode) and not parent.is_symlink(), "ordinary control ancestry")
    if absent: require(not p.exists() and not p.is_symlink(), "new owned result/fixture path")
    else: require(stat.S_ISDIR(p.lstat().st_mode) and not p.is_symlink(), "ordinary selected source root")
    return p


def main():
    require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode, "actual -I -S -B required")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--group", choices=tuple(GROUPS), required=True)
    for name in ("package", "legacy", "fixture-root", "output", "selection-sha256"):
        p.add_argument("--" + name, required=True)
    for name in ("selection-bytes", "transfer-bytes", "seconds"):
        p.add_argument("--" + name, type=int, required=True)
    a = p.parse_args()
    require((a.transfer_bytes, a.seconds) == GROUPS[a.group], "exact reviewed group envelope")
    overall_end, case_end = START + a.seconds, START + a.seconds - 2
    base = canonical_root(str(Path(__file__).absolute().parent))
    package, legacy = canonical_root(a.package), canonical_root(a.legacy)
    root, output = canonical_root(a.fixture_root, absent=True), canonical_root(a.output, absent=True)
    require(root.parent == base and output.parent == base and root != output, "task-owned fresh direct child outputs")
    bootstrap_read = bootstrap_write = 0

    def bootstrap(pin):
        nonlocal bootstrap_read, bootstrap_write
        require(type(pin["bytes"]) is int and 0 < pin["bytes"] <= 2**20, "finite pinned control source")
        require(time.monotonic() < case_end and bootstrap_read + bootstrap_write + 4 * pin["bytes"] + 1 <= a.transfer_bytes,
                "pre-effect bootstrap reservation")
        bootstrap_read += 2 * pin["bytes"] + 1; bootstrap_write += 2 * pin["bytes"]
        path = base / pin["path"]
        require(not Path(pin["path"]).is_absolute() and ".." not in Path(pin["path"]).parts
                and str(Path(pin["path"])) == pin["path"], "relative selected control source")
        for parent in (path.parent, *path.parent.parents):
            require(stat.S_ISDIR(parent.lstat().st_mode) and not parent.is_symlink(), "ordinary bootstrap parents")
        s = path.lstat()
        require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size == pin["bytes"], "ordinary bootstrap member")
        fd, first, secondary, result = None, None, [], None
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            opened = os.fstat(fd)
            body = bytearray()
            while len(body) <= pin["bytes"]:
                part = os.read(fd, min(65536, pin["bytes"] + 1 - len(body)))
                if not part: break
                body.extend(part)
            after = os.fstat(fd)
            stamp = lambda q: (q.st_dev, q.st_ino, q.st_size, q.st_mtime_ns, q.st_ctime_ns)
            require(stamp(s) == stamp(opened) == stamp(after) == stamp(path.lstat()), "stable selected control source")
            require(len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"], "control source pin")
            result = bytes(body)
        except BaseException as exc:
            first = exc
        finally:
            if fd is not None:
                try: os.close(fd)
                except BaseException as exc:
                    if first is None: first = exc
                    else: secondary.append(exc)
        if first is not None:
            first.morse_control_secondary_errors = tuple(getattr(first, "morse_control_secondary_errors", ())) + tuple(secondary)
            raise first
        return result

    selection_body = bootstrap({"path": "CONTROL_SELECTION.json", "bytes": a.selection_bytes, "sha256": a.selection_sha256})
    selection = json.loads(selection_body)
    require(selection["schema"] == "morse_wiring_control_selection_v1" and selection["execution_selected"] is False,
            "frozen proposal schema; authority remains external")
    bodies = {r["path"]: bootstrap(r) for r in selection["control_sources"]}
    require("run_controls.py" in bodies, "actual entry is a selected member; root owner pins it before execution")
    require(bootstrap_read + bootstrap_write < a.transfer_bytes, "bootstrap complete reservation")
    support_extent = len(bodies["control_support.py"])
    require(time.monotonic() < case_end and bootstrap_read + bootstrap_write + 2 * support_extent <= a.transfer_bytes,
            "prospective direct support compile reservation")
    bootstrap_read += support_extent; bootstrap_write += support_extent
    support = types.ModuleType("control_support"); support.__file__ = str(base / "control_support.py")
    sys.modules["control_support"] = support
    exec(compile(bodies["control_support.py"], support.__file__, "exec"), support.__dict__)
    meter = support.Meter(a.transfer_bytes, a.seconds)
    meter.end = case_end
    meter.read_used, meter.write_used = bootstrap_read, bootstrap_write
    meter.charges.append({"read": bootstrap_read, "write": bootstrap_write, "label": "prospectively admitted complete control bootstrap"})
    meter.charge(read=65536, write=5 * 65536, label="result dumps/concatenation/encoding/file write/hash plus final summary and error output")
    log = support.CaseLog()
    first, secondary, detail, module = None, [], None, None

    def forbidden(*args, **kwargs):
        raise AssertionError("unselected real subprocess or network leaf")

    old_popen, old_connect, old_socket = subprocess.Popen, socket.create_connection, socket.socket
    subprocess.Popen, socket.create_connection, socket.socket = forbidden, forbidden, forbidden
    try:
        root.mkdir(mode=0o700)
        with support.Sources(package, legacy, meter) as sources:
            if a.group == "storage":
                key, name = "storage-controls-v1/storage_controls.py", "morse_storage_controls"
            elif a.group == "boundary":
                key, name = "boundary_controls.py", "morse_boundary_controls"
            else:
                key, name = "full_caller_controls.py", "morse_full_caller_controls"
            module = types.ModuleType(name); module.__file__ = str(base / key)
            meter.charge(read=len(bodies[key]), write=len(bodies[key]), label="direct selected control group compile")
            exec(compile(bodies[key], module.__file__, "exec"), module.__dict__)
            if a.group == "storage":
                detail = module.run(sources.fresh, meter)
                for item in detail["checks"]:
                    require(item["status"] == "PASS", "storage group incomplete")
                    log.rows.append(item)
            elif a.group == "boundary":
                detail = module.run(sources, meter, root, log)
            else:
                detail = module.run(sources, meter, root, log, late_failure=a.group == "full_last_failure")
            meter.check()
    except BaseException as exc:
        first = exc
        if hasattr(exc, "partial"):
            detail = {"partial": exc.partial, "original_error_type": type(getattr(exc, "original", exc)).__name__}
            if not log.rows and type(exc.partial) is dict:
                log.rows.extend(exc.partial.get("checks", []))
        elif module is not None and hasattr(module, "PARTIAL"):
            detail = {"partial": module.PARTIAL}
    finally:
        subprocess.Popen, socket.create_connection, socket.socket = old_popen, old_connect, old_socket
    # Evidence publication uses its preselected reserve and the ORIGINAL outer
    # horizon. No deadline is renewed after the engineering work fails.
    value = {"schema": "morse_wiring_invented_control_result_v1", "group": a.group,
             "complete": first is None, "checks": log.rows, "detail": detail,
             "transfer": meter.snapshot(), "first_error_type": None if first is None else type(first).__name__,
             "first_error_text_prefix": None if first is None else str(first)[:2048],
             "secondary_error_types": [type(e).__name__ for e in getattr(first, "morse_control_secondary_errors", ())],
             "elapsed_internal_seconds": time.monotonic() - START,
             "natural_outer_status_required_separately": True, "full_external_elapsed_not_measured_here": True,
             "task_source_manifest_sha256": support.MANIFEST_SHA256,
             "authentic_signal_bytes": 0, "scientific_result": False, "native_qualification": False,
             "fixture_root_preserved": str(root)}
    try:
        require(time.monotonic() < overall_end, "original final-publication horizon exhausted")
        body = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        require(len(body) <= 65536, "finite control result output")
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        write_error, close_error = None, None
        try:
            with os.fdopen(fd, "wb", closefd=False) as stream: stream.write(body); stream.flush()
        except BaseException as exc:
            write_error = exc
        finally:
            try: os.close(fd)
            except BaseException as exc: close_error = exc
        if write_error is not None:
            if close_error is not None: secondary.append(close_error)
            raise write_error
        if close_error is not None: raise close_error
        require(time.monotonic() < overall_end, "result publication completed after original deadline")
        print(json.dumps({"group": a.group, "complete": first is None, "checks": len(log.rows),
                          "result_bytes": len(body), "result_sha256": hashlib.sha256(body).hexdigest()}), flush=True)
        require(time.monotonic() < overall_end, "final stdout completed after original horizon")
    except BaseException as exc:
        secondary.append(exc)
        if first is None: first = exc
    if first is not None:
        traceback.print_exception(type(first), first, first.__traceback__, limit=12)
        for exc in secondary:
            print("secondary publication: " + type(exc).__name__ + ": " + str(exc)[:512], file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        # Bootstrap failures precede the structured result writer. Preserve
        # original-first traceback and separately expose every raw close error.
        for secondary in getattr(exc, "morse_control_secondary_errors", ()):
            print("secondary source close:", type(secondary).__name__, str(secondary)[:512], file=sys.stderr)
        raise
