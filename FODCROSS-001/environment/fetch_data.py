"""Stage the three pinned Sherbrooke inputs, including corrected b-vectors, at build time."""
import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path


API = "https://digital.lib.washington.edu/server/api/core/bitstreams/"
MIRROR = "https://workshop.dipy.org/services/data/researchworks/bitstream/handle/1773/38475/"
FETCHER = "https://raw.githubusercontent.com/dipy/dipy/1.12.1/dipy/data/fetcher.py"
CORRECTION_COMMIT = "1aee6a3a2bb74bfc7c16c9421bd3d47ec9f9de76"
SOURCE_FILES = {
    "HARDI193.nii.gz": ("image", API + "28691a7c-262a-48aa-8848-5d8da0201721/content",
                        API + "28691a7c-262a-48aa-8848-5d8da0201721"),
    "HARDI193.bval": ("bval", API + "06d89887-da2e-4635-b551-407f587fd7ae/content",
                      API + "06d89887-da2e-4635-b551-407f587fd7ae"),
    "HARDI193.bvec": ("bvec", MIRROR + "HARDI193.bvec", FETCHER),
}


def validate_manifest(manifest):
    records = manifest["files"]
    if len(records) != 3 or {row["path"] for row in records} != set(SOURCE_FILES):
        raise ValueError("Manifest must contain exactly the three Sherbrooke diffusion files")
    if (manifest["source_version"] != "dipy-1.12.1-corrected-bvec"
            or manifest["bvec_correction"]["commit"] != CORRECTION_COMMIT):
        raise ValueError("Manifest must identify the upstream corrected b-vector version")
    for row in records:
        role, url, metadata_url = SOURCE_FILES[row["path"]]
        if row["role"] != role or row["url"] != url or row["metadata_url"] != metadata_url:
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
    with tempfile.TemporaryDirectory(prefix="sherbrooke-build-", dir=destination.parent) as temp:
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
        # No source member is published until the complete bundle is verified.
        for record in manifest["files"]:
            (staging / record["path"]).replace(destination / record["path"])
        (destination / "data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/sherbrooke"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("data_manifest.json"))
    parser.add_argument("--source-dir", type=Path, help="Optional local bundle, reverified before reuse")
    args = parser.parse_args()
    manifest = stage_data(args.destination, args.manifest, args.source_dir)
    print(f"Staged {len(manifest['files'])} verified Sherbrooke inputs in {args.destination}")


if __name__ == "__main__":
    main()
