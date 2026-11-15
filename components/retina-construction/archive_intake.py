"""Validate and retain all-18 archive bytes through an explicit response provider.

No default network transport, RAR/MAT decoding or participant export is supplied.
Authentic acquisition requires independently verified metadata and an outer owner.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import time

from retina_contract import Refusal, require, validate_release_manifest

CHUNK = 1048576


def acquire(manifest, output, wall_seconds, open_response):
    """One pass per archive, no retries, stop on first failure, preserve partials."""
    plan = validate_release_manifest(manifest)
    require(type(wall_seconds) in (int, float) and 0 < wall_seconds <= 86400, "wall:bound")
    output = Path(output)
    require(output.is_absolute(), "output:absolute")
    for ancestor in output.parents:
        s = ancestor.lstat()
        require(stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode), "output:ancestor")
    output.mkdir(mode=0o700, exist_ok=False)
    start = time.monotonic()
    deadline = start + wall_seconds
    result = {
        "schema": "retina-byte-intake-result-v1", "status": "INCOMPLETE",
        "attempted_archives": [], "not_attempted": [x["name"] for x in plan["archives"]],
        "observed_entity_bytes": 0, "requested_read_bytes": 0,
        "successfully_written_bytes": 0, "failed_read_prefix_bytes_unmeasured": False,
        "data_commit": plan["data_commit"], "archive_extraction_performed": False,
        "scientific_qualification": False,
    }
    failure = None
    try:
        for item in plan["archives"]:
            remaining_wall = deadline - time.monotonic()
            require(remaining_wall > 0, "wall:expired_before_request")
            row = {"name": item["name"], "expected_bytes": item["bytes"],
                   "observed_bytes": 0, "written_bytes": 0, "complete": False}
            result["attempted_archives"].append(row)
            result["not_attempted"].remove(item["name"])
            h = hashlib.sha256()
            fd = os.open(output / item["name"], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                before = os.fstat(fd)
                with open_response(item["url"], remaining_wall) as response:
                    require(response.status == 200 and response.geturl() == item["url"],
                            "http:status_or_redirect")
                    encoding = response.headers.get_all("Content-Encoding", [])
                    require(not encoding or encoding == ["identity"], "http:encoding")
                    lengths = response.headers.get_all("Content-Length", [])
                    transfer = response.headers.get_all("Transfer-Encoding", [])
                    require(len(lengths) <= 1, "http:duplicate_length")
                    require(not (lengths and transfer), "http:ambiguous_framing")
                    require(not transfer or transfer == ["chunked"], "http:transfer_encoding")
                    if lengths:
                        require(lengths[0].isdigit() and int(lengths[0]) == item["bytes"], "http:length")
                    while True:
                        require(time.monotonic() < deadline, "wall:expired_during_stream")
                        request_n = min(CHUNK, item["bytes"] - row["observed_bytes"] + 1)
                        require(request_n > 0, "body:overflow")
                        require(result["requested_read_bytes"] + request_n <= plan["requested_read_admission_bytes"],
                                "read:requested_ceiling")
                        result["requested_read_bytes"] += request_n
                        try:
                            block = response.read(request_n)
                        except BaseException:
                            result["failed_read_prefix_bytes_unmeasured"] = True
                            raise
                        require(type(block) is bytes and len(block) <= request_n, "read:contract")
                        row["observed_bytes"] += len(block)
                        result["observed_entity_bytes"] += len(block)
                        require(time.monotonic() < deadline, "wall:expired_after_read")
                        if not block:
                            break
                        require(row["observed_bytes"] <= item["bytes"], "body:overflow")
                        h.update(block)
                        view = memoryview(block)
                        while view:
                            written = os.write(fd, view)
                            require(written > 0, "write:zero_progress")
                            row["written_bytes"] += written
                            result["successfully_written_bytes"] += written
                            view = view[written:]
                os.fsync(fd)
                after = os.fstat(fd)
                require((before.st_dev, before.st_ino, before.st_mode, before.st_nlink) ==
                        (after.st_dev, after.st_ino, after.st_mode, after.st_nlink)
                        and after.st_nlink == 1 and after.st_size == row["written_bytes"],
                        "output:identity_or_extent")
                row["actual_sha256"] = h.hexdigest()
                require(row["observed_bytes"] == row["written_bytes"] == item["bytes"], "body:short")
                require(row["actual_sha256"] == item["sha256"], "body:digest")
                row["complete"] = True
            finally:
                os.close(fd)
        result["status"] = "COMPLETE_ARCHIVE_BYTES_ONLY"
    except BaseException as exc:
        failure = exc
        result["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
        if result["attempted_archives"]:
            result["attempted_archives"][-1]["failure_preserved"] = True
    result["elapsed_seconds"] = time.monotonic() - start
    receipt = (json.dumps(result, sort_keys=True, allow_nan=False) + "\n").encode()
    require(len(receipt) <= 65536, "receipt:ceiling")
    fd = os.open(output / "RECEIPT.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(receipt)
        while view:
            n = os.write(fd, view)
            require(n > 0, "receipt:zero_progress")
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    if failure is not None:
        raise Refusal("intake incomplete; inspect retained receipt and partial archive") from failure
    return result
