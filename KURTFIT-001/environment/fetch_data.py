"""Stage only the three pinned CFIN diffusion inputs during image build."""
import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path


PREFIX = "__DTI_AX_ep2d_2_5_iso_33d_20141015095334_4"
API = "https://digital.lib.washington.edu/server/api/core/bitstreams/"
SOURCE_FILES = {
    PREFIX + ".nii": ("image", "03594011-23b8-40b2-875e-7985945df9b5"),
    PREFIX + ".bval": ("bval", "e46f2a2f-d466-457a-894d-53a71161f48d"),
    PREFIX + ".bvec": ("bvec", "73f8406c-c175-4788-afbe-4a16b08053cf"),
}


def validate_manifest(manifest):
    records = manifest["files"]
    if len(records) != 3 or {row["path"] for row in records} != set(SOURCE_FILES):
        raise ValueError("Manifest must contain exactly the three CFIN diffusion files")
    for row in records:
        role, uuid = SOURCE_FILES[row["path"]]
        if (row["role"] != role or row["metadata_url"] != API + uuid
                or row["url"] != API + uuid + "/content"):
            raise ValueError(f"Source identity mismatch: {row['path']}")


def verify_file(path, record):
    if path.stat().st_size != record["size_bytes"]:
        raise ValueError(f"Size mismatch: {path.name}")
    digests = {name: hashlib.new(name) for name in ("md5", "sha256")}
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            for digest in digests.values():
                digest.update(block)
    for name, digest in digests.items():
        if digest.hexdigest() != record[name]:
            raise ValueError(f"{name} mismatch: {path.name}")


def download_file(record, target):
    count = 0
    with urllib.request.urlopen(record["url"], timeout=120) as response, target.open("wb") as output:
        for block in iter(lambda: response.read(1024 * 1024), b""):
            count += len(block)
            if count > record["size_bytes"]:
                raise ValueError(f"Download exceeds pinned size: {target.name}")
            output.write(block)
    verify_file(target, record)


def stage_data(destination, manifest_path, source_dir=None):
    manifest = json.loads(manifest_path.read_text())
    validate_manifest(manifest)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cfin-build-", dir=destination.parent) as temp:
        staging = Path(temp)
        for record in manifest["files"]:
            target = staging / record["path"]
            if source_dir is None:
                download_file(record, target)
            else:
                source = source_dir / record["path"]
                verify_file(source, record)
                shutil.copyfile(source, target)
                verify_file(target, record)
            print(f"Verified {record['path']}", flush=True)
        # Publish no source files until the complete bundle has passed verification.
        for record in manifest["files"]:
            (staging / record["path"]).replace(destination / record["path"])
        (destination / "data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/cfin"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("data_manifest.json"))
    parser.add_argument("--source-dir", type=Path, help="Optional local bundle, reverified before reuse")
    args = parser.parse_args()
    manifest = stage_data(args.destination, args.manifest, args.source_dir)
    print(f"Staged {len(manifest['files'])} verified CFIN diffusion inputs in {args.destination}")


if __name__ == "__main__":
    main()
