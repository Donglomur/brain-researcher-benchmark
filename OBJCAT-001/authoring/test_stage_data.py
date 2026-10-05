"""Tiny offline stager fixtures; no public-source downloads or scientific fits."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest


TASK = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("objcat_source_stager", TASK / "environment/fetch_data.py")
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)


def record(path, payload, **kwargs):
    return dict(path=path, size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(), **kwargs)


@pytest.fixture
def tiny_manifest():
    payloads = {"subj2/bold.nii.gz": b"tiny original BOLD fixture", "subj2/labels.txt": b"labels chunks\nrest 0\n", "mask.nii.gz": b"tiny mask"}
    manifest = {"task_id": "OBJCAT-001", "dataset_id": "haxby2001", "subject": 2, "dataset_license": "CC-BY-SA-3.0", "mask_license": "not-established",
                "files": [record(path, payload, role=s.FILES[path], **({"url": s.MASK_URL} if path == "mask.nii.gz" else {"archive_member": path})) for path, payload in payloads.items()],
                "archive": record(s.ARCHIVE_NAME, b"archive", url=s.SOURCE_BASE + s.ARCHIVE_NAME, md5=s.ARCHIVE_MD5),
                "published_checksums": record("MD5SUMS", b"registry", url=s.SOURCE_BASE + "MD5SUMS")}
    return manifest, payloads


def fixture_inputs(tmp_path, monkeypatch, tiny_manifest):
    manifest, payloads = tiny_manifest
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    source = tmp_path / "source"
    for name, payload in payloads.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    monkeypatch.setattr(s, "read_manifest", lambda supplied: (manifest, path.read_bytes()))
    monkeypatch.setattr(s.urllib.request, "urlopen", lambda *args, **kwargs: pytest.fail("network forbidden in fixture"))
    return path, source, tmp_path / "destination", manifest


def test_verified_offline_source_copy_and_idempotence(tmp_path, monkeypatch, tiny_manifest):
    path, source, destination, manifest = fixture_inputs(tmp_path, monkeypatch, tiny_manifest)
    s.stage_data(destination, path, source)
    original_stats = {item["path"]: (destination / item["path"]).stat().st_ino for item in manifest["files"]}
    s.stage_data(destination, path)
    assert (destination / "data_manifest.json").read_bytes() == path.read_bytes()
    for item in manifest["files"]:
        s.verify_file(destination / item["path"], item)
        assert (destination / item["path"]).stat().st_ino == original_stats[item["path"]]


@pytest.mark.parametrize("conflict", ["source_bytes", "destination_bytes", "source_link", "target_link", "parent_link", "manifest_conflict"])
def test_preserves_conflicts_without_network_or_publication(tmp_path, monkeypatch, tiny_manifest, conflict):
    path, source, destination, manifest = fixture_inputs(tmp_path, monkeypatch, tiny_manifest)
    target = destination / "subj2/bold.nii.gz"
    if conflict == "source_bytes": (source / "subj2/bold.nii.gz").write_bytes(b"incorrect")
    elif conflict == "source_link":
        original = source / "subj2/bold.nii.gz"
        original.rename(source / "retained")
        original.symlink_to(source / "retained")
    elif conflict == "target_link":
        target.parent.mkdir(parents=True)
        target.symlink_to(source / "subj2/bold.nii.gz")
    elif conflict == "parent_link":
        destination.mkdir()
        (destination / "subj2").symlink_to(source / "subj2", target_is_directory=True)
    elif conflict == "destination_bytes":
        target.parent.mkdir(parents=True)
        target.write_bytes(b"user existing content")
    else:
        destination.mkdir()
        (destination / "data_manifest.json").write_bytes(b"existing metadata")
    with pytest.raises(ValueError): s.stage_data(destination, path, source)
    if conflict == "destination_bytes": assert target.read_bytes() == b"user existing content"
    if conflict == "manifest_conflict": assert (destination / "data_manifest.json").read_bytes() == b"existing metadata"
    assert not (destination / "mask.nii.gz").exists()


def test_manifest_full_hash_rejects_even_cosmetic_change(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_bytes(b"{}\n")
    with pytest.raises(ValueError, match="SHA256"):
        s.read_manifest(path)


def real_manifest():
    return json.loads((TASK / "environment/data_manifest.json").read_text())


def test_frozen_public_manifest_has_complete_pins():
    manifest, raw = s.read_manifest(TASK / "environment/data_manifest.json")
    s.validate_manifest(manifest)
    assert hashlib.sha256(raw).hexdigest() == s.MANIFEST_SHA256
    assert {item["path"] for item in manifest["files"]} == set(s.FILES)


@pytest.mark.parametrize("mutation", ["subject", "license", "mask_license", "extra_file", "path", "role", "mask_url", "archive_url", "md5", "size", "sha", "member"])
def test_manifest_identity_drift_rejected(mutation):
    manifest = real_manifest()
    if mutation == "subject": manifest["subject"] = 1
    elif mutation == "license": manifest["dataset_license"] = "BSD"
    elif mutation == "mask_license": manifest["mask_license"] = "BSD"
    elif mutation == "extra_file": manifest["files"].append(copy.deepcopy(manifest["files"][0]))
    elif mutation == "path": manifest["files"][0]["path"] = "../escape"
    elif mutation == "role": manifest["files"][0]["role"] = "anat"
    elif mutation == "mask_url": next(item for item in manifest["files"] if item["role"] == "mask")["url"] = "https://example.org/other"
    elif mutation == "archive_url": manifest["archive"]["url"] = "http://example.org/other"
    elif mutation == "md5": manifest["archive"]["md5"] = "0" * 32
    elif mutation == "size": manifest["archive"]["size_bytes"] = True
    elif mutation == "sha": manifest["archive"]["sha256"] = "NO_HASH"
    else: next(item for item in manifest["files"] if item["role"] == "bold")["archive_member"] = "subj2/anat.nii.gz"
    with pytest.raises(ValueError): s.validate_manifest(manifest)


def tar_fixture(path, entries):
    with tarfile.open(path, "w:gz") as archive:
        for name, payload, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "symlink": info.type, info.linkname = tarfile.SYMTYPE, "/outside"
            elif kind == "hardlink": info.type, info.linkname = tarfile.LNKTYPE, "subj2/bold.nii.gz"
            elif kind == "directory": info.type = tarfile.DIRTYPE
            else: info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload) if kind == "file" else None)


def extraction_records():
    return [record(name, payload, archive_member=name) for name, payload in
            (("subj2/bold.nii.gz", b"BOLD"), ("subj2/labels.txt", b"labels"))]


def test_extracts_only_allowlisted_regular_members(tmp_path):
    path = tmp_path / "archive.tar.gz"
    tar_fixture(path, [("subj2", b"", "directory"), ("subj2/bold.nii.gz", b"BOLD", "file"),
                       ("subj2/labels.txt", b"labels", "file"), ("subj2/anat.nii.gz", b"do not extract", "file")])
    out = s.extract_allowlisted(path, extraction_records(), tmp_path / "members")
    assert set(out) == {"subj2/bold.nii.gz", "subj2/labels.txt"}
    assert not (tmp_path / "members/subj2/anat.nii.gz").exists()


@pytest.mark.parametrize("name,kind", [("../escape", "file"), ("/absolute", "file"), ("subj2\\escape", "file"),
                                       ("subj2/link", "symlink"), ("subj2/link", "hardlink")])
def test_unsafe_archive_member_rejected_even_when_not_requested(tmp_path, name, kind):
    path = tmp_path / "archive.tar.gz"
    tar_fixture(path, [(name, b"bad", kind), ("subj2/bold.nii.gz", b"BOLD", "file"), ("subj2/labels.txt", b"labels", "file")])
    with pytest.raises(ValueError): s.extract_allowlisted(path, extraction_records(), tmp_path / "members")


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "changed_bytes", "changed_size", "unsafe_record"])
def test_archive_integrity_and_membership(tmp_path, mutation):
    entries = [("subj2/bold.nii.gz", b"BOLD", "file"), ("subj2/labels.txt", b"labels", "file")]
    records = extraction_records()
    if mutation == "duplicate": entries.append(entries[0])
    elif mutation == "missing": entries.pop()
    elif mutation == "changed_bytes": entries[0] = ("subj2/bold.nii.gz", b"FAKE", "file")
    elif mutation == "changed_size": entries[0] = ("subj2/bold.nii.gz", b"FAKE_LONG", "file")
    else: records[0]["path"] = "../escape"
    path = tmp_path / "archive.tar.gz"
    tar_fixture(path, entries)
    with pytest.raises(ValueError): s.extract_allowlisted(path, records, tmp_path / "members")


class Response(io.BytesIO):
    def __init__(self, payload, url, status=200, headers=None):
        super().__init__(payload)
        self.url, self.status = url, status
        self.headers = {"Content-Length": str(len(payload)), **(headers or {})}
    def geturl(self): return self.url


def test_one_serial_download_verified_and_prior_attempt_preserved(tmp_path, monkeypatch):
    payload = b"tiny transport"
    item = record("mask.nii.gz", payload, url=s.MASK_URL)
    calls = []
    def opener(request, timeout):
        assert "Range" not in request.headers and request.headers["Accept-encoding"] == "identity"
        calls.append(request.full_url)
        return Response(payload, item["url"])
    monkeypatch.setattr(s.urllib.request, "urlopen", opener)
    ledger = tmp_path / "download"
    received = s.download_sources([item], ledger)
    s.verify_file(received["mask.nii.gz"], item)
    receipt = json.loads((ledger / "result.json").read_text())
    assert receipt["status"] == "verified" and receipt["transferred_bytes"] == len(payload)
    with pytest.raises(FileExistsError): s.download_sources([item], ledger)
    assert calls == [s.MASK_URL]


@pytest.mark.parametrize("failure", ["truncated", "oversized", "wrong_hash", "status", "redirect", "encoded", "length", "timeout", "budget"])
def test_failed_transfer_receipt_and_no_retry(tmp_path, monkeypatch, failure):
    payload = b"transport"
    item = record("mask.nii.gz", payload, url=s.MASK_URL)
    calls = []
    def opener(request, timeout):
        calls.append(request.full_url)
        if failure == "timeout": raise TimeoutError("fixture timeout")
        actual = payload[:-1] if failure == "truncated" else payload + b"extra" if failure == "oversized" else b"corruptxx" if failure == "wrong_hash" else payload
        return Response(actual, "http://unexpected" if failure == "redirect" else s.MASK_URL,
                        206 if failure == "status" else 200,
                        {"Content-Length": "99" if failure == "length" else str(len(payload)),
                         **({"Content-Encoding": "gzip"} if failure == "encoded" else {})})
    monkeypatch.setattr(s.urllib.request, "urlopen", opener)
    if failure == "budget": monkeypatch.setattr(s, "CAP_BYTES", 3)
    ledger = tmp_path / "download"
    with pytest.raises((ValueError, TimeoutError)): s.download_sources([item], ledger)
    before = (ledger / "result.json").read_bytes()
    assert json.loads(before)["status"] == "failed"
    with pytest.raises(FileExistsError): s.download_sources([item], ledger)
    assert (ledger / "result.json").read_bytes() == before and len(calls) == 1


def test_registry_subject2_checksum_exact_and_unique(tmp_path):
    path = tmp_path / "MD5SUMS"
    line = s.ARCHIVE_MD5 + "  " + s.ARCHIVE_NAME + "\n"
    path.write_text(line)
    s.verify_registry(path)
    path.write_text(line * 2)
    with pytest.raises(ValueError): s.verify_registry(path)
    path.write_text("0" * 32 + "  " + s.ARCHIVE_NAME + "\n")
    with pytest.raises(ValueError): s.verify_registry(path)


def test_no_digestless_verification(tmp_path):
    path = tmp_path / "source"
    path.write_bytes(b"x")
    with pytest.raises(ValueError, match="SHA256"):
        s.verify_file(path, {"size_bytes": 1})
