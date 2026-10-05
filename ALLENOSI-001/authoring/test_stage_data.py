"""Tiny source-staging fixtures; no NWB reads, scientific processing, or downloads."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

ENV = Path(__file__).parents[1]/"environment"
SPEC = importlib.util.spec_from_file_location("allenosi_fetch", ENV/"fetch_data.py")
fetch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch)


def manifest():
    return json.loads((ENV/"data_manifest.json").read_text())


def tiny(tmp_path):
    source = manifest(); record = source["files"][0]
    payload = b"tiny source-transfer fixture; not NWB\n"
    record.update(size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    directory = tmp_path/"original"; directory.mkdir()
    (directory/fetch.FILENAME).write_bytes(payload)
    return source, directory, payload


class Response(io.BytesIO):
    def __init__(self, payload, record, headers=None, status=200, url=None):
        super().__init__(payload)
        self.status = status
        self.url = record["transport_url"] if url is None else url
        self.headers = {"Content-Length": str(record["size_bytes"]), "ETag": '"'+record["dandi_etag"]+'"',
                        "x-amz-version-id": record["s3_version_id"], "Content-Encoding": "identity"}
        if headers: self.headers.update(headers)

    def geturl(self):
        return self.url


def test_whole_manifest_pin_and_exact_single_asset():
    source, raw = fetch.read_manifest(ENV/"data_manifest.json")
    assert hashlib.sha256(raw).hexdigest() == fetch.MANIFEST_SHA256
    assert len(source["files"]) == 1
    assert source["files"][0]["size_bytes"] == 1736516600
    assert source["license"] == "CC-BY-4.0"
    assert "noncommercial" in source["license_scope_note"]


@pytest.mark.parametrize("key", ["task_id", "dandiset_id", "dandiset_version", "doi", "version_metadata_url", "license", "additional_terms_url"])
def test_release_and_both_license_notices_are_fixed(key):
    source = manifest(); source[key] = "incorrect"
    with pytest.raises(ValueError): fetch.validate_manifest(source)


@pytest.mark.parametrize("key", list(fetch.PIN))
def test_every_source_identity_field_is_fixed(key):
    source = manifest(); source["files"][0][key] = "incorrect"
    with pytest.raises(ValueError): fetch.validate_manifest(source)


@pytest.mark.parametrize("mutation", ["extra", "missing", "traversal", "absolute"])
def test_no_other_asset_or_unsafe_path(mutation):
    source = manifest()
    if mutation == "extra": source["files"].append(copy.deepcopy(source["files"][0]))
    elif mutation == "missing": source["files"] = []
    else: source["files"][0]["path"] = "../outside" if mutation == "traversal" else "/outside"
    with pytest.raises(ValueError): fetch.validate_manifest(source)


def test_manifest_cannot_silently_refresh_or_change_terms(tmp_path):
    source = manifest(); source["license_scope_note"] = "unrestricted"
    path = tmp_path/"manifest.json"; path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="manifest SHA256"): fetch.read_manifest(path)


@pytest.mark.parametrize("kind", ["size", "digest", "symlink", "directory"])
def test_source_file_integrity_and_type(tmp_path, kind):
    source, directory, payload = tiny(tmp_path); record = source["files"][0]; path = directory/fetch.FILENAME
    if kind == "size": path.write_bytes(payload+b"x")
    elif kind == "digest": path.write_bytes(b"x"*len(payload))
    elif kind == "symlink":
        link = tmp_path/"link"; link.symlink_to(path); path = link
    else: path = directory
    with pytest.raises(ValueError): fetch.verify_file(path, record)


@pytest.mark.parametrize("kind", ["status", "redirect", "length", "etag", "version", "encoding", "truncated", "oversized", "digest", "timeout"])
def test_download_failures_preserve_attempt_and_block_retry(tmp_path, monkeypatch, kind):
    source, directory, payload = tiny(tmp_path); record = source["files"][0]
    options = {}
    if kind == "status": options["status"] = 206
    elif kind == "redirect": options["url"] = "https://example.invalid/other"
    elif kind in ("length", "etag", "version", "encoding"):
        header = {"length": "Content-Length", "etag": "ETag", "version": "x-amz-version-id", "encoding": "Content-Encoding"}[kind]
        options["headers"] = {header: "0" if kind == "length" else "incorrect"}
    elif kind == "truncated": payload = payload[:-1]
    elif kind == "oversized": payload += b"x"
    elif kind == "digest": payload = b"x"*len(payload)
    count = []
    def open_response(request, **kwargs):
        count.append(request)
        if kind == "timeout": raise TimeoutError("fixture timeout")
        return Response(payload, record, **options)
    monkeypatch.setattr(fetch.urllib.request, "urlopen", open_response)
    ledger = tmp_path/"attempt"
    with pytest.raises((ValueError, TimeoutError)): fetch.download_file(record, ledger)
    assert json.loads((ledger/"result.json").read_text())["status"] == "failed"
    with pytest.raises(FileExistsError): fetch.download_file(record, ledger)
    assert len(count) == 1


def test_success_has_published_identity_guards_and_no_range(tmp_path, monkeypatch):
    source, directory, payload = tiny(tmp_path); record = source["files"][0]
    calls = []
    def open_response(request, **kwargs):
        calls.append(request)
        return Response(payload, record)
    monkeypatch.setattr(fetch.urllib.request, "urlopen", open_response)
    ledger = tmp_path/"attempt"
    result = fetch.download_file(record, ledger)
    assert result.read_bytes() == payload
    receipt = json.loads((ledger/"result.json").read_text())
    assert receipt["status"] == "sha256_verified" and receipt["transferred_bytes"] == len(payload)
    assert calls[0].get_header("Range") is None
    assert calls[0].get_header("If-match") == '"'+record["dandi_etag"]+'"'


def test_cumulative_cap_applies_before_publication(tmp_path, monkeypatch):
    source, directory, payload = tiny(tmp_path); record = source["files"][0]
    monkeypatch.setattr(fetch, "CAP_BYTES", len(payload)-1)
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **kw: Response(payload, record))
    with pytest.raises(ValueError, match="budget"): fetch.download_file(record, tmp_path/"attempt")


def test_local_reuse_and_completed_destination_never_download(tmp_path, monkeypatch):
    source, directory, payload = tiny(tmp_path)
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture manifest"))
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("Unexpected network"))
    destination = tmp_path/"staged"; source_mode = (directory/fetch.FILENAME).stat().st_mode
    fetch.stage_data(destination, tmp_path/"unused", directory)
    fetch.stage_data(destination, tmp_path/"unused")
    assert (destination/fetch.FILENAME).read_bytes() == payload
    assert (destination/fetch.FILENAME).stat().st_mode & 0o222 == 0
    assert (directory/fetch.FILENAME).stat().st_mode == source_mode


@pytest.mark.parametrize("kind", ["file", "manifest", "target_symlink", "destination_symlink", "parent_symlink"])
def test_conflicting_destinations_preserved_without_network(tmp_path, monkeypatch, kind):
    source, directory, payload = tiny(tmp_path)
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture manifest"))
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("Unexpected network"))
    destination = tmp_path/"staged"
    if kind in ("destination_symlink", "parent_symlink"):
        destination.symlink_to(directory, target_is_directory=True)
        if kind == "parent_symlink": destination = destination/"child"
    else:
        destination.mkdir()
        if kind == "file": (destination/fetch.FILENAME).write_bytes(b"preserve")
        elif kind == "manifest": (destination/"data_manifest.json").write_bytes(b"preserve")
        else: (destination/fetch.FILENAME).symlink_to(directory/fetch.FILENAME)
    with pytest.raises(ValueError): fetch.stage_data(destination, tmp_path/"unused", directory)
    assert (directory/fetch.FILENAME).read_bytes() == payload
    if kind == "file": assert (destination/fetch.FILENAME).read_bytes() == b"preserve"
    if kind == "manifest": assert (destination/"data_manifest.json").read_bytes() == b"preserve"


def test_corrupt_local_source_publishes_nothing(tmp_path, monkeypatch):
    source, directory, payload = tiny(tmp_path)
    (directory/fetch.FILENAME).write_bytes(b"x"*len(payload))
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture manifest"))
    destination = tmp_path/"staged"
    with pytest.raises(ValueError): fetch.stage_data(destination, tmp_path/"unused", directory)
    assert not destination.exists()


def test_successful_download_staging_preserves_owned_transfer_receipt(tmp_path, monkeypatch):
    source, directory, payload = tiny(tmp_path); record = source["files"][0]
    monkeypatch.setattr(fetch, "read_manifest", lambda _: (source, b"fixture manifest"))
    monkeypatch.setattr(fetch.urllib.request, "urlopen", lambda *a, **kw: Response(payload, record))
    destination, ledger = tmp_path/"staged", tmp_path/"attempt"
    fetch.stage_data(destination, tmp_path/"unused", ledger=ledger)
    assert (destination/fetch.FILENAME).read_bytes() == payload
    assert (destination/fetch.FILENAME).stat().st_ino == (ledger/"payload.partial").stat().st_ino
    assert json.loads((ledger/"result.json").read_text())["transferred_bytes"] == len(payload)
