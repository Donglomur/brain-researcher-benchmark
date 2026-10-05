"""Small fixtures test source handling, not IVIM fitting or biological validity."""
import hashlib
import importlib.util
import io
import json
import urllib.error
from pathlib import Path

import pytest

ENVIRONMENT = Path(__file__).resolve().parents[1] / "environment"
spec = importlib.util.spec_from_file_location("ivim_source_fetch", ENVIRONMENT / "fetch_data.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


@pytest.fixture
def bundle(tmp_path):
    manifest = json.loads((ENVIRONMENT / "data_manifest.json").read_text())
    source = tmp_path / "source"
    source.mkdir()
    for row in manifest["files"]:
        content = (row["path"] + " small source-handling fixture").encode()
        (source / row["path"]).write_bytes(content)
        row["size_bytes"] = len(content)
        row["md5"] = hashlib.md5(content).hexdigest()
        row["sha256"] = hashlib.sha256(content).hexdigest()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return source, manifest, path, tmp_path / "staged"


def test_public_pins_match_original_observations_not_depositor_fit():
    manifest = json.loads((ENVIRONMENT / "data_manifest.json").read_text())
    fetch.validate_manifest(manifest)
    assert {row["file_id"]: row["md5"] for row in manifest["files"]} == {
        5305243: "cda596f89dc2676af7d9bf1cabccf600",
        5305246: "f03d89f84aa9a9397103a400e43af43a",
        5305249: "fb633a06b02807355e49ccd85cb92565",
    }
    assert sum(row["size_bytes"] for row in manifest["files"]) == 274689129
    assert all(len(row["sha256"]) == 64 for row in manifest["files"])
    assert manifest["license"] == "CC0-1.0"
    assert manifest["observed_geometry"]["shape"] == [256, 256, 54, 21]
    assert manifest["observed_geometry"]["nifti_spatial_units"] == "mm"
    assert "not identified" in manifest["scientific_context"]["relationship"]


def test_verified_bundle_is_published(bundle):
    source, manifest, path, destination = bundle
    fetch.stage_data(destination, path, source)
    assert {p.name for p in destination.iterdir()} == set(fetch.SOURCE_FILES) | {"data_manifest.json"}
    for row in manifest["files"]:
        assert (destination / row["path"]).read_bytes() == (source / row["path"]).read_bytes()


@pytest.mark.parametrize("kind", ["same_size_corruption", "truncated"])
def test_changed_member_cannot_publish_partial_bundle(bundle, kind):
    source, manifest, path, destination = bundle
    row = manifest["files"][-1]
    (source / row["path"]).write_bytes(b"x" * (row["size_bytes"] if kind == "same_size_corruption" else 1))
    with pytest.raises(ValueError, match="mismatch"):
        fetch.stage_data(destination, path, source)
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("digest", ["md5", "sha256"])
def test_both_digest_checks_are_required(bundle, digest):
    source, manifest, path, destination = bundle
    manifest["files"][-1][digest] = "0" * len(manifest["files"][-1][digest])
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=digest + " mismatch"):
        fetch.stage_data(destination, path, source)
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "traversal", "wrong_role", "wrong_url",
                                     "wrong_mirror", "wrong_metadata", "wrong_file_id", "version", "doi",
                                     "depositor_fit"])
def test_manifest_cannot_change_source_identity(bundle, mutation):
    source, manifest, path, destination = bundle
    if mutation == "missing":
        manifest["files"].pop()
    elif mutation == "duplicate":
        manifest["files"][-1] = manifest["files"][0].copy()
    elif mutation == "traversal":
        manifest["files"][0]["path"] = "../outside.nii.gz"
    elif mutation == "depositor_fit":
        manifest["files"][0]["path"] = "fit.nii.gz"
        manifest["files"][0]["file_id"] = 5305255
    elif mutation == "version":
        manifest["source_version"] = "latest"
    elif mutation == "doi":
        manifest["doi"] = "10.6084/m9.figshare.3395704"
    else:
        key, value = {
            "wrong_role": ("role", "bval"), "wrong_url": ("url", "https://example.org/data"),
            "wrong_mirror": ("mirror_url", "https://example.org/mirror"),
            "wrong_metadata": ("metadata_url", "https://api.figshare.com/v2/articles/3395704"),
            "wrong_file_id": ("file_id", 5305255),
        }[mutation]
        manifest["files"][0][key] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        fetch.stage_data(destination, path, source)
    assert not destination.exists()


@pytest.mark.parametrize("kind", ["valid", "truncated", "oversized", "corrupted"])
def test_download_is_bounded_and_verified(bundle, monkeypatch, kind):
    source, manifest, path, destination = bundle
    row = manifest["files"][0]
    content = (source / row["path"]).read_bytes()
    response = {"valid": content, "truncated": content[:-1], "oversized": content + b"x",
                "corrupted": b"x" * len(content)}[kind]
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(response))
    target = source.parent / "download.nii.gz"
    if kind == "valid":
        fetch.download_file(row, target)
        assert target.read_bytes() == content
    else:
        with pytest.raises(ValueError):
            fetch.download_file(row, target)


def test_only_documented_mirror_is_tried_on_transport_failure(bundle, monkeypatch):
    source, manifest, path, destination = bundle
    row = manifest["files"][0]
    content = (source / row["path"]).read_bytes()
    calls = []

    def open_url(url, **kwargs):
        calls.append(url)
        if url == row["url"]:
            raise urllib.error.HTTPError(url, 403, "stale signed redirect", {}, None)
        return io.BytesIO(content)

    monkeypatch.setattr(fetch.urllib.request, "urlopen", open_url)
    fetch.download_file(row, source.parent / "download.nii.gz")
    assert calls == [row["url"], row["mirror_url"]]


def test_exhausted_transports_fail_closed(bundle, monkeypatch):
    source, manifest, path, destination = bundle

    def fail_url(*args, **kwargs):
        raise urllib.error.URLError("unavailable")

    monkeypatch.setattr(fetch.urllib.request, "urlopen", fail_url)
    with pytest.raises(urllib.error.URLError):
        fetch.stage_data(destination, path)
    assert list(destination.iterdir()) == []
