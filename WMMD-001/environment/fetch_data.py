"""Stage only checksum-pinned original CFIN inputs; no preprocessing or fitting."""
import argparse
import hashlib
import json
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path

MANIFEST_SHA256 = "9e83d360ddcdf1d76ecfae7d5bd6af906d202727d7de1ef44c200dca8f9a4cc9"
PREFIX = "__DTI_AX_ep2d_2_5_iso_33d_20141015095334_4"
API = "https://digital.lib.washington.edu/server/api/core/bitstreams/"
SOURCE_FILES = {
    PREFIX + ".nii": ("image", "03594011-23b8-40b2-875e-7985945df9b5"),
    PREFIX + ".bval": ("bval", "e46f2a2f-d466-457a-894d-53a71161f48d"),
    PREFIX + ".bvec": ("bvec", "73f8406c-c175-4788-afbe-4a16b08053cf"),
}
SOURCE_CAP_BYTES = 200_000_000


def validate_manifest(manifest):
    if (manifest.get("repository_handle") != "1773/38488"
            or manifest.get("license") != "CC0-1.0"):
        raise ValueError("Expected the pinned CFIN source identity and published license")
    records = manifest.get("files", [])
    if len(records) != 3 or {r["path"] for r in records} != set(SOURCE_FILES):
        raise ValueError("Manifest must contain exactly the three CFIN diffusion files")
    for record in records:
        role, uuid = SOURCE_FILES[record["path"]]
        if (record["role"] != role or record["metadata_url"] != API + uuid
                or record["url"] != API + uuid + "/content"):
            raise ValueError("Only the original official bitstream identity is allowed")
        if (type(record["size_bytes"]) is not int or not 0 < record["size_bytes"] < SOURCE_CAP_BYTES
                or re.fullmatch("[a-f0-9]{32}", record["md5"]) is None
                or re.fullmatch("[a-f0-9]{64}", record["sha256"]) is None):
            raise ValueError("Invalid source size, published MD5, or measured SHA256")
    if sum(record["size_bytes"] for record in records) > SOURCE_CAP_BYTES:
        raise ValueError("Source bundle exceeds the bounded acquisition contract")


def read_manifest(path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Source manifest SHA256 mismatch; do not silently refresh pins")
    manifest = json.loads(raw)
    validate_manifest(manifest)
    return manifest, raw


def verify_file(path, record):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular source file: {path.name}")
    if path.stat().st_size != record["size_bytes"]:
        raise ValueError(f"Source size mismatch: {path.name}")
    digests = {name: hashlib.new(name) for name in ("md5", "sha256")}
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            for digest in digests.values():
                digest.update(block)
    for name, digest in digests.items():
        if digest.hexdigest() != record[name]:
            raise ValueError(f"Source {name} mismatch: {path.name}")


def download_file(record, target):
    request = urllib.request.Request(record["url"], headers={"User-Agent": "wmmd-source-staging/1.0"})
    count = 0
    with urllib.request.urlopen(request, timeout=90) as response, target.open("wb") as output:
        for block in iter(lambda: response.read(65536), b""):
            count += len(block)
            if count > record["size_bytes"]:
                raise ValueError("Download exceeds pinned source size")
            output.write(block)
    verify_file(target, record)


def stage_data(destination, manifest_path, source_dir=None):
    manifest, raw_manifest = read_manifest(manifest_path)
    manifest_target = destination / "data_manifest.json"
    if manifest_target.is_symlink():
        raise ValueError("Destination manifest must not be a symbolic link")
    if manifest_target.exists() and manifest_target.read_bytes() != raw_manifest:
        raise ValueError("Existing destination manifest differs; preserve it")
    # Reject conflicting destination files before any download or publication.
    for record in manifest["files"]:
        path = destination / record["path"]
        if path.exists() or path.is_symlink():
            verify_file(path, record)
    resolved = {}
    with tempfile.TemporaryDirectory(prefix="wmmd-cfin-source-") as temporary:
        temporary = Path(temporary)
        for record in manifest["files"]:
            target = temporary / record["path"]
            existing = destination / record["path"]
            if source_dir is not None:
                source = source_dir / record["path"]
                verify_file(source, record)
                shutil.copyfile(source, target)
                verify_file(target, record)
            elif existing.exists():
                target = existing
                verify_file(target, record)
            else:
                download_file(record, target)
            resolved[record["path"]] = target
        # Publish only a complete verified input bundle. Never replace old files.
        destination.mkdir(parents=True, exist_ok=True)
        for record in manifest["files"]:
            target = destination / record["path"]
            if target.exists() or target.is_symlink():
                verify_file(target, record)
            else:
                shutil.copyfile(resolved[record["path"]], target)
                verify_file(target, record)
            target.chmod(0o444)
        if not manifest_target.exists():
            manifest_target.write_bytes(raw_manifest)
        manifest_target.chmod(0o444)
    print("Staged three verified original CFIN files; no preprocessing or fitting.", flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/cfin"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("data_manifest.json"))
    parser.add_argument("--source-dir", type=Path, help="Optional exact local raw-source bundle, fully reverified without network")
    args = parser.parse_args()
    stage_data(args.destination, args.manifest, args.source_dir)


if __name__ == "__main__":
    main()
