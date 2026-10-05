"""Stage only the checksum-pinned PET TAC/source-lineage bundle at image build."""
import argparse
import hashlib
import json
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path

MANIFEST_SHA256 = "4cf33fba2a84354186a7e20b5e767f53de463e2c0bb91a87c910b6804cf92d71"
GIT_COMMIT_SHA = "2b21a6d6e57cf712ec068faf594be4bbf14cdcbe"
GIT_TREE_SHA = "c937d6f6c05c0e7c788190f4962c0393534a7212"
BASE = "https://openneuro.org/crn/datasets/ds001420/snapshots/1.2.0/files/"
SCANS = [(sub, ses) for sub in ("sub-01", "sub-02") for ses in ("ses-baseline", "ses-rescan")]


def expected_files():
    result = {"dataset_description.json": ("dataset_metadata", None, None),
              "README": ("readme", None, None), "CHANGES": ("changelog", None, None)}
    for sub, ses in SCANS:
        stem = f"{sub}_{ses}"
        prefix = f"derivatives/PETPrep1/{sub}/{ses}/pet/"
        for path, role in [(f"{sub}/{ses}/pet/{stem}_pet.json", "pet_metadata"),
            (prefix+f"{stem}_pvc-nopvc_desc-mc_tacs.tsv", "tac"),
            (prefix+f"{stem}_desc-mc_pet.json", "motion_metadata"),
            (prefix+"agtm/mri_gtmpvc.log", "extraction_log"),
            (prefix+"agtm/km.ref.tac.dat", "reference_tac_provenance")]:
            result[path] = (role, sub, ses)
    result["derivatives/PETPrep1/sub-01/ses-baseline/pet/agtm/aux/seg.ctab"] = ("segmentation_labels", "sub-01", "ses-baseline")
    return result


def validate_manifest(manifest):
    if (manifest.get("dataset_id") != "ds001420" or manifest.get("snapshot") != "1.2.0"
            or manifest.get("git_tree_sha1") != GIT_TREE_SHA or manifest.get("git_tag_commit_sha1") != GIT_COMMIT_SHA
            or manifest.get("license") != "CC0"):
        raise ValueError("Manifest must identify the pinned published snapshot and license")
    records = manifest.get("files", [])
    expected = expected_files()
    if len(records) != len(expected) or {r["path"] for r in records} != set(expected):
        raise ValueError("Only the exact 24 original source/lineage files are allowed")
    for record in records:
        role, subject, session = expected[record["path"]]
        if (record["role"], record.get("subject"), record.get("session")) != (role, subject, session):
            raise ValueError("Source role or scan identity mismatch")
        if record["url"] != BASE+record["path"].replace("/", ":"):
            raise ValueError("Only the official pinned snapshot URL is allowed")
        if (not isinstance(record["size_bytes"], int) or not 0 < record["size_bytes"] < 100_000
                or re.fullmatch("[a-f0-9]{64}", record["sha256"]) is None
                or re.fullmatch("[a-f0-9]{40}", record["git_blob_sha1"]) is None):
            raise ValueError("Invalid source size or checksum")
        kind = record.get("git_entry_kind")
        if kind not in ("direct_text_blob", "annex_symlink"):
            raise ValueError("Unknown Git source identity")
        if kind == "annex_symlink":
            pointer = record["annex_pointer"].encode()
            pointer_hash = hashlib.sha1(f"blob {len(pointer)}\0".encode()+pointer).hexdigest()
            anchor = re.search(rb"MD5E-s(\d+)--([0-9a-f]{32})", pointer)
            if (pointer_hash != record["git_blob_sha1"] or anchor is None
                    or int(anchor[1]) != record["size_bytes"] or anchor[2].decode() != record["annex_md5"]):
                raise ValueError("Published Git-annex pointer does not bind content identity")


def read_manifest(path):
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Source manifest SHA256 mismatch; do not silently refresh pins")
    manifest = json.loads(content)
    validate_manifest(manifest)
    return manifest, content


def verify_file(path, record):
    if path.stat().st_size != record["size_bytes"]:
        raise ValueError(f"Source size mismatch: {record['path']}")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError(f"Source SHA256 mismatch: {record['path']}")
    if record["git_entry_kind"] == "direct_text_blob":
        actual = hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
        expected = record["git_blob_sha1"]
    else:
        actual, expected = hashlib.md5(data).hexdigest(), record["annex_md5"]
    if actual != expected:
        raise ValueError(f"Published source checksum mismatch: {record['path']}")


def download_file(record, target):
    request = urllib.request.Request(record["url"], headers={"User-Agent": "petref-source-staging/1.0"})
    count = 0
    with urllib.request.urlopen(request, timeout=60) as response, target.open("wb") as output:
        for block in iter(lambda: response.read(65536), b""):
            count += len(block)
            if count > record["size_bytes"]:
                raise ValueError("Download exceeds pinned size")
            output.write(block)
    verify_file(target, record)


def stage_data(destination, manifest_path, source_dir=None):
    manifest, manifest_bytes = read_manifest(manifest_path)
    existing_manifest = destination/"source_manifest.json"
    if existing_manifest.exists() and existing_manifest.read_bytes() != manifest_bytes:
        raise ValueError("Existing destination manifest differs; preserve it")
    for record in manifest["files"]:
        existing = destination/record["path"]
        if existing.exists():
            verify_file(existing, record)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Verify the entire bundle before publishing any source bytes.
    with tempfile.TemporaryDirectory(prefix="petref-source-", dir=destination.parent) as temp:
        temp = Path(temp)
        for record in manifest["files"]:
            target = temp/record["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            if source_dir is None:
                download_file(record, target)
            else:
                source = source_dir/record["path"]
                verify_file(source, record)
                shutil.copyfile(source, target)
                verify_file(target, record)
        destination.mkdir(parents=True, exist_ok=True)
        for record in manifest["files"]:
            target = destination/record["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                verify_file(target, record)
            else:
                (temp/record["path"]).replace(target)
            target.chmod(0o444)
        if not existing_manifest.exists():
            existing_manifest.write_bytes(manifest_bytes)
        existing_manifest.chmod(0o444)
    print("Verified 24 original PET source/lineage files; no images or fitted parameter tables staged.", flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/petref"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("source_manifest.json"))
    parser.add_argument("--source-dir", type=Path, help="Optional exact local bundle, fully reverified before reuse")
    args = parser.parse_args()
    stage_data(args.destination, args.manifest, args.source_dir)


if __name__ == "__main__":
    main()
