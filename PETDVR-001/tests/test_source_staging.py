"""Source identity/staging mechanics only; no scientific fits or source downloads."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

ENV = Path(__file__).parents[1]/"environment"
spec = importlib.util.spec_from_file_location("petdvr_stage", ENV/"stage_data.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def manifest():
    return json.loads((ENV/"source_manifest.json").read_text())


def tiny_record(data=b"mechanics only\n"):
    return {"path":"tiny.txt", "size_bytes":len(data), "sha256":hashlib.sha256(data).hexdigest(),
        "git_blob_sha1":hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest(),
        "git_entry_kind":"direct_text_blob", "url":"https://example.invalid/no-network"}


def test_manifest_whole_file_pin_and_source_scope():
    source, _ = stage.read_manifest(ENV/"source_manifest.json")
    assert len(source["files"]) == 24
    assert sum(r["role"] == "tac" for r in source["files"]) == 4
    assert sum(r["size_bytes"] for r in source["files"]) == 270682
    assert not any("_km-" in r["path"] or r["path"].endswith(".nii.gz") for r in source["files"])
    assert source["derivative_provenance"]["extraction_rerun"] is False


@pytest.mark.parametrize("field,value", [("dataset_id","ds000001"),("snapshot","latest"),
    ("license","unknown"),("git_tree_sha1","0"*40),("git_tag_commit_sha1","0"*40)])
def test_reject_wrong_snapshot_identity(field,value):
    source=manifest(); source[field]=value
    with pytest.raises(ValueError): stage.validate_manifest(source)


@pytest.mark.parametrize("kind",["drop","duplicate","traversal","absolute","role","subject","session","url","size","sha","gitsha","entrykind","pointer","md5"])
def test_reject_mutated_source_contract(kind):
    source=manifest(); record=next(r for r in source["files"] if r["role"]=="extraction_log")
    if kind=="drop": source["files"].pop()
    elif kind=="duplicate": source["files"].append(copy.deepcopy(record))
    elif kind=="traversal": record["path"]="../outside"
    elif kind=="absolute": record["path"]="/outside"
    elif kind=="role": record["role"]="tac"
    elif kind=="subject": record["subject"]="sub-99"
    elif kind=="session": record["session"]="ses-99"
    elif kind=="url": record["url"]="https://example.invalid/source"
    elif kind=="size": record["size_bytes"]=-1
    elif kind=="sha": record["sha256"]="not a digest"
    elif kind=="gitsha": record["git_blob_sha1"]="0"*40
    elif kind=="entrykind": record["git_entry_kind"]="other"
    elif kind=="pointer": record["annex_pointer"] += "changed"
    elif kind=="md5": record["annex_md5"]="0"*32
    with pytest.raises(ValueError): stage.validate_manifest(source)


def test_edited_manifest_cannot_refresh_source_pins(tmp_path):
    path=tmp_path/"manifest.json"; path.write_text(json.dumps(manifest()))
    with pytest.raises(ValueError,match="manifest SHA256"): stage.read_manifest(path)


@pytest.mark.parametrize("kind",["size","sha256","git_blob_sha1","annex_md5"])
def test_content_checksums_are_independent(tmp_path,kind):
    data=b"mechanics only\n"; path=tmp_path/"tiny.txt"; path.write_bytes(data)
    record=tiny_record(data)
    if kind=="size": record["size_bytes"] += 1
    elif kind=="annex_md5": record.update(git_entry_kind="annex_symlink",annex_md5="0"*32)
    else: record[kind]="0"*len(record[kind])
    with pytest.raises(ValueError): stage.verify_file(path,record)


def test_valid_direct_and_annex_checksums(tmp_path):
    data=b"mechanics only\n"; path=tmp_path/"tiny.txt"; path.write_bytes(data)
    record=tiny_record(data); stage.verify_file(path,record)
    record.update(git_entry_kind="annex_symlink",annex_md5=hashlib.md5(data).hexdigest())
    stage.verify_file(path,record)


class Response(io.BytesIO):
    status = 200
    def __init__(self, body, headers=None):
        super().__init__(body)
        self.headers = headers or {}


def mock_transport(monkeypatch, responder):
    class Opener:
        def open(self, request, timeout):
            return responder(request, timeout)
    monkeypatch.setattr(stage.urllib.request, "build_opener", lambda *args: Opener())


def test_stream_download_is_size_bounded(tmp_path, monkeypatch):
    record = tiny_record()
    mock_transport(monkeypatch, lambda *args: Response(b"x"*100))
    with pytest.raises(ValueError, match="exceeds pinned size"):
        stage.download_file(record, tmp_path/"out")


@pytest.mark.parametrize("body", [b"short", b"x"*15])
def test_download_requires_correct_content(tmp_path, monkeypatch, body):
    record = tiny_record()
    mock_transport(monkeypatch, lambda *args: Response(body))
    with pytest.raises(ValueError):
        stage.download_file(record, tmp_path/"out")


def test_download_checks_declared_length(tmp_path, monkeypatch):
    record = tiny_record()
    mock_transport(monkeypatch, lambda *args: Response(b"", {"Content-Length": "999999"}))
    with pytest.raises(ValueError, match="Content-Length"):
        stage.download_file(record, tmp_path/"out")


def test_download_success(tmp_path, monkeypatch):
    data = b"mechanics only\\n"; record = tiny_record(data)
    mock_transport(monkeypatch, lambda *args: Response(data))
    stage.download_file(record, tmp_path/"out")
    assert (tmp_path/"out").read_bytes() == data


def test_transport_http_error_is_not_retried(tmp_path, monkeypatch):
    calls = []
    def respond(req, timeout):
        calls.append(req.full_url)
        raise stage.urllib.error.HTTPError(req.full_url, 503, "private server text", {}, None)
    mock_transport(monkeypatch, respond)
    with pytest.raises(RuntimeError, match="503"):
        stage.download_file(tiny_record(), tmp_path/"out")
    assert len(calls) == 1


@pytest.mark.parametrize("url", ["http://s3.amazonaws.com/openneuro.org/ds001420/tiny.txt",
    "https://evil.invalid/x", "https://s3.amazonaws.com/wrong/path",
    "https://user:secret@s3.amazonaws.com/openneuro.org/ds001420/tiny.txt"])
def test_reject_foreign_redirect_before_body(tmp_path, monkeypatch, url):
    calls = []
    def respond(req, timeout):
        calls.append(req.full_url)
        raise stage.urllib.error.HTTPError(req.full_url, 302, "redirect", {"Location": url}, None)
    mock_transport(monkeypatch, respond)
    with pytest.raises(ValueError, match="endpoint"):
        stage.download_file(tiny_record(), tmp_path/"out")
    assert len(calls) == 1
    assert not (tmp_path/"out").exists()


def test_approved_redirect_is_hash_verified(tmp_path, monkeypatch):
    data=b"mechanics only\\n"; record=tiny_record(data); calls=[]
    def respond(req, timeout):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise stage.urllib.error.HTTPError(req.full_url, 302, "redirect",
                {"Location": "https://s3.amazonaws.com/openneuro.org/ds001420/tiny.txt?versionId=fixture"}, None)
        return Response(data)
    mock_transport(monkeypatch, respond)
    stage.download_file(record, tmp_path/"out")
    assert len(calls) == 2


def test_local_staging_rehashes_and_is_idempotent(tmp_path,monkeypatch):
    data=b"mechanics only\n"; record=tiny_record(data)
    source=tmp_path/"source"; source.mkdir(); (source/record["path"]).write_bytes(data)
    monkeypatch.setattr(stage,"read_manifest",lambda path:({"files":[record]},b"fixture manifest"))
    monkeypatch.setattr(stage.urllib.request,"urlopen",lambda *a,**k:pytest.fail("local reuse must not download"))
    destination=tmp_path/"destination"
    for _ in range(2): stage.stage_data(destination,tmp_path/"unused",source)
    assert (destination/record["path"]).read_bytes()==data
    assert (destination/record["path"]).stat().st_mode & 0o222 == 0


def test_corrupt_local_source_does_not_publish(tmp_path,monkeypatch):
    record=tiny_record(); source=tmp_path/"source"; source.mkdir()
    (source/record["path"]).write_bytes(b"x"*record["size_bytes"])
    monkeypatch.setattr(stage,"read_manifest",lambda path:({"files":[record]},b"fixture"))
    destination=tmp_path/"destination"
    with pytest.raises(ValueError): stage.stage_data(destination,tmp_path/"unused",source)
    assert not destination.exists()


def test_existing_conflicting_destination_is_preserved(tmp_path,monkeypatch):
    record=tiny_record(); destination=tmp_path/"destination"; destination.mkdir()
    (destination/record["path"]).write_bytes(b"retain conflicting old source")
    monkeypatch.setattr(stage,"read_manifest",lambda path:({"files":[record]},b"fixture"))
    with pytest.raises(ValueError): stage.stage_data(destination,tmp_path/"unused")
    assert (destination/record["path"]).read_bytes()==b"retain conflicting old source"


def fixture_bundle(tmp_path, monkeypatch):
    data=b"mechanics only\n"; record=tiny_record(data)
    source=tmp_path/"source"; source.mkdir(); (source/"tiny.txt").write_bytes(data)
    monkeypatch.setattr(stage, "read_manifest",
        lambda path: ({"files": [record]}, b"fixture manifest"))
    return source, record


@pytest.mark.parametrize("where", ["file", "root", "ancestor"])
def test_source_symlinks_rejected(tmp_path, monkeypatch, where):
    source, record=fixture_bundle(tmp_path,monkeypatch)
    if where == "file":
        (source/"tiny.txt").rename(source/"real.txt")
        (source/"tiny.txt").symlink_to(source/"real.txt")
    elif where == "root":
        original=source; source=tmp_path/"source-link"; source.symlink_to(original, target_is_directory=True)
    else:
        root=tmp_path/"link"; root.symlink_to(tmp_path,target_is_directory=True); source=root/"source"
    with pytest.raises(ValueError, match="Symlink|Nonregular"):
        stage.stage_data(tmp_path/"destination", tmp_path/"ignored", source)


def test_source_unexpected_file_rejected(tmp_path,monkeypatch):
    source,_=fixture_bundle(tmp_path,monkeypatch); (source/"unexpected.txt").write_text("not source")
    with pytest.raises(ValueError,match="Unexpected"):
        stage.stage_data(tmp_path/"destination",tmp_path/"ignored",source)
    assert not (tmp_path/"destination").exists()


def test_source_missing_file_rejected(tmp_path,monkeypatch):
    source,_=fixture_bundle(tmp_path,monkeypatch); (source/"tiny.txt").unlink()
    with pytest.raises(ValueError,match="missing"):
        stage.stage_data(tmp_path/"destination",tmp_path/"ignored",source)


def test_destination_symlink_rejected(tmp_path,monkeypatch):
    source,_=fixture_bundle(tmp_path,monkeypatch)
    target=tmp_path/"destination"; target.symlink_to(tmp_path/"new")
    with pytest.raises(ValueError,match="Symlink"):
        stage.stage_data(target,tmp_path/"ignored",source)


def test_existing_destination_extra_preserved(tmp_path,monkeypatch):
    source,_=fixture_bundle(tmp_path,monkeypatch); target=tmp_path/"destination"
    stage.stage_data(target,tmp_path/"ignored",source)
    (target/"extra").write_text("preserve this")
    with pytest.raises(ValueError,match="Unexpected"):
        stage.stage_data(target,tmp_path/"ignored",source)
    assert (target/"extra").read_text()=="preserve this"


def test_verify_staged_requires_manifest(tmp_path,monkeypatch):
    source,_=fixture_bundle(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match="missing"):
        stage.verify_staged(source)


def test_manifest_symlink_rejected(tmp_path):
    target=tmp_path/"manifest.json"
    target.symlink_to(ENV/"source_manifest.json")
    with pytest.raises(ValueError,match="regular"):
        stage.read_manifest(target)


def test_reference_input_description_is_task_specific():
    source=manifest()
    text=source["derivative_provenance"]["generic_reference"]
    assert "analysis input for PETDVR-001" in text
    assert "not an analysis input" not in text


def test_expired_deadline_never_opens_transport(tmp_path, monkeypatch):
    mock_transport(monkeypatch, lambda *args: pytest.fail("expired deadline must not fetch"))
    with pytest.raises(TimeoutError):
        stage.download_file(tiny_record(), tmp_path/"out", deadline=0)


def test_all_downloads_share_one_total_deadline(tmp_path, monkeypatch):
    data = b"mechanics only\n"
    records = [tiny_record(data), tiny_record(data)]
    records[1]["path"] = "second.txt"
    monkeypatch.setattr(stage, "read_manifest", lambda path: ({"files": records}, b"fixture"))
    deadlines = []
    def capture(record, target, deadline):
        deadlines.append(deadline)
        target.write_bytes(data)
    monkeypatch.setattr(stage, "download_file", capture)
    before = stage.time.monotonic()
    stage.stage_data(tmp_path/"destination", tmp_path/"ignored")
    assert len(deadlines) == 2 and deadlines[0] == deadlines[1]
    assert 0 < deadlines[0]-before <= 180.1


@pytest.mark.parametrize("http", [False, True])
def test_cli_failure_is_sanitized_and_actionable(monkeypatch, capsys, http):
    def fail(*args):
        stage.DIAGNOSTIC.update(phase="download_source", record_path="README")
        if http:
            raise stage.SourceHTTPError(503)
        raise OSError("https://private.invalid/path?token=DO_NOT_LOG server response cookie=secret")
    monkeypatch.setattr(stage, "stage_data", fail)
    monkeypatch.setattr(stage.sys, "argv", ["stage_data.py"])
    with pytest.raises(SystemExit):
        stage.main()
    text = capsys.readouterr().err
    result = json.loads(text)
    assert result["phase"] == "download_source" and result["record_path"] == "README"
    assert "private.invalid" not in text and "DO_NOT_LOG" not in text and "cookie" not in text
    assert result.get("http_status") == (503 if http else None)


def test_exact_published_segmentation_alias_is_permitted():
    record = next(r for r in manifest()["files"] if r["role"] == "segmentation_labels")
    alias = "https://s3.amazonaws.com/openneuro.org/ds001420/derivatives/PETPrep1/sub-02/ses-rescan/pet/agtm/aux/seg.ctab?versionId=fixture"
    assert stage.allowed_endpoint(alias, record)
    assert not stage.allowed_endpoint(alias.replace("sub-02/ses-rescan", "sub-01/ses-rescan"), record)
    assert not stage.allowed_endpoint(alias, next(r for r in manifest()["files"] if r["role"] == "tac"))


def test_alias_body_still_checks_original_record_identity(tmp_path, monkeypatch):
    record = next(r for r in manifest()["files"] if r["role"] == "segmentation_labels")
    calls = []
    def respond(request, timeout):
        calls.append(request.full_url)
        if len(calls) == 1:
            raise stage.urllib.error.HTTPError(request.full_url, 302, "redirect", {"Location":
                "https://s3.amazonaws.com/openneuro.org/ds001420/derivatives/PETPrep1/sub-02/ses-rescan/pet/agtm/aux/seg.ctab?versionId=fixture"}, None)
        return Response(b"x"*record["size_bytes"])
    mock_transport(monkeypatch, respond)
    with pytest.raises(ValueError, match="SHA256"):
        stage.download_file(record, tmp_path/"out")
    assert len(calls) == 2


def test_diagnostic_error_codes_never_relay_arbitrary_messages():
    assert stage.failure_code(ValueError("Unapproved source endpoint")) == "endpoint_rejected"
    assert stage.failure_code(ValueError("Source Content-Length mismatch")) == "content_length_mismatch"
    assert stage.failure_code(ValueError("https://private.invalid/?token=secret")) == "unclassified_local_failure"


def test_published_directories_are_traversable_by_non_build_users(tmp_path, monkeypatch):
    data = b"mechanics only\n"; record = tiny_record(data)
    record["path"] = "nested/deeper/tiny.txt"
    source = tmp_path/"source"; original = source/record["path"]
    original.parent.mkdir(parents=True); original.write_bytes(data)
    source.chmod(0o700)
    monkeypatch.setattr(stage, "read_manifest", lambda path: ({"files": [record]}, b"fixture"))
    target = tmp_path/"destination"
    stage.stage_data(target, tmp_path/"ignored", source)
    for directory in (target, target/"nested", target/"nested/deeper"):
        assert directory.stat().st_mode & 0o777 == 0o755
    assert (target/record["path"]).stat().st_mode & 0o777 == 0o444
    assert (target/"source_manifest.json").stat().st_mode & 0o777 == 0o444
    assert source.stat().st_mode & 0o777 == 0o700
