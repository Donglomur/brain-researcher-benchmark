"""Stage one immutable DANDI NWB; bounded transfer, no scientific processing."""
import argparse
import contextlib
import hashlib
import json
import os
import shutil
import signal
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_SHA256 = "0997a4b254812d6967c87444809039197a4864d98838c4f6432d05cdfccd6534"
FILENAME = "sub-707296975_ses-721123822.nwb"
ASSET = "224b57e5-c9a3-46ef-85db-966713f3ccbe"
VERSION_URL = "https://api.dandiarchive.org/api/dandisets/000021/versions/0.251116.2246/"
BLOB = "https://dandiarchive.s3.us-east-2.amazonaws.com/blobs/9f2/c60/9f2c6063-0bcf-4c5e-9039-c6d7144bcbe1"
VERSION_ID = "ICyOFm4ZxqGhChutSRrXWK3gMf1PQ4WF"
ETAG = "4ef35488b5b0e2b790a5aa11055f6ba3-26"
PIN = {"path": FILENAME, "role": "session_nwb", "source_path": "sub-707296975/"+FILENAME,
       "asset_id": ASSET, "subject_id": "707296975", "session_id": "721123822",
       "size_bytes": 1736516600, "sha256": "4e284295a1be5c6cca49df84fab52ad38b4749d2361b2edebeb676051cf09921",
       "dandi_etag": ETAG, "metadata_url": VERSION_URL+"assets/"+ASSET+"/",
       "download_url": "https://api.dandiarchive.org/api/assets/"+ASSET+"/download/",
       "blob_url": BLOB, "s3_version_id": VERSION_ID, "transport_url": BLOB+"?versionId="+VERSION_ID}
CAP_BYTES = 1_800_000_000
TIMEOUT_SECONDS = 600


def reject_symlinks(path):
    for item in (path.absolute(), *path.absolute().parents):
        if item.is_symlink():
            raise ValueError("Symlinks are not permitted in source staging paths")


def validate_manifest(manifest):
    expected = {"task_id": "ALLENOSI-001", "dandiset_id": "000021", "dandiset_version": "0.251116.2246",
                "doi": "10.48324/dandi.000021/0.251116.2246", "version_metadata_url": VERSION_URL,
                "license": "CC-BY-4.0", "additional_terms_url": "https://alleninstitute.org/legal/terms-of-use"}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError("Expected the pinned DANDI release and both source license notices")
    files = manifest.get("files", [])
    if len(files) != 1 or any(files[0].get(key) != value for key, value in PIN.items()):
        raise ValueError("Expected only the pinned original session NWB")
    if type(files[0]["size_bytes"]) is not int or not 0 < files[0]["size_bytes"] <= CAP_BYTES:
        raise ValueError("Invalid source size")


def read_manifest(path):
    reject_symlinks(path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Full source manifest SHA256 mismatch")
    manifest = json.loads(raw)
    validate_manifest(manifest)
    return manifest, raw


def verify_file(path, record):
    reject_symlinks(path)
    if not path.is_file() or path.stat().st_size != record["size_bytes"]:
        raise ValueError("Expected regular source file with pinned size")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    if digest.hexdigest() != record["sha256"]:
        raise ValueError("Source SHA256 mismatch")


@contextlib.contextmanager
def deadline(seconds):
    def expired(*unused):
        raise TimeoutError("Source download exceeded the declared wall-clock limit")
    old_handler = signal.signal(signal.SIGALRM, expired)
    old_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *old_timer)
        signal.signal(signal.SIGALRM, old_handler)


def write_new_json(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def download_file(record, ledger):
    reject_symlinks(ledger)
    # An existing attempt is preserved and blocks another full transfer, even if incomplete.
    ledger.mkdir(parents=True, exist_ok=False)
    attempt = {"status": "started", "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "url": record["transport_url"], "expected_size_bytes": record["size_bytes"],
               "maximum_transferred_bytes": CAP_BYTES, "timeout_seconds": TIMEOUT_SECONDS,
               "automatic_retries": False, "range_requests": False}
    write_new_json(ledger/"attempt.json", attempt)
    target = ledger/"payload.partial"
    transferred = 0
    start = time.monotonic()
    response_headers = {}
    request = urllib.request.Request(record["transport_url"], headers={
        "User-Agent": "allenosi-source-staging/1.0", "Accept-Encoding": "identity", "If-Match": '"'+record["dandi_etag"]+'"'})
    try:
        with deadline(TIMEOUT_SECONDS), urllib.request.urlopen(request, timeout=60) as response:
            response_headers = dict(response.headers.items())
            if (response.status != 200 or response.geturl() != record["transport_url"]
                    or int(response.headers.get("Content-Length", -1)) != record["size_bytes"]
                    or response.headers.get("ETag", "").strip('"') != record["dandi_etag"]
                    or response.headers.get("x-amz-version-id") != record["s3_version_id"]
                    or response.headers.get("Content-Encoding", "identity") != "identity"):
                raise ValueError("HTTP status, size, object version, ETag, encoding, or transport mismatch")
            with target.open("xb") as stream:
                while True:
                    block = response.read(min(1024*1024, record["size_bytes"]+1-transferred))
                    if not block:
                        break
                    transferred += len(block)
                    if transferred > min(record["size_bytes"], CAP_BYTES):
                        raise ValueError("Transfer exceeds pinned size or cumulative source budget")
                    stream.write(block)
        verify_file(target, record)
    except BaseException as exc:
        write_new_json(ledger/"result.json", dict(attempt, status="failed", transferred_bytes=transferred,
                       elapsed_seconds=time.monotonic()-start, response_headers=response_headers,
                       error=f"{type(exc).__name__}: {exc}", partial_payload=str(target)))
        raise
    write_new_json(ledger/"result.json", dict(attempt, status="sha256_verified", transferred_bytes=transferred,
                   sha256=record["sha256"], elapsed_seconds=time.monotonic()-start, response_headers=response_headers))
    return target


def stage_data(destination, manifest_path, source_dir=None, ledger=None):
    manifest, raw_manifest = read_manifest(manifest_path)
    record = manifest["files"][0]
    reject_symlinks(destination)
    target, metadata = destination/FILENAME, destination/"data_manifest.json"
    reject_symlinks(target); reject_symlinks(metadata)
    if metadata.exists() and metadata.read_bytes() != raw_manifest:
        raise ValueError("Preserve conflicting destination manifest")
    if target.exists():
        verify_file(target, record)
    if source_dir is not None:
        source = source_dir/FILENAME
        verify_file(source, record)
    elif target.exists():
        source = target
    else:
        source = download_file(record, ledger or destination.parent/"source_download")
    destination.mkdir(parents=True, exist_ok=True)
    if target.exists():
        verify_file(target, record)
    else:
        if source_dir is None:
            # The completed attempt and destination are on the same owned filesystem.
            # An exclusive hard link preserves acquisition evidence without a second GB copy.
            os.link(source, target)
        else:
            with source.open("rb") as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst, length=1024*1024)
        verify_file(target, record)
    target.chmod(0o444)
    if metadata.exists():
        if metadata.read_bytes() != raw_manifest:
            raise ValueError("Preserve conflicting destination manifest")
    else:
        with metadata.open("xb") as stream:
            stream.write(raw_manifest)
    metadata.chmod(0o444)
    print(f"Staged one SHA256-verified original NWB ({record['size_bytes']} bytes); no scientific processing.", flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/allenosi"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("data_manifest.json"))
    parser.add_argument("--source-dir", type=Path, help="Optional exact local original NWB, reverified offline")
    parser.add_argument("--ledger", type=Path, help="Owned single-attempt download evidence directory")
    args = parser.parse_args()
    stage_data(args.destination, args.manifest, args.source_dir, args.ledger)


if __name__ == "__main__":
    main()
