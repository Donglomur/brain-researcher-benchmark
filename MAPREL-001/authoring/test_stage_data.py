"""Manufactured-only qualification of the exact portable staging module."""
from __future__ import annotations
import copy
from email.message import Message
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import types

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "environment" / "stage_data.py"
spec = importlib.util.spec_from_file_location("pr193_portable_stager", MODULE_PATH)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def digests(raw):
    return dict(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                md5=hashlib.md5(raw).hexdigest(),
                git_blob_sha1=hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest())


def tar_bytes(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name, raw, kind in entries:
            item = tarfile.TarInfo(name)
            item.type = kind
            item.size = len(raw) if kind == tarfile.REGTYPE else 0
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE): item.linkname = "escape"
            archive.addfile(item, io.BytesIO(raw) if item.isfile() else None)
    return stream.getvalue()


def manufacture():
    spheres = [(name, ("manufactured-" + role).encode(), tarfile.REGTYPE)
               for name, role in m.SPHERES.items()]
    archive = tar_bytes(spheres + [("README", b"opaque provenance", tarfile.REGTYPE)])
    object_roles = sorted((m.SCIENCE_ROLES - {"sphere_l", "sphere_r"}) |
                          {"spheres_archive"} | m.PROVENANCE_ROLES)
    objects, payloads = [], {}
    for index, role in enumerate(object_roles):
        raw = archive if role == "spheres_archive" else ("opaque-" + role).encode()
        row = dict(key=role, role=role, **digests(raw))
        if role in {"gradient_l", "gradient_r", "thickness_l", "thickness_r", "spheres_archive"}:
            row.update(transport="osf", source_guid=f"a{index:04d}", node_id="4mw3a",
                       object_id=f"{index:024x}", source_version=1)
            row["source_url"] = f"https://osf.io/download/{row['source_guid']}/?revision=1"
        else:
            repo = "ThomasYeoLab/CBIG" if role == "atlas" or role.startswith("cbig_") else "netneurolab/neuromaps"
            row.update(transport="raw_commit", repository=repo, commit="a" * 40,
                       source_url=f"https://raw.githubusercontent.com/{repo}/{'a' * 40}/{role}.txt")
        if role == "spheres_archive":
            row.update(archive_format="tar.gz", required_members=list(m.SPHERES),
                       inventory=[dict(path=name, size_bytes=len(body), directory=False)
                                  for name, body, _ in spheres + [("README", b"opaque provenance", tarfile.REGTYPE)]])
        objects.append(row); payloads[role] = raw
    by_role = {row["role"]: row for row in objects}
    files = []
    for role in sorted(m.SCIENCE_ROLES | m.PROVENANCE_ROLES):
        path = f"provenance/{role}.txt" if role in m.PROVENANCE_ROLES else role + ".source"
        if role in ("sphere_l", "sphere_r"):
            name, raw, _ = next(entry for entry in spheres if m.SPHERES[entry[0]] == role)
            files.append(dict(role=role, path=path, object_key="spheres_archive", archive_member=name, **digests(raw)))
            payloads[role] = raw
        else:
            row = by_role[role]
            files.append(dict(role=role, path=path, object_key=role,
                              **{key: row[key] for key in digests(payloads[role])}))
    doc = dict(schema_version="maprel-source-v2", task_id="MAPREL-001",
               runtime_data_directory="/app/data/maprel", source_manifest_inside_data_root=True,
               source_file_count=13, download_object_count=12, files=files, objects=objects,
               source_bytes=sum(row["size_bytes"] for row in files),
               download_bytes=sum(row["size_bytes"] for row in objects))
    return doc, payloads


def write_manifest(path, doc, monkeypatch):
    raw = (json.dumps(doc, sort_keys=True, indent=2) + "\n").encode()
    path.write_bytes(raw); monkeypatch.setattr(m, "MANIFEST_SHA256", m.sha(raw)); return raw


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    doc, payloads = manufacture()
    manifest = tmp_path / "manifest.json"; raw = write_manifest(manifest, doc, monkeypatch)
    source = tmp_path / "source"; source.mkdir()
    for row in doc["files"]:
        target = source / row["path"]; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payloads[row["role"]])
    (source / "source_manifest.json").write_bytes(raw)
    monkeypatch.setattr(m.shutil, "disk_usage", lambda _: types.SimpleNamespace(free=2 * 1024**3))
    return types.SimpleNamespace(doc=doc, payloads=payloads, manifest=manifest, raw=raw,
                                 source=source, dst=tmp_path / "destination", work=tmp_path / "work")


class Response:
    def __init__(self, url, body=b"", status=200, pairs=None):
        self.url, self.code, self.stream, self.closed, self.reads = url, status, io.BytesIO(body), False, 0
        self.headers = Message()
        for key, value in (pairs if pairs is not None else [("Content-Length", str(len(body))), ("Content-Type", "application/octet-stream")]):
            self.headers[key] = value
    def geturl(self): return self.url
    def read1(self, n): self.reads += 1; return self.stream.read(n)
    def close(self): self.closed = True


def fake_transport(bundle, calls):
    rows = {row["source_url"]: row for row in bundle.doc["objects"]}
    def transport(url, timeout):
        calls.append((url, timeout)); row = rows[url]
        return Response(url, bundle.payloads[row["role"]])
    return transport


def test_cold_stage_and_offline_verify_closed_bundle(bundle, monkeypatch):
    calls = []
    result = m.stage(bundle.dst, bundle.work, bundle.manifest, transport=fake_transport(bundle, calls))
    assert result["status"] == "verified_closed_source_bundle"
    assert result["object_starts"] == result["network_requests"] == len(calls) == 12
    assert result["received_body_bytes"] == bundle.doc["download_bytes"]
    assert result["automatic_retries"] == 0 and result["scientific_values_parsed"] is False
    assert not (bundle.work / "pending").exists()
    assert (bundle.dst / "source_manifest.json").read_bytes() == bundle.raw
    monkeypatch.setattr(m, "open_once", lambda *_: pytest.fail("offline verification attempted network"))
    before = {str(p): p.stat().st_mtime_ns for p in bundle.dst.rglob("*")}
    assert m.verify_staged(bundle.dst, bundle.manifest) == bundle.doc
    assert before == {str(p): p.stat().st_mtime_ns for p in bundle.dst.rglob("*")}
    assert len([p for p in bundle.dst.rglob("*") if p.is_file()]) == 14


def test_local_copy_is_authenticated_before_writes_and_never_fetches(bundle):
    result = m.stage(bundle.dst, bundle.work, bundle.manifest, bundle.source,
                     transport=lambda *_: pytest.fail("local staging attempted network"))
    assert result["mode"] == "local_verified_copy" and result["network_requests"] == 0
    assert result["object_starts"] == result["received_body_bytes"] == 0
    for row in bundle.doc["files"]:
        assert (bundle.dst / row["path"]).read_bytes() == bundle.payloads[row["role"]]
        assert (bundle.dst / row["path"]).stat().st_ino != (bundle.source / row["path"]).stat().st_ino


def test_bad_local_source_refuses_before_output_or_work(bundle):
    row = bundle.doc["files"][-1]; target = bundle.source / row["path"]
    target.write_bytes(b"x" * row["size_bytes"])
    with pytest.raises(m.Refusal, match="source_digest_mismatch"):
        m.stage(bundle.dst, bundle.work, bundle.manifest, bundle.source)
    assert not bundle.dst.exists() and not bundle.work.exists()
    assert target.read_bytes() == b"x" * row["size_bytes"]


@pytest.mark.parametrize("mode", ["extra_file", "extra_dir", "symlink_file", "symlink_dir", "manifest_changed", "missing"])
def test_closed_inventory_rejects_changes(bundle, mode):
    target = bundle.source / bundle.doc["files"][0]["path"]
    if mode == "extra_file": (bundle.source / "extra").write_bytes(b"x")
    elif mode == "extra_dir": (bundle.source / "empty").mkdir()
    elif mode == "symlink_file": target.unlink(); target.symlink_to(bundle.manifest)
    elif mode == "symlink_dir": (bundle.source / "link").symlink_to(bundle.work, target_is_directory=True)
    elif mode == "manifest_changed": (bundle.source / "source_manifest.json").write_bytes(b"{}")
    elif mode == "missing": target.unlink()
    with pytest.raises(m.Refusal): m.verify_staged(bundle.source, bundle.manifest)


@pytest.mark.parametrize("kind", ["destination", "work", "nested_source", "manifest_parent", "same_paths"])
def test_existing_and_overlapping_destinations_refused(bundle, kind):
    dst, work = bundle.dst, bundle.work
    if kind == "destination": dst.mkdir(); (dst / "keep").write_bytes(b"keep")
    elif kind == "work": work.mkdir(); (work / "keep").write_bytes(b"keep")
    elif kind == "nested_source": dst = bundle.source / "new"
    elif kind == "manifest_parent": dst = bundle.manifest.parent
    elif kind == "same_paths": work = dst
    with pytest.raises(m.Refusal): m.stage(dst, work, bundle.manifest, bundle.source)
    for p in (bundle.dst / "keep", bundle.work / "keep"):
        if p.exists(): assert p.read_bytes() == b"keep"


@pytest.mark.parametrize("suffix", ["../escaped", "./alias"])
def test_literal_dot_ancestry_rejected(tmp_path, suffix):
    with pytest.raises(m.Refusal, match="unsafe_path"): m.safe_path(str(tmp_path) + "/" + suffix)


def test_symlink_ancestry_and_dangling_destination_rejected(tmp_path):
    link = tmp_path / "link"; link.symlink_to(tmp_path / "missing", target_is_directory=True)
    with pytest.raises(m.Refusal, match="symlink_path"): m.safe_path(link / "child")
    with pytest.raises(m.Refusal, match="symlink_path"): m.safe_path(link)


def test_atomic_publication_preserves_raced_destination(tmp_path):
    pending, destination = tmp_path / "pending", tmp_path / "destination"
    pending.mkdir(); destination.mkdir(); (destination / "keep").write_bytes(b"keep")
    with pytest.raises(OSError): m.publish_no_replace(pending, destination)
    assert pending.is_dir() and (destination / "keep").read_bytes() == b"keep"


@pytest.mark.parametrize("field,value", [("task_id", "OTHER"), ("schema_version", "wrong"),
    ("source_file_count", 12), ("download_object_count", 13), ("source_manifest_inside_data_root", False),
    ("runtime_data_directory", "/wrong"), ("source_bytes", 1), ("download_bytes", 1)])
def test_manifest_identity_and_layout(bundle, monkeypatch, field, value):
    doc = copy.deepcopy(bundle.doc); doc[field] = value; write_manifest(bundle.manifest, doc, monkeypatch)
    with pytest.raises(m.Refusal): m.read_manifest(bundle.manifest)


@pytest.mark.parametrize("change", ["role", "path", "size_bool", "sha", "md5", "git", "object", "version", "url", "repository", "archive"])
def test_manifest_member_mutations(bundle, monkeypatch, change):
    doc = copy.deepcopy(bundle.doc); row = doc["files"][0]
    if change == "role": row["role"] = doc["files"][1]["role"]
    elif change == "path": row["path"] = "../escape"
    elif change == "size_bool": row["size_bytes"] = True
    elif change == "sha": row["sha256"] = "z" * 64
    elif change == "md5": row["md5"] = "0" * 32
    elif change == "git": row["git_blob_sha1"] = "0" * 40
    elif change == "object": row["object_key"] = "missing"
    elif change == "version": next(r for r in doc["objects"] if r["transport"] == "osf")["source_version"] = 2
    elif change == "url": next(r for r in doc["objects"] if r["transport"] == "osf")["source_url"] += "&revision=2"
    elif change == "repository": next(r for r in doc["objects"] if r["transport"] == "raw_commit")["repository"] = "other/repo"
    elif change == "archive": next(r for r in doc["objects"] if r["role"] == "spheres_archive")["required_members"] = []
    write_manifest(bundle.manifest, doc, monkeypatch)
    with pytest.raises(m.Refusal): m.read_manifest(bundle.manifest)


def test_manifest_pin_and_json_duplicate_nonfinite(bundle, monkeypatch):
    monkeypatch.setattr(m, "MANIFEST_SHA256", "0" * 64)
    with pytest.raises(m.Refusal, match="manifest_pin"): m.read_manifest(bundle.manifest)
    for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"extra":[1e999]}'):
        with pytest.raises(m.Refusal): m.strict_json(raw)


def test_manifest_path_prefix_collision(bundle, monkeypatch):
    doc = copy.deepcopy(bundle.doc); doc["files"][1]["path"] = doc["files"][0]["path"] + "/child"
    write_manifest(bundle.manifest, doc, monkeypatch)
    with pytest.raises(m.Refusal, match="manifest_path_collision"): m.read_manifest(bundle.manifest)


def osf_row(bundle): return next(r for r in bundle.doc["objects"] if r["role"] == "gradient_l")


def test_fresh_signed_redirect_closes_unread_body_and_redacts(bundle, tmp_path):
    row = osf_row(bundle); url = row["source_url"]
    signed = f"https://storage.googleapis.com/cos-osf-prod-files-ca-1/{row['sha256']}?GoogleAccessId=account&Expires=100&Signature=SECRET"
    first = Response(url, b"UNREAD_REDIRECT_BODY", 302, [("Location", signed)])
    second = Response(signed, bundle.payloads[row["role"]]); replies = iter((first, second)); calls = []
    def transport(request, _): calls.append(request); return next(replies)
    target = tmp_path / "download"; target.mkdir(); record = {}; budget = m.Budget()
    output = m.download(row, target, budget, record, transport)
    assert output.read_bytes() == bundle.payloads[row["role"]]
    assert first.reads == 0 and first.closed and second.closed and len(calls) == 2
    assert "SECRET" not in json.dumps(record) and "account" not in json.dumps(record)
    assert record["canonical_source_url"] == url
    assert record["redirects"][0]["allowed"] is True


@pytest.mark.parametrize("bad", ["host", "object", "bucket", "unsigned", "partial_signature", "userinfo", "fragment", "port", "version", "conflict"])
def test_endpoint_escape_rejected(bundle, bad):
    row = osf_row(bundle)
    urls = {
        "host": "https://example.org/file",
        "object": f"https://storage.googleapis.com/cos-osf-prod-files-ca-1/{'0' * 64}?GoogleAccessId=a&Expires=1&Signature=x",
        "bucket": f"https://storage.googleapis.com/arbitrary/{row['sha256']}?GoogleAccessId=a&Expires=1&Signature=x",
        "unsigned": f"https://storage.googleapis.com/cos-osf-prod-files-ca-1/{row['sha256']}",
        "partial_signature": f"https://storage.googleapis.com/cos-osf-prod-files-ca-1/{row['sha256']}?Signature=x",
        "userinfo": row["source_url"].replace("osf.io", "user:password@osf.io"),
        "fragment": row["source_url"] + "#fragment",
        "port": row["source_url"].replace("osf.io", "osf.io:444"),
        "version": row["source_url"].replace("revision=1", "revision=2"),
        "conflict": row["source_url"] + "&version=2",
    }
    with pytest.raises(m.Refusal): m.endpoint(urls[bad], row)


@pytest.mark.parametrize("kind", ["missing_length", "duplicate_length", "truncated", "oversized", "hash", "encoding", "html", "status", "final_url", "duplicate_type"])
def test_download_rejections_preserve_partial_no_retry(bundle, tmp_path, kind):
    row = osf_row(bundle); raw = bundle.payloads[row["role"]]; url = row["source_url"]
    pairs = [("Content-Length", str(len(raw))), ("Content-Type", "application/octet-stream")]
    if kind == "missing_length": pairs = pairs[1:]
    if kind == "duplicate_length": pairs.append(("Content-Length", str(len(raw))))
    if kind == "truncated": raw = raw[:-1]
    if kind == "oversized": raw += b"x"
    if kind == "hash": raw = b"x" * len(raw)
    if kind == "encoding": pairs.append(("Content-Encoding", "gzip"))
    if kind == "html": pairs[1] = ("Content-Type", "text/html")
    if kind == "duplicate_type": pairs.append(("Content-Type", "application/octet-stream"))
    response = Response(url + ("&other=1" if kind == "final_url" else ""), raw,
                        500 if kind == "status" else 200, pairs)
    calls = []
    def transport(*_): calls.append(1); return response
    target = tmp_path / "download"; target.mkdir(); record = {}
    with pytest.raises(m.Refusal): m.download(row, target, m.Budget(), record, transport)
    assert len(calls) == 1 and response.closed and record["status"] == "failed"
    assert (target / "gradient_l.partial").is_file() and not (target / "gradient_l.source").exists()
    if kind in ("missing_length", "duplicate_length", "encoding", "html", "status", "final_url", "duplicate_type"):
        assert response.reads == 0


def test_download_aggregate_cap_duplicate_starts_and_deadline(bundle, tmp_path):
    row = osf_row(bundle); target = tmp_path / "download"; target.mkdir()
    budget = m.Budget(m.Limits(received_bytes=1)); response = Response(row["source_url"], bundle.payloads[row["role"]])
    with pytest.raises(m.Refusal, match="received_byte_cap"):
        m.download(row, target, budget, {}, lambda *_: response)
    assert budget.received == 1
    with pytest.raises(m.Refusal, match="duplicate_or_excess_start"):
        m.download(row, target, budget, {}, lambda *_: pytest.fail("duplicate request"))
    now = [0.]; deadline = m.Budget(m.Limits(wall_seconds=1), clock=lambda: now[0]); now[0] = 2.
    with pytest.raises(m.Refusal, match="wall_deadline"):
        m.download(row, target, deadline, {}, lambda *_: pytest.fail("past deadline request"))


def test_failed_first_object_cancels_new_scheduling_and_preserves_report(bundle):
    calls = []
    def fail(url, _): calls.append(url); return Response(url, status=500)
    with pytest.raises(m.Refusal, match="http_status"):
        m.stage(bundle.dst, bundle.work, bundle.manifest, transport=fail)
    result = json.loads((bundle.work / "result.json").read_bytes())
    assert len(calls) == result["object_starts"] == 1 and result["status"] == "failed_preserved"
    assert not bundle.dst.exists() and (bundle.work / "pending").exists()


def test_raw_commit_refuses_redirect_without_reading_body(bundle, tmp_path):
    row = next(r for r in bundle.doc["objects"] if r["role"] == "atlas")
    response = Response(row["source_url"], b"UNREAD", 302, [("Location", "https://example.org")])
    target = tmp_path / "download"; target.mkdir()
    with pytest.raises(m.Refusal, match="redirect_limit_or_atlas_redirect"):
        m.download(row, target, m.Budget(), {}, lambda *_: response)
    assert response.reads == 0 and response.closed


@pytest.mark.parametrize("kind", ["traversal", "absolute", "backslash", "symlink", "hardlink", "fifo", "duplicate", "missing", "collision"])
def test_tar_unsafe_inventory_refused(tmp_path, kind):
    entries = [(name, b"opaque sphere", tarfile.REGTYPE) for name in m.SPHERES]
    if kind == "traversal": entries.append(("../escape", b"x", tarfile.REGTYPE))
    if kind == "absolute": entries.append(("/escape", b"x", tarfile.REGTYPE))
    if kind == "backslash": entries.append(("a\\b", b"x", tarfile.REGTYPE))
    if kind == "symlink": entries.append(("link", b"", tarfile.SYMTYPE))
    if kind == "hardlink": entries.append(("link", b"", tarfile.LNKTYPE))
    if kind == "fifo": entries.append(("fifo", b"", tarfile.FIFOTYPE))
    if kind == "duplicate": entries.append(entries[0])
    if kind == "missing": entries = entries[:1]
    if kind == "collision": entries.extend([("collision", b"x", tarfile.REGTYPE), ("collision/file", b"x", tarfile.REGTYPE)])
    archive = tmp_path / "archive.tar.gz"; archive.write_bytes(tar_bytes(entries))
    with pytest.raises(m.Refusal): m.tar_inventory(archive, m.Budget())


@pytest.mark.parametrize("limit", ["members", "expanded_bytes", "member_bytes", "tar_stream_bytes"])
def test_tar_caps_enforced(tmp_path, limit):
    archive = tmp_path / "archive.tar.gz"
    archive.write_bytes(tar_bytes([(name, b"opaque sphere", tarfile.REGTYPE) for name in m.SPHERES]))
    with pytest.raises(m.Refusal): m.tar_inventory(archive, m.Budget(m.Limits(**{limit: 1})))


def test_archive_rehashed_after_inventory_before_extraction(bundle, monkeypatch):
    original = m.tar_inventory; seen = []
    def tamper(path, budget, selected_dir=None):
        result = original(path, budget, selected_dir); seen.append(selected_dir)
        path.chmod(0o644); raw = path.read_bytes(); path.write_bytes(b"x" + raw[1:]); return result
    monkeypatch.setattr(m, "tar_inventory", tamper)
    with pytest.raises(m.Refusal, match="source_digest_mismatch"):
        m.stage(bundle.dst, bundle.work, bundle.manifest, transport=fake_transport(bundle, []))
    assert seen == [None] and not (bundle.work / "selected").exists() and not bundle.dst.exists()


def test_expected_archive_inventory_is_enforced(bundle, monkeypatch):
    doc = copy.deepcopy(bundle.doc)
    next(r for r in doc["objects"] if r["role"] == "spheres_archive")["inventory"] = []
    write_manifest(bundle.manifest, doc, monkeypatch)
    with pytest.raises(m.Refusal, match="published_archive_inventory_changed"):
        m.stage(bundle.dst, bundle.work, bundle.manifest, transport=fake_transport(bundle, []))
    assert not bundle.dst.exists() and not (bundle.work / "selected").exists()


def test_late_publication_failure_never_marks_complete(bundle, monkeypatch):
    monkeypatch.setattr(m, "publish_no_replace", lambda *_: (_ for _ in ()).throw(OSError("manufactured")))
    with pytest.raises(OSError): m.stage(bundle.dst, bundle.work, bundle.manifest, bundle.source)
    result = json.loads((bundle.work / "result.json").read_bytes())
    assert result["status"] == "failed_preserved" and not bundle.dst.exists()
    assert (bundle.work / "pending" / "source_manifest.json").is_file()


def test_verify_cli_no_work_no_network(bundle, capsys):
    assert m.main(["--verify-existing", "--manifest", str(bundle.manifest), "--destination", str(bundle.source)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["source_file_count"] == 13 and result["network_requests"] == 0
    assert not bundle.work.exists()


def test_cli_bad_pin_reports_failure_without_trace_or_work(bundle, monkeypatch, capsys):
    monkeypatch.setattr(m, "MANIFEST_SHA256", "0" * 64)
    assert m.main(["--manifest", str(bundle.manifest), "--destination", str(bundle.dst), "--work-dir", str(bundle.work)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["reason"] == "manifest_pin" and not bundle.work.exists() and not bundle.dst.exists()


def test_import_does_not_stage_or_access_network(monkeypatch):
    monkeypatch.setattr(m.os, "mkdir", lambda *_a, **_k: pytest.fail("import mkdir"))
    import urllib.request
    monkeypatch.setattr(urllib.request, "build_opener", lambda *_a, **_k: pytest.fail("import network"))
    alternate = importlib.util.spec_from_file_location("pr193_import_guard", MODULE_PATH)
    module = importlib.util.module_from_spec(alternate); sys.modules[alternate.name] = module
    alternate.loader.exec_module(module)
    assert module.MANIFEST_SHA256 == "279658ffc93a8957287298471b539fc034fb7e11f0836325de322acc4b232f7f"
