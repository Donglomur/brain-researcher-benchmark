"""Offline unit tests for staging mechanics; fake payloads are not EEG evidence."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest


TASK = Path(__file__).resolve().parents[1]
ENVIRONMENT = TASK / "environment"
PINNED_PATHS = {
    f"S{subject:03d}/S{subject:03d}R{run:02d}.edf"
    for subject in range(1, 6) for run in (1, 2)
}


@pytest.fixture
def staging():
    spec = importlib.util.spec_from_file_location("alphaband_fetch_data", ENVIRONMENT / "fetch_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_bundle(tmp_path):
    manifest = json.loads((ENVIRONMENT / "data_manifest.json").read_text())
    payloads = {path: f"unit-test payload for {path}".encode() for path in manifest["files"]}
    manifest["files"] = {path: hashlib.sha256(payload).hexdigest() for path, payload in payloads.items()}
    path = tmp_path / "unit_manifest.json"
    path.write_text(json.dumps(manifest))
    return path, manifest, payloads


def test_public_manifest_pins_only_the_requested_ten_recordings():
    manifest = json.loads((ENVIRONMENT / "data_manifest.json").read_text())
    assert manifest["version"] == "1.0.0"
    assert manifest["base_url"] == "https://physionet.org/files/eegmmidb/1.0.0/"
    assert set(manifest["files"]) == PINNED_PATHS
    assert len(manifest["files"]) == 10
    for digest in manifest["files"].values():
        assert len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


def test_downloads_only_allowlisted_paths_and_checks_every_payload(staging, fake_bundle, tmp_path, monkeypatch):
    manifest_path, manifest, payloads = fake_bundle
    calls = []

    def fake_urlopen(url, timeout):
        assert 0 < timeout <= 60
        relative = url.removeprefix(manifest["base_url"])
        assert relative in PINNED_PATHS
        calls.append(relative)
        return io.BytesIO(payloads[relative])

    monkeypatch.setattr(staging, "urlopen", fake_urlopen)
    destination = tmp_path / "bundle"
    staging.acquire(manifest_path, destination)
    assert set(calls) == PINNED_PATHS and len(calls) == 10
    for path, payload in payloads.items():
        assert (destination / path).read_bytes() == payload
    assert (destination / "data_manifest.json").read_bytes() == manifest_path.read_bytes()


def test_verified_existing_bundle_needs_no_network(staging, fake_bundle, tmp_path, monkeypatch):
    manifest_path, _, payloads = fake_bundle
    destination = tmp_path / "bundle"
    for path, payload in payloads.items():
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    def no_download(*args, **kwargs):
        raise AssertionError("a complete verified bundle must not need a download")

    monkeypatch.setattr(staging, "urlopen", no_download)
    staging.acquire(manifest_path, destination)
    for path, payload in payloads.items():
        assert (destination / path).read_bytes() == payload


def test_corrupt_existing_recording_is_not_overwritten(staging, fake_bundle, tmp_path, monkeypatch):
    manifest_path, _, payloads = fake_bundle
    first_path = next(iter(payloads))
    destination = tmp_path / "bundle"
    target = destination / first_path
    target.parent.mkdir(parents=True)
    original = b"existing corrupt or user-owned bytes"
    target.write_bytes(original)

    def no_download(*args, **kwargs):
        raise AssertionError("corrupt existing input must fail before a download")

    monkeypatch.setattr(staging, "urlopen", no_download)
    with pytest.raises(ValueError, match="checksum mismatch"):
        staging.acquire(manifest_path, destination)
    assert target.read_bytes() == original
    assert not (destination / "data_manifest.json").exists()


def test_bad_download_is_rejected_before_writing_recording(staging, fake_bundle, tmp_path, monkeypatch):
    manifest_path, _, payloads = fake_bundle
    destination = tmp_path / "bundle"
    monkeypatch.setattr(staging, "urlopen", lambda *args, **kwargs: io.BytesIO(b"wrong download bytes"))
    with pytest.raises(ValueError, match="checksum mismatch downloading"):
        staging.acquire(manifest_path, destination)
    assert not (destination / next(iter(payloads))).exists()
    assert not (destination / "data_manifest.json").exists()
