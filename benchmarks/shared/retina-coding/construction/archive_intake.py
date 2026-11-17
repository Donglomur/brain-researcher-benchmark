"""Validate and retain all-18 byte streams through a required response provider.

Supports declared provider MD5 plus observed SHA256, or the strict SHA256 schema.
No default transport, RAR/MAT decoding, participant export or scientific score.
"""
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import stat
import time

from retina_contract import Refusal, require, validate_release_manifest
from provider_md5 import validate_provider_md5_manifest

CHUNK = 1048576
HEADER_CAP = 262144


def exclusive_record(path, body, ceiling):
    require(len(body) <= ceiling, "record:ceiling")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(body)
        while view:
            written = os.write(fd, view)
            require(written > 0, "record:zero_progress")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def acquire(manifest, output, wall_seconds, open_response, minimum_free_bytes=0):
    """One sequential pass; preserve all observed bounded body bytes; never retry."""
    provider_mode = type(manifest) is dict and manifest.get("schema") == "retina-provider-md5-intake-v1"
    plan = validate_provider_md5_manifest(manifest) if provider_mode else validate_release_manifest(manifest)
    require(type(wall_seconds) in (int, float) and 0 < wall_seconds <= 86400, "wall:bound")
    require(type(minimum_free_bytes) is int and minimum_free_bytes >= 0, "disk:reserve")
    output = Path(output)
    require(output.is_absolute(), "output:absolute")
    for ancestor in output.parents:
        s = ancestor.lstat()
        require(stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode), "output:ancestor")
    output.mkdir(mode=0o700, exist_ok=False)
    start = time.monotonic()
    deadline = start + wall_seconds
    result = {
        "schema": "retina-byte-intake-result-v3", "status": "INCOMPLETE",
        "integrity_mode": "provider_md5_observed_sha256" if provider_mode else "expected_sha256",
        "attempted_archives": [], "not_attempted": [x["name"] for x in plan["archives"]],
        "observed_entity_bytes": 0, "requested_read_bytes": 0,
        "successfully_written_bytes": 0, "failed_read_prefix_bytes_unmeasured": False,
        "data_commit": plan["data_commit"], "archive_extraction_performed": False,
        "scientific_qualification": False, "provider_sha256_available": not provider_mode,
        "HTTP_header_original_bytes": 0, "provider_digest_verified": False,
    }
    failure = None
    try:
        for item in plan["archives"]:
            remaining_wall = deadline - time.monotonic()
            require(remaining_wall > 0, "wall:expired_before_request")
            if minimum_free_bytes:
                remaining_payload = plan["total_archive_bytes"] - result["successfully_written_bytes"]
                require(shutil.disk_usage(output).free >= remaining_payload + minimum_free_bytes,
                        "disk:remaining_all18_capacity")
            row = {"name": item["name"], "url": item["url"], "expected_bytes": item["bytes"],
                   "observed_bytes": 0, "written_bytes": 0, "complete": False,
                   "provider_digest_verified": False}
            result["attempted_archives"].append(row)
            result["not_attempted"].remove(item["name"])
            sha = hashlib.sha256()
            md5 = hashlib.md5(usedforsecurity=False) if provider_mode else None
            fd = os.open(output / item["name"], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)

            def retain(block, requested):
                require(type(block) is bytes and len(block) <= requested, "read:contract")
                row["observed_bytes"] += len(block)
                result["observed_entity_bytes"] += len(block)
                view = memoryview(block)
                while view:
                    written = os.write(fd, view)
                    require(written > 0, "write:zero_progress")
                    sha.update(view[:written])
                    if md5 is not None:
                        md5.update(view[:written])
                    row["written_bytes"] += written
                    result["successfully_written_bytes"] += written
                    view = view[written:]
                # Preserve the admitted one-byte overflow sentinel before refusal.
                require(row["observed_bytes"] <= item["bytes"], "body:overflow")

            try:
                before = os.fstat(fd)
                with open_response(item["url"], remaining_wall) as response:
                    header_record = {"requested_url": item["url"], "final_url": response.geturl(),
                                     "status": response.status, "protocol_version": getattr(response, "version", None),
                                     "reason": str(getattr(response, "reason", "")),
                                     "headers": list(response.headers.raw_items()),
                                     "response_body_selected": response.status == 200}
                    raw_headers = (json.dumps(header_record, ensure_ascii=True, sort_keys=True) + "\n").encode()
                    require(len(raw_headers) <= HEADER_CAP, "http:header_custody_ceiling")
                    header_name = item["name"] + ".http.json"
                    exclusive_record(output / header_name, raw_headers, HEADER_CAP)
                    row["http_original"] = {"name": header_name, "bytes": len(raw_headers),
                                            "sha256": hashlib.sha256(raw_headers).hexdigest()}
                    result["HTTP_header_original_bytes"] += len(raw_headers)
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
                        except http.client.IncompleteRead as exc:
                            retain(exc.partial, request_n)
                            row["incomplete_read_partial_retained"] = len(exc.partial)
                            raise Refusal("body:incomplete_read") from exc
                        except BaseException:
                            result["failed_read_prefix_bytes_unmeasured"] = True
                            raise
                        retain(block, request_n)
                        require(time.monotonic() < deadline, "wall:expired_after_read")
                        if not block:
                            break
                os.fsync(fd)
                after = os.fstat(fd)
                require((before.st_dev, before.st_ino, before.st_mode, before.st_nlink) ==
                        (after.st_dev, after.st_ino, after.st_mode, after.st_nlink)
                        and after.st_nlink == 1 and after.st_size == row["written_bytes"],
                        "output:identity_or_extent")
                require(row["observed_bytes"] == row["written_bytes"] == item["bytes"], "body:short")
                if provider_mode:
                    require(md5.hexdigest() == item["provider_md5"], "body:provider_md5")
                    row["provider_digest_verified"] = True
                else:
                    require(sha.hexdigest() == item["sha256"], "body:digest")
                row["complete"] = True
            finally:
                row["written_sha256"] = sha.hexdigest()
                row["actual_sha256"] = sha.hexdigest()  # Received local bytes, not a provider SHA in MD5 mode.
                if md5 is not None:
                    row["written_md5"] = md5.hexdigest()
                    row["expected_provider_md5"] = item["provider_md5"]
                row["unretained_observed_bytes"] = row["observed_bytes"] - row["written_bytes"]
                try:
                    os.fsync(fd)
                except OSError as exc:
                    row["partial_fsync_error"] = str(exc)[:1000]
                    if row["complete"]:
                        raise
                finally:
                    os.close(fd)
        result["status"] = "COMPLETE_ARCHIVE_BYTES_ONLY"
        result["provider_digest_verified"] = provider_mode and all(
            x["provider_digest_verified"] for x in result["attempted_archives"])
    except BaseException as exc:
        failure = exc
        result["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
        if result["attempted_archives"]:
            result["attempted_archives"][-1]["failure_preserved"] = True
    result["elapsed_seconds"] = time.monotonic() - start
    receipt = (json.dumps(result, sort_keys=True, allow_nan=False) + "\n").encode()
    exclusive_record(output / "RECEIPT.json", receipt, 65536)
    if failure is not None:
        raise Refusal("intake incomplete; inspect retained receipt and partial archive") from failure
    return result
