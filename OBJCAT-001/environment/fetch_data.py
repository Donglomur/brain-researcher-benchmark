"""Build-time staging of exactly Haxby subject 2 BOLD/labels and one mask.

No runtime fetching, preprocessing or scientific analysis. The versioned archive
is authenticated before allowlisted member extraction. Conflicting existing
files, symlinks and prior transfer attempts are preserved and cause failure.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import signal
import tarfile
import time
import urllib.request


MANIFEST_SHA256 = "702e97410687dea0193f5d300d988e86c02a1c14cd1fac3016f7a6f7d865cb3a"
SOURCE_BASE = "http://data.pymvpa.org/datasets/haxby2001/"
ARCHIVE_NAME = "subj2-2010.01.14.tar.gz"
MASK_URL = "https://www.nitrc.org/frs/download.php/7868/mask.nii.gz"
ARCHIVE_MD5 = "56902b0583c0329b8364cadc1abb3ed5"
FILES = {"subj2/bold.nii.gz": "bold", "subj2/labels.txt": "labels", "mask.nii.gz": "mask"}
CAP_BYTES = 300_000_000
TIMEOUT_SECONDS = 600


def reject_symlinks(path):
    path = Path(path).absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Symlink in source staging path; preserve it unchanged")


def validate_manifest(manifest):
    if manifest.get("task_id") != "OBJCAT-001" or manifest.get("dataset_id") != "haxby2001" or manifest.get("subject") != 2:
        raise ValueError("Expected Haxby subject 2 source identity")
    if manifest.get("dataset_license") != "CC-BY-SA-3.0" or manifest.get("mask_license") != "not-established":
        raise ValueError("Dataset and separately hosted mask license scopes must remain separate")
    records = manifest.get("files", [])
    if len(records) != 3 or {item.get("path"): item.get("role") for item in records} != FILES:
        raise ValueError("Expected exactly the three source paths and roles")
    archive, registry = manifest["archive"], manifest["published_checksums"]
    if (archive["url"], archive["path"], archive["size_bytes"], archive["md5"]) != (
            SOURCE_BASE + ARCHIVE_NAME, ARCHIVE_NAME, 291168628, ARCHIVE_MD5):
        raise ValueError("Expected exact versioned archive and published MD5")
    if (registry["url"], registry["path"], registry["size_bytes"]) != (SOURCE_BASE + "MD5SUMS", "MD5SUMS", 408):
        raise ValueError("Expected original published checksum registry")
    mask = next(item for item in records if item["role"] == "mask")
    if mask.get("url") != MASK_URL or mask["size_bytes"] != 2969:
        raise ValueError("Unexpected separately hosted whole-brain mask")
    for item in (*records, archive, registry):
        if type(item.get("size_bytes")) is not int or not 0 < item["size_bytes"] <= CAP_BYTES:
            raise ValueError("Invalid pinned size")
        sha = item.get("sha256", "")
        if len(sha) != 64 or any(char not in "0123456789abcdef" for char in sha):
            raise ValueError("Expected a literal SHA256 pin")
    for item in records:
        if item["role"] != "mask" and item.get("archive_member") != item["path"]:
            raise ValueError("Archive member must match its fixed relative source path")
    if sum(item["size_bytes"] for item in (archive, registry, mask)) > CAP_BYTES:
        raise ValueError("Manifest exceeds total source transfer budget")


def read_manifest(path):
    path = Path(path)
    reject_symlinks(path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Full immutable data_manifest.json SHA256 mismatch")
    manifest = json.loads(raw)
    validate_manifest(manifest)
    return manifest, raw


def verify_file(path, record):
    path = Path(path)
    reject_symlinks(path)
    if not path.is_file() or path.stat().st_size != record["size_bytes"]:
        raise ValueError(f"Pinned source file size/type mismatch: {path}")
    if "sha256" not in record: raise ValueError("Source verification requires SHA256")
    algorithms = {key: hashlib.new(key) for key in ("sha256", "md5") if key in record}
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            for algorithm in algorithms.values(): algorithm.update(block)
    if any(algorithm.hexdigest() != record[key] for key, algorithm in algorithms.items()):
        raise ValueError(f"Source digest mismatch: {path}")


def verify_registry(path):
    lines = [line.split() for line in Path(path).read_text().splitlines()]
    matches = [value for value, name in lines if name.lstrip("*") == ARCHIVE_NAME]
    if matches != [ARCHIVE_MD5]:
        raise ValueError("Independently published subject-2 MD5 missing or changed")


@contextlib.contextmanager
def deadline(seconds):
    def expired(*unused): raise TimeoutError("Source staging exceeded the transfer wall-clock limit")
    old_handler = signal.signal(signal.SIGALRM, expired)
    old_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try: yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *old_timer)
        signal.signal(signal.SIGALRM, old_handler)


def write_new_json(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def download_sources(records, ledger):
    """One serial request per required source, shared deadline/budget; no retries."""
    ledger = Path(ledger)
    reject_symlinks(ledger)
    ledger.mkdir(parents=True, exist_ok=False)
    start, total, completed, active = time.monotonic(), 0, {}, None
    write_new_json(ledger / "attempt.json", {"started_utc": datetime.now(timezone.utc).isoformat(),
                   "records": records, "maximum_transferred_bytes": CAP_BYTES,
                   "timeout_seconds": TIMEOUT_SECONDS, "automatic_retries": False, "range_requests": False})
    try:
        with deadline(TIMEOUT_SECONDS):
            for index, record in enumerate(records):
                active = {"url": record["url"], "size_bytes": record["size_bytes"], "received_bytes": 0}
                request = urllib.request.Request(record["url"], headers={"User-Agent": "objcat-source-staging/1.0", "Accept-Encoding": "identity"})
                target = ledger / f"payload-{index}.partial"
                with urllib.request.urlopen(request, timeout=60) as response:
                    active.update(final_url=response.geturl(), status=response.status, response_headers=dict(response.headers.items()))
                    if response.status != 200 or response.geturl() != record["url"]:
                        raise ValueError("Unexpected source HTTP status or redirect")
                    if int(response.headers.get("Content-Length", -1)) != record["size_bytes"] or response.headers.get("Content-Encoding", "identity") != "identity":
                        raise ValueError("Unexpected HTTP source length or encoding")
                    with target.open("xb") as stream:
                        while True:
                            block = response.read(min(1024 * 1024, record["size_bytes"] + 1 - active["received_bytes"]))
                            if not block: break
                            total += len(block)
                            active["received_bytes"] += len(block)
                            if total > CAP_BYTES or active["received_bytes"] > record["size_bytes"]:
                                raise ValueError("Pinned source size/cumulative transfer budget exceeded")
                            stream.write(block)
                verify_file(target, record)
                if record["path"] == "MD5SUMS": verify_registry(target)
                target.chmod(0o444)
                completed[record["path"]] = target
                write_new_json(ledger / f"payload-{index}.receipt.json", dict(active, sha256=record["sha256"], status="verified"))
        write_new_json(ledger / "result.json", {"status": "verified", "transferred_bytes": total,
                       "elapsed_seconds": time.monotonic() - start, "paths": {key: str(value) for key, value in completed.items()}})
    except BaseException as error:
        write_new_json(ledger / "result.json", {"status": "failed", "transferred_bytes": total,
                       "elapsed_seconds": time.monotonic() - start, "active_source": active,
                       "error": f"{type(error).__name__}: {error}", "automatic_retry_allowed": False})
        raise
    return completed


def extract_allowlisted(archive_path, records, destination):
    """Write only literal manifest members; never tar.extract/extractall."""
    destination = Path(destination)
    reject_symlinks(destination)
    required = {record["archive_member"]: record for record in records}
    if (len(required) != len(records) or not required or not set(required) <= {"subj2/bold.nii.gz", "subj2/labels.txt"}
            or any(record["path"] != name for name, record in required.items())):
        raise ValueError("Extraction records must be unique literal allowlisted source members")
    seen, found, unpacked = set(), {}, 0
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive:
            name = member.name
            if (not name or name.startswith("/") or ".." in PurePosixPath(name).parts or "\\" in name
                    or not (member.isfile() or member.isdir()) or member.size < 0):
                raise ValueError("Unsafe tar member path/type")
            if name in seen: raise ValueError("Duplicate tar member")
            seen.add(name)
            unpacked += member.size
            if len(seen) > 64 or unpacked > CAP_BYTES:
                raise ValueError("Unexpected archive expansion")
            if name not in required: continue
            record = required[name]
            if not member.isfile() or member.size != record["size_bytes"]:
                raise ValueError("Allowlisted member size/type mismatch")
            target = destination / record["path"]
            reject_symlinks(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open("xb") as output:
                remaining = member.size
                while remaining:
                    block = source.read(min(1024 * 1024, remaining))
                    if not block: raise ValueError("Truncated tar member")
                    output.write(block); remaining -= len(block)
                if source.read(1): raise ValueError("Excess tar member bytes")
            verify_file(target, record)
            target.chmod(0o444)
            found[name] = target
    if set(found) != set(required): raise ValueError("Missing allowlisted tar member")
    return found


def stage_data(destination, manifest_path, source_dir=None, ledger=None):
    destination = Path(destination)
    manifest, raw = read_manifest(manifest_path)
    records = manifest["files"]
    reject_symlinks(destination)
    metadata = destination / "data_manifest.json"
    reject_symlinks(metadata)
    if metadata.exists() and metadata.read_bytes() != raw:
        raise ValueError("Preserve conflicting destination manifest")
    # Verify every preexisting target before network or any input publication.
    missing = []
    for record in records:
        target = destination / record["path"]
        reject_symlinks(target)
        if target.exists(): verify_file(target, record)
        else: missing.append(record)
    sources = {}
    if source_dir is not None:
        source_dir = Path(source_dir)
        for record in records:
            source = source_dir / record["path"]
            verify_file(source, record)
            sources[record["path"]] = source
    elif missing:
        ledger = Path(ledger) if ledger is not None else destination.parent / "objcat_source_download"
        archive_records = [record for record in missing if record["role"] != "mask"]
        needed = [manifest["published_checksums"], manifest["archive"]] if archive_records else []
        needed.extend(record for record in missing if record["role"] == "mask")
        downloaded = download_sources(needed, ledger)
        if archive_records:
            verify_file(downloaded[ARCHIVE_NAME], manifest["archive"])
            sources.update(extract_allowlisted(downloaded[ARCHIVE_NAME], archive_records, ledger / "members"))
        if "mask.nii.gz" in downloaded: sources["mask.nii.gz"] = downloaded["mask.nii.gz"]
    destination.mkdir(parents=True, exist_ok=True)
    for record in missing:
        source = sources[record["path"]]
        target = destination / record["path"]
        reject_symlinks(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive copy avoids clobbering concurrent or previously unverified files.
        with source.open("rb") as src, target.open("xb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
        verify_file(target, record)
        target.chmod(0o444)
    if metadata.exists():
        if metadata.read_bytes() != raw: raise ValueError("Preserve destination manifest race")
    else:
        with metadata.open("xb") as stream: stream.write(raw)
        metadata.chmod(0o444)
    print("Staged exactly three source files; no preprocessing or scientific analysis.", flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/objcat"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("data_manifest.json"))
    parser.add_argument("--source-dir", type=Path, help="Exact verified local source files; offline reuse")
    parser.add_argument("--ledger", type=Path, help="Fresh owned directory for one transfer attempt")
    args = parser.parse_args()
    stage_data(args.destination, args.manifest, args.source_dir, args.ledger)


if __name__ == "__main__": main()
