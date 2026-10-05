"""Build-time staging of a frozen, locally hashed Allen API response snapshot.

This is not an official immutable atlas release. Any upstream byte drift fails
closed; the script never refreshes expected hashes or substitutes another cohort.
"""
import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path


SNAPSHOT_ID = "allen-connectivity-20261001"
MANIFEST_SHA256 = "f37c21e753aa0cfbc61a41c9764ce3688ec7ea6f391b5793805cf9a29ae47ebe"
METADATA_ROLES = {"experiments_api_response.json": "experiments", "structures_api_response.json": "structures"}
PAGE_PATHS = {f"projection_raw_pages/batch_{batch:02d}_start_{start:06d}.json"
              for batch in range(5) for start in range(0, 30001, 5000)}


def read_manifest(path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Frozen source manifest SHA256 mismatch; do not silently refresh the snapshot")
    manifest = json.loads(raw)
    if (manifest.get("snapshot_id") != SNAPSHOT_ID
            or manifest.get("official_immutable_release") is not False
            or manifest.get("api_base") != "https://api.brain-map.org/api/v2/"
            or manifest.get("license") != "Allen Institute Terms of Use (research/noncommercial)"):
        raise ValueError("Incorrect snapshot identity or source provenance")
    records = manifest["files"]
    if len(records) != 37 or {row["path"] for row in records} != set(METADATA_ROLES) | PAGE_PATHS:
        raise ValueError("Require exactly two original metadata responses and35 original projection pages")
    for row in records:
        role = METADATA_ROLES.get(row["path"], "projection_page")
        url = urllib.parse.urlsplit(row["url"])
        query = urllib.parse.parse_qs(url.query)
        if (row["role"] != role or url.scheme != "https" or url.netloc != "api.brain-map.org"
                or url.path != "/api/v2/data/query.json" or set(query) != {"criteria"}
                or len(query["criteria"]) != 1 or url.fragment):
            raise ValueError("Unexpected source role or API transport")
        if role == "projection_page":
            criteria = query["criteria"][0]
            if (criteria != row["criteria"] or not criteria.startswith("model::ProjectionStructureUnionize,")
                    or "[is_injection$eqfalse]" not in criteria or "[hemisphere_id$eq3]" not in criteria
                    or "[order$eq'id']" not in criteria):
                raise ValueError("Unexpected projection compartment or query")
        if (not isinstance(row["size_bytes"], int) or row["size_bytes"] <= 0
                or len(row["sha256"]) != 64 or not set(row["sha256"]) <= set("0123456789abcdef")):
            raise ValueError("Invalid pinned byte count or SHA256")
    if sum(row["size_bytes"] for row in records) != manifest["raw_source_total_size_bytes"]:
        raise ValueError("Source bundle byte count mismatch")
    return manifest, raw


def verify_file(path, record):
    if path.stat().st_size != record["size_bytes"]:
        raise ValueError(f"Size mismatch: {record['path']}")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != record["sha256"]:
        raise ValueError(f"SHA256 mismatch: {record['path']}; upstream drift is not an automatic refresh")


def download_file(record, target):
    received = 0
    with urllib.request.urlopen(record["url"], timeout=60) as response, target.open("wb") as output:
        for block in iter(lambda: response.read(1024 * 1024), b""):
            received += len(block)
            if received > record["size_bytes"]:
                raise ValueError(f"Download exceeds pinned size: {record['path']}")
            output.write(block)
    verify_file(target, record)


def stage_data(destination, manifest_path, source_dir=None):
    manifest, raw_manifest = read_manifest(manifest_path)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="allen-source-", dir=destination.parent) as temporary:
        staging = Path(temporary)
        for record in manifest["files"]:
            target = staging / record["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            if source_dir is None:
                download_file(record, target)
            else:
                source = source_dir / record["path"]
                verify_file(source, record)
                shutil.copyfile(source, target)
                verify_file(target, record)
            print(f"Verified {record['path']}", flush=True)
        # Never publish a partly verified bundle. There is no imputation,
        # projection aggregation, fitted result or answer key in this step.
        for record in manifest["files"]:
            destination_path = destination / record["path"]
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            (staging / record["path"]).replace(destination_path)
        (destination / "source_manifest.json").write_bytes(raw_manifest)
    print(f"Staged {len(manifest['files'])} source responses for {SNAPSHOT_ID}", flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data/allen"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("source_manifest.json"))
    parser.add_argument("--source-dir", type=Path, help="Previously frozen local source root; every byte reverified")
    args = parser.parse_args()
    stage_data(args.destination, args.manifest, args.source_dir)


if __name__ == "__main__":
    main()
