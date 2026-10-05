"""Build-source boundary tests using small bytes, never substitute sleep data."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

ENVIRONMENT = Path(__file__).resolve().parents[1] / "environment"
spec = importlib.util.spec_from_file_location("sleep_source_fetch", ENVIRONMENT / "fetch_data.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


@pytest.fixture
def bundle(tmp_path):
    manifest = json.loads((ENVIRONMENT / "data_manifest.json").read_text())
    source = tmp_path / "source"
    source.mkdir()
    for row in manifest["files"]:
        content = (row["path"] + " small source boundary fixture").encode()
        (source / row["path"]).write_bytes(content)
        row["size_bytes"] = len(content)
        row["sha256"] = hashlib.sha256(content).hexdigest()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return source, manifest, path, tmp_path / "staged"


def test_verified_bundle_has_exact_members_and_manifest(bundle):
    source, manifest, path, destination = bundle
    fetch.stage_data(destination, path, source)
    assert {p.name for p in destination.iterdir()} == set(fetch.SOURCE_FILES) | {"data_manifest.json"}
    for row in manifest["files"]:
        assert (destination / row["path"]).read_bytes() == (source / row["path"]).read_bytes()


@pytest.mark.parametrize("kind", ["same_size_corruption", "truncated"])
def test_changed_member_rejected_before_bundle_publication(bundle, kind):
    source, manifest, path, destination = bundle
    row = manifest["files"][-1]
    target = source / row["path"]
    target.write_bytes(b"x" * (row["size_bytes"] if kind == "same_size_corruption" else 1))
    with pytest.raises(ValueError, match="mismatch"):
        fetch.stage_data(destination, path, source)
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "traversal", "wrong_subject", "wrong_role", "wrong_recording", "wrong_url", "wrong_transport"])
def test_manifest_cannot_change_source_membership(bundle, mutation):
    source, manifest, path, destination = bundle
    if mutation == "missing":
        manifest["files"].pop()
    elif mutation == "duplicate":
        manifest["files"][-1] = manifest["files"][0].copy()
    elif mutation == "traversal":
        manifest["files"][0]["path"] = "../outside.edf"
    else:
        key, value = {"wrong_subject": ("subject", 99), "wrong_role": ("role", "hypnogram"),
                      "wrong_recording": ("recording", 2), "wrong_url": ("url", "https://example.org/unknown.edf"),
                      "wrong_transport": ("transport_url", "https://example.org/unknown.edf")}[mutation]
        manifest["files"][0][key] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        fetch.stage_data(destination, path, source)
    assert not destination.exists()


@pytest.mark.parametrize("kind", ["valid", "truncated", "oversized", "corrupted"])
def test_download_checks_size_and_digest(bundle, monkeypatch, kind):
    source, manifest, path, destination = bundle
    row = manifest["files"][0]
    content = (source / row["path"]).read_bytes()
    response = {"valid": content, "truncated": content[:-1], "oversized": content + b"x",
                "corrupted": b"x" * len(content)}[kind]
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(response))
    target = source.parent / "download.edf"
    if kind == "valid":
        fetch.download_file(row, target)
        assert target.read_bytes() == content
    else:
        with pytest.raises(ValueError):
            fetch.download_file(row, target)
