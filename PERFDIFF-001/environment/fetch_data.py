"""Stage the three checksum-pinned IVIM observations at Docker build time only."""
import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


METADATA = "https://api.figshare.com/v2/articles/3395704/versions/1"
ORIGINAL = "https://ndownloader.figshare.com/files/"
MIRROR = "https://workshop.dipy.org/services/data/files/"
SOURCE_FILES = {
    "IVIM.nii.gz": ("image", 5305243),
    "IVIM.bvals": ("bval", 5305246),
    "IVIM.bvecs": ("bvec", 5305249),
}


def validate_manifest(manifest):
    records = manifest["files"]
    if len(records) != 3 or {row["path"] for row in records} != set(SOURCE_FILES):
        raise ValueError("Manifest must contain exactly the three original IVIM observation files")
    if (manifest["source_version"] != "figshare-3395704-v1"
            or manifest["doi"] != "10.6084/m9.figshare.3395704.v1"):
        raise ValueError("Manifest must identify the pinned Figshare version")
    for row in records:
        role, file_id = SOURCE_FILES[row["path"]]
        if (row["role"] != role or row["file_id"] != file_id
                or row["url"] != ORIGINAL + str(file_id)
                or row["mirror_url"] != MIRROR + str(file_id)
                or row["metadata_url"] != METADATA):
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
    """Use only the original URL or DIPY's documented same-byte mirror."""
    for index, url in enumerate((record["url"], record["mirror_url"])):
        try:
            count = 0
            with urllib.request.urlopen(url, timeout=60) as response, target.open("wb") as output:
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    count += len(block)
                    if count > record["size_bytes"]:
                        raise ValueError(f"Download exceeds pinned size: {target.name}")
                    output.write(block)
            verify_file(target, record)
            return
        except (urllib.error.URLError, TimeoutError):
            if index == 1:
                raise
            print(f"Original transport unavailable; trying the pinned DIPY mirror for {target.name}",
                  flush=True)


def stage_data(destination, manifest_path, source_dir=None):
    manifest = json.loads(manifest_path.read_text())
    validate_manifest(manifest)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ivim-build-", dir=destination.parent) as temp:
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
        # Do not publish any source member until the complete bundle is verified.
        for record in manifest["files"]:
            (staging / record["path"]).replace(destination / record["path"])
        (destination / "data_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/ivim"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("data_manifest.json"))
    parser.add_argument("--source-dir", type=Path, help="Optional local bundle, reverified before reuse")
    args = parser.parse_args()
    manifest = stage_data(args.destination, args.manifest, args.source_dir)
    print(f"Staged {len(manifest['files'])} verified IVIM inputs in {args.destination}")


if __name__ == "__main__":
    main()
