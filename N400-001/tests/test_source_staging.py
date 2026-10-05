"""Synthetic bytes only. No network, original EEG, or analysis work."""
import copy
import hashlib
import io
import json
import time

import pytest

import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "environment" / "fetch_data.py"
SPEC = importlib.util.spec_from_file_location("source_fetch", MODULE)
acquisition = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acquisition)


def entry_for(body=b"synthetic original bytes"):
    return dict(subject=1, name="1_N400_shifted_ds.set", file_id="5f1694d20596f601307a31c0", version=1,
                size_bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), md5=hashlib.md5(body).hexdigest(),
                download_url="https://osf.io/download/as6c2/?revision=1")


class Response(io.BytesIO):
    def __init__(self, body=b"", code=200, headers=None):
        super().__init__(body)
        self.code = code
        self.headers = {"Content-Length": str(len(body)), **(headers or {})}
        self.read_calls = 0

    def read(self, n=-1):
        self.read_calls += 1
        return super().read(n)


class Opener:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request.full_url)
        if not self.responses:
            raise AssertionError("Unexpected retry/request")
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def budget(**kwargs):
    return dict(used=0, cap=220000000, deadline=time.monotonic() + 10, **kwargs)


def test_exact_original_inventory_is_pinned():
    files = acquisition.read_manifest()[0]["files"]
    assert len(files) == 24
    assert sum(f["size_bytes"] for f in files) == 197427832


def test_changed_metadata_is_not_repinned(tmp_path):
    path = tmp_path / "changed.json"
    path.write_text("{}")
    with pytest.raises(ValueError, match="no pin refresh"):
        acquisition.read_manifest(path)


def test_full_verified_body_promoted_atomically(tmp_path):
    body = b"synthetic original bytes"
    entry = entry_for(body)
    ledger, allowance = [], budget()
    opener = Opener(Response(body))
    row = acquisition.transfer_file(entry, tmp_path, ledger, allowance, opener)
    assert (tmp_path / entry["name"]).read_bytes() == body
    assert not (tmp_path / (entry["name"] + ".partial")).exists()
    assert row["status"] == "verified" and allowance["used"] == len(body)
    assert len(opener.requests) == 1


def test_observed_official_redirects_only_and_no_sensitive_logs(tmp_path):
    body = b"synthetic original bytes"
    entry = entry_for(body)
    waterbutler = f"https://files.osf.io/v1/resources/29xpq/providers/osfstorage/{entry['file_id']}?version=1"
    storage = f"https://storage.googleapis.com/cos-osf-prod-files-us-east1/{entry['sha256']}?Signature=do-not-log&GoogleAccessId=do-not-log"
    redirect1 = Response(b"do not read", 302, {"Location": waterbutler, "Set-Cookie": "do-not-log"})
    redirect2 = Response(b"do not read", 302, {"Location": storage, "Authorization": "do-not-log"})
    ledger = []
    opener = Opener(redirect1, redirect2, Response(body, headers={"Set-Cookie": "do-not-log"}))
    acquisition.transfer_file(entry, tmp_path, ledger, budget(), opener)
    assert redirect1.read_calls == redirect2.read_calls == 0
    assert "do-not-log" not in json.dumps(ledger)
    assert len(opener.requests) == 3
    assert ledger[0]["redirect_chain"][-1]["endpoint"]["query_parameter_names"] == ["GoogleAccessId", "Signature"]


@pytest.mark.parametrize("url", [
    "http://osf.io/download/as6c2/?revision=1", "https://attacker.test/file", "https://osf.io.attacker.test/file",
    "https://user:pass@osf.io/download/as6c2/?revision=1", "https://osf.io:444/download/as6c2/?revision=1",
    "https://files.osf.io/v1/resources/WRONG/providers/osfstorage/5f1694d20596f601307a31c0?version=1",
    "https://files.osf.io/v1/resources/29xpq/providers/osfstorage/5f1694d20596f601307a31c0?version=2",
    "https://storage.googleapis.com/cos-osf-prod-files-us-east1/wrong",
])
def test_unapproved_redirect_fails_before_next_request(tmp_path, url):
    response = Response(b"unused", 302, {"Location": url})
    opener, ledger = Opener(response), []
    with pytest.raises(RuntimeError, match="sanitized receipt"):
        acquisition.transfer_file(entry_for(), tmp_path, ledger, budget(), opener)
    assert len(opener.requests) == 1 and response.read_calls == 0
    assert ledger[0]["measured_bytes"] == 0


def test_google_redirect_must_follow_actual_files_osf_response(tmp_path):
    entry = entry_for()
    url = f"https://storage.googleapis.com/cos-osf-prod-files-us-east1/{entry['sha256']}"
    opener = Opener(Response(b"", 302, {"Location": url}))
    with pytest.raises(RuntimeError):
        acquisition.transfer_file(entry, tmp_path, [], budget(), opener)
    assert len(opener.requests) == 1


@pytest.mark.parametrize("code,headers", [(404, {}), (206, {}), (200, {"Content-Length": "1"}), (200, {"Content-Encoding": "gzip"})])
def test_bad_response_rejected_before_body(tmp_path, code, headers):
    response = Response(b"synthetic original bytes", code, headers)
    opener, ledger = Opener(response), []
    with pytest.raises(RuntimeError):
        acquisition.transfer_file(entry_for(), tmp_path, ledger, budget(), opener)
    assert response.read_calls == 0 and len(opener.requests) == 1


@pytest.mark.parametrize("body", [b"short", b"synthetic original wrong", b"synthetic original bytesMORE"])
def test_wrong_body_preserves_partial_without_retry(tmp_path, body):
    entry = entry_for()
    opener = Opener(Response(body, headers={"Content-Length": str(entry["size_bytes"])}))
    ledger = []
    with pytest.raises(RuntimeError):
        acquisition.transfer_file(entry, tmp_path, ledger, budget(), opener)
    assert (tmp_path / (entry["name"] + ".partial")).exists()
    assert not (tmp_path / entry["name"]).exists()
    assert ledger[0]["status"] == "failed" and len(opener.requests) == 1


def test_aggregate_budget_stops_body(tmp_path):
    allowance = budget()
    allowance["cap"] = 4
    with pytest.raises(RuntimeError):
        acquisition.transfer_file(entry_for(), tmp_path, [], allowance, Opener(Response(b"synthetic original bytes")))
    assert allowance["used"] == 4


def test_expired_deadline_stops_before_body(tmp_path):
    allowance = budget()
    allowance["deadline"] = time.monotonic() - 1
    response = Response(b"synthetic original bytes")
    with pytest.raises(RuntimeError):
        acquisition.transfer_file(entry_for(), tmp_path, [], allowance, Opener(response))
    assert response.read_calls == 0


@pytest.mark.parametrize("suffix", ["", ".partial"])
def test_existing_evidence_is_preserved(tmp_path, suffix):
    path = tmp_path / (entry_for()["name"] + suffix)
    path.write_bytes(b"keep")
    opener = Opener()
    with pytest.raises(FileExistsError):
        acquisition.transfer_file(entry_for(), tmp_path, [], budget(), opener)
    assert path.read_bytes() == b"keep" and not opener.requests


def test_symlink_destination_refused(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="Symlink"):
        acquisition.transfer_file(entry_for(), link, [], budget(), Opener())


def test_original_verification_both_hashes(tmp_path):
    body = b"synthetic original bytes"
    entry = entry_for(body)
    path = tmp_path / entry["name"]
    path.write_bytes(body)
    acquisition.verify_file(path, entry)
    wrong = copy.deepcopy(entry)
    wrong["md5"] = "0" * 32
    with pytest.raises(ValueError, match="checksum"):
        acquisition.verify_file(path, wrong)


def test_upstream_exception_signed_url_not_retained(tmp_path):
    ledger = []
    with pytest.raises(RuntimeError) as captured:
        acquisition.transfer_file(entry_for(), tmp_path, ledger, budget(), Opener(OSError("secret Signature=token")))
    assert "token" not in str(captured.value) and "token" not in json.dumps(ledger)


@pytest.fixture
def tiny_sources(tmp_path, monkeypatch):
    manifest, _ = acquisition.read_manifest()
    source = tmp_path / "originals"
    source.mkdir()
    for entry in manifest["files"]:
        body = ("fixture:" + entry["path"]).encode()
        (source / entry["path"]).write_bytes(body)
        entry.update(size_bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), md5=hashlib.md5(body).hexdigest())
    raw = (json.dumps(manifest, indent=2) + "\n").encode()
    path = tmp_path / "fixture_manifest.json"
    path.write_bytes(raw)
    monkeypatch.setattr(acquisition, "MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())
    return source, path, manifest


def test_full_local_staging_exact_inventory_no_network(tiny_sources, tmp_path, monkeypatch):
    source, manifest_path, manifest = tiny_sources
    monkeypatch.setattr(acquisition.urllib.request, "build_opener", lambda *args: pytest.fail("Local staging must be offline"))
    destination = tmp_path / "stage"
    result = acquisition.stage_data(destination, source, manifest_path)
    assert result["status"] == "verified"
    assert len(list(destination.iterdir())) == 25
    assert acquisition.verify_staged(destination) == manifest
    assert acquisition.stage_data(destination, source, manifest_path)["status"] == "existing_verified"


@pytest.mark.parametrize("kind", ["wronghash", "missing", "wrongsize", "symlink"])
def test_local_original_mismatch_fails_closed(tiny_sources, tmp_path, kind):
    source, path, manifest = tiny_sources
    file = source / manifest["files"][0]["path"]
    if kind == "wronghash":
        file.write_bytes(b"x" * file.stat().st_size)
    elif kind == "missing":
        file.unlink()
    elif kind == "wrongsize":
        file.write_bytes(b"x")
    else:
        target = source / "target"
        file.rename(target)
        file.symlink_to(target)
    with pytest.raises(RuntimeError):
        acquisition.stage_data(tmp_path / "stage", source, path)
    assert json.loads((tmp_path / "stage_staging_receipt.json").read_text())["status"] == "failed"


@pytest.mark.parametrize("kind", ["extra", "stale", "symlink", "wrongmanifest"])
def test_existing_stage_not_overwritten(tiny_sources, tmp_path, kind):
    source, path, manifest = tiny_sources
    destination = tmp_path / "stage"
    acquisition.stage_data(destination, source, path)
    if kind == "extra":
        (destination / "answer.json").write_text("{}")
    elif kind == "wrongmanifest":
        (destination / acquisition.MANIFEST_NAME).write_text("{}")
    else:
        file = destination / manifest["files"][0]["path"]
        if kind == "stale":
            file.write_bytes(b"x" * file.stat().st_size)
        else:
            file.unlink()
            file.symlink_to(source / manifest["files"][0]["path"])
    with pytest.raises(ValueError):
        acquisition.stage_data(destination, source, path)
    if kind == "extra":
        assert (destination / "answer.json").read_text() == "{}"


def test_receipt_cannot_be_inside_runtime_source(tiny_sources, tmp_path):
    source, path, _ = tiny_sources
    with pytest.raises(ValueError, match="outside runtime"):
        acquisition.stage_data(tmp_path / "stage", source, path, tmp_path / "stage" / "receipt.json")


def test_failed_build_emits_safe_receipt_without_signed_exception(tiny_sources, tmp_path, monkeypatch, capsys):
    _, path, _ = tiny_sources
    opener = Opener(OSError("https://storage.googleapis.com/file?Signature=secret-token"))
    monkeypatch.setattr(acquisition.urllib.request, "build_opener", lambda *args: opener)
    with pytest.raises(RuntimeError):
        acquisition.stage_data(tmp_path / "stage", manifest_path=path)
    error = capsys.readouterr().err
    assert "secret-token" not in error and "Signature=" not in error
    record = json.loads(error)
    assert record["status"] == "failed" and record["files"][0]["error_type"] == "OSError"
    assert record["body_bytes"] == 0 and len(opener.requests) == 1
