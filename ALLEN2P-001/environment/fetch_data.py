"""Build-time-only staging of one frozen released Allen Visual Coding NWB.

No analysis, SDK cache, alternate assets, implicit refresh or automatic retry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import signal
import stat
import tempfile
import time
from urllib.request import HTTPRedirectHandler, Request, build_opener

MANIFEST_PATH = Path(__file__).with_name("source_manifest.json")
MANIFEST_SHA256 = "1b678f699e50065b16230d1206aa5459fec2132435882f62813004d6c5b12a29"
SOURCE_URL = "https://allen-brain-observatory.s3.us-west-2.amazonaws.com/visual-coding-2p/ophys_experiment_data/501271265.nwb"
SOURCE_FILENAME = "501271265.nwb"
SAFE_HEADERS = {"content-type", "content-length", "etag", "last-modified", "date",
                "accept-ranges", "content-encoding", "x-amz-version-id", "x-amz-checksum-sha256"}


def no_symlinks(path):
    path = Path(path).absolute()
    for part in [*reversed(path.parents), path]:
        if part.is_symlink():
            raise ValueError("Source/staging paths may not traverse symlinks")


def regular_file(path):
    path = Path(path)
    no_symlinks(path)
    if not path.exists() or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("Expected a regular source file")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path=None):
    path = MANIFEST_PATH if path is None else Path(path)
    regular_file(path)
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Frozen source manifest identity mismatch; do not repin")
    manifest = json.loads(body)
    if (manifest["task_id"] != "ALLEN2P-001" or manifest["ophys_experiment_id"] != 501271265
            or manifest["experiment_container_id"] != 511509529 or manifest["well_known_file_id"] != 514516625):
        raise ValueError("Original dataset/asset identity mismatch")
    if len(manifest["files"]) != 1:
        raise ValueError("Expected exactly one original released NWB")
    item = manifest["files"][0]
    if item["path"] != SOURCE_FILENAME or item["role"] != "original_released_session_nwb":
        raise ValueError("Wrong or unsafe original source path/role")
    if (type(item["size_bytes"]) is not int or item["size_bytes"] <= 0
            or not re.fullmatch("[0-9a-f]{64}", item["sha256"])):
        raise ValueError("Invalid original source size or checksum")
    policy = manifest["transport"]
    if (policy["url"] != SOURCE_URL or policy["automatic_retries"] != 0 or policy["redirects"] is not False
            or type(policy["timeout_seconds"]) is not int or not 0 < policy["timeout_seconds"] <= 600
            or type(policy["transfer_cap_bytes"]) is not int
            or not item["size_bytes"] < policy["transfer_cap_bytes"] <= 600000000):
        raise ValueError("Source transport/resource policy differs from contract")
    return manifest


def verify_source(path, manifest):
    path = Path(path)
    regular_file(path)
    item = manifest["files"][0]
    if path.stat().st_size != item["size_bytes"] or sha256(path) != item["sha256"]:
        raise ValueError("Frozen source size/SHA256 mismatch; do not refresh")


def verify_staged(data_dir):
    """Verify exact original source and manifest; never fetch or modify anything."""
    data_dir = Path(data_dir)
    no_symlinks(data_dir)
    if not data_dir.is_dir():
        raise ValueError("Expected a staged source directory")
    expected = {SOURCE_FILENAME, "source_manifest.json"}
    if {p.name for p in data_dir.iterdir()} != expected:
        raise ValueError("Runtime source must contain exactly NWB and frozen manifest")
    manifest = read_manifest(data_dir / "source_manifest.json")
    verify_source(data_dir / SOURCE_FILENAME, manifest)
    return manifest


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Frozen source transport forbids redirects")


def safe_headers(headers):
    return {key: value for key, value in headers.items() if key.lower() in SAFE_HEADERS}


def download_source(path, manifest, receipt):
    path = Path(path)
    no_symlinks(path)
    if path.exists():
        raise FileExistsError("Refuse to overwrite an existing source download")
    policy, item = manifest["transport"], manifest["files"][0]
    if policy["url"] != SOURCE_URL:
        raise ValueError("Only the exact original HTTPS S3 object is allowed")
    receipt.update(url=SOURCE_URL, automatic_retries=0, measured_bytes=0)
    old_handler = signal.getsignal(signal.SIGALRM)
    def deadline(_signum, _frame):
        raise TimeoutError("Frozen source acquisition deadline exceeded")
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(policy["timeout_seconds"])
    try:
        request = Request(SOURCE_URL, headers={"If-Match": '"' + policy["etag"] + '"',
                                             "Accept-Encoding": "identity"}, method="GET")
        with build_opener(NoRedirect()).open(request, timeout=60) as response:
            receipt["headers"] = safe_headers(response.headers)
            if response.status != 200 or response.url != SOURCE_URL:
                raise ValueError("Expected exact original source URL and complete HTTP200")
            if int(response.headers.get("Content-Length", -1)) != item["size_bytes"]:
                raise ValueError("Source content-length mismatch")
            if response.headers.get("ETag", "").strip('"') != policy["etag"]:
                raise ValueError("Source ETag mismatch")
            if response.headers.get("Last-Modified") != policy["last_modified"]:
                raise ValueError("Source last-modified mismatch")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("Source transport must not encode the original body")
            with path.open("xb") as handle:
                while True:
                    remaining = policy["transfer_cap_bytes"] - receipt["measured_bytes"]
                    if remaining <= 0:
                        raise ValueError("Source transfer cap reached")
                    block = response.read(min(1024 * 1024, remaining))
                    if not block:
                        break
                    receipt["measured_bytes"] += len(block)
                    if receipt["measured_bytes"] > item["size_bytes"]:
                        raise ValueError("Source payload exceeds exact expected size")
                    handle.write(block)
        verify_source(path, manifest)
        receipt["sha256"] = item["sha256"]
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def stage_data(destination, source_file=None, receipt_path=None):
    manifest = read_manifest()
    destination = Path(destination).absolute()
    no_symlinks(destination)
    if destination.exists():
        verify_staged(destination)
        return {"status": "verified_existing", "destination": str(destination), "network_requests": 0}
    if receipt_path is not None:
        receipt_path = Path(receipt_path).absolute()
        no_symlinks(receipt_path)
        if receipt_path.exists() or receipt_path.is_relative_to(destination):
            raise FileExistsError("Receipt must be a new path outside runtime source")
    destination.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="." + destination.name + "-source-", dir=destination.parent))
    staged = work / "selected"
    staged.mkdir()
    receipt = dict(status="in_progress", destination=str(destination), source_manifest_sha256=MANIFEST_SHA256,
                   temporary_directory=str(work), automatic_retries=0)
    start = time.monotonic()
    try:
        target = staged / SOURCE_FILENAME
        if source_file is None:
            receipt["download"] = {}
            download_source(target, manifest, receipt["download"])
            receipt["network_requests"] = 1
        else:
            source_file = Path(source_file)
            verify_source(source_file, manifest)
            with source_file.open("rb") as source, target.open("xb") as output:
                total = 0
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    total += len(block)
                    if total > manifest["files"][0]["size_bytes"]:
                        raise ValueError("Local source changed while copying")
                    output.write(block)
            receipt.update(local_source=str(source_file), network_requests=0)
        with (staged / "source_manifest.json").open("xb") as output:
            output.write(MANIFEST_PATH.read_bytes())
        verify_staged(staged)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("Destination appeared during staging; preserve it")
        staged.rename(destination)
        work.rmdir()  # Only the new, empty private directory from this invocation.
        receipt.update(status="verified", source_sha256=manifest["files"][0]["sha256"])
        return receipt
    except BaseException as error:
        receipt.update(status="failed", error_type=type(error).__name__, error=str(error),
                       partial_artifacts_retained=True)
        raise
    finally:
        receipt["elapsed_seconds"] = time.monotonic() - start
        if receipt_path is None:
            with tempfile.NamedTemporaryFile(mode="w", prefix=destination.name + "-stage-", suffix=".json",
                                             dir=destination.parent, delete=False) as handle:
                json.dump(receipt, handle, indent=2)
        else:
            with receipt_path.open("x") as handle:
                json.dump(receipt, handle, indent=2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/source"))
    parser.add_argument("--source-file", type=Path, help="Exact verified local original NWB; no network")
    parser.add_argument("--receipt", type=Path, help="New JSON ledger path outside the runtime source directory")
    args = parser.parse_args(argv)
    print(json.dumps(stage_data(args.destination, args.source_file, args.receipt), indent=2))


if __name__ == "__main__":
    main()
