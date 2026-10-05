"""Source handling fixtures only; no simulated connectome or scientific bank."""
import hashlib
import importlib.util
import io
import json
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

ENVIRONMENT = Path(__file__).resolve().parents[1] / "environment"
spec = importlib.util.spec_from_file_location("allen_stage", ENVIRONMENT / "stage_data.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def pin_fixture(path, manifest, monkeypatch):
    """Explicitly change byte pins only inside a tiny source-handling fixture."""
    raw = (json.dumps(manifest, indent=2) + "\n").encode()
    path.write_bytes(raw)
    monkeypatch.setattr(stage, "MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    manifest = json.loads((ENVIRONMENT / "source_manifest.json").read_text())
    source = tmp_path / "source"
    for record in manifest["files"]:
        path = source / record["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        content = (record["path"] + ": small source-handling fixture, not observations").encode()
        path.write_bytes(content)
        record["size_bytes"] = len(content)
        record["sha256"] = hashlib.sha256(content).hexdigest()
    manifest["raw_source_total_size_bytes"] = sum(row["size_bytes"] for row in manifest["files"])
    manifest_path = tmp_path / "source_manifest.json"
    pin_fixture(manifest_path, manifest, monkeypatch)
    return source, manifest, manifest_path, tmp_path / "staged"


def test_public_source_identity_and_license_boundary():
    manifest, raw = stage.read_manifest(ENVIRONMENT / "source_manifest.json")
    assert hashlib.sha256(raw).hexdigest() == "f37c21e753aa0cfbc61a41c9764ce3688ec7ea6f391b5793805cf9a29ae47ebe"
    assert manifest["snapshot_id"] == "allen-connectivity-20261001"
    assert manifest["official_immutable_release"] is False
    assert manifest["raw_source_total_size_bytes"] == 91890571
    assert len(manifest["files"]) == 37
    assert sum(row["role"] == "projection_page" for row in manifest["files"]) == 35
    assert "research/noncommercial" in manifest["license"]
    assert "not independently published" in manifest["checksum_provenance"]
    assert all("retrieved_at_utc" in row and "etag" in row for row in manifest["files"])


def test_complete_verified_bundle_only_is_published(bundle):
    source, manifest, manifest_path, destination = bundle
    (source / "unrelated_matrix.csv").write_text("not a raw source")
    stage.stage_data(destination, manifest_path, source)
    expected = {row["path"] for row in manifest["files"]} | {"source_manifest.json"}
    assert {str(path.relative_to(destination)) for path in destination.rglob("*") if path.is_file()} == expected
    for row in manifest["files"]:
        assert (destination / row["path"]).read_bytes() == (source / row["path"]).read_bytes()
    assert (destination / "source_manifest.json").read_bytes() == manifest_path.read_bytes()


@pytest.mark.parametrize("kind", ["missing", "truncated", "same_size_corruption"])
def test_last_invalid_source_prevents_any_publication(bundle, kind):
    source, manifest, manifest_path, destination = bundle
    row = manifest["files"][-1]
    path = source / row["path"]
    if kind == "missing":
        path.unlink()
    else:
        path.write_bytes(b"x" * (row["size_bytes"] if kind == "same_size_corruption" else 1))
    with pytest.raises((ValueError, FileNotFoundError)):
        stage.stage_data(destination, manifest_path, source)
    assert list(destination.iterdir()) == []


def test_changed_manifest_cannot_refresh_pins(bundle):
    source, manifest, manifest_path, destination = bundle
    manifest["files"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="manifest SHA256 mismatch"):
        stage.stage_data(destination, manifest_path, source)
    assert not destination.exists()


@pytest.mark.parametrize("mutation", ["snapshot", "official_release", "license", "api_base", "missing",
                                     "duplicate", "traversal", "role", "transport", "model", "injection",
                                     "hemisphere", "order", "size", "digest", "total_bytes"])
def test_repinned_tiny_fixture_still_enforces_source_schema(bundle, monkeypatch, mutation):
    source, manifest, manifest_path, destination = bundle
    row = manifest["files"][-1]
    if mutation in ("snapshot", "official_release", "license", "api_base"):
        key, value = {"snapshot": ("snapshot_id", "latest"), "official_release": ("official_immutable_release", True),
                      "license": ("license", "CC0-1.0"), "api_base": ("api_base", "https://example.org/")}[mutation]
        manifest[key] = value
    elif mutation == "missing":
        manifest["files"].pop()
    elif mutation == "duplicate":
        manifest["files"][-1] = manifest["files"][0].copy()
    elif mutation == "traversal":
        row["path"] = "../outside.json"
    elif mutation == "role":
        row["role"] = "reference_matrix"
    elif mutation == "transport":
        row["url"] = "https://example.org/source.json"
    elif mutation in ("model", "injection", "hemisphere", "order"):
        before, after = {
            "model": ("ProjectionStructureUnionize", "StructureUnionize"),
            "injection": ("[is_injection$eqfalse]", "[is_injection$eqtrue]"),
            "hemisphere": ("[hemisphere_id$eq3]", "[hemisphere_id$eq1]"),
            "order": ("[order$eq'id']", "[order$eq'structure_id']"),
        }[mutation]
        row["criteria"] = row["criteria"].replace(before, after)
        row["url"] = "https://api.brain-map.org/api/v2/data/query.json?" + urllib.parse.urlencode({"criteria": row["criteria"]})
    elif mutation == "size":
        row["size_bytes"] = -1
    elif mutation == "digest":
        row["sha256"] = "not-a-sha256"
    else:
        manifest["raw_source_total_size_bytes"] += 1
    pin_fixture(manifest_path, manifest, monkeypatch)
    with pytest.raises(ValueError):
        stage.stage_data(destination, manifest_path, source)
    assert not destination.exists()


@pytest.mark.parametrize("kind", ["valid", "truncated", "oversized", "corrupted"])
def test_download_is_bounded_and_hashed(bundle, monkeypatch, kind):
    source, manifest, manifest_path, destination = bundle
    row = manifest["files"][0]
    content = (source / row["path"]).read_bytes()
    body = {"valid": content, "truncated": content[:-1], "oversized": content+b"x",
            "corrupted": b"x"*len(content)}[kind]
    urls = []

    def open_url(url, **kwargs):
        urls.append(url)
        return io.BytesIO(body)

    monkeypatch.setattr(stage.urllib.request, "urlopen", open_url)
    target = source.parent / "download.json"
    if kind == "valid":
        stage.download_file(row, target)
        assert target.read_bytes() == content
    else:
        with pytest.raises(ValueError):
            stage.download_file(row, target)
    assert urls == [row["url"]]


def test_portable_download_uses_exact_recorded_urls(bundle, monkeypatch):
    source, manifest, manifest_path, destination = bundle
    content = {row["url"]: (source/row["path"]).read_bytes() for row in manifest["files"]}
    urls = []

    def open_url(url, **kwargs):
        urls.append(url)
        return io.BytesIO(content[url])

    monkeypatch.setattr(stage.urllib.request, "urlopen", open_url)
    stage.stage_data(destination, manifest_path)
    assert urls == [row["url"] for row in manifest["files"]]
    assert (destination / "source_manifest.json").read_bytes() == manifest_path.read_bytes()


def test_upstream_drift_fails_without_refresh_or_fallback(bundle, monkeypatch):
    source, manifest, manifest_path, destination = bundle
    calls = []
    row = manifest["files"][0]
    original_manifest = manifest_path.read_bytes()

    def drift(url, **kwargs):
        calls.append(url)
        return io.BytesIO(b"x" * row["size_bytes"])

    monkeypatch.setattr(stage.urllib.request, "urlopen", drift)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        stage.stage_data(destination, manifest_path)
    assert calls == [row["url"]]
    assert manifest_path.read_bytes() == original_manifest
    assert list(destination.iterdir()) == []


def test_transport_failure_fails_closed(bundle, monkeypatch):
    source, manifest, manifest_path, destination = bundle

    def fail(*args, **kwargs):
        raise urllib.error.URLError("unavailable")

    monkeypatch.setattr(stage.urllib.request, "urlopen", fail)
    with pytest.raises(urllib.error.URLError):
        stage.stage_data(destination, manifest_path)
    assert list(destination.iterdir()) == []


def test_invalid_replacement_preserves_existing_valid_bundle(bundle):
    source, manifest, manifest_path, destination = bundle
    stage.stage_data(destination, manifest_path, source)
    row = manifest["files"][-1]
    old = (destination / row["path"]).read_bytes()
    (source / row["path"]).write_bytes(b"x" * row["size_bytes"])
    with pytest.raises(ValueError):
        stage.stage_data(destination, manifest_path, source)
    assert (destination / row["path"]).read_bytes() == old
