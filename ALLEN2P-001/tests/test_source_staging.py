"""Synthetic source-transport mechanics only; never substitutes a scientific NWB."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "environment" / "fetch_data.py"
SPEC = importlib.util.spec_from_file_location("allen2p_staging", SOURCE)
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)


@pytest.fixture
def source_fixture(tmp_path, monkeypatch):
    manifest = json.loads(STAGE.MANIFEST_PATH.read_text())
    body = b"small synthetic fixture: not a scientific NWB\x00\x01"
    manifest["files"][0]["size_bytes"] = len(body)
    manifest["files"][0]["sha256"] = hashlib.sha256(body).hexdigest()
    manifest["transport"]["transfer_cap_bytes"] = len(body) + 10
    original = tmp_path / "original.nwb"
    original.write_bytes(body)
    path = tmp_path / "fixture_manifest.json"
    path.write_text(json.dumps(manifest, indent=2))
    monkeypatch.setattr(STAGE, "MANIFEST_PATH", path)
    monkeypatch.setattr(STAGE, "MANIFEST_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())
    return manifest, body, original


def repin_fixture(manifest):
    STAGE.MANIFEST_PATH.write_text(json.dumps(manifest))
    STAGE.MANIFEST_SHA256 = hashlib.sha256(STAGE.MANIFEST_PATH.read_bytes()).hexdigest()


def no_network(*args, **kwargs):
    raise AssertionError("No source network permitted for this fixture")


def test_original_manifest_pin_and_frozen_identity():
    manifest = STAGE.read_manifest()
    assert manifest["ophys_experiment_id"] == 501271265
    assert manifest["files"][0]["size_bytes"] == 565631796
    assert manifest["files"][0]["sha256"] == "7c9f26aea7f636126c7fe0c1fdf445229b1850601d03be7d30a13c3cda4578b1"


def test_local_stage_no_network_two_files_only(source_fixture, tmp_path, monkeypatch):
    manifest, body, original = source_fixture
    monkeypatch.setattr(STAGE, "build_opener", no_network)
    destination = tmp_path / "staged"
    receipt = tmp_path / "receipt.json"
    STAGE.stage_data(destination, original, receipt)
    assert {p.name for p in destination.iterdir()} == {"source_manifest.json", "501271265.nwb"}
    assert (destination / "501271265.nwb").read_bytes() == body
    assert STAGE.verify_staged(destination) == manifest
    assert original.read_bytes() == body
    assert json.loads(receipt.read_text())["network_requests"] == 0
    assert not list(tmp_path.glob(".staged-source-*"))
    assert STAGE.stage_data(destination)["status"] == "verified_existing"


def test_existing_conflict_is_preserved(source_fixture, tmp_path):
    destination = tmp_path / "existing"
    destination.mkdir()
    marker = destination / "user.txt"
    marker.write_text("preserve user evidence")
    with pytest.raises(ValueError):
        STAGE.stage_data(destination, source_fixture[2])
    assert marker.read_text() == "preserve user evidence"


@pytest.mark.parametrize("field,value", [("path", "../501271265.nwb"), ("path", "/501271265.nwb"),
                                         ("path", "other.nwb"), ("role", "analysis"),
                                         ("size_bytes", 0), ("size_bytes", True), ("sha256", "bad")])
def test_manifest_invalid_file_fields(source_fixture, field, value):
    manifest = copy.deepcopy(source_fixture[0])
    manifest["files"][0][field] = value
    repin_fixture(manifest)
    with pytest.raises(ValueError):
        STAGE.read_manifest()


@pytest.mark.parametrize("field,value", [("url", "http://example.test/x"), ("automatic_retries", 1),
                                         ("redirects", True), ("timeout_seconds", 601),
                                         ("transfer_cap_bytes", 600000001)])
def test_manifest_invalid_transport_fields(source_fixture, field, value):
    manifest = copy.deepcopy(source_fixture[0])
    manifest["transport"][field] = value
    repin_fixture(manifest)
    with pytest.raises(ValueError):
        STAGE.read_manifest()


def test_manifest_bytes_not_silent_refresh(source_fixture):
    STAGE.MANIFEST_PATH.write_text(STAGE.MANIFEST_PATH.read_text() + " ")
    with pytest.raises(ValueError, match="manifest identity"):
        STAGE.read_manifest()


@pytest.mark.parametrize("mutation", ["hash", "size", "missing", "extra", "manifest", "nested_directory"])
def test_tampered_stage_fails(source_fixture, tmp_path, mutation):
    destination = tmp_path / "staged"
    STAGE.stage_data(destination, source_fixture[2])
    nwb = destination / STAGE.SOURCE_FILENAME
    if mutation == "hash":
        nwb.write_bytes(b"x" * nwb.stat().st_size)
    elif mutation == "size":
        nwb.write_bytes(b"wrong size")
    elif mutation == "missing":
        nwb.unlink()
    elif mutation == "extra":
        (destination / "analysis.h5").write_bytes(b"unrequested")
    elif mutation == "manifest":
        (destination / "source_manifest.json").write_text("{}")
    else:
        (destination / "unrequested").mkdir()
    with pytest.raises(ValueError):
        STAGE.verify_staged(destination)


@pytest.mark.parametrize("kind", ["source", "source_parent", "destination", "manifest", "staged_nwb"])
def test_symlink_paths_fail(source_fixture, tmp_path, kind):
    manifest, _body, original = source_fixture
    link = tmp_path / "link"
    if kind == "source":
        link.symlink_to(original)
        with pytest.raises(ValueError):
            STAGE.stage_data(tmp_path / "staged", link)
    elif kind == "source_parent":
        link.symlink_to(tmp_path, target_is_directory=True)
        with pytest.raises(ValueError):
            STAGE.verify_source(link / original.name, manifest)
    elif kind == "destination":
        link.symlink_to(tmp_path, target_is_directory=True)
        with pytest.raises(ValueError):
            STAGE.stage_data(link / "staged", original)
    elif kind == "manifest":
        link.symlink_to(STAGE.MANIFEST_PATH)
        with pytest.raises(ValueError):
            STAGE.read_manifest(link)
    else:
        destination = tmp_path / "staged"
        STAGE.stage_data(destination, original)
        (destination / STAGE.SOURCE_FILENAME).unlink()
        (destination / STAGE.SOURCE_FILENAME).symlink_to(original)
        with pytest.raises(ValueError):
            STAGE.verify_staged(destination)


def test_source_sha_failure_preserves_existing_input(source_fixture, tmp_path):
    source_fixture[2].write_bytes(b"bad".ljust(len(source_fixture[1]), b"x"))
    with pytest.raises(ValueError):
        STAGE.stage_data(tmp_path / "staged", source_fixture[2], tmp_path / "failure.json")
    receipt = json.loads((tmp_path / "failure.json").read_text())
    assert receipt["status"] == "failed" and receipt["partial_artifacts_retained"]
    assert source_fixture[2].exists()


def test_receipt_inside_runtime_or_existing_is_rejected(source_fixture, tmp_path):
    destination = tmp_path / "staged"
    with pytest.raises(FileExistsError):
        STAGE.stage_data(destination, source_fixture[2], destination / "receipt.json")
    old_receipt = tmp_path / "existing.json"
    old_receipt.write_text("old evidence")
    with pytest.raises(FileExistsError):
        STAGE.stage_data(destination, source_fixture[2], old_receipt)
    assert old_receipt.read_text() == "old evidence"


class FakeResponse(io.BytesIO):
    def __init__(self, body, manifest, **overrides):
        super().__init__(body)
        self.status = overrides.get("status", 200)
        self.url = overrides.get("url", STAGE.SOURCE_URL)
        self.headers = {"Content-Length": str(len(body)), "ETag": '"' + manifest["transport"]["etag"] + '"',
                        "Last-Modified": manifest["transport"]["last_modified"],
                        "Set-Cookie": "fixture cookie value must not be retained", "Authorization": "fixture credential"}
        self.headers.update(overrides.get("headers", {}))


def mock_transport(monkeypatch, response):
    calls = []
    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            return response
    monkeypatch.setattr(STAGE, "build_opener", lambda *a: Opener())
    return calls


def test_exact_conditional_download_without_sensitive_headers(source_fixture, tmp_path, monkeypatch):
    manifest, body, _original = source_fixture
    calls = mock_transport(monkeypatch, FakeResponse(body, manifest))
    destination = tmp_path / "downloaded"
    receipt = {}
    STAGE.download_source(destination, manifest, receipt)
    assert destination.read_bytes() == body
    assert len(calls) == 1
    assert calls[0].get_header("If-match") == '"' + manifest["transport"]["etag"] + '"'
    assert "fixture cookie" not in json.dumps(receipt)
    assert "fixture credential" not in json.dumps(receipt)
    assert receipt["automatic_retries"] == 0


@pytest.mark.parametrize("overrides", [{"status": 206}, {"url": "https://example.test/other"},
    {"headers": {"Content-Length": "1"}}, {"headers": {"ETag": '"different"'}},
    {"headers": {"Last-Modified": "different"}}, {"headers": {"Content-Encoding": "gzip"}}])
def test_download_invalid_response_fails_before_body(source_fixture, tmp_path, monkeypatch, overrides):
    manifest, body, _ = source_fixture
    calls = mock_transport(monkeypatch, FakeResponse(body, manifest, **overrides))
    target = tmp_path / "invalid"
    with pytest.raises(ValueError):
        STAGE.download_source(target, manifest, {})
    assert len(calls) == 1 and not target.exists()


@pytest.mark.parametrize("body_change", ["truncated", "extended", "wronghash"])
def test_download_wrong_body_fails_without_retry(source_fixture, tmp_path, monkeypatch, body_change):
    manifest, original, _ = source_fixture
    body = original[:-1] if body_change == "truncated" else original + b"x" if body_change == "extended" else b"x" * len(original)
    response = FakeResponse(body, manifest, headers={"Content-Length": str(len(original))})
    calls = mock_transport(monkeypatch, response)
    with pytest.raises(ValueError):
        STAGE.download_source(tmp_path / "partial", manifest, {})
    assert len(calls) == 1


def test_network_failure_is_single_attempt_and_partial_preserved(source_fixture, tmp_path, monkeypatch):
    calls = []
    class FailingOpener:
        def open(self, *args, **kwargs):
            calls.append(1)
            raise TimeoutError("fixture timeout")
    monkeypatch.setattr(STAGE, "build_opener", lambda *a: FailingOpener())
    with pytest.raises(TimeoutError):
        STAGE.stage_data(tmp_path / "staged", receipt_path=tmp_path / "failure.json")
    assert len(calls) == 1
    receipt = json.loads((tmp_path / "failure.json").read_text())
    assert receipt["partial_artifacts_retained"]
    assert Path(receipt["temporary_directory"]).is_dir()


def test_redirects_always_rejected():
    with pytest.raises(ValueError):
        STAGE.NoRedirect().redirect_request(None, None, 302, "", {}, STAGE.SOURCE_URL)


def test_midstream_failure_retains_partial_bytes(source_fixture, tmp_path, monkeypatch):
    manifest, body, _ = source_fixture
    class InterruptedResponse(FakeResponse):
        def read(self, size=-1):
            if self.tell() >= 5:
                raise TimeoutError("fixture interrupted transfer")
            return super().read(5)
    calls = mock_transport(monkeypatch, InterruptedResponse(body, manifest))
    with pytest.raises(TimeoutError):
        STAGE.stage_data(tmp_path / "staged", receipt_path=tmp_path / "failure.json")
    receipt = json.loads((tmp_path / "failure.json").read_text())
    partial = Path(receipt["temporary_directory"]) / "selected" / STAGE.SOURCE_FILENAME
    assert partial.read_bytes() == body[:5]
    assert receipt["download"]["measured_bytes"] == 5 and len(calls) == 1


def test_default_cli_destination_is_public_source_path(monkeypatch, capsys):
    captured = []
    monkeypatch.setattr(STAGE, "stage_data", lambda *args: captured.append(args) or {"status": "fixture"})
    STAGE.main([])
    assert captured[0][0] == Path("/app/source")
