"""Two-name N063 exporter and binary-safe host copyout; no action on import.

The producer must have finished and sealed its output before this finite export
barrier. The container remains owned under the same absolute deadline until
export and removal complete. Killing the Docker CLI never proves container exit.
This module does not create containers, grant deployment, or parse archives.
"""
import hashlib
import json
import os
import posixpath
import math
from pathlib import Path
import re
import selectors
import stat
import subprocess
import sys
import time

OUTPUT_CAPS = {"plane_metadata.json": 33554432, "session_support.json": 100663296}
EXPORT_PATH = "/operator/n063_fixed_export.py"
STOP_HELPER_SHA256 = "661defbfd525f6ca2fea14cbc077808839b54dd263206008646611b2a95b4b9e"


def need(ok, message):
    if not ok:
        raise ValueError(message)


def validate_endpoint(value):
    """Canonical local Unix endpoint; authority/daemon proof belongs to controller."""
    need(type(value) is str and value.startswith("unix:///")
         and len(value.encode("utf-8")) <= 4096
         and not any(c in value for c in "%?#")
         and not any(ord(c) < 33 or ord(c) == 127 for c in value),
         "canonical explicit local Unix socket endpoint")
    path = value[len("unix://"):]
    need(path != "/" and not path.startswith("//") and posixpath.normpath(path) == path,
         "absolute ordinary endpoint spelling")
    return value


def absolute_posix_path(value):
    need(type(value) is str and value.startswith("/") and not value.startswith("//")
         and len(value.encode("utf-8")) <= 4096 and posixpath.normpath(value) == value
         and not any(ord(c) < 32 or ord(c) == 127 for c in value),
         "explicit canonical absolute POSIX path")
    return value


def descriptor(value):
    need(type(value) is dict and set(value) == {"name", "bytes", "sha256"}
         and value["name"] in OUTPUT_CAPS and type(value["bytes"]) is int
         and 0 < value["bytes"] <= OUTPUT_CAPS[value["name"]]
         and type(value["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]),
         "bounded fixed artifact descriptor")
    return value


def stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_nlink, info.st_mode)


def export_one(expected):
    """Container side: output raw artifact bytes, no JSON/text transformation."""
    descriptor(expected)
    path = Path("/output") / expected["name"]
    need(all(not p.is_symlink() for p in (path, *path.parents)), "ordinary output ancestors")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == expected["bytes"] and before.st_mode & 0o222 == 0,
             "sealed ordinary producer output")
        total, requested, digest = 0, 0, hashlib.sha256()
        while total < expected["bytes"]:
            count = min(65536, expected["bytes"] - total)
            need(requested + count <= expected["bytes"] + 1, "export source requested-read ceiling")
            requested += count
            block = os.read(fd, count)
            need(block, "complete output input")
            digest.update(block)
            offset = 0
            while offset < len(block):
                count = os.write(sys.stdout.fileno(), memoryview(block)[offset:])
                need(count > 0, "complete binary export write")
                offset += count
            total += len(block)
        need(requested + 1 <= expected["bytes"] + 1, "export source EOF reservation")
        requested += 1
        need(not os.read(fd, 1) and stamp(before) == stamp(os.fstat(fd))
             and stamp(before) == stamp(path.lstat()), "stable complete export identity")
        need(digest.hexdigest() == expected["sha256"], "complete exported body SHA256")
    finally:
        os.close(fd)


def export_command(deployment, container_id, expected):
    descriptor(expected)
    need(type(deployment) is dict and set(deployment) == {
         "docker", "endpoint", "python_in_image", "exporter_in_image", "image_id",
         "runtime_receipt_sha256", "exporter_receipt_sha256", "delegation_receipt_sha256",
         "stop_helper_sha256"}, "exact task deployment")
    validate_endpoint(deployment["endpoint"])
    need(deployment["exporter_in_image"] == EXPORT_PATH, "fixed contained exporter path")
    absolute_posix_path(deployment["python_in_image"])
    binary = deployment["docker"]
    need(type(binary) is dict and set(binary) == {"path", "resolved_path", "bytes", "sha256"}
         and type(binary["bytes"]) is int and binary["bytes"] > 0
         and re.fullmatch(r"[0-9a-f]{64}", binary["sha256"]), "unresolved authenticated Docker binary")
    absolute_posix_path(binary["path"])
    absolute_posix_path(binary["resolved_path"])
    need(type(container_id) is str and re.fullmatch(r"[0-9a-f]{64}", container_id)
         and type(deployment["image_id"]) is str
         and re.fullmatch(r"sha256:[0-9a-f]{64}", deployment["image_id"]), "exact owned deployment identity")
    need(all(type(deployment[k]) is str and re.fullmatch(r"[0-9a-f]{64}", deployment[k])
             for k in ("runtime_receipt_sha256", "exporter_receipt_sha256", "delegation_receipt_sha256"))
         and deployment["stop_helper_sha256"] == STOP_HELPER_SHA256, "authenticated helper/delegation closure")
    return [binary["path"], "--host", deployment["endpoint"], "exec", "--user", "65534:65534", container_id,
            deployment["python_in_image"], "-I", "-S", "-B", EXPORT_PATH,
            expected["name"], str(expected["bytes"]), expected["sha256"]]


def copyout(lease, expected, *, deployment, stop_cli_leader):
    """Host side; a single pre-reserved attempt, no retry, no scientific JSON parse.

The trusted outer operator supplies a lease only after authenticating the exact
container, finished producer, immutable output, deployment and global reserve.
This function validates those cross-bindings; it does not manufacture that proof.
The immutable pinned bank.stop_cli_leader is supplied by the verified loader.
"""
    descriptor(expected)
    need(type(lease) is dict and set(lease) == {"kind", "identity", "container_id", "output_path",
         "host_deadline_monotonic", "clock_domain", "closure_seconds", "export_read_bytes", "host_write_bytes",
         "reservation_sha256", "producer_receipt_sha256", "ownership_receipt_sha256",
         "image_id", "single_export_attempt"}, "exact reserved fixed export lease")
    need(lease["kind"] in ("plane", "session") and lease["single_export_attempt"] is True
         and re.fullmatch(r"[0-9]{1,20}", lease["identity"]), "one original unit export")
    wanted = "plane_metadata.json" if lease["kind"] == "plane" else "session_support.json"
    need(expected["name"] == wanted and lease["image_id"] == deployment["image_id"], "same unit/image")
    need(all(type(lease[k]) is str and re.fullmatch(r"[0-9a-f]{64}", lease[k])
             for k in ("reservation_sha256", "producer_receipt_sha256", "ownership_receipt_sha256")),
         "owned finished-producer and reservation receipts")
    need(type(lease["export_read_bytes"]) is int and lease["export_read_bytes"] >= expected["bytes"] + 8193
         and type(lease["host_write_bytes"]) is int and lease["host_write_bytes"] >= expected["bytes"],
         "full byte envelope reserved before dispatch")
    need(type(lease["closure_seconds"]) is int and lease["closure_seconds"] >= 2,
         "CLI closure inside common deadline")
    deadline = lease["host_deadline_monotonic"]
    need(lease["clock_domain"] == "host_monotonic"
         and type(deadline) in (int, float) and math.isfinite(deadline), "finite host-local deadline")
    end = deadline - lease["closure_seconds"]
    need(time.monotonic() + 1 < end, "finite export time remaining")
    command = export_command(deployment, lease["container_id"], expected)
    path = Path(lease["output_path"])
    need(path.is_absolute() and str(path) == os.path.normpath(str(path)) and path.name == expected["name"]
         and path.parent.name == lease["kind"] + "-" + lease["identity"]
         and len(str(path).encode()) <= 2048
         and path.parent.is_dir() and all(not p.is_symlink() for p in (path, *path.parents)),
         "ordinary exact host unit output")
    env = {k: os.environ[k] for k in ("HOME", "TMPDIR") if k in os.environ}
    env.update(PATH="/usr/bin:/bin:/usr/sbin:/sbin", LANG="C", LC_ALL="C")
    fd = proc = selector = None
    total = written = requested = write_calls = 0
    digest = hashlib.sha256()
    stderr = bytearray()
    eof = {"stdout": False, "stderr": False}
    result = {"schema": "neural063_binary_copyout_v1", "identity": lease["identity"],
              "container_id": lease["container_id"], "reservation_sha256": lease["reservation_sha256"],
              "verified": False, "artifact": None, "partial_path": None, "write_uncertain": False,
              "container_absence_verified": False, "outer_group_absence_required": True,
              "attempt_marker_created": False, "cleanup_errors": []}
    error = None
    cleanup = {"leader_reaped": False, "whole_group_cleanup_delegated_to_watchdog": True}
    try:
        marker = (json.dumps({"reservation_sha256": lease["reservation_sha256"],
                  "container_id": lease["container_id"], "expected": expected},
                  sort_keys=True, separators=(",", ":")) + "\n").encode()
        need(len(marker) <= 1024, "bounded one-use attempt marker")
        marker_fd = os.open(path.parent / "COPYOUT_ATTEMPT.json",
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        result["attempt_marker_created"] = True
        try:
            count = os.write(marker_fd, marker)
            result["attempt_marker_bytes_confirmed"] = count
            need(count == len(marker), "complete nonretryable attempt marker")
            os.fsync(marker_fd)
        finally:
            os.close(marker_fd)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        result["partial_path"] = str(path)
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env, close_fds=True, start_new_session=False)
        selector = selectors.DefaultSelector()
        for name, stream in (("stdout", proc.stdout), ("stderr", proc.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            left = end - time.monotonic()
            need(left > 0, "binary export deadline")
            for key, _ in selector.select(min(0.025, left)):
                remaining = expected["bytes"] - written if key.data == "stdout" else 8192 - len(stderr)
                block = os.read(key.fileobj.fileno(), min(65536, remaining + 1))
                total += len(block)
                need(total <= lease["export_read_bytes"], "cumulative export read bound")
                if not block:
                    eof[key.data] = True
                    selector.unregister(key.fileobj)
                    continue
                need(len(block) <= remaining, "fixed output/stderr ceiling")
                if key.data == "stderr":
                    stderr.extend(block)
                else:
                    offset = 0
                    while offset < len(block):
                        result["write_uncertain"] = True
                        piece = memoryview(block)[offset:]
                        need(requested + len(piece) <= lease["host_write_bytes"], "requested host artifact-write ceiling")
                        requested += len(piece)
                        write_calls += 1
                        count = os.write(fd, piece)
                        need(count > 0, "complete host stream write")
                        digest.update(memoryview(block)[offset:offset + count])
                        written += count
                        offset += count
                        result["write_uncertain"] = False
        proc.wait(timeout=max(0.001, end - time.monotonic()))
        need(proc.returncode == 0 and not stderr and all(eof.values()), "complete successful binary export")
        need(written == expected["bytes"] and digest.hexdigest() == expected["sha256"], "exact opaque byte identity")
        os.fsync(fd)
        os.fchmod(fd, 0o444)
        st = os.fstat(fd)
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == written
             and stamp(st) == stamp(path.lstat()), "same-FD/named-path complete host output")
        parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        need(stamp(st) == stamp(os.fstat(fd)) == stamp(path.lstat()), "durable unchanged output identity")
    except BaseException as exc:
        error = type(exc).__name__ + ": " + str(exc)[:256]
    finally:
        if selector is not None:
            try:
                selector.close()
            except BaseException as exc:
                message = type(exc).__name__ + ": " + str(exc)[:256]
                result["cleanup_errors"].append(message)
                error = error or message
        if proc is not None:
            try:
                cleanup = stop_cli_leader(proc)
            except BaseException as exc:
                message = type(exc).__name__ + ": " + str(exc)[:256]
                result["cleanup_errors"].append(message)
                error = error or message
            for stream in (proc.stdout, proc.stderr):
                try:
                    stream.close()
                except BaseException as exc:
                    message = type(exc).__name__ + ": " + str(exc)[:256]
                    result["cleanup_errors"].append(message)
                    error = error or message
        if fd is not None:
            try:
                final_stat = os.fstat(fd)
                result["retained_extent_bytes"] = final_stat.st_size
                if error is None:
                    need(stamp(final_stat) == stamp(path.lstat()), "final same-FD/named-path identity")
            except BaseException as exc:
                result["write_uncertain"] = True
                message = type(exc).__name__ + ": " + str(exc)[:256]
                result["cleanup_errors"].append(message)
                error = error or message
            finally:
                try:
                    os.close(fd)
                except BaseException as exc:
                    result["write_uncertain"] = True
                    message = type(exc).__name__ + ": " + str(exc)[:256]
                    result["cleanup_errors"].append(message)
                    error = error or message
    result.update(read_bytes=total, confirmed_written_bytes=written,
                  requested_write_bytes=requested, write_calls=write_calls,
                  confirmed_prefix_sha256=digest.hexdigest(), streams_eof=all(eof.values()),
                  cli_cleanup=cleanup, error=error, stderr_bytes=len(stderr),
                  stderr_sha256=hashlib.sha256(stderr).hexdigest())
    if time.monotonic() >= deadline:
        result["error"] = result["error"] or "host publication/closure deadline exceeded"
    if result["error"] is None and cleanup.get("leader_reaped") is True and not result["write_uncertain"]:
        result.update(verified=True, artifact=dict(expected), partial_path=None,
                      write_usage={"bytes_requested": requested, "bytes_confirmed": written,
                                   "write_calls": write_calls, "exclusive_append_only": True,
                                   "same_fd_path": True, "fsync": True, "complete": True,
                                   "sha256": digest.hexdigest()})
    return result


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        need(len(args) == 3 and re.fullmatch(r"[0-9]{1,9}", args[1]), "fixed export arguments")
        export_one({"name": args[0], "bytes": int(args[1]), "sha256": args[2]})
        return 0
    except BaseException as exc:
        os.write(2, ("N063 export refused: " + type(exc).__name__ + "\n").encode())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
