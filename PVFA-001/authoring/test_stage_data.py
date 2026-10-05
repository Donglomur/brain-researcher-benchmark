"""Offline source-staging unit tests; no scientific data acquisition or fitting."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

ENV = Path(__file__).parents[1] / "environment"
spec = importlib.util.spec_from_file_location("pvfa_fetch", ENV / "fetch_data.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def manifest():
    return json.loads((ENV / "data_manifest.json").read_text())


def tiny_bundle(tmp_path):
    source = manifest(); directory = tmp_path / "raw"; directory.mkdir()
    for index, record in enumerate(source["files"]):
        data = f"source mechanics fixture {index}\n".encode()
        record.update(size_bytes=len(data), md5=hashlib.md5(data).hexdigest(), sha256=hashlib.sha256(data).hexdigest())
        (directory/record["path"]).write_bytes(data)
    return source, directory


def test_whole_manifest_pin_and_exact_source_only_scope():
    source, _ = fetch.read_manifest(ENV / "data_manifest.json")
    assert len(source["files"]) == 3
    assert sum(r["size_bytes"] for r in source["files"]) == 192519151
    assert {r["role"] for r in source["files"]} == {"image", "bval", "bvec"}
    assert source["license"] == "CC0-1.0"


@pytest.mark.parametrize("kind", ["handle", "license", "drop", "duplicate", "traversal", "absolute",
    "role", "url", "metadata_url", "source_identity", "version", "correction", "task_id", "negative_size", "bool_size", "excessive_size", "bundle_cap", "md5", "sha256"])
def test_reject_mutated_source_identity(kind):
    source = manifest(); record = source["files"][0]
    if kind == "handle": source["repository_handle"] = "other"
    elif kind == "license": source["license"] = "unverified"
    elif kind == "drop": source["files"].pop()
    elif kind == "duplicate": source["files"].append(copy.deepcopy(record))
    elif kind == "traversal": record["path"] = "../outside"
    elif kind == "absolute": record["path"] = "/outside"
    elif kind == "role": record["role"] = "derived_roi"
    elif kind == "url": record["url"] = "https://example.invalid/raw.nii"
    elif kind == "metadata_url": record["metadata_url"] = "https://example.invalid/metadata"
    elif kind == "source_identity": record[kind] = "derived_roi"
    elif kind == "version": source["source_version"] = "unknown"
    elif kind == "correction": source["bvec_correction"]["commit"] = "0" * 40
    elif kind == "task_id": source["task_id"] = "other"
    elif kind == "negative_size": record["size_bytes"] = -1
    elif kind == "bool_size": record["size_bytes"] = True
    elif kind == "excessive_size": record["size_bytes"] = fetch.SOURCE_CAP_BYTES
    elif kind == "bundle_cap":
        for row in source["files"]: row["size_bytes"] = 100_000_000
    else: record[kind] = "invalid hash"
    with pytest.raises(ValueError): fetch.validate_manifest(source)


def test_pins_cannot_be_silently_refreshed(tmp_path):
    source = manifest(); source["files"][0]["sha256"] = "0" * 64
    path = tmp_path/"manifest.json"; path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="manifest SHA256"): fetch.read_manifest(path)


@pytest.mark.parametrize("kind", ["size_bytes", "md5", "sha256", "symlink", "directory"])
def test_file_size_and_both_hashes_and_type_are_checked(tmp_path, kind):
    source, directory = tiny_bundle(tmp_path); record = source["files"][0]
    path = directory/record["path"]
    if kind == "size_bytes": record[kind] += 1
    elif kind in ("md5", "sha256"): record[kind] = "0" * len(record[kind])
    elif kind == "symlink":
        other = tmp_path/"linked"; other.symlink_to(path); path = other
    else: path = directory
    with pytest.raises(ValueError): fetch.verify_file(path, record)


@pytest.mark.parametrize("kind", ["oversized", "truncated", "wrong_hash"])
def test_download_content_is_bounded_and_checked(tmp_path, monkeypatch, kind):
    source, directory = tiny_bundle(tmp_path); record = source["files"][0]
    raw = (directory/record["path"]).read_bytes()
    payload = raw + b"x" if kind == "oversized" else raw[:-1] if kind == "truncated" else b"x" * len(raw)
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(payload))
    with pytest.raises(ValueError): fetch.download_file(record, tmp_path/"out")


def test_correct_download_passes_both_hashes(tmp_path, monkeypatch):
    source, directory = tiny_bundle(tmp_path); record = source["files"][0]
    raw = (directory/record["path"]).read_bytes()
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(raw))
    fetch.download_file(record, tmp_path/"out")
    assert (tmp_path/"out").read_bytes() == raw


def test_local_reuse_and_complete_destination_are_offline_and_idempotent(tmp_path, monkeypatch):
    source, directory = tiny_bundle(tmp_path); destination = tmp_path/"destination"
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"mechanics fixture manifest"))
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: pytest.fail("unexpected network"))
    fetch.stage_data(destination, tmp_path/"unused", directory)
    fetch.stage_data(destination, tmp_path/"unused", directory)
    fetch.stage_data(destination, tmp_path/"unused")
    for record in source["files"]:
        assert (destination/record["path"]).read_bytes() == (directory/record["path"]).read_bytes()
        assert (destination/record["path"]).stat().st_mode & 0o222 == 0


def test_corrupt_local_source_publishes_no_bundle(tmp_path, monkeypatch):
    source, directory = tiny_bundle(tmp_path); record = source["files"][-1]
    (directory/record["path"]).write_bytes(b"x" * record["size_bytes"])
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture"))
    destination = tmp_path/"destination"
    with pytest.raises(ValueError): fetch.stage_data(destination, tmp_path/"unused", directory)
    assert not destination.exists()


def test_conflicting_existing_destination_is_preserved_before_network(tmp_path, monkeypatch):
    source, directory = tiny_bundle(tmp_path); destination = tmp_path/"destination"; destination.mkdir()
    path = destination/source["files"][0]["path"]; path.write_bytes(b"preserve these existing bytes")
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture"))
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: pytest.fail("unexpected network"))
    with pytest.raises(ValueError): fetch.stage_data(destination, tmp_path/"unused", directory)
    assert path.read_bytes() == b"preserve these existing bytes"
    assert not (destination/"data_manifest.json").exists()


@pytest.mark.parametrize("kind", ["mismatch", "symlink"])
def test_existing_manifest_is_never_overwritten(tmp_path, monkeypatch, kind):
    source, directory = tiny_bundle(tmp_path); destination = tmp_path/"destination"; destination.mkdir()
    target = destination/"data_manifest.json"
    if kind == "mismatch": target.write_bytes(b"retain old manifest")
    else:
        other = tmp_path/"other.json"; other.write_bytes(b"fixture"); target.symlink_to(other)
    before = target.read_bytes()
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture"))
    with pytest.raises(ValueError): fetch.stage_data(destination, tmp_path/"unused", directory)
    assert target.read_bytes() == before


def test_explicit_source_dir_is_reverified_even_with_complete_destination(tmp_path, monkeypatch):
    source, directory = tiny_bundle(tmp_path); destination = tmp_path/"destination"
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture"))
    fetch.stage_data(destination, tmp_path/"unused", directory)
    record = source["files"][0]; (directory/record["path"]).write_bytes(b"x" * record["size_bytes"])
    before = (destination/record["path"]).read_bytes()
    with pytest.raises(ValueError): fetch.stage_data(destination, tmp_path/"unused", directory)
    assert (destination/record["path"]).read_bytes() == before


@pytest.mark.parametrize("kind", ["destination", "parent", "file", "broken_file", "source_dir", "source_parent", "manifest"])
def test_symlink_paths_are_rejected_without_changing_targets(tmp_path, monkeypatch, kind):
    source, directory = tiny_bundle(tmp_path)
    destination = tmp_path/"destination"
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture"))
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: pytest.fail("unexpected network"))
    if kind in ("destination", "parent"):
        real = tmp_path/"real"; real.mkdir()
        destination.symlink_to(real, target_is_directory=True)
        if kind == "parent": destination = destination/"child"
    elif kind in ("file", "broken_file"):
        destination.mkdir()
        referent = directory/source["files"][0]["path"] if kind == "file" else tmp_path/"missing"
        (destination/source["files"][0]["path"]).symlink_to(referent)
    elif kind in ("source_dir", "source_parent"):
        linked = tmp_path/"linked"; linked.symlink_to(directory if kind == "source_dir" else tmp_path, target_is_directory=True)
        directory = linked if kind == "source_dir" else linked/"raw"
    else:
        destination.mkdir()
        (destination/"data_manifest.json").symlink_to(tmp_path/"missing")
    with pytest.raises(ValueError, match="Symbolic links"):
        fetch.stage_data(destination, tmp_path/"unused", directory)


def test_unrelated_existing_destination_file_is_preserved(tmp_path, monkeypatch):
    source, directory = tiny_bundle(tmp_path)
    destination = tmp_path/"destination"; destination.mkdir()
    unrelated = destination/"unrelated.txt"; unrelated.write_bytes(b"user-owned")
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture"))
    fetch.stage_data(destination, tmp_path/"unused", directory)
    assert unrelated.read_bytes() == b"user-owned"


def test_source_permissions_are_unchanged(tmp_path, monkeypatch):
    source, directory = tiny_bundle(tmp_path)
    before = {r["path"]: (directory/r["path"]).stat().st_mode for r in source["files"]}
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture"))
    fetch.stage_data(tmp_path/"destination", tmp_path/"unused", directory)
    assert before == {r["path"]: (directory/r["path"]).stat().st_mode for r in source["files"]}


def test_download_never_overwrites_existing_file(tmp_path, monkeypatch):
    source, directory = tiny_bundle(tmp_path); record = source["files"][0]
    raw = (directory/record["path"]).read_bytes()
    target = tmp_path/"out"; target.write_bytes(b"preserve")
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(raw))
    with pytest.raises(FileExistsError): fetch.download_file(record, target)
    assert target.read_bytes() == b"preserve"


def test_manifest_symlink_is_rejected(tmp_path):
    target = tmp_path/"manifest"; target.symlink_to(ENV/"data_manifest.json")
    with pytest.raises(ValueError, match="Symbolic links"): fetch.read_manifest(target)
