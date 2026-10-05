"""Small source-handling fixtures; these are not scientific validation."""
import hashlib
import importlib.util
import io
import json
import urllib.error
from pathlib import Path

import pytest

ENVIRONMENT = Path(__file__).resolve().parents[1] / "environment"
spec = importlib.util.spec_from_file_location("steinmetz_stage", ENVIRONMENT / "stage_data.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    manifest = json.loads((ENVIRONMENT / "source_manifest.json").read_text())
    source = tmp_path / "source"
    source.mkdir()
    content = b"small source-handling fixture, not an NWB"
    (source / stage.FILENAME).write_bytes(content)
    row = manifest["files"][0]
    # Explicitly replace production byte anchors only for the tiny fixture.
    row["size_bytes"] = len(content)
    row["sha256"] = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(stage, "PIN", {key: row[key] for key in stage.PIN})
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return source, manifest, path, tmp_path / "staged"


def test_public_pins_are_the_published_session():
    manifest = json.loads((ENVIRONMENT / "source_manifest.json").read_text())
    stage.validate_manifest(manifest)
    assert manifest["dandiset_version"] == "0.240329.1926"
    assert manifest["license"] == "CC-BY-4.0"
    assert manifest["files"][0]["size_bytes"] == 311814662
    assert manifest["files"][0]["sha256"] == "d8433a826049f82cd832f41f98a9f9fafad0ac66998d4dbfd89b15b594fc4236"
    assert "secondary" in manifest["source_paper"]["relationship"]


def test_verified_source_is_published_without_other_files(bundle):
    source, manifest, path, destination = bundle
    (source / "unrelated.txt").write_text("do not copy")
    stage.stage_data(destination, path, source)
    assert {p.name for p in destination.iterdir()} == {stage.FILENAME, "source_manifest.json"}
    assert (destination / stage.FILENAME).read_bytes() == (source / stage.FILENAME).read_bytes()
    assert json.loads((destination / "source_manifest.json").read_text()) == manifest


@pytest.mark.parametrize("kind", ["corrupted", "truncated", "missing"])
def test_bad_local_source_is_never_published(bundle, kind):
    source, manifest, path, destination = bundle
    member = source / stage.FILENAME
    if kind == "missing":
        member.unlink()
    else:
        member.write_bytes(b"x" * (manifest["files"][0]["size_bytes"] if kind == "corrupted" else 1))
    with pytest.raises((ValueError, FileNotFoundError)):
        stage.stage_data(destination, path, source)
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("key,value", [
    ("dandiset_id", "000018"), ("dandiset_version", "draft"), ("doi", "unversioned"),
    ("version_metadata_url", "https://api.dandiarchive.org/api/dandisets/000017/versions/draft/"),
    ("license", "CC0-1.0"),
])
def test_source_release_cannot_change(bundle, key, value):
    source, manifest, path, destination = bundle
    manifest[key] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        stage.stage_data(destination, path, source)
    assert not destination.exists()


@pytest.mark.parametrize("key,value", [
    ("path", "../outside.nwb"), ("source_path", "sub-Cori/another.nwb"),
    ("role", "reference"), ("asset_id", "another-asset"), ("size_bytes", 1),
    ("sha256", "0" * 64), ("metadata_url", "https://example.org/meta"),
    ("download_url", "https://example.org/download"), ("transport_url", "https://example.org/blob"),
])
def test_source_identity_and_anchors_cannot_change(bundle, key, value):
    source, manifest, path, destination = bundle
    manifest["files"][0][key] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        stage.stage_data(destination, path, source)
    assert not destination.exists()


@pytest.mark.parametrize("count", [0, 2])
def test_only_one_source_member_is_allowed(bundle, count):
    source, manifest, path, destination = bundle
    manifest["files"] = manifest["files"] * count
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        stage.stage_data(destination, path, source)
    assert not destination.exists()


@pytest.mark.parametrize("kind", ["valid", "truncated", "oversized", "corrupted"])
def test_download_is_bounded_and_verified(bundle, monkeypatch, kind):
    source, manifest, path, destination = bundle
    content = (source / stage.FILENAME).read_bytes()
    body = {"valid": content, "truncated": content[:-1], "oversized": content + b"x",
            "corrupted": b"x" * len(content)}[kind]
    urls = []

    def open_url(url, **kwargs):
        urls.append(url)
        return io.BytesIO(body)

    monkeypatch.setattr(stage.urllib.request, "urlopen", open_url)
    if kind == "valid":
        stage.stage_data(destination, path)
        assert (destination / stage.FILENAME).read_bytes() == content
    else:
        with pytest.raises(ValueError):
            stage.stage_data(destination, path)
        assert list(destination.iterdir()) == []
    assert urls == [manifest["files"][0]["transport_url"]]


def test_transport_failure_does_not_fall_back_to_another_asset(bundle, monkeypatch):
    source, manifest, path, destination = bundle
    calls = []

    def unavailable(url, **kwargs):
        calls.append(url)
        raise urllib.error.URLError("unavailable")

    monkeypatch.setattr(stage.urllib.request, "urlopen", unavailable)
    with pytest.raises(urllib.error.URLError):
        stage.stage_data(destination, path)
    assert calls == [manifest["files"][0]["transport_url"]]
    assert list(destination.iterdir()) == []


def test_bad_download_does_not_replace_existing_valid_source(bundle, monkeypatch):
    source, manifest, path, destination = bundle
    stage.stage_data(destination, path, source)
    before = (destination / stage.FILENAME).read_bytes()
    monkeypatch.setattr(stage.urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(b"bad"))
    with pytest.raises(ValueError):
        stage.stage_data(destination, path)
    assert (destination / stage.FILENAME).read_bytes() == before
