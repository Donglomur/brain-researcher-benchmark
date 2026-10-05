"""Bake the twelve pinned Sleep-EDF files into an offline task image."""
import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path


SOURCE_BASE = "https://physionet.org/files/sleep-edfx/1.0.0/sleep-cassette/"
MIRROR_BASE = "https://physionet-open.s3.amazonaws.com/sleep-edfx/1.0.0/sleep-cassette/"
SOURCE_FILES = {}
for subject, scorer in enumerate(["C", "H", "H", "C", "C", "C"]):
    SOURCE_FILES[f"SC40{subject}1E0-PSG.edf"] = (subject, "psg", 1)
    SOURCE_FILES[f"SC40{subject}1E{scorer}-Hypnogram.edf"] = (subject, "hypnogram", 1)


def verify_file(path, record):
    if path.stat().st_size != record["size_bytes"]:
        raise ValueError(f"Size mismatch: {path.name}")
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != record["sha256"]:
        raise ValueError(f"SHA256 mismatch: {path.name}")


def validate_manifest(manifest):
    records = manifest["files"]
    if len(records) != 12 or {row["path"] for row in records} != set(SOURCE_FILES):
        raise ValueError("Manifest must contain exactly the twelve allowed source EDFs")
    for row in records:
        identity = (row["subject"], row["role"], row["recording"])
        if (identity != SOURCE_FILES[row["path"]] or row["url"] != SOURCE_BASE + row["path"]
                or row["transport_url"] != MIRROR_BASE + row["path"]):
            raise ValueError(f"Source identity mismatch: {row['path']}")


def download_file(record, target, download_source="s3"):
    count = 0
    url = record["transport_url"] if download_source == "s3" else record["url"]
    with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as output:
        for block in iter(lambda: response.read(1024 * 1024), b""):
            count += len(block)
            if count > record["size_bytes"]:
                raise ValueError(f"Download exceeds pinned size: {target.name}")
            output.write(block)
    verify_file(target, record)


def stage_data(destination, manifest_path, source_dir=None, download_source="s3"):
    manifest = json.loads(manifest_path.read_text())
    validate_manifest(manifest)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sleep-edf-build-", dir=destination.parent) as temp:
        staging = Path(temp)
        for record in manifest["files"]:
            target = staging / record["path"]
            if source_dir is None:
                download_file(record, target, download_source)
            else:
                source = source_dir / record["path"]
                verify_file(source, record)
                shutil.copyfile(source, target)
                verify_file(target, record)
            print(f"Verified {record['path']}", flush=True)
        # A partial download is not exposed as a complete source bundle.
        for record in manifest["files"]:
            (staging / record["path"]).replace(destination / record["path"])
        (destination / "data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/sleep-edf"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("data_manifest.json"))
    parser.add_argument("--source-dir", type=Path, help="Optional local bundle; every source is reverified")
    parser.add_argument("--download-source", choices=["s3", "physionet"], default="s3",
                        help="Official mirror or primary host; identical published checksum verification")
    args = parser.parse_args()
    manifest = stage_data(args.destination, args.manifest, args.source_dir, args.download_source)
    print(f"Staged {len(manifest['files'])} verified EDFs in {args.destination}")


if __name__ == "__main__":
    main()
