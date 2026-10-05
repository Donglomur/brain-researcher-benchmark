"""Tiny source-integrity fixtures; never acquire or analyze the original session."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

TASK = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("outcomepred_staging", TASK / "environment/stage_data.py")
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)
ORIGINAL = json.loads((TASK / "environment/source_manifest.json").read_text())


@pytest.fixture
def source(tmp_path, monkeypatch):
    manifest = copy.deepcopy(ORIGINAL)
    payload = b"tiny synthetic source fixture; not scientific data"
    record = manifest["files"][0]
    record.update(size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    raw = (json.dumps(manifest, indent=2) + "\n").encode()
    metadata = tmp_path / "manifest.json"
    metadata.write_bytes(raw)
    original = tmp_path / "original.nwb"
    original.write_bytes(payload)
    monkeypatch.setattr(stage, "MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())
    return manifest, metadata, original, tmp_path / "staged"


def test_original_manifest_pin_and_scope():
    manifest, raw = stage.read_manifest()
    assert hashlib.sha256(raw).hexdigest() == "d87c000f92d2aa54b4eaa0de50d5ffd7ab3035141d1fccd45b4e674d1c56d63d"
    assert manifest["files"][0]["size_bytes"] == 385181169
    assert manifest["license"] == "CC-BY-4.0"
    assert len(manifest["files"]) == 1


def test_offline_stage_and_reuse(source, monkeypatch):
    manifest, metadata, original, destination = source
    monkeypatch.setattr(stage.urllib.request, "build_opener", lambda *a: pytest.fail("No network for offline reuse"))
    before = original.read_bytes(), original.stat().st_mode
    assert stage.stage_data(destination, original, manifest_path=metadata) == manifest
    assert stage.verify_staged(destination) == manifest
    assert stage.stage_data(destination, manifest_path=metadata) == manifest
    assert (original.read_bytes(), original.stat().st_mode) == before
    assert destination.stat().st_mode & 0o777 == 0o755
    assert all(p.stat().st_mode & 0o777 == 0o444 for p in destination.iterdir())


@pytest.mark.parametrize("change", ["content", "size", "missing", "manifest", "extra", "directory", "symlink"])
def test_tampered_staged_inventory_rejected(source, change):
    _, metadata, original, destination = source
    stage.stage_data(destination, original, manifest_path=metadata)
    target = destination / "session.nwb"
    target.chmod(0o644)
    if change == "content": target.write_bytes(b"x" * target.stat().st_size)
    elif change == "size": target.write_bytes(b"x")
    elif change == "missing": target.unlink()
    elif change == "manifest":
        path = destination / "source_manifest.json"; path.chmod(0o644); path.write_text("{}")
    elif change == "extra": (destination / "answer.json").write_text("{}")
    elif change == "directory": target.unlink(); target.mkdir()
    else: target.unlink(); target.symlink_to(original)
    with pytest.raises(ValueError): stage.verify_staged(destination)


def test_conflicting_existing_destination_preserved(source, monkeypatch):
    _, metadata, original, destination = source
    destination.mkdir()
    (destination / "user.txt").write_text("preserve")
    monkeypatch.setattr(stage, "download_file", lambda *a: pytest.fail("Do not download over conflicts"))
    with pytest.raises(ValueError): stage.stage_data(destination, manifest_path=metadata)
    assert (destination / "user.txt").read_text() == "preserve"


@pytest.mark.parametrize("which", ["source", "destination", "ancestor", "manifest"])
def test_symlink_paths_rejected(source, tmp_path, which):
    _, metadata, original, destination = source
    link = tmp_path / "link"
    if which == "source": link.symlink_to(original); original = link
    elif which == "destination": link.symlink_to(destination); destination = link
    elif which == "manifest": link.symlink_to(metadata); metadata = link
    else:
        parent = tmp_path / "parent"; parent.mkdir(); link.symlink_to(parent); destination = link / "staged"
    with pytest.raises(ValueError): stage.stage_data(destination, original, manifest_path=metadata)


@pytest.mark.parametrize("field,value", [("path", "../session.nwb"), ("role", "answer"),
    ("transport_url", "https://evil.example/data"), ("s3_version_id", "draft"),
    ("asset_id", "other"), ("size_bytes", True), ("size_bytes", 400000001)])
def test_manifest_semantic_identity_after_fixture_repin(source, monkeypatch, field, value):
    manifest, metadata, _, _ = source
    manifest["files"][0][field] = value
    body = json.dumps(manifest).encode(); metadata.write_bytes(body)
    monkeypatch.setattr(stage, "MANIFEST_SHA256", hashlib.sha256(body).hexdigest())
    with pytest.raises(ValueError): stage.read_manifest(metadata)


def fake_network(monkeypatch, record, payload, **changes):
    class Response(io.BytesIO):
        status = changes.get("status", 200)
        headers = {"Content-Length": str(record["size_bytes"]), "ETag": '"'+record["dandi_etag"]+'"',
                   "x-amz-version-id": stage.VERSION_ID, "Set-Cookie": "do-not-retain"}
        def geturl(self): return changes.get("url", stage.SOURCE_URL)
    Response.headers.update(changes.get("headers", {}))
    calls = []
    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            if changes.get("exception"): raise OSError("fixture transport failure")
            return Response(payload)
    monkeypatch.setattr(stage.urllib.request, "build_opener", lambda *a: Opener())
    return calls


def test_single_verified_download_records_no_secret_headers(source, tmp_path, monkeypatch):
    manifest, _, original, _ = source
    record = manifest["files"][0]
    calls = fake_network(monkeypatch, record, original.read_bytes())
    ledger = tmp_path / "download"
    result = stage.download_file(record, ledger)
    assert result.read_bytes() == original.read_bytes() and calls == [stage.SOURCE_URL]
    receipt = json.loads((ledger / "result.json").read_text())
    assert receipt["status"] == "sha256_verified" and receipt["automatic_retries"] == 0
    assert "Set-Cookie" not in receipt["response_headers"]
    with pytest.raises(FileExistsError): stage.download_file(record, ledger)
    assert len(calls) == 1


@pytest.mark.parametrize("failure", ["status", "length", "etag", "version", "encoding", "url", "short", "long", "hash", "network"])
def test_bad_transfer_fails_once_with_preserved_ledger(source, tmp_path, monkeypatch, failure):
    manifest, _, original, _ = source
    record = manifest["files"][0]
    payload = original.read_bytes(); changes = {}
    if failure == "status": changes["status"] = 206
    elif failure == "length": changes["headers"] = {"Content-Length": "1"}
    elif failure == "etag": changes["headers"] = {"ETag": '"wrong"'}
    elif failure == "version": changes["headers"] = {"x-amz-version-id": "other"}
    elif failure == "encoding": changes["headers"] = {"Content-Encoding": "gzip"}
    elif failure == "url": changes["url"] = "https://evil.example/other"
    elif failure == "short": payload = payload[:-1]
    elif failure == "long": payload += b"x"
    elif failure == "hash": payload = b"x" * len(payload)
    else: changes["exception"] = True
    calls = fake_network(monkeypatch, record, payload, **changes)
    ledger = tmp_path / "failed"
    with pytest.raises((ValueError, OSError)): stage.download_file(record, ledger)
    assert len(calls) == 1
    assert json.loads((ledger / "result.json").read_text())["status"] == "failed"
    assert not (ledger / "session.nwb").exists()


def test_ledger_cannot_be_inside_destination(source):
    _, metadata, _, destination = source
    with pytest.raises(ValueError): stage.stage_data(destination, ledger=destination / "ledger", manifest_path=metadata)


def test_redirect_refused():
    with pytest.raises(ValueError): stage.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example")


def test_changed_manifest_bytes_fail_whole_file_pin(source):
    _, metadata, _, _ = source
    metadata.write_bytes(metadata.read_bytes() + b" ")
    with pytest.raises(ValueError): stage.read_manifest(metadata)


def test_corrupt_offline_original_preserved(source):
    _, metadata, original, destination = source
    original.write_bytes(b"broken original")
    with pytest.raises(ValueError): stage.stage_data(destination, original, manifest_path=metadata)
    assert original.read_bytes() == b"broken original" and not destination.exists()
