"""Authenticate three unchanged shipped images against exact official ZIP members."""
import argparse
import hashlib
import json
import re
import shutil
import tempfile
import urllib.request
import zlib
from pathlib import Path

import nibabel as nib
import numpy as np

MANIFEST_SHA256 = "91e88266157656f228fe8edc1510f9a6ee51139f0c60bd99bb14b13a241637cd"
ARCHIVE_URL = "https://www.neuroimaging.at/media/qsm/20170327_qsm2016_recon_challenge.zip"
ARCHIVE_SIZE = 244982259
ARCHIVE_ETAG = '"e9a21f3-54bb981c8b280"'
EXPECTED = {"phs_tissue.nii.gz": ("field", "float32", "float32"),
            "msk.nii.gz": ("brain_mask", "uint8", "float32"),
            "evaluation_mask.nii.gz": ("evaluation_mask", "uint8", "int16")}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_manifest(manifest):
    archive = manifest.get("archive", {})
    if (manifest.get("dataset_id") != "qsm-reconstruction-challenge-2016"
            or manifest.get("archive_version") != "20170327"
            or (archive.get("url"), archive.get("size_bytes"), archive.get("etag"))
            != (ARCHIVE_URL, ARCHIVE_SIZE, ARCHIVE_ETAG)):
        raise ValueError("Only the pinned official dated archive is allowed")
    records = manifest.get("files", [])
    if len(records) != 3 or {r["path"] for r in records} != set(EXPECTED):
        raise ValueError("Only the exact three original source members are allowed")
    if manifest.get("license", {}).get("redistribution_authorized") is not False:
        raise ValueError("No dataset redistribution license has been established")
    intervals = []
    for record in records:
        original = record["original"]
        if (record["role"], record["dtype"], original["dtype"]) != EXPECTED[record["path"]]:
            raise ValueError("Source role or dtype mismatch")
        if (original["path"] != "original/" + record["path"] or
                original["member"] != "20170327_qsm2016_recon_challenge/data/" + record["path"]):
            raise ValueError("Unsafe or incorrect original member path")
        for item in (record, original, original["zip_range"]):
            if (type(item["size_bytes"]) is not int or not 0 < item["size_bytes"] < 10_000_000
                    or re.fullmatch("[a-f0-9]{64}", item["sha256"]) is None):
                raise ValueError("Invalid source size or SHA256")
        if re.fullmatch("[a-f0-9]{8}", original["crc32"]) is None:
            raise ValueError("Invalid original ZIP CRC32")
        part = original["zip_range"]
        offset, size = part["offset"], part["size_bytes"]
        if type(offset) is not int or offset < 0 or offset + size > ARCHIVE_SIZE:
            raise ValueError("Unsafe ZIP byte range")
        intervals.append((offset, offset + size))
    intervals.sort()
    if sum(b-a for a,b in intervals) > 10_000_000 or any(a[1] > b[0] for a,b in zip(intervals, intervals[1:])):
        raise ValueError("ZIP ranges overlap or exceed bounded source scope")


def read_manifest(path):
    raw = path.read_bytes()
    if sha256(raw) != MANIFEST_SHA256:
        raise ValueError("Source manifest SHA256 mismatch; do not silently refresh pins")
    manifest = json.loads(raw)
    validate_manifest(manifest)
    return manifest, raw


def verify_bytes(data, record):
    if len(data) != record["size_bytes"] or sha256(data) != record["sha256"]:
        raise ValueError("Source size or SHA256 mismatch")
    if "crc32" in record and f"{zlib.crc32(data):08x}" != record["crc32"]:
        raise ValueError("Original ZIP CRC32 mismatch")


def verify_file(path, record):
    if path.stat().st_size != record["size_bytes"]:
        raise ValueError(f"Source size mismatch: {path.name}")
    verify_bytes(path.read_bytes(), record)


def download_original(record, target):
    original, part = record["original"], record["original"]["zip_range"]
    start, size = part["offset"], part["size_bytes"]
    end = start + size - 1
    request = urllib.request.Request(ARCHIVE_URL, headers={
        "Range": f"bytes={start}-{end}", "If-Range": ARCHIVE_ETAG,
        "Accept-Encoding": "identity", "User-Agent": "qsmdipole-source-staging/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        # Fail before reading if a server ignores ranges or serves another archive.
        if (response.status != 206 or response.headers.get("ETag") != ARCHIVE_ETAG
                or response.headers.get("Content-Range") != f"bytes {start}-{end}/{ARCHIVE_SIZE}"):
            raise ValueError("Official archive range/ETag response mismatch")
        compressed = response.read(size + 1)
    verify_bytes(compressed, part)
    decoder = zlib.decompressobj(-15)
    data = decoder.decompress(compressed, original["size_bytes"] + 1)
    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("Invalid or oversized ZIP member")
    verify_bytes(data, original)
    target.write_bytes(data)


def compare_images(original_path, shipped_path, record, geometry):
    original, shipped = nib.load(original_path), nib.load(shipped_path)
    for img, dtype in ((original, record["original"]["dtype"]), (shipped, record["dtype"])):
        if (list(img.shape) != geometry["shape"] or str(img.get_data_dtype()) != dtype
                or not np.array_equal(img.affine, geometry["affine"])
                or not np.array_equal(img.header.get_zooms(), geometry["zooms"])
                or list(img.header.get_xyzt_units()) != record["units"]
                or int(img.header["qform_code"]) != record["qform_code"]
                or int(img.header["sform_code"]) != record["sform_code"]
                or float(img.dataobj.slope) != 1 or float(img.dataobj.inter) != 0):
            raise ValueError("Original/shipped image geometry, dtype, or scaling mismatch")
    left, right = np.asanyarray(original.dataobj), np.asanyarray(shipped.dataobj)
    if not np.isfinite(left).all() or not np.array_equal(left, right):
        raise ValueError("Original/shipped voxel values differ or are nonfinite")
    if record["role"] == "brain_mask" and not np.isin(left, [0, 1]).all():
        raise ValueError("Brain mask must be binary")
    if record["role"] == "evaluation_mask" and not np.isin(left, np.arange(12)).all():
        raise ValueError("Evaluation mask label domain mismatch")
    return {"path": record["path"], "shipped_sha256": record["sha256"],
            "original_path": record["original"]["path"], "original_sha256": record["original"]["sha256"],
            "original_crc32_verified": True, "image_values_exactly_equal": True,
            "geometry_exactly_equal": True, "different_voxel_count": 0,
            "original_dtype": record["original"]["dtype"], "shipped_dtype": record["dtype"]}


def stage_data(destination, manifest_path, source_dir=None):
    manifest, manifest_bytes = read_manifest(manifest_path)
    manifest_target = destination / "source_manifest.json"
    receipt_target = destination / "source_comparison.json"
    if manifest_target.exists() and manifest_target.read_bytes() != manifest_bytes:
        raise ValueError("Existing destination manifest differs; preserve it")
    for record in manifest["files"]:
        verify_file(destination / record["path"], record)
        original_target = destination / record["original"]["path"]
        if original_target.exists():
            verify_file(original_target, record["original"])
    comparisons = []
    with tempfile.TemporaryDirectory(prefix="qsmdipole-source-") as temp:
        temp = Path(temp)
        for record in manifest["files"]:
            target = temp / record["path"]
            if source_dir is None:
                download_original(record, target)
            else:
                source = source_dir / record["path"]
                verify_file(source, record["original"])
                shutil.copyfile(source, target)
            verify_file(target, record["original"])
            comparisons.append(compare_images(target, destination / record["path"], record, manifest["geometry"]))
        receipt = {"source_manifest_sha256": sha256(manifest_bytes),
                   "scope": "Original released processed images versus unchanged lossless shipped repacks; no reconstruction or truth validation",
                   "files": comparisons, "dataset_redistribution_authorized": False}
        receipt_bytes = (json.dumps(receipt, indent=2) + "\n").encode()
        if receipt_target.exists() and receipt_target.read_bytes() != receipt_bytes:
            raise ValueError("Existing source comparison receipt differs; preserve it")
        # Publish only after all three originals and comparisons pass.
        for record in manifest["files"]:
            target = destination / record["original"]["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copyfile(temp / record["path"], target)
            target.chmod(0o444)
        for target, content in ((manifest_target, manifest_bytes), (receipt_target, receipt_bytes)):
            if not target.exists():
                target.write_bytes(content)
            target.chmod(0o444)
    print("Verified exact original source identity and all-voxel equality for three shipped images.", flush=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/app/data"))
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("source_manifest.json"))
    parser.add_argument("--source-dir", type=Path, help="Optional directory containing three exact original .nii.gz members; no network")
    args = parser.parse_args()
    stage_data(args.destination, args.manifest, args.source_dir)


if __name__ == "__main__":
    main()
