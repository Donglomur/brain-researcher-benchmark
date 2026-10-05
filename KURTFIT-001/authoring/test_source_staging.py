"""Small fixtures test immutable-input handling, not diffusion reconstruction."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

ENVIRONMENT = Path(__file__).resolve().parents[1] / "environment"
spec = importlib.util.spec_from_file_location("cfin_source_fetch", ENVIRONMENT / "fetch_data.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


@pytest.fixture
def bundle(tmp_path):
    manifest = json.loads((ENVIRONMENT / "data_manifest.json").read_text())
    source = tmp_path / "source"
    source.mkdir()
    for row in manifest["files"]:
        content = (row["path"] + " small boundary-test fixture").encode()
        (source / row["path"]).write_bytes(content)
        row["size_bytes"] = len(content)
        row["md5"] = hashlib.md5(content).hexdigest()
        row["sha256"] = hashlib.sha256(content).hexdigest()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return source, manifest, path, tmp_path / "staged"


def test_exact_verified_bundle_is_published(bundle):
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


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "traversal", "wrong_role", "wrong_url", "wrong_metadata_url"])
def test_manifest_cannot_change_source_identity(bundle, mutation):
    source, manifest, path, destination = bundle
    if mutation == "missing":
        manifest["files"].pop()
    elif mutation == "duplicate":
        manifest["files"][-1] = manifest["files"][0].copy()
    elif mutation == "traversal":
        manifest["files"][0]["path"] = "../outside.nii"
    else:
        key, value = {"wrong_role": ("role", "bval"), "wrong_url": ("url", "https://example.org/data"),
                      "wrong_metadata_url": ("metadata_url", "https://example.org/metadata")}[mutation]
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
    target = source.parent / "download.nii"
    if kind == "valid":
        fetch.download_file(row, target)
        assert target.read_bytes() == content
    else:
        with pytest.raises(ValueError):
            fetch.download_file(row, target)
