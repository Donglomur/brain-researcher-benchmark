"""Stage 30 original EEGBCI EDFs at build time; no EEG preprocessing or fitting."""
import argparse
import datetime
import hashlib
import json
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path

MANIFEST_SHA256 = "939a5725a743d3162f24ac1d10c6088888991559c4a07207ee935a4061fc88c7"
BASE = "https://physionet.org/files/eegmmidb/1.0.0/"
TRANSPORT_BASE = "https://physionet-open.s3.amazonaws.com/eegmmidb/1.0.0/"
SOURCE_CAP_BYTES = 100_000_000
SOURCE_FILES = {
    f"S{subject:03d}/S{subject:03d}R{run:02d}.edf": (subject, run)
    for subject in range(1, 11) for run in (6, 10, 14)
}


def reject_symlinks(path):
    """Reject existing symlinks anywhere in an input or publication path."""
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError(f"Symbolic links are not accepted: {component}")


def validate_manifest(manifest):
    if (manifest.get("dataset_id") != "eegmmidb" or manifest.get("version") != "1.0.0"
            or manifest.get("license") != "ODC-By-1.0"):
        raise ValueError("Expected the pinned EEGBCI version and published dataset license")
    registry = manifest.get("checksum_registry", {})
    if manifest.get("transport", {}).get("base_url") != TRANSPORT_BASE:
        raise ValueError("Only the documented official versioned public mirror is allowed")
    if (registry.get("url") != BASE + "SHA256SUMS.txt"
            or registry.get("sha256") != "7f5d16957d8ee7bce86cc7ccba0e5994f63f33781607eb3f838392d49311a208"
            or registry.get("size_bytes") != 259919):
        raise ValueError("Expected the independently captured official checksum registry")
    records = manifest.get("files", [])
    if len(records) != 30 or {r["path"] for r in records} != set(SOURCE_FILES):
        raise ValueError("Manifest must contain exactly subjects 1-10 and runs 6,10,14")
    for record in records:
        subject, run = SOURCE_FILES[record["path"]]
        if (type(record["subject"]) is not int or type(record["run"]) is not int
                or (record["subject"], record["run"]) != (subject, run)
                or record["role"] != "eeg_edf" or record["url"] != BASE + record["path"]
                or record["transport_url"] != TRANSPORT_BASE + record["path"]):
            raise ValueError("Only the exact official EDF identity is allowed")
        if (type(record["size_bytes"]) is not int or not 0 < record["size_bytes"] < SOURCE_CAP_BYTES
                or re.fullmatch("[a-f0-9]{64}", record["sha256"]) is None):
            raise ValueError("Invalid source size or published SHA256")
    total = sum(record["size_bytes"] for record in records)
    if total > SOURCE_CAP_BYTES or manifest.get("total_size_bytes") != total:
        raise ValueError("Source bundle size differs from the bounded acquisition contract")


def read_manifest(path):
    reject_symlinks(path)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Source manifest SHA256 mismatch; do not silently refresh pins")
    manifest = json.loads(raw)
    validate_manifest(manifest)
    return manifest, raw


def verify_file(path, record):
    reject_symlinks(path)
    if not path.is_file() or path.stat().st_size != record["size_bytes"]:
        raise ValueError(f"Expected a regular source file with pinned size: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != record["sha256"]:
        raise ValueError(f"Source SHA256 mismatch: {path}")


def download_file(record, target):
    request = urllib.request.Request(record["transport_url"], headers={"User-Agent": "brbench-eegbci-source-staging/1.0"})
    count = 0
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with urllib.request.urlopen(request, timeout=90) as response, target.open("xb") as output:
        if response.status != 200 or response.url != record["transport_url"]:
            raise ValueError("Expected an unchanged official versioned source URL and HTTP 200")
        for block in iter(lambda: response.read(65536), b""):
            count += len(block)
            if count > record["size_bytes"]:
                raise ValueError("Download exceeds pinned source size")
            output.write(block)
        receipt = {"url": response.url, "status": response.status, "headers": dict(response.headers),
                   "started_at_utc": started, "completed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    verify_file(target, record)
    return receipt


def stage_data(destination, manifest_path, source_dir=None, receipt_path=None):
    manifest, raw_manifest = read_manifest(manifest_path)
    reject_symlinks(destination)
    if destination.exists() and not destination.is_dir():
        raise ValueError("The destination must be a directory")
    for parent in destination.parents:
        if parent.exists() and not parent.is_dir():
            raise ValueError("The destination cannot descend from an existing regular file")
    if source_dir is not None:
        reject_symlinks(source_dir)
    if receipt_path is not None:
        reject_symlinks(receipt_path)
        if receipt_path.exists():
            raise ValueError("Preserve the existing staging receipt")
    manifest_target = destination / "data_manifest.json"
    reject_symlinks(manifest_target)
    if manifest_target.exists() and (not manifest_target.is_file() or manifest_target.read_bytes() != raw_manifest):
        raise ValueError("Existing destination manifest differs; preserve it")
    # Fail before any acquisition if the destination contains conflicting data.
    for record in manifest["files"]:
        path = destination / record["path"]
        reject_symlinks(path)
        if path.exists():
            verify_file(path, record)
    resolved = {}
    receipts = []
    with tempfile.TemporaryDirectory(prefix="motorimagery-eegbci-source-") as temporary:
        temporary = Path(temporary)
        for record in manifest["files"]:
            target = temporary / record["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            existing = destination / record["path"]
            receipt = {"path": record["path"], "size_bytes": record["size_bytes"], "sha256": record["sha256"]}
            if source_dir is not None:
                source = source_dir / record["path"]
                verify_file(source, record)
                shutil.copyfile(source, target)
                verify_file(target, record)
                receipt["acquisition"] = "reverified_local_original"
            elif existing.exists():
                target = existing
                verify_file(target, record)
                receipt["acquisition"] = "reverified_existing_destination"
            else:
                receipt["acquisition"] = "official_versioned_download"
                receipt["http"] = download_file(record, target)
            resolved[record["path"]] = target
            receipts.append(receipt)
            print(f"Verified {record['path']}", flush=True)
        # Publish only after the complete input bundle has been verified.
        destination.mkdir(parents=True, exist_ok=True)
        for record in manifest["files"]:
            target = destination / record["path"]
            reject_symlinks(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                verify_file(target, record)
            else:
                with resolved[record["path"]].open("rb") as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                verify_file(target, record)
                target.chmod(0o444)
        reject_symlinks(manifest_target)
        if manifest_target.exists() and (not manifest_target.is_file() or manifest_target.read_bytes() != raw_manifest):
            raise ValueError("Destination manifest changed during staging; preserve it")
        if not manifest_target.exists():
            with manifest_target.open("xb") as output:
                output.write(raw_manifest)
            manifest_target.chmod(0o444)
    if receipt_path is not None:
        with receipt_path.open("x") as output:
            json.dump({"manifest_sha256": MANIFEST_SHA256, "files": receipts,
                       "total_size_bytes": manifest["total_size_bytes"], "preprocessing_performed": False}, output, indent=2)
            output.write("\n")
    print("Staged 30 verified original EDF files; no preprocessing or fitting.", flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/eegbci"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("data_manifest.json"))
    parser.add_argument("--source-dir", type=Path, help="Optional exact local raw-source bundle, fully reverified without network")
    parser.add_argument("--receipt", type=Path, help="Optional new local source-verification receipt")
    args = parser.parse_args()
    stage_data(args.destination, args.manifest, args.source_dir, args.receipt)


if __name__ == "__main__":
    main()
