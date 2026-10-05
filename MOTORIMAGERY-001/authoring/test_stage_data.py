"""Tiny offline mechanics fixtures; not EEG analysis or scientific calibration."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

ENV = Path(__file__).parents[1] / "environment"
spec = importlib.util.spec_from_file_location("motorimagery_fetch", ENV / "fetch_data.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def manifest():
    return json.loads((ENV / "data_manifest.json").read_text())


def tiny_bundle(tmp_path):
    source = manifest()
    directory = tmp_path / "raw"
    directory.mkdir()
    for index, record in enumerate(source["files"]):
        data = f"source mechanics fixture {index}\n".encode()
        record.update(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        path = directory / record["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    source["total_size_bytes"] = sum(r["size_bytes"] for r in source["files"])
    return source, directory


class Response(io.BytesIO):
    def __init__(self, raw, url, status=200):
        super().__init__(raw)
        self.url, self.status, self.headers = url, status, {"Content-Length": str(len(raw))}


def test_whole_manifest_pin_and_exact_source_scope():
    source, _ = fetch.read_manifest(ENV / "data_manifest.json")
    assert len(source["files"]) == 30
    assert source["total_size_bytes"] == 77_040_000
    assert source["license"] == "ODC-By-1.0"
    assert {(r["subject"], r["run"]) for r in source["files"]} == {
        (s, r) for s in range(1, 11) for r in (6, 10, 14)}


@pytest.mark.parametrize("kind", ["dataset", "version", "license", "registry_url", "registry_hash", "registry_size",
    "drop", "duplicate", "traversal", "absolute", "subject", "bool_subject", "run", "role", "url",
    "transport", "transport_url", "negative_size", "bool_size", "excessive_size", "bundle_cap", "total", "sha256"])
def test_reject_mutated_source_identity(kind):
    source = manifest()
    record = source["files"][0]
    if kind == "dataset": source["dataset_id"] = "other"
    elif kind == "version": source["version"] = "latest"
    elif kind == "license": source["license"] = "unverified"
    elif kind == "registry_url": source["checksum_registry"]["url"] = "https://example.invalid/sums"
    elif kind == "registry_hash": source["checksum_registry"]["sha256"] = "0" * 64
    elif kind == "registry_size": source["checksum_registry"]["size_bytes"] += 1
    elif kind == "drop": source["files"].pop()
    elif kind == "duplicate": source["files"][-1] = copy.deepcopy(record)
    elif kind == "traversal": record["path"] = "../outside"
    elif kind == "absolute": record["path"] = "/outside"
    elif kind == "subject": record["subject"] = 2
    elif kind == "bool_subject": record["subject"] = True
    elif kind == "run": record["run"] = 4
    elif kind == "role": record["role"] = "derived_epochs"
    elif kind == "url": record["url"] = "https://example.invalid/raw.edf"
    elif kind == "transport": source["transport"]["base_url"] = "https://example.invalid/"
    elif kind == "transport_url": record["transport_url"] = "https://example.invalid/raw.edf"
    elif kind == "negative_size": record["size_bytes"] = -1
    elif kind == "bool_size": record["size_bytes"] = True
    elif kind == "excessive_size": record["size_bytes"] = fetch.SOURCE_CAP_BYTES
    elif kind == "bundle_cap":
        for row in source["files"]: row["size_bytes"] = 4_000_000
        source["total_size_bytes"] = 120_000_000
    elif kind == "total": source["total_size_bytes"] -= 1
    else: record["sha256"] = "invalid hash"
    with pytest.raises(ValueError): fetch.validate_manifest(source)


def test_pins_cannot_be_silently_refreshed(tmp_path):
    source = manifest()
    source["files"][0]["sha256"] = "0" * 64
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="manifest SHA256"): fetch.read_manifest(path)


@pytest.mark.parametrize("kind", ["size", "sha256", "symlink", "directory", "parent_symlink"])
def test_source_size_digest_and_path_checked(tmp_path, kind):
    source, directory = tiny_bundle(tmp_path)
    record = source["files"][0]
    path = directory / record["path"]
    if kind == "size": record["size_bytes"] += 1
    elif kind == "sha256": record["sha256"] = "0" * 64
    elif kind == "symlink":
        other = tmp_path / "linked"
        other.symlink_to(path)
        path = other
    elif kind == "parent_symlink":
        other = tmp_path / "linked"
        other.symlink_to(directory, target_is_directory=True)
        path = other / record["path"]
    else: path = directory
    with pytest.raises(ValueError): fetch.verify_file(path, record)


@pytest.mark.parametrize("kind", ["oversized", "truncated", "wrong_hash", "redirect", "bad_status"])
def test_download_content_and_transport_are_bounded_and_checked(tmp_path, monkeypatch, kind):
    source, directory = tiny_bundle(tmp_path)
    record = source["files"][0]
    raw = (directory / record["path"]).read_bytes()
    payload = raw + b"x" if kind == "oversized" else raw[:-1] if kind == "truncated" else b"x" * len(raw) if kind == "wrong_hash" else raw
    url = "https://example.invalid/raw" if kind == "redirect" else record["transport_url"]
    status = 206 if kind == "bad_status" else 200
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: Response(payload, url, status))
    with pytest.raises(ValueError): fetch.download_file(record, tmp_path / "out")


def test_correct_download_passes(tmp_path, monkeypatch):
    source, directory = tiny_bundle(tmp_path)
    record = source["files"][0]
    raw = (directory / record["path"]).read_bytes()
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: Response(raw, record["transport_url"]))
    receipt = fetch.download_file(record, tmp_path / "out")
    assert (tmp_path / "out").read_bytes() == raw
    assert receipt["status"] == 200


def test_local_reuse_and_complete_destination_are_offline_and_idempotent(tmp_path, monkeypatch):
    source, directory = tiny_bundle(tmp_path)
    destination = tmp_path / "destination"
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"mechanics fixture manifest"))
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: pytest.fail("unexpected network"))
    fetch.stage_data(destination, tmp_path / "unused", directory, tmp_path / "receipt.json")
    before = {r["path"]: (destination / r["path"]).stat() for r in source["files"]}
    fetch.stage_data(destination, tmp_path / "unused", directory)
    fetch.stage_data(destination, tmp_path / "unused")
    for record in source["files"]:
        path = destination / record["path"]
        assert path.read_bytes() == (directory / record["path"]).read_bytes()
        assert path.stat().st_mode & 0o222 == 0
        assert path.stat().st_mtime_ns == before[record["path"]].st_mtime_ns
        assert path.stat().st_ino == before[record["path"]].st_ino
    assert len(json.loads((tmp_path / "receipt.json").read_text())["files"]) == 30


def test_corrupt_local_source_publishes_no_bundle(tmp_path, monkeypatch):
    source, directory = tiny_bundle(tmp_path)
    record = source["files"][-1]
    (directory / record["path"]).write_bytes(b"x" * record["size_bytes"])
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture"))
    destination = tmp_path / "destination"
    with pytest.raises(ValueError): fetch.stage_data(destination, tmp_path / "unused", directory)
    assert not destination.exists()


@pytest.mark.parametrize("kind", ["file", "manifest", "subject_symlink", "destination_symlink", "manifest_symlink", "receipt"])
def test_conflicting_existing_targets_preserved_before_network(tmp_path, monkeypatch, kind):
    source, directory = tiny_bundle(tmp_path)
    destination = tmp_path / "destination"
    destination.mkdir()
    marker = tmp_path / "preserve"
    marker.write_bytes(b"existing bytes")
    receipt_path = None
    if kind == "file":
        target = destination / source["files"][0]["path"]
        target.parent.mkdir()
        target.write_bytes(b"conflicting existing file")
    elif kind == "manifest":
        target = destination / "data_manifest.json"
        target.write_bytes(b"conflicting existing manifest")
    elif kind == "subject_symlink":
        target = destination / "S001"
        target.symlink_to(directory / "S001", target_is_directory=True)
    elif kind == "destination_symlink":
        destination.rmdir()
        destination.symlink_to(directory, target_is_directory=True)
        target = destination
    elif kind == "manifest_symlink":
        target = destination / "data_manifest.json"
        target.symlink_to(marker)
    else:
        receipt_path = marker
        target = marker
    before = target.read_bytes() if target.is_file() else target.readlink()
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture"))
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: pytest.fail("unexpected network"))
    with pytest.raises(ValueError): fetch.stage_data(destination, tmp_path / "unused", directory, receipt_path)
    assert (target.read_bytes() if target.is_file() else target.readlink()) == before
    assert marker.read_bytes() == b"existing bytes"


def test_explicit_source_dir_reverified_even_with_complete_destination(tmp_path, monkeypatch):
    source, directory = tiny_bundle(tmp_path)
    destination = tmp_path / "destination"
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture"))
    fetch.stage_data(destination, tmp_path / "unused", directory)
    record = source["files"][0]
    (directory / record["path"]).write_bytes(b"x" * record["size_bytes"])
    before = (destination / record["path"]).read_bytes()
    with pytest.raises(ValueError): fetch.stage_data(destination, tmp_path / "unused", directory)
    assert (destination / record["path"]).read_bytes() == before


@pytest.mark.parametrize("kind", ["destination", "parent"])
def test_destination_regular_file_conflict_fails_before_network(tmp_path, monkeypatch, kind):
    source, directory = tiny_bundle(tmp_path)
    target = tmp_path / "existing_file"
    target.write_bytes(b"preserve")
    destination = target if kind == "destination" else target / "child"
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture"))
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: pytest.fail("unexpected network"))
    with pytest.raises(ValueError): fetch.stage_data(destination, tmp_path / "unused", directory)
    assert target.read_bytes() == b"preserve"
