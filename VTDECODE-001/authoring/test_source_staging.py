"""Small corrupt-source fixtures for the task's build-only staging boundary."""
import hashlib
import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "environment/fetch_data.py"
spec = importlib.util.spec_from_file_location("pr140_fetch", MODULE_PATH)
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def fixture(tmp_path, symlink=False):
    archive = tmp_path / "tiny.tar.gz"
    files = []
    with tarfile.open(archive, "w:gz") as output:
        for index, name in enumerate(sorted(fetch.SOURCE_FILES)):
            content = (name + " fixture bytes").encode()
            item = tarfile.TarInfo(name)
            item.size = len(content)
            if symlink and index == 0:
                item.type = tarfile.SYMTYPE
                item.linkname = "/etc/passwd"
                output.addfile(item)
            else:
                output.addfile(item, io.BytesIO(content))
            files.append({"path": name, "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
    blob = archive.read_bytes()
    manifest = {"files": files, "archive": {"size_bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "md5": hashlib.md5(blob).hexdigest()}}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return archive, manifest, manifest_path


def test_valid_allowlisted_package(tmp_path):
    archive, manifest, manifest_path = fixture(tmp_path)
    destination = tmp_path / "staged"
    fetch.stage_data(destination, manifest_path, archive)
    assert {str(path.relative_to(destination)) for path in destination.rglob("*") if path.is_file()} == fetch.SOURCE_FILES | {"data_manifest.json"}


@pytest.mark.parametrize("field,value", [("sha256", "0" * 64), ("md5", "0" * 32), ("size_bytes", 0)])
def test_changed_archive_rejected(tmp_path, field, value):
    archive, manifest, manifest_path = fixture(tmp_path)
    manifest["archive"][field] = value
    manifest_path.write_text(json.dumps(manifest))
    destination = tmp_path / "staged"
    with pytest.raises(ValueError, match="mismatch"):
        fetch.stage_data(destination, manifest_path, archive)
    assert not list(destination.rglob("*.gz"))


def test_changed_member_rejected_before_publication(tmp_path):
    archive, manifest, manifest_path = fixture(tmp_path)
    manifest["files"][-1]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    destination = tmp_path / "staged"
    with pytest.raises(ValueError, match="sha256 mismatch"):
        fetch.stage_data(destination, manifest_path, archive)
    assert not list(destination.rglob("*.gz"))


def test_symlink_member_rejected(tmp_path):
    archive, manifest, manifest_path = fixture(tmp_path, symlink=True)
    with pytest.raises(ValueError, match="Invalid archive member"):
        fetch.stage_data(tmp_path / "staged", manifest_path, archive)


def test_path_traversal_manifest_rejected(tmp_path):
    archive, manifest, manifest_path = fixture(tmp_path)
    manifest["files"][0]["path"] = "../outside"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="exactly the three"):
        fetch.stage_data(tmp_path / "staged", manifest_path, archive)
