"""Source-staging mechanics on tiny synthetic bytes, never original recordings."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

ENV = Path(__file__).resolve().parents[1] / "environment"
SPEC = importlib.util.spec_from_file_location("hippotheta_fetch", ENV / "fetch_data.py")
stager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stager)


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    manifest = json.loads((ENV / "source_manifest.json").read_text())
    bodies = {"raw": b"tiny synthetic raw fixture", "behavior": b"tiny synthetic behavior fixture"}
    source = tmp_path / "originals"
    source.mkdir()
    for entry in manifest["files"]:
        body = bodies[entry["role"]]
        entry["size_bytes"] = len(body)
        entry["sha256"] = hashlib.sha256(body).hexdigest()
        path = source / entry["path"]
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(body)
    manifest_path = tmp_path / "fixture_manifest.json"

    def freeze():
        raw = (json.dumps(manifest, indent=2) + "\n").encode()
        manifest_path.write_bytes(raw)
        monkeypatch.setattr(stager, "MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())

    freeze()
    return {"manifest": manifest, "manifest_path": manifest_path, "bodies": bodies,
            "source": source, "destination": tmp_path / "staged", "freeze": freeze, "monkeypatch": monkeypatch}


def local_stage(fixture):
    return stager.stage_data(fixture["destination"], fixture["source"], fixture["manifest_path"])


def test_real_manifest_is_frozen_without_reading_originals():
    manifest, raw = stager.read_manifest(ENV / "source_manifest.json")
    assert hashlib.sha256(raw).hexdigest() == stager.MANIFEST_SHA256
    assert sum(e["size_bytes"] for e in manifest["files"]) == 7108180912
    assert manifest["license"] == "CC-BY-4.0"


def test_verified_local_copy_and_exact_runtime_inventory(fixture):
    result = local_stage(fixture)
    assert result["status"] == "complete" and result["body_bytes_read"] == 0
    verified = stager.verify_staged(fixture["destination"])
    assert verified == fixture["manifest"]
    expected = {"source_manifest.json", *(e["path"] for e in verified["files"])}
    observed = {p.relative_to(fixture["destination"]).as_posix() for p in fixture["destination"].rglob("*") if p.is_file()}
    assert observed == expected
    for entry in verified["files"]:
        assert (fixture["destination"] / entry["path"]).read_bytes() == fixture["bodies"][entry["role"]]


def test_existing_complete_source_verified_without_network(fixture):
    local_stage(fixture)
    fixture["monkeypatch"].setattr(stager.urllib.request, "build_opener", lambda *args: pytest.fail("No network on existing source"))
    result = local_stage(fixture)
    assert result["status"] == "existing_verified"


def test_local_copy_never_opens_remote_source(fixture):
    class Opener:
        def open(self, *args, **kwargs):
            pytest.fail("Local staging must not request remote source")
    fixture["monkeypatch"].setattr(stager.urllib.request, "build_opener", lambda *args: Opener())
    assert local_stage(fixture)["status"] == "complete"


@pytest.mark.parametrize("mutation", ["missing", "wrong_size", "wrong_hash"])
def test_bad_original_fails_without_silent_substitution(fixture, mutation):
    entry = fixture["manifest"]["files"][0]
    path = fixture["source"] / entry["path"]
    if mutation == "missing":
        path.unlink()
    elif mutation == "wrong_size":
        path.write_bytes(b"wrong")
    else:
        path.write_bytes(b"x" * entry["size_bytes"])
    with pytest.raises(stager.SourceError):
        local_stage(fixture)
    assert not (fixture["destination"] / entry["path"]).exists()


@pytest.mark.parametrize("mutation", ["extra_file", "extra_directory", "stale_hash", "missing_file", "wrong_manifest"])
def test_conflicting_existing_destination_not_overwritten(fixture, mutation):
    local_stage(fixture)
    root = fixture["destination"]
    entry = fixture["manifest"]["files"][0]
    if mutation == "extra_file":
        (root / "notes.txt").write_text("user file")
    elif mutation == "extra_directory":
        (root / "other").mkdir()
    elif mutation == "stale_hash":
        (root / entry["path"]).write_bytes(b"x" * entry["size_bytes"])
    elif mutation == "missing_file":
        (root / entry["path"]).unlink()
    else:
        (root / "source_manifest.json").write_text("{}")
    with pytest.raises(stager.SourceError):
        local_stage(fixture)


@pytest.mark.parametrize("where", ["source_file", "source_parent", "destination", "destination_file", "manifest"])
def test_symlink_refused(fixture, where, tmp_path):
    entry = fixture["manifest"]["files"][0]
    if where == "source_file":
        path = fixture["source"] / entry["path"]
        moved = path.with_name("real.nwb")
        path.rename(moved)
        path.symlink_to(moved)
    elif where == "source_parent":
        linked = tmp_path / "linked_originals"
        linked.symlink_to(fixture["source"], target_is_directory=True)
        fixture["source"] = linked
    elif where == "destination":
        fixture["destination"].symlink_to(fixture["source"], target_is_directory=True)
    elif where == "destination_file":
        local_stage(fixture)
        path = fixture["destination"] / entry["path"]
        path.unlink()
        path.symlink_to(fixture["source"] / entry["path"])
    else:
        linked = tmp_path / "linked_manifest.json"
        linked.symlink_to(fixture["manifest_path"])
        fixture["manifest_path"] = linked
    with pytest.raises(stager.SourceError, match="Symlink|symlink"):
        local_stage(fixture)


def test_manifest_byte_tampering_refused(fixture):
    fixture["manifest_path"].write_bytes(fixture["manifest_path"].read_bytes() + b" ")
    with pytest.raises(stager.SourceError, match="manifest SHA256"):
        local_stage(fixture)


@pytest.mark.parametrize("path", ["/absolute.nwb", "../escape.nwb", "sub-e15-13f1/../escape.nwb", "sub-e15-13f1//file.nwb", "sub-e15-13f1\\file.nwb", "other/file.nwb"])
def test_unsafe_paths_refused_even_in_rehashed_fixture(fixture, path):
    fixture["manifest"]["files"][0]["path"] = path
    fixture["freeze"]()
    with pytest.raises(stager.SourceError):
        local_stage(fixture)


@pytest.mark.parametrize("url", ["http://dandiarchive.s3.us-east-2.amazonaws.com/blobs/a", "https://example.com/blobs/a", "https://dandiarchive.s3.us-east-2.amazonaws.com:444/blobs/a", "https://user@dandiarchive.s3.us-east-2.amazonaws.com/blobs/a", "https://dandiarchive.s3.us-east-2.amazonaws.com/blobs/a?refresh=1"])
def test_changed_transport_scope_refused(fixture, url):
    fixture["manifest"]["files"][0]["url"] = url
    fixture["freeze"]()
    with pytest.raises(stager.SourceError, match="URL"):
        local_stage(fixture)


class Response(io.BytesIO):
    def __init__(self, body, entry):
        super().__init__(body)
        self.status = 200
        self.read_count = 0
        self.headers = {"Content-Length": str(entry["size_bytes"]), "ETag": '"' + entry["etag"] + '"', "x-amz-version-id": entry["version_id"], "Set-Cookie": "do-not-record"}

    def read(self, size=-1):
        self.read_count += 1
        return super().read(size)


def remote_fixture(fixture):
    responses = [Response(fixture["bodies"][e["role"]], e) for e in fixture["manifest"]["files"]]
    calls = []
    class Opener:
        def open(self, request, timeout):
            calls.append(request)
            return responses[len(calls) - 1]
    fixture["monkeypatch"].setattr(stager.urllib.request, "build_opener", lambda *args: Opener())
    return responses, calls


def test_mock_remote_full_verification_and_safe_receipt(fixture):
    responses, calls = remote_fixture(fixture)
    result = stager.stage_data(fixture["destination"], manifest_path=fixture["manifest_path"])
    assert result["status"] == "complete" and len(calls) == 2
    assert result["body_bytes_read"] == sum(map(len, fixture["bodies"].values()))
    assert "do-not-record" not in json.dumps(result)
    assert "versionId=" in calls[0].full_url


@pytest.mark.parametrize("key,value", [("Content-Length", "999"), ("ETag", '"wrong"'), ("x-amz-version-id", "wrong")])
def test_mock_remote_wrong_headers_before_read(fixture, key, value):
    responses, calls = remote_fixture(fixture)
    responses[0].headers[key] = value
    with pytest.raises(stager.SourceError, match="before body"):
        stager.stage_data(fixture["destination"], manifest_path=fixture["manifest_path"])
    assert len(calls) == 1 and responses[0].read_count == 0


@pytest.mark.parametrize("status", [206, 302, 403])
def test_mock_remote_wrong_status_before_read(fixture, status):
    responses, calls = remote_fixture(fixture)
    responses[0].status = status
    with pytest.raises(stager.SourceError, match="before body"):
        stager.stage_data(fixture["destination"], manifest_path=fixture["manifest_path"])
    assert len(calls) == 1 and responses[0].read_count == 0


@pytest.mark.parametrize("kind", ["truncated", "bad_hash"])
def test_mock_remote_bad_bytes_preserve_partial_without_retry(fixture, kind):
    responses, calls = remote_fixture(fixture)
    entry = fixture["manifest"]["files"][0]
    responses[0] = Response(b"short" if kind == "truncated" else b"x" * entry["size_bytes"], entry)
    with pytest.raises(stager.SourceError):
        stager.stage_data(fixture["destination"], manifest_path=fixture["manifest_path"])
    assert len(calls) == 1
    assert (fixture["destination"] / (entry["path"] + ".partial")).exists()
    assert not (fixture["destination"] / entry["path"]).exists()


def test_no_redirect_policy():
    with pytest.raises(stager.SourceError, match="Redirect"):
        stager.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.invalid/")


def test_receipt_cannot_pollute_runtime_source(fixture):
    with pytest.raises(stager.SourceError, match="outside"):
        stager.stage_data(fixture["destination"], fixture["source"], fixture["manifest_path"], fixture["destination"] / "receipt.json")
