"""Manufactured bytes only. Never access an original source or the network."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat

import pytest

SPEC = importlib.util.spec_from_file_location("netseg_stage", Path(__file__).parents[1] / "environment" / "stage_data.py")
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)


def digest_record(path, data, osf=True):
    row = {"path": path, "role": "bold", "participant_id": "synthetic", "size_bytes": len(data),
           "sha256": hashlib.sha256(data).hexdigest(), "md5": hashlib.md5(data).hexdigest(),
           "git_blob_sha1": hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()}
    if osf:
        row.update(source_url="https://osf.io/download/abcde/?revision=2", source_guid="abcde",
                   source_version=2, osf_object_id="a" * 24)
    else:
        row.update(source_commit="c" * 40, source_url="https://raw.githubusercontent.com/owner/repo/" + "c" * 40 + "/x")
    return row


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    data = b"manufactured source only\n"
    (source / "tiny.bin").write_bytes(data)
    rows = [digest_record("tiny.bin", data)]
    manifest = {"n_files": 1, "total_bytes": len(data), "files": rows}
    body = json.dumps(manifest).encode()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(body)
    monkeypatch.setattr(s, "EXPECTED_COUNT", 1)
    monkeypatch.setattr(s, "EXPECTED_BYTES", len(data))
    monkeypatch.setattr(s, "MANIFEST_SHA256", hashlib.sha256(body).hexdigest())
    return source, tmp_path / "staged", manifest_path, rows[0], data


def state():
    return {"requests": 0, "body_bytes": 0, "files_verified": 0}


class Response(io.BytesIO):
    def __init__(self, data=b"", code=200, headers=None):
        super().__init__(data)
        self.code = code
        self.headers = {"Content-Length": str(len(data))} if headers is None else headers
        self.read_calls = 0

    def read(self, n=-1):
        self.read_calls += 1
        return super().read(n)


def transport_chain(row, data, extra_headers=None):
    redirect = Response(code=302, headers={"Location": "https://files.osf.io/v1/resources/5hju4/providers/osfstorage/" + row["osf_object_id"] + "?revision=2"})
    onward = Response(code=302, headers={"Location": "https://storage.googleapis.com/cos-osf-prod-files-us-east1/" + row["sha256"] + "?secret=never-log"})
    final = Response(data, headers={"Content-Length": str(len(data)), **(extra_headers or {})})
    replies = [redirect, onward, final]
    calls = []
    def transport(url, timeout):
        calls.append((url, timeout))
        return replies[len(calls) - 1]
    return transport, replies, calls


def test_local_stage_and_idempotent_verify(fixture):
    source, dest, manifest_path, row, data = fixture
    result = s.stage(dest, source, manifest_path=manifest_path)
    assert result["status"] == "ok" and result["files_verified"] == 1
    assert (dest / row["path"]).read_bytes() == data
    assert s.verify_staged(dest)["files"] == [row]
    assert s.stage(dest, source, manifest_path=manifest_path)["status"] == "verified_existing"
    assert stat.S_IMODE(dest.stat().st_mode) == 0o755
    assert stat.S_IMODE((dest / row["path"]).stat().st_mode) == 0o444
    assert stat.S_IMODE((dest / s.MANIFEST_NAME).stat().st_mode) == 0o444
    assert {p.name for p in dest.iterdir()} == {row["path"], s.MANIFEST_NAME}
    receipt = json.loads(dest.with_name(dest.name + ".staging_receipt.json").read_text())
    assert receipt["automatic_retries"] == 0 and receipt["requests"] == 0


@pytest.mark.parametrize("extra", ["file", "emptydir", "link", "fifo", "missing", "modified", "manifest"])
def test_closed_staged_inventory(fixture, extra):
    source, dest, manifest_path, row, _ = fixture
    s.stage(dest, source, manifest_path=manifest_path)
    if extra == "file":
        (dest / "extra").write_bytes(b"x")
    elif extra == "emptydir":
        (dest / "extra").mkdir()
    elif extra == "link":
        (dest / "extra").symlink_to(source / row["path"])
    elif extra == "fifo":
        os.mkfifo(dest / "extra")
    elif extra == "missing":
        (dest / row["path"]).unlink()
    elif extra == "modified":
        (dest / row["path"]).chmod(0o644)
        (dest / row["path"]).write_bytes(b"x" * row["size_bytes"])
    else:
        (dest / s.MANIFEST_NAME).chmod(0o644)
        (dest / s.MANIFEST_NAME).write_bytes(b"{}")
    with pytest.raises(s.Refusal):
        s.verify_staged(dest)


@pytest.mark.parametrize("value", ["relative", "/tmp/../x", "/tmp/./x", "/tmp/x\0y"])
def test_bad_absolute_paths(value):
    with pytest.raises(s.Refusal):
        s.safe_path(value)


@pytest.mark.parametrize("value", ["../x", "/x", "a/../x", "a//x", "a/./x", "", "a\\x", "x\0"])
def test_bad_relative_paths(value):
    with pytest.raises(s.Refusal):
        s.relative_path(value)


def test_original_symlink_component_before_parent_normalization(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
    for value in (str(tmp_path / "link" / "x"), str(tmp_path / "link") + "/../x"):
        with pytest.raises(s.Refusal):
            s.safe_path(value)


@pytest.mark.parametrize("which", ["equal", "ancestor", "descendant"])
def test_source_destination_overlap(fixture, which):
    source, _, manifest, _, _ = fixture
    dest = source if which == "equal" else source.parent if which == "ancestor" else source / "dest"
    with pytest.raises(s.Refusal, match="overlap"):
        s.stage(dest, source, manifest_path=manifest)


def test_atomic_publication_refuses_existing_empty_directory(tmp_path):
    pending, dest = tmp_path / "pending", tmp_path / "dest"
    pending.mkdir()
    dest.mkdir()
    (pending / "data").write_bytes(b"untouched")
    with pytest.raises(OSError):
        s.publish_no_replace(pending, dest)
    assert (pending / "data").read_bytes() == b"untouched" and list(dest.iterdir()) == []


def test_existing_conflicting_destination_is_preserved(fixture):
    source, dest, manifest, _, _ = fixture
    dest.mkdir()
    (dest / "mine").write_bytes(b"preserve")
    with pytest.raises(Exception):
        s.stage(dest, source, manifest_path=manifest)
    assert (dest / "mine").read_bytes() == b"preserve"


@pytest.mark.parametrize("field", ["sha256", "md5", "git_blob_sha1"])
def test_all_source_digests_enforced(fixture, field):
    source, _, _, row, _ = fixture
    bad = dict(row, **{field: "0" * len(row[field])})
    with pytest.raises(s.Refusal, match=field):
        s.file_identity(source / row["path"], bad)


@pytest.mark.parametrize("field,value", [("size_bytes", 1), ("sha256", "nonsense"), ("path", "../escape")])
def test_manifest_pin_cannot_refresh_itself(fixture, field, value):
    _, _, manifest, row, _ = fixture
    body = json.loads(manifest.read_text())
    body["files"][0][field] = value
    manifest.write_text(json.dumps(body))
    with pytest.raises(s.Refusal, match="manifest_hash_mismatch"):
        s.load_manifest(manifest)


def test_get_redirects_no_redirect_body_and_safe_receipt(fixture, capsys):
    _, dest, manifest, row, data = fixture
    transport, responses, calls = transport_chain(row, data, {"Set-Cookie": "never-store-cookie"})
    result = s.stage(dest, manifest_path=manifest, transport=transport)
    assert result["requests"] == 3 and result["body_bytes"] == len(data)
    assert len(calls) == 3 and all(r.closed for r in responses)
    assert responses[0].read_calls == responses[1].read_calls == 0
    logged = capsys.readouterr().out + dest.with_name(dest.name + ".staging_receipt.json").read_text()
    assert "never-log" not in logged and "never-store-cookie" not in logged
    assert all(timeout > 0 and timeout <= 30 for _, timeout in calls)


def test_waterbutler_direct_terminal_allowed(fixture, tmp_path):
    _, _, _, row, data = fixture
    calls = []
    def transport(url, timeout):
        calls.append(url)
        if len(calls) == 1:
            return Response(code=302, headers={"Location": "https://files.osf.io/v1/resources/5hju4/providers/osfstorage/" + row["osf_object_id"] + "?revision=2"})
        return Response(data)
    s.transfer(row, tmp_path / "copied", state(), s.time.monotonic() + 5, transport=transport)
    assert len(calls) == 2


@pytest.mark.parametrize("url", [
    "http://osf.io/download/abcde/?revision=2",
    "https://osf.io/download/other/?revision=2",
    "https://osf.io/download/abcde/?version=2",
    "https://osf.io/download/abcde/?revision=1",
    "https://osf.io/download/abcde/?revision=2&revision=2",
    "https://evil.example/x", "https://osf.io:444/download/abcde/?revision=2",
    "https://user@osf.io/download/abcde/?revision=2",
    "https://files.osf.io/v1/resources/5hju4/providers/osfstorage/" + "a" * 24,
    "https://files.osf.io/v1/resources/5hju4/providers/osfstorage/" + "b" * 24 + "?revision=2",
    "https://storage.googleapis.com/wrong/object",
])
def test_endpoint_rejections(fixture, url):
    with pytest.raises(s.Refusal):
        s.endpoint(url, fixture[3])


@pytest.mark.parametrize("case", ["length", "status", "encoding", "truncated", "oversized", "wrong_digest", "transport", "timeout", "aggregate"])
def test_failed_transfer_preserves_safe_receipt_without_retry(fixture, monkeypatch, capsys, case):
    _, dest, manifest, row, data = fixture
    calls = []
    def transport(url, timeout):
        calls.append(url)
        if case == "transport":
            raise RuntimeError("https://secret/?token=never-print")
        if len(calls) == 1:
            return Response(code=302, headers={"Location": "https://storage.googleapis.com/cos-osf-prod-files-us-east1/" + row["sha256"] + "?token=never-print"})
        contents = data
        headers = {"Content-Length": str(len(data))}
        code = 200
        if case == "length": headers["Content-Length"] = "1"
        if case == "status": code = 403
        if case == "encoding": headers["Content-Encoding"] = "gzip"
        if case == "truncated": contents = data[:-1]
        if case == "oversized": contents = data + b"x"
        if case == "wrong_digest": contents = b"x" * len(data)
        if case == "timeout": monkeypatch.setattr(s.time, "monotonic", lambda: 1e30)
        return Response(contents, code=code, headers=headers)
    if case == "aggregate": monkeypatch.setattr(s, "MAX_BYTES", 1)
    with pytest.raises(Exception):
        s.stage(dest, manifest_path=manifest, transport=transport)
    assert len(calls) <= 2 and not dest.exists()
    receipt = dest.with_name(dest.name + ".staging_receipt.json").read_text()
    assert json.loads(receipt)["status"] == "failed"
    assert "never-print" not in receipt + capsys.readouterr().err
    assert list(dest.parent.glob(dest.name + ".partial-*"))


def test_local_fifo_refused_without_open(fixture):
    source, dest, manifest, row, _ = fixture
    (source / row["path"]).unlink()
    os.mkfifo(source / row["path"])
    with pytest.raises(s.Refusal, match="local_type_or_size"):
        s.stage(dest, source, manifest_path=manifest)


def test_local_symlink_refused(fixture):
    source, dest, manifest, row, _ = fixture
    (source / row["path"]).rename(source / "real")
    (source / row["path"]).symlink_to(source / "real")
    with pytest.raises(s.Refusal, match="symlink"):
        s.stage(dest, source, manifest_path=manifest)


def test_github_commit_endpoint_fixed():
    row = digest_record("x", b"x", osf=False)
    assert s.endpoint(row["source_url"], row)["host"] == "raw.githubusercontent.com"
    for url in (row["source_url"].replace("c" * 40, "main"), row["source_url"] + "?query=x"):
        with pytest.raises(s.Refusal):
            s.endpoint(url, row)


def test_zero_time_cap_refuses_before_any_transport(fixture, monkeypatch):
    _, dest, manifest, _, _ = fixture
    monkeypatch.setattr(s, "MAX_SECONDS", 0)
    def fail(*args):
        pytest.fail("transport must not run")
    with pytest.raises(s.Refusal, match="elapsed_cap"):
        s.stage(dest, manifest_path=manifest, transport=fail)


def test_provenance_alias_local_copy(fixture, monkeypatch):
    source, dest, manifest_path, _, data = fixture
    provenance = source.parent / "documents"
    provenance.mkdir()
    (provenance / "OSF_README_version2.md").write_bytes(data)
    row = digest_record("provenance/processing_README_version2.md", data)
    manifest = {"n_files": 1, "total_bytes": len(data), "files": [row]}
    body = json.dumps(manifest).encode()
    manifest_path.write_bytes(body)
    monkeypatch.setattr(s, "MANIFEST_SHA256", hashlib.sha256(body).hexdigest())
    s.stage(dest, source, provenance, manifest_path)
    assert (dest / row["path"]).read_bytes() == data
    assert stat.S_IMODE((dest / "provenance").stat().st_mode) & 0o055 == 0o055


def test_existing_receipt_refuses_new_attempt(fixture):
    source, dest, manifest_path, _, _ = fixture
    receipt = dest.with_name(dest.name + ".staging_receipt.json")
    receipt.write_text("preserve")
    with pytest.raises(s.Refusal, match="existing_staging_receipt"):
        s.stage(dest, source, manifest_path=manifest_path)
    assert receipt.read_text() == "preserve" and not dest.exists()


def test_cli_overlap_does_not_create_source_directories(fixture, monkeypatch, capsys):
    source, _, manifest, _, _ = fixture
    before = sorted(p.relative_to(source).as_posix() for p in source.rglob("*"))
    monkeypatch.setattr(s.sys, "argv", ["stage_data.py", "--destination", str(source / "newdir" / "out"),
                                      "--source-root", str(source), "--manifest", str(manifest)])
    assert s.main() == 1
    assert before == sorted(p.relative_to(source).as_posix() for p in source.rglob("*"))
    assert json.loads(capsys.readouterr().err)["error_code"] == "source_destination_overlap"


def test_cli_destination_parent_created_after_preflight(fixture, monkeypatch):
    source, dest, manifest, _, _ = fixture
    nested = dest.parent / "newparent" / "out"
    monkeypatch.setattr(s.sys, "argv", ["stage_data.py", "--destination", str(nested),
                                      "--source-root", str(source), "--manifest", str(manifest)])
    assert s.main() == 0 and nested.is_dir()


@pytest.mark.parametrize("kind", ["loop", "cap", "missing_location", "wrong_host", "missing_length", "terminal_osf"])
def test_strict_redirect_and_terminal_policy(fixture, kind):
    _, dest, manifest, row, data = fixture
    calls = []
    def transport(url, timeout):
        calls.append(url)
        if kind == "terminal_osf":
            return Response(data)
        if kind == "loop":
            location = url
        elif kind == "cap":
            location = "https://osf.io/download/abcde/?revision=2&download=" + str(len(calls))
        elif kind == "wrong_host":
            location = "https://evil.example/secret?token=unlogged"
        elif kind == "missing_location":
            return Response(code=302, headers={})
        else:
            location = "https://storage.googleapis.com/cos-osf-prod-files-us-east1/" + row["sha256"]
            if len(calls) > 1:
                return Response(data, headers={})
        return Response(code=302, headers={"Location": location})
    with pytest.raises(s.Refusal):
        s.stage(dest, manifest_path=manifest, transport=transport)
    assert len(calls) <= 6


def test_production_manifest_metadata_only_validation():
    # Reads only the small task manifest, never any original scientific payload.
    manifest, body = s.load_manifest()
    assert len(manifest["files"]) == 86
    assert sum(r["size_bytes"] for r in manifest["files"]) == 249626034
    assert hashlib.sha256(body).hexdigest() == "d0c4f2afdfe9161907fe64d74ab07e85e6162726f5efc0b10ff46cf2ece954f1"
    assert sum("source_guid" in r for r in manifest["files"]) == 82


def test_open_once_get_no_default_redirect(monkeypatch):
    captured = []
    response = Response(b"fixture")
    class Opener:
        def open(self, request, timeout):
            captured.append((request, timeout))
            return response
    monkeypatch.setattr(s, "build_opener", lambda guard: Opener())
    assert s.open_once("https://osf.io/download/abcde/?revision=2", 3) is response
    assert captured[0][0].method == "GET" and captured[0][1] == 3
    assert s.NoRedirect().redirect_request(None, None, 302, None, None, "https://other") is None


def test_network_uses_single_underlying_read_and_rechecks_deadline(fixture, monkeypatch):
    _, dest, manifest, row, data = fixture
    original_clock = s.time.monotonic
    calls = []
    class DripResponse(Response):
        def read(self, n=-1):
            pytest.fail("filling network read is forbidden")
        def read1(self, n=-1):
            calls.append(n)
            monkeypatch.setattr(s.time, "monotonic", lambda: original_clock() + 1000)
            return b"x"
    def transport(url, timeout):
        if "osf.io/download" in url:
            return Response(code=302, headers={"Location": "https://storage.googleapis.com/cos-osf-prod-files-us-east1/" + row["sha256"]})
        return DripResponse(data)
    with pytest.raises(s.Refusal, match="elapsed_cap"):
        s.stage(dest, manifest_path=manifest, transport=transport)
    assert len(calls) == 1 and not dest.exists()


def test_cli_arms_and_restores_total_deadline(fixture, monkeypatch):
    source, dest, manifest, _, _ = fixture
    timers, handlers = [], []
    previous = s.signal.getsignal(s.signal.SIGALRM)
    monkeypatch.setattr(s.signal, "setitimer", lambda kind, value: timers.append((kind, value)))
    monkeypatch.setattr(s.signal, "signal", lambda kind, handler: handlers.append((kind, handler)))
    monkeypatch.setattr(s.sys, "argv", ["stage_data.py", "--destination", str(dest),
                                      "--source-root", str(source), "--manifest", str(manifest)])
    assert s.main() == 0
    assert timers == [(s.signal.ITIMER_REAL, 600), (s.signal.ITIMER_REAL, 0)]
    assert handlers[-1] == (s.signal.SIGALRM, previous)
    with pytest.raises(s.Refusal, match="elapsed_cap"):
        handlers[0][1](s.signal.SIGALRM, None)


def test_interrupt_during_copy_preserves_receipt(fixture, monkeypatch):
    source, dest, manifest, _, _ = fixture
    def interrupted(*args, **kwargs):
        raise s.Refusal("elapsed_cap")
    monkeypatch.setattr(s, "transfer", interrupted)
    monkeypatch.setattr(s.sys, "argv", ["stage_data.py", "--destination", str(dest),
                                      "--source-root", str(source), "--manifest", str(manifest)])
    assert s.main() == 1
    receipt = json.loads(dest.with_name(dest.name + ".staging_receipt.json").read_text())
    assert receipt["status"] == "failed" and receipt["error_code"] == "elapsed_cap"
    assert not dest.exists() and Path(receipt["pending_directory"]).is_dir()
