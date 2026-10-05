"""Bounded source-staging mechanics; no network, reconstruction, or real-data fit."""
import copy
import importlib.util
import io
import json
import shutil
import zlib
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

ENV = Path(__file__).parents[1] / "environment"
spec = importlib.util.spec_from_file_location("qsmdipole_stage", ENV / "stage_data.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def manifest():
    return json.loads((ENV / "source_manifest.json").read_text())


def test_source_manifest_pins_exact_scope_and_no_license_inference():
    source, _ = stage.read_manifest(ENV / "source_manifest.json")
    assert len(source["files"]) == 3
    assert sum(r["original"]["zip_range"]["size_bytes"] for r in source["files"]) == 3635069
    assert source["archive"]["full_archive_sha256"] is None
    assert source["license"]["redistribution_authorized"] is False


@pytest.mark.parametrize("kind", ["url", "etag", "archive_size", "version", "license", "drop", "duplicate",
    "traversal", "absolute", "original_path", "member", "role", "dtype", "sha", "crc", "size",
    "negative_offset", "past_end", "bool_offset", "overlap"])
def test_reject_mutated_identity_or_unsafe_range(kind):
    source = manifest(); record = source["files"][0]; original = record["original"]
    if kind == "url": source["archive"]["url"] = "https://example.invalid/archive.zip"
    elif kind == "etag": source["archive"]["etag"] = '"changed"'
    elif kind == "archive_size": source["archive"]["size_bytes"] += 1
    elif kind == "version": source["archive_version"] = "latest"
    elif kind == "license": source["license"]["redistribution_authorized"] = True
    elif kind == "drop": source["files"].pop()
    elif kind == "duplicate": source["files"].append(copy.deepcopy(record))
    elif kind == "traversal": record["path"] = "../outside"
    elif kind == "absolute": record["path"] = "/outside"
    elif kind == "original_path": original["path"] = "../outside"
    elif kind == "member": original["member"] = "other/data/phs_tissue.nii.gz"
    elif kind == "role": record["role"] = "reference"
    elif kind == "dtype": original["dtype"] = "uint8"
    elif kind == "sha": original["sha256"] = "not-a-hash"
    elif kind == "crc": original["crc32"] = "invalid"
    elif kind == "size": original["size_bytes"] = 0
    elif kind == "negative_offset": original["zip_range"]["offset"] = -1
    elif kind == "past_end": original["zip_range"]["offset"] = stage.ARCHIVE_SIZE
    elif kind == "bool_offset": original["zip_range"]["offset"] = True
    elif kind == "overlap": original["zip_range"]["offset"] = source["files"][1]["original"]["zip_range"]["offset"]
    with pytest.raises(ValueError): stage.validate_manifest(source)


def test_whole_manifest_pin_rejects_even_plausible_checksum_refresh(tmp_path):
    source = manifest(); source["files"][0]["sha256"] = "0" * 64
    path = tmp_path / "manifest.json"; path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="manifest SHA256"): stage.read_manifest(path)


def tiny_bundle(tmp_path):
    source_dir, destination = tmp_path / "source", tmp_path / "destination"
    source_dir.mkdir(); destination.mkdir()
    source = manifest()
    source["geometry"] = {"shape": [4, 4, 4], "zooms": [1., 1., 1.], "affine": np.eye(4).tolist()}
    for i, record in enumerate(source["files"]):
        record.update(units=["unknown", "unknown"], qform_code=0, sform_code=1)
        array = (np.linspace(-0.1, 0.1, 64).reshape(4,4,4) if i == 0 else
                 np.ones((4,4,4)) if i == 1 else np.arange(64).reshape(4,4,4) % 12)
        for folder, dtype, target_record in [(source_dir, record["original"]["dtype"], record["original"]),
                                              (destination, record["dtype"], record)]:
            image = nib.Nifti1Image(array.astype(dtype), np.eye(4))
            image.set_qform(np.eye(4), 0); image.set_sform(np.eye(4), 1)
            path = folder / record["path"]; nib.save(image, path)
            data = path.read_bytes()
            target_record.update(size_bytes=len(data), sha256=stage.sha256(data))
            if folder == source_dir:
                target_record["crc32"] = f"{zlib.crc32(data):08x}"
    return source, source_dir, destination


@pytest.mark.parametrize("kind", ["size", "sha", "crc"])
def test_original_content_checks_are_all_enforced(tmp_path, kind):
    source, original, _ = tiny_bundle(tmp_path)
    record = source["files"][0]["original"]
    if kind == "size": record["size_bytes"] += 1
    elif kind == "sha": record["sha256"] = "0" * 64
    else: record["crc32"] = "0" * 8
    with pytest.raises(ValueError): stage.verify_file(original / "phs_tissue.nii.gz", record)


@pytest.mark.parametrize("kind", ["affine", "zooms", "shape", "dtype", "units", "qform", "sform", "scaling", "voxels"])
def test_exact_image_comparison_rejects_geometry_or_value_changes(tmp_path, kind):
    source, original, destination = tiny_bundle(tmp_path)
    record = source["files"][0]; path = destination / record["path"]
    image = nib.load(path); data = np.asanyarray(image.dataobj).copy(); affine = image.affine.copy()
    if kind == "affine": affine[0,3] = 1
    elif kind == "zooms": affine[0,0] = 2
    elif kind == "shape": data = data[:3]
    elif kind == "dtype": data = data.astype(np.float64)
    elif kind == "voxels": data.flat[0] += 0.01
    new = nib.Nifti1Image(data, affine)
    new.set_qform(affine, 1 if kind == "qform" else 0)
    new.set_sform(affine, 2 if kind == "sform" else 1)
    if kind == "units": new.header.set_xyzt_units("mm")
    if kind == "scaling": new.header.set_slope_inter(2,0)
    nib.save(new, path)
    with pytest.raises(ValueError): stage.compare_images(original / record["path"], path, record, source["geometry"])


def test_local_reuse_is_offline_idempotent_and_preserves_shipped_files(tmp_path, monkeypatch):
    source, original, destination = tiny_bundle(tmp_path)
    before = {r["path"]: (destination/r["path"]).read_bytes() for r in source["files"]}
    monkeypatch.setattr(stage, "read_manifest", lambda _: (source, b"fixture-manifest"))
    monkeypatch.setattr(stage.urllib.request, "urlopen", lambda *a, **k: pytest.fail("offline source reuse downloaded"))
    for _ in range(2): stage.stage_data(destination, tmp_path / "unused", original)
    for record in source["files"]:
        assert (destination/record["path"]).read_bytes() == before[record["path"]]
        assert (destination/record["original"]["path"]).read_bytes() == (original/record["path"]).read_bytes()
        assert (destination/record["original"]["path"]).stat().st_mode & 0o222 == 0
    assert all(item["image_values_exactly_equal"] for item in json.loads((destination/"source_comparison.json").read_text())["files"])


@pytest.mark.parametrize("which", ["original", "shipped"])
def test_corrupt_input_fails_before_publishing_any_original(tmp_path, monkeypatch, which):
    source, original, destination = tiny_bundle(tmp_path)
    path = (original if which == "original" else destination) / source["files"][0]["path"]
    original_bytes = path.read_bytes(); corrupted = b"x" + original_bytes[1:]; path.write_bytes(corrupted)
    monkeypatch.setattr(stage, "read_manifest", lambda _: (source, b"fixture-manifest"))
    monkeypatch.setattr(stage.urllib.request, "urlopen", lambda *a, **k: pytest.fail("unexpected network"))
    with pytest.raises(ValueError): stage.stage_data(destination, tmp_path / "unused", original)
    assert path.read_bytes() == corrupted
    assert not (destination/"original").exists()
    assert not (destination/"source_manifest.json").exists()


class Response(io.BytesIO):
    def __init__(self, payload, status, headers):
        super().__init__(payload); self.status = status; self.headers = headers; self.was_read = False

    def read(self, *args):
        self.was_read = True
        return super().read(*args)


def download_fixture(tmp_path):
    source, original, _ = tiny_bundle(tmp_path)
    record = source["files"][0]
    raw = (original/record["path"]).read_bytes()
    encoder = zlib.compressobj(wbits=-15); payload = encoder.compress(raw) + encoder.flush()
    record["original"]["zip_range"] = {"offset": 42, "size_bytes": len(payload), "sha256": stage.sha256(payload)}
    headers = {"ETag": stage.ARCHIVE_ETAG, "Content-Range": f"bytes 42-{41+len(payload)}/{stage.ARCHIVE_SIZE}"}
    return record, raw, payload, headers


@pytest.mark.parametrize("kind", ["status", "etag", "range", "length", "hash", "crc"])
def test_download_fails_closed_on_transport_or_payload_error(tmp_path, monkeypatch, kind):
    record, raw, payload, headers = download_fixture(tmp_path)
    status = 200 if kind == "status" else 206
    if kind == "etag": headers["ETag"] = '"other"'
    if kind == "range": headers["Content-Range"] = "bytes 0-1/2"
    if kind == "length": payload += b"x"
    if kind == "hash": payload = b"x" + payload[1:]
    if kind == "crc": record["original"]["crc32"] = "0" * 8
    response = Response(payload, status, headers)
    monkeypatch.setattr(stage.urllib.request, "urlopen", lambda *a, **k: response)
    with pytest.raises(ValueError): stage.download_original(record, tmp_path/"out")
    assert not (tmp_path/"out").exists()
    if kind in ("status", "etag", "range"): assert not response.was_read


def test_download_accepts_only_exact_source_member(tmp_path, monkeypatch):
    record, raw, payload, headers = download_fixture(tmp_path)
    monkeypatch.setattr(stage.urllib.request, "urlopen", lambda *a, **k: Response(payload, 206, headers))
    stage.download_original(record, tmp_path/"out")
    assert (tmp_path/"out").read_bytes() == raw
