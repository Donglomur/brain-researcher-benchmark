"""Build-time staging of the exact published Cori NWB; no runtime fetching."""
import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path


FILENAME = "sub-Cori_ses-20161214T120000.nwb"
ASSET_ID = "92694e6e-84fd-4198-a7e3-64e764f8e086"
VERSION_URL = "https://api.dandiarchive.org/api/dandisets/000017/versions/0.240329.1926/"
PIN = {
    "path": FILENAME,
    "role": "session_nwb",
    "source_path": "sub-Cori/" + FILENAME,
    "asset_id": ASSET_ID,
    "size_bytes": 311814662,
    "sha256": "d8433a826049f82cd832f41f98a9f9fafad0ac66998d4dbfd89b15b594fc4236",
    "metadata_url": VERSION_URL + "assets/" + ASSET_ID + "/",
    "download_url": "https://api.dandiarchive.org/api/assets/" + ASSET_ID + "/download/",
    "transport_url": "https://dandiarchive.s3.us-east-2.amazonaws.com/blobs/eed/3ed/eed3ed78-e076-468a-b48f-0d3f4ee0319c",
}


def validate_manifest(manifest):
    if (manifest.get("dandiset_id") != "000017"
            or manifest.get("dandiset_version") != "0.240329.1926"
            or manifest.get("doi") != "10.48324/dandi.000017/0.240329.1926"
            or manifest.get("version_metadata_url") != VERSION_URL
            or manifest.get("license") != "CC-BY-4.0"):
        raise ValueError("Manifest must identify the pinned published DANDI version and license")
    records = manifest.get("files", [])
    if len(records) != 1 or any(records[0].get(key) != value for key, value in PIN.items()):
        raise ValueError("Manifest must contain only the checksum-pinned Cori session")


def verify_file(path, record):
    if path.stat().st_size != record["size_bytes"]:
        raise ValueError(f"Size mismatch: {path.name}")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != record["sha256"]:
        raise ValueError(f"SHA256 mismatch: {path.name}")


def download_file(record, target):
    count = 0
    # The direct transport is the immutable blob URL in the published metadata;
    # no draft resolution or search for a different session occurs here.
    with urllib.request.urlopen(record["transport_url"], timeout=60) as response, target.open("wb") as output:
        for block in iter(lambda: response.read(1024 * 1024), b""):
            count += len(block)
            if count > record["size_bytes"]:
                raise ValueError("Download exceeds the pinned source size")
            output.write(block)
    verify_file(target, record)


def stage_data(destination, manifest_path, source_dir=None):
    manifest = json.loads(manifest_path.read_text())
    validate_manifest(manifest)
    record = manifest["files"][0]
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="steinmetz-source-", dir=destination.parent) as tmp:
        target = Path(tmp) / FILENAME
        if source_dir is None:
            download_file(record, target)
        else:
            source = source_dir / FILENAME
            verify_file(source, record)
            shutil.copyfile(source, target)
            verify_file(target, record)
        # Verification completes before publication. An existing valid source
        # is never overwritten by a partially downloaded or corrupted file.
        target.replace(destination / FILENAME)
        (destination / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Verified and staged {FILENAME} ({record['size_bytes']} bytes)", flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/steinmetz"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("source_manifest.json"))
    parser.add_argument("--source-dir", type=Path, help="Optional local source directory, reverified before reuse")
    args = parser.parse_args()
    stage_data(args.destination, args.manifest, args.source_dir)


if __name__ == "__main__":
    main()
