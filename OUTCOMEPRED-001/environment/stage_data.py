"""Stage exactly one published IBL session; no scientific processing or runtime fetch."""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
import urllib.request

MANIFEST_PATH = Path(__file__).with_name("source_manifest.json")
MANIFEST_SHA256 = "d87c000f92d2aa54b4eaa0de50d5ffd7ab3035141d1fccd45b4e674d1c56d63d"
BLOB_URL = "https://dandiarchive.s3.us-east-2.amazonaws.com/blobs/d4c/d64/d4cd649e-9876-4853-8ecc-13fbfcea5eca"
VERSION_ID = "__znurCQe6dlYB_aln02wTisn1X_0ee7"
SOURCE_URL = BLOB_URL + "?versionId=" + VERSION_ID
CAP_BYTES = 400_000_000
TIMEOUT_SECONDS = 600
SAFE_HEADERS = {"content-length", "content-type", "content-encoding", "etag", "last-modified", "date", "x-amz-version-id"}


def reject_symlinks(path):
    path = Path(path).absolute()
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError("Source paths and their ancestors must not be symlinks")


def read_manifest(path=MANIFEST_PATH):
    path = Path(path)
    reject_symlinks(path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Whole source manifest SHA-256 mismatch")
    manifest = json.loads(raw)
    if (manifest.get("task_id") != "OUTCOMEPRED-001"
            or manifest.get("dandiset_id") != "000409"
            or manifest.get("dandiset_version") != "0.260309.1324"
            or manifest.get("license") != "CC-BY-4.0"
            or manifest.get("access") != "OpenAccess"):
        raise ValueError("Unexpected original release or source license")
    files = manifest.get("files", [])
    if len(files) != 1:
        raise ValueError("Only the one declared original session may be staged")
    record = files[0]
    if (record.get("path") != "session.nwb" or record.get("role") != "session_nwb"
            or record.get("asset_id") != "73c3cf70-88a0-43ae-b7fd-03a0ac156222"
            or record.get("blob_url") != BLOB_URL or record.get("transport_url") != SOURCE_URL
            or record.get("s3_version_id") != VERSION_ID
            or type(record.get("size_bytes")) is not int or not 0 < record["size_bytes"] <= CAP_BYTES):
        raise ValueError("Unexpected source path, immutable object identity, or size")
    return manifest, raw


def verify_file(path, record):
    path = Path(path)
    reject_symlinks(path)
    if not path.is_file() or path.stat().st_size != record["size_bytes"]:
        raise ValueError("Original file missing or size differs from published metadata")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    if digest.hexdigest() != record["sha256"]:
        raise ValueError("Original file SHA-256 differs from the published digest")


def verify_staged(data_dir):
    data_dir = Path(data_dir)
    reject_symlinks(data_dir)
    if not data_dir.is_dir():
        raise ValueError("Staged source directory is absent")
    members = list(data_dir.iterdir())
    if {p.name for p in members} != {"session.nwb", "source_manifest.json"}:
        raise ValueError("Staged source inventory must be exactly NWB plus original manifest")
    if any(p.is_symlink() or not p.is_file() for p in members):
        raise ValueError("Only regular, non-symlink source files are permitted")
    manifest, _ = read_manifest(data_dir / "source_manifest.json")
    verify_file(data_dir / "session.nwb", manifest["files"][0])
    return manifest


def write_new_json(path, value):
    reject_symlinks(path)
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


@contextlib.contextmanager
def deadline(seconds):
    def expire(*unused):
        raise TimeoutError("Source transfer exceeded its declared wall limit")
    old_handler = signal.signal(signal.SIGALRM, expire)
    old_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *old_timer)
        signal.signal(signal.SIGALRM, old_handler)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("No redirect or alternate object is authorized")


def download_file(record, ledger):
    ledger = Path(ledger)
    reject_symlinks(ledger)
    ledger.mkdir(parents=True, exist_ok=False)
    attempt = dict(status="started", source_url=record["transport_url"],
                   started_at_utc=datetime.now(timezone.utc).isoformat(),
                   expected_size_bytes=record["size_bytes"], expected_sha256=record["sha256"],
                   maximum_transferred_bytes=CAP_BYTES, timeout_seconds=TIMEOUT_SECONDS,
                   automatic_retries=0, range_requests=False)
    write_new_json(ledger / "attempt.json", attempt)
    partial = ledger / "session.nwb.partial"
    transferred = 0
    started = time.monotonic()
    headers = {}
    digest = hashlib.sha256()
    print(f"Source download start: session.nwb, expected {record['size_bytes']} bytes, one attempt", flush=True)
    try:
        if record["transport_url"] != SOURCE_URL or record["size_bytes"] > CAP_BYTES:
            raise ValueError("Unexpected source identity or transfer budget")
        request = urllib.request.Request(SOURCE_URL, headers={
            "User-Agent": "outcomepred-source-staging/1.0", "Accept-Encoding": "identity",
            "If-Match": '"' + record["dandi_etag"] + '"'})
        opener = urllib.request.build_opener(NoRedirect())
        with deadline(TIMEOUT_SECONDS), opener.open(request, timeout=60) as response:
            headers = {k: v for k, v in response.headers.items() if k.lower() in SAFE_HEADERS}
            if (response.status != 200 or response.geturl() != SOURCE_URL
                    or int(response.headers.get("Content-Length", "-1")) != record["size_bytes"]
                    or response.headers.get("ETag", "").strip('"') != record["dandi_etag"]
                    or response.headers.get("x-amz-version-id") != VERSION_ID
                    or response.headers.get("Content-Encoding", "identity") != "identity"):
                raise ValueError("Source HTTP status/length/ETag/version/encoding/URL mismatch")
            with partial.open("xb") as stream:
                while True:
                    block = response.read(min(1 << 20, record["size_bytes"] + 1 - transferred))
                    if not block:
                        break
                    transferred += len(block)
                    if transferred > min(record["size_bytes"], CAP_BYTES):
                        raise ValueError("Source transfer exceeded pinned size or cumulative budget")
                    digest.update(block)
                    stream.write(block)
            if transferred != record["size_bytes"] or digest.hexdigest() != record["sha256"]:
                raise ValueError("Downloaded byte count or SHA-256 mismatch")
        original = ledger / "session.nwb"
        if original.exists():
            raise FileExistsError("Preserve existing original source")
        partial.rename(original)
        original.chmod(0o444)
        result = dict(attempt, status="sha256_verified", transferred_bytes=transferred,
                      measured_sha256=digest.hexdigest(), response_headers=headers,
                      elapsed_seconds=time.monotonic()-started)
        write_new_json(ledger / "result.json", result)
        print(f"Source download complete: session.nwb, {transferred} bytes, published SHA-256 verified", flush=True)
        return original
    except BaseException as error:
        write_new_json(ledger / "result.json", dict(attempt, status="failed",
                       transferred_bytes=transferred, response_headers=headers,
                       elapsed_seconds=time.monotonic()-started, error_type=type(error).__name__,
                       error=str(error), partial_payload=str(partial)))
        print(f"Source download failed: session.nwb, {transferred} bytes, {type(error).__name__}: {error}", flush=True)
        raise


def stage_data(destination, source_file=None, ledger=None, manifest_path=MANIFEST_PATH):
    destination = Path(destination)
    reject_symlinks(destination)
    manifest, raw_manifest = read_manifest(manifest_path)
    record = manifest["files"][0]
    if destination.exists():
        verified = verify_staged(destination)
        print("Verified existing source; no files changed and no network request", flush=True)
        return verified
    if source_file is not None:
        source = Path(source_file)
        verify_file(source, record)
    else:
        ledger = Path(ledger) if ledger is not None else destination.parent / (destination.name + "-source-download")
        if ledger.absolute() == destination.absolute() or destination.absolute() in ledger.absolute().parents:
            raise ValueError("Download evidence must be outside runtime source directory")
        source = download_file(record, ledger)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="." + destination.name + "-staging-", dir=destination.parent))
    temporary.chmod(0o755)
    # Preserve incomplete owned staging evidence on failure; never overwrite a destination.
    target = temporary / "session.nwb"
    if source_file is None:
        os.link(source, target)
    else:
        with source.open("rb") as src, target.open("xb") as dst:
            shutil.copyfileobj(src, dst, length=1 << 20)
    target.chmod(0o444)
    with (temporary / "source_manifest.json").open("xb") as stream:
        stream.write(raw_manifest)
    (temporary / "source_manifest.json").chmod(0o444)
    verify_staged(temporary)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Destination appeared during staging; preserve both paths")
    temporary.rename(destination)
    print("Staged exactly one verified original session plus manifest; no scientific processing", flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/outcomepred"))
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--source-file", type=Path, help="Optional verified original NWB for offline reuse")
    parser.add_argument("--ledger", type=Path, help="New, owned single-download evidence directory")
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing:
        verify_staged(args.destination)
        print("Offline original source verification passed", flush=True)
    else:
        stage_data(args.destination, args.source_file, args.ledger, args.manifest)


if __name__ == "__main__":
    main()
