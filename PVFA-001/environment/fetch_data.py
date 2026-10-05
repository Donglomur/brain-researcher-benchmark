"""Build-time staging of three authenticated Sherbrooke inputs; no analysis."""
import argparse
import hashlib
import json
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path

MANIFEST_SHA256 = "f59a83a45da820308010d02ea93a29291df1bee117a66f399ddc95978c6be2fa"
API = "https://digital.lib.washington.edu/server/api/core/bitstreams/"
MIRROR = "https://workshop.dipy.org/services/data/researchworks/bitstream/handle/1773/38475/"
FETCHER = "https://raw.githubusercontent.com/dipy/dipy/1.12.1/dipy/data/fetcher.py"
CORRECTION_COMMIT = "1aee6a3a2bb74bfc7c16c9421bd3d47ec9f9de76"
SOURCE_FILES = {
    "HARDI193.nii.gz": ("image", API + "28691a7c-262a-48aa-8848-5d8da0201721/content",
                        API + "28691a7c-262a-48aa-8848-5d8da0201721", "unmodified_original"),
    "HARDI193.bval": ("bval", API + "06d89887-da2e-4635-b551-407f587fd7ae/content",
                      API + "06d89887-da2e-4635-b551-407f587fd7ae", "unmodified_original"),
    "HARDI193.bvec": ("bvec", MIRROR + "HARDI193.bvec", FETCHER,
                      "upstream_orientation_corrected_derivative"),
}
SOURCE_CAP_BYTES = 200_000_000


def validate_manifest(manifest):
    if (manifest.get("task_id") != "PVFA-001" or manifest.get("repository_handle") != "1773/38475"
            or manifest.get("license") != "CC0-1.0"
            or manifest.get("source_version") != "dipy-1.12.1-corrected-bvec"
            or manifest.get("bvec_correction", {}).get("commit") != CORRECTION_COMMIT):
        raise ValueError("Expected pinned Sherbrooke identity, license, and upstream gradient correction")
    records = manifest.get("files", [])
    if len(records) != 3 or {row["path"] for row in records} != set(SOURCE_FILES):
        raise ValueError("Manifest must contain exactly the three Sherbrooke diffusion inputs")
    for row in records:
        expected = SOURCE_FILES[row["path"]]
        if (row["role"], row["url"], row["metadata_url"], row["source_identity"]) != expected:
            raise ValueError("Only the pinned official source identities are allowed")
        if (type(row["size_bytes"]) is not int or not 0 < row["size_bytes"] < SOURCE_CAP_BYTES
                or re.fullmatch("[a-f0-9]{32}", row["md5"]) is None
                or re.fullmatch("[a-f0-9]{64}", row["sha256"]) is None):
            raise ValueError("Invalid size, published MD5, or measured SHA256")
    if sum(row["size_bytes"] for row in records) > SOURCE_CAP_BYTES:
        raise ValueError("Input bundle exceeds the bounded source contract")


def reject_symlinks(path):
    for component in (path.absolute(), *path.absolute().parents):
        if component.is_symlink():
            raise ValueError(f"Symbolic links are not allowed in source staging paths: {component}")


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
    if not path.is_file():
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
    request = urllib.request.Request(record["url"], headers={"User-Agent": "pvfa-source-staging/1.0"})
    count = 0
    with urllib.request.urlopen(request, timeout=120) as response, target.open("xb") as output:
        for block in iter(lambda: response.read(65536), b""):
            count += len(block)
            if count > record["size_bytes"]:
                raise ValueError("Download exceeds pinned source size")
            output.write(block)
    verify_file(target, record)


def stage_data(destination, manifest_path, source_dir=None):
    manifest, raw_manifest = read_manifest(manifest_path)
    reject_symlinks(destination)
    if source_dir is not None:
        reject_symlinks(source_dir)
    manifest_target = destination / "data_manifest.json"
    reject_symlinks(manifest_target)
    if manifest_target.exists() and manifest_target.read_bytes() != raw_manifest:
        raise ValueError("Existing destination manifest differs; preserve it")
    # Verify conflicts before any network call or publication, preserving existing bytes.
    for record in manifest["files"]:
        path = destination / record["path"]
        if path.exists() or path.is_symlink():
            verify_file(path, record)
    resolved = {}
    with tempfile.TemporaryDirectory(prefix="pvfa-sherbrooke-source-") as temporary:
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
        # Publish only after all three inputs verify. Exclusive creation never overwrites.
        destination.mkdir(parents=True, exist_ok=True)
        for record in manifest["files"]:
            target = destination / record["path"]
            reject_symlinks(target)
            if target.exists():
                verify_file(target, record)
            else:
                with resolved[record["path"]].open("rb") as src, target.open("xb") as dst:
                    shutil.copyfileobj(src, dst)
                verify_file(target, record)
            target.chmod(0o444)
        reject_symlinks(manifest_target)
        if manifest_target.exists():
            if manifest_target.read_bytes() != raw_manifest:
                raise ValueError("Existing destination manifest differs; preserve it")
        else:
            with manifest_target.open("xb") as stream:
                stream.write(raw_manifest)
        manifest_target.chmod(0o444)
    print("Staged three authenticated Sherbrooke inputs; no masks, preprocessing, or fits.", flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/sherbrooke"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("data_manifest.json"))
    parser.add_argument("--source-dir", type=Path, help="Optional exact local raw-source bundle, reverified offline")
    args = parser.parse_args()
    stage_data(args.destination, args.manifest, args.source_dir)


if __name__ == "__main__":
    main()
