"""Build-time acquisition or verified local staging of two unchanged NWB files.

Importing this module never downloads data. Runtime use is verify_staged() only.
No redirects, retries, implicit source substitution, or preprocessing are allowed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import signal
import stat
import time
import urllib.parse
import urllib.request

MANIFEST_NAME = "source_manifest.json"
MANIFEST_SHA256 = "175cdbcbeaa8259bd8f825521919bdd71698a65e03341d9f391c19c783075ec8"
MANIFEST_PATH = Path(__file__).with_name(MANIFEST_NAME)
CHUNK = 1024 * 1024
SAFE_HEADERS = {"content-length", "content-type", "etag", "last-modified", "x-amz-version-id", "date"}


class SourceError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SourceError("Redirect refused; only the pinned original object is allowed")


def require_safe_ancestry(path):
    path = Path(path).absolute()
    if ".." in path.parts:
        raise SourceError("Parent traversal refused")
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise SourceError("Symlinked path or ancestor refused")
    return path


def read_manifest(path=MANIFEST_PATH):
    path = require_safe_ancestry(path)
    if not path.is_file() or path.stat().st_size > 65536:
        raise SourceError("Missing or oversized source manifest")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise SourceError("Frozen source manifest SHA256 mismatch")
    manifest = json.loads(raw)
    if manifest.get("schema_version") != 1 or manifest.get("dataset_id") != "dandi000552" or manifest.get("version") != "0.230630.2304":
        raise SourceError("Unexpected manifest identity")
    entries = manifest.get("files", [])
    if len(entries) != 2 or {entry.get("role") for entry in entries} != {"raw", "behavior"}:
        raise SourceError("Expected exactly the original raw and behavior assets")
    paths = []
    for entry in entries:
        rel = PurePosixPath(entry["path"])
        if rel.is_absolute() or ".." in rel.parts or str(rel) != entry["path"] or "\\" in entry["path"]:
            raise SourceError("Unsafe or noncanonical source path")
        if not rel.parts or rel.parts[0] != "sub-e15-13f1" or rel.suffix != ".nwb":
            raise SourceError("Unexpected source path")
        url = urllib.parse.urlsplit(entry["url"])
        if url.scheme != "https" or url.netloc != "dandiarchive.s3.us-east-2.amazonaws.com" or url.query or url.fragment or url.username:
            raise SourceError("Unexpected source URL")
        if not entry["url"].startswith("https://dandiarchive.s3.us-east-2.amazonaws.com/blobs/"):
            raise SourceError("Unexpected original-object path")
        if not isinstance(entry["size_bytes"], int) or entry["size_bytes"] <= 0:
            raise SourceError("Invalid original byte count")
        if len(entry["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in entry["sha256"]):
            raise SourceError("Invalid source SHA256")
        paths.append(entry["path"])
    if len(set(paths)) != len(paths):
        raise SourceError("Duplicate source path")
    limits = manifest["acquisition_limits"]
    if limits != {"total_body_bytes": 7200000000, "timeout_seconds": 1800, "concurrent_requests": 1, "automatic_retries": 0}:
        raise SourceError("Changed acquisition budget or retry policy")
    if sum(entry["size_bytes"] for entry in entries) > limits["total_body_bytes"]:
        raise SourceError("Source inventory exceeds declared acquisition budget")
    return manifest, raw


def hash_regular(path, expected_size):
    path = require_safe_ancestry(path)
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size != expected_size:
        raise SourceError(f"Missing, nonregular, or wrong-size source: {path.name}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_inventory(root, manifest):
    allowed_files = {MANIFEST_NAME, *(entry["path"] for entry in manifest["files"])}
    allowed_dirs = {str(parent) for name in allowed_files for parent in PurePosixPath(name).parents if str(parent) != "."}
    stack = [root]
    observed = set()
    while stack:
        directory = stack.pop()
        for path in directory.iterdir():
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                raise SourceError("Symlink in staged source inventory")
            if path.is_dir():
                if rel not in allowed_dirs:
                    raise SourceError(f"Unexpected source directory: {rel}")
                stack.append(path)
            elif path.is_file() and rel in allowed_files:
                observed.add(rel)
            else:
                raise SourceError(f"Unexpected source file or filesystem object: {rel}")
    if observed != allowed_files:
        raise SourceError("Incomplete staged source inventory")


def verify_staged(data_dir):
    """Return the frozen manifest after authenticating every original source byte."""
    root = require_safe_ancestry(data_dir)
    if not root.is_dir():
        raise SourceError("Missing source directory")
    manifest, _ = read_manifest(root / MANIFEST_NAME)
    verify_inventory(root, manifest)
    for entry in manifest["files"]:
        if hash_regular(root / entry["path"], entry["size_bytes"]) != entry["sha256"]:
            raise SourceError(f"Original source SHA256 mismatch: {entry['role']}")
    return manifest


def stage_data(destination, source_root=None, manifest_path=MANIFEST_PATH, receipt_path=None):
    """Stage unchanged originals locally or download once at Docker build time."""
    manifest, raw_manifest = read_manifest(manifest_path)
    destination = require_safe_ancestry(destination)
    if destination.exists():
        verified = verify_staged(destination)
        return {"status": "existing_verified", "source_sha256": {e["path"]: e["sha256"] for e in verified["files"]}}
    if source_root is not None:
        source_root = require_safe_ancestry(source_root)
        if not source_root.is_dir():
            raise SourceError("Local original-source root does not exist")
    receipt_path = require_safe_ancestry(receipt_path or destination.with_name(destination.name + "_staging_receipt.json"))
    if receipt_path == destination or destination in receipt_path.parents or receipt_path.exists():
        raise SourceError("Receipt must be a new path outside the runtime source directory")
    destination.mkdir(parents=True)
    started = time.monotonic()
    limits = manifest["acquisition_limits"]
    deadline = started + limits["timeout_seconds"]
    receipt = {"status": "in_progress", "mode": "local_verified_copy" if source_root else "build_time_download",
               "source_manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(), "body_bytes_read": 0,
               "files": [], "automatic_retries": 0, "scientific_processing": False}

    def save():
        receipt["elapsed_seconds"] = time.monotonic() - started
        with receipt_path.open("w") as stream:
            json.dump(receipt, stream, indent=2, allow_nan=False)
            stream.write("\n")

    def expire(signum, frame):
        raise SourceError("Staging deadline exceeded; partial retained without retry")

    old_handler = signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, limits["timeout_seconds"])
    opener = urllib.request.build_opener(NoRedirect)
    save()
    try:
        for entry in manifest["files"]:
            final = destination / entry["path"]
            final.parent.mkdir(parents=True, exist_ok=True)
            require_safe_ancestry(final.parent)
            partial = final.with_name(final.name + ".partial")
            if final.exists() or partial.exists() or final.is_symlink() or partial.is_symlink():
                raise SourceError("Existing staged target refused")
            item = {"role": entry["role"], "path": entry["path"], "status": "copying" if source_root else "requesting", "size_bytes": 0}
            receipt["files"].append(item)
            save()
            if source_root:
                origin = require_safe_ancestry(source_root / entry["path"])
                if not origin.is_file() or not stat.S_ISREG(origin.stat().st_mode) or origin.stat().st_size != entry["size_bytes"]:
                    raise SourceError("Missing, nonregular, or wrong-size local source")
                stream = origin.open("rb")
            else:
                if receipt["body_bytes_read"] + entry["size_bytes"] > limits["total_body_bytes"]:
                    raise SourceError("Acquisition would exceed total byte budget")
                url = entry["url"] + "?" + urllib.parse.urlencode({"versionId": entry["version_id"]})
                request = urllib.request.Request(url, headers={"If-Match": '"' + entry["etag"] + '"', "Accept-Encoding": "identity", "User-Agent": "BRBench-build-time-source/1.0"})
                stream = opener.open(request, timeout=min(30, max(0.001, deadline - time.monotonic())))
                item["http_status"] = stream.status
                item["headers"] = {k.lower(): v for k, v in stream.headers.items() if k.lower() in SAFE_HEADERS}
                headers = item["headers"]
                if stream.status != 200 or int(headers.get("content-length", -1)) != entry["size_bytes"] or headers.get("etag", "").strip('"') != entry["etag"] or headers.get("x-amz-version-id") != entry["version_id"]:
                    stream.close()
                    raise SourceError("Original response status/length/ETag/VersionId mismatch before body")
            digest = hashlib.sha256()
            with stream, partial.open("xb") as output:
                while item["size_bytes"] < entry["size_bytes"]:
                    if time.monotonic() >= deadline:
                        raise SourceError("Staging time limit exceeded")
                    length = min(CHUNK, entry["size_bytes"] - item["size_bytes"])
                    block = stream.read(length)
                    if not block:
                        raise SourceError("Truncated original; partial retained, no retry")
                    item["size_bytes"] += len(block)
                    if not source_root:
                        receipt["body_bytes_read"] += len(block)
                    digest.update(block)
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            item["sha256"] = digest.hexdigest()
            if item["size_bytes"] != entry["size_bytes"] or partial.stat().st_size != entry["size_bytes"] or item["sha256"] != entry["sha256"]:
                raise SourceError("Full original size or SHA256 mismatch; partial retained")
            if final.exists() or final.is_symlink():
                raise SourceError("Target appeared while staging")
            os.rename(partial, final)
            item["status"] = "complete"
            save()
        manifest_partial = destination / (MANIFEST_NAME + ".partial")
        with manifest_partial.open("xb") as stream:
            stream.write(raw_manifest)
            stream.flush()
            os.fsync(stream.fileno())
        os.rename(manifest_partial, destination / MANIFEST_NAME)
        verify_staged(destination)
        receipt["status"] = "complete"
        receipt["full_source_sha256_verified"] = True
    except Exception as error:
        receipt["status"] = "failed"
        receipt["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        save()
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/source"))
    parser.add_argument("--source-root", type=Path, help="Verified local original-byte source; no network when provided")
    parser.add_argument("--receipt", type=Path, help="Optional new staging receipt outside destination")
    args = parser.parse_args()
    result = stage_data(args.destination, args.source_root, receipt_path=args.receipt)
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
