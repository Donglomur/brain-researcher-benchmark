"""Bounded manufactured I/O only; no original sources or task imports."""
import os

import numpy as np
import pytest

import artifact_reader as a
def emit(output):
    output.mkdir()
    for name in a.REQUIRED:
        path = output / name
        if name.endswith(".csv"): path.write_bytes(b"a,b\n1,2\n")
        elif name.endswith(".json"): path.write_bytes(b"{}")
        else: path.write_text("Manufactured bounded I/O fixture.\n")


def test_five_complete_artifacts_and_harmless_extra(tmp_path):
    output = tmp_path / "output"; emit(output)
    (output / "optional.txt").write_text("A finite harmless extra.")
    assert set(a.read_artifacts(output)) == set(a.REQUIRED)


@pytest.mark.parametrize("kind", ["empty", "dangling", "directory", "receipt"])
def test_authoritative_failure_even_empty_or_dangling(tmp_path, kind):
    output = tmp_path / "output"; emit(output); marker = output / a.FAILURE
    if kind == "empty": marker.touch()
    if kind == "dangling": marker.symlink_to(output / "absent")
    if kind == "directory": marker.mkdir()
    if kind == "receipt": marker.write_text('{"status":"failed"}')
    with pytest.raises(ValueError, match="authoritative"): a.read_artifacts(output)


@pytest.mark.parametrize("kind", ["fifo", "symlink", "dangling"])
def test_special_inventory_rejected_without_blocking(tmp_path, kind):
    output = tmp_path / "output"; emit(output); extra = output / "extra"
    if kind == "fifo": os.mkfifo(extra)
    if kind == "symlink": extra.symlink_to(output / "findings.md")
    if kind == "dangling": extra.symlink_to(output / "absent")
    with pytest.raises(ValueError, match="nonregular"): a.read_artifacts(output)


def test_symlink_ancestor_not_hidden_by_dotdot(tmp_path):
    (tmp_path / "real").mkdir(); (tmp_path / "link").symlink_to(tmp_path / "real")
    (tmp_path / "safe.txt").write_text("safe")
    with pytest.raises(ValueError, match="symlink"): a.read_bytes(tmp_path / "link" / ".." / "safe.txt", 100)


@pytest.mark.parametrize("payload", [b'{"x":1,"x":2}', b'{"a":{"x":1,"x":2}}', b'{"x":NaN}', b'{"x":Infinity}', b'{"note":[1e999]}', b'[]'])
def test_strict_json(payload):
    with pytest.raises(ValueError): a.parse_json(payload)


@pytest.mark.parametrize("payload", [b'a,a\n1,2\n', b'a,b\n1\n', b'a,b\n1,2,3\n', b'a,b\n1,\x00\n', b',b\n1,2\n'])
def test_strict_csv(payload):
    with pytest.raises(ValueError): a.parse_csv(payload)


def test_numeric_key_aliases_collide_but_literal_ids_do_not():
    with pytest.raises(ValueError, match="duplicate"):
        a.keyed_rows([dict(frame="1"), dict(frame="1e0")], ["frame"], integer_columns=["frame"])
    assert len(a.keyed_rows([dict(id="001"), dict(id="1")], ["id"])) == 2


@pytest.mark.parametrize("value", [True, "1e100000000", 2**63, -2**63-1, np.inf, .5])
def test_integer_range_bool_and_fraction(value):
    with pytest.raises(ValueError): a.integer(value)


def test_exact_large_integer_and_integral_json_float():
    assert a.integer(str(2**53+1)) == 2**53+1
    assert a.integer(2**63-1) == 2**63-1
    assert a.integer(1.0, json_number=True) == 1


def test_same_buffer_small_file_and_oversize_guard(tmp_path):
    path = tmp_path / "tiny"; path.write_bytes(b"abc")
    assert a.read_bytes(path, 3) == b"abc"
    with pytest.raises(ValueError, match="oversized"): a.read_bytes(path, 2)


def test_late_failure_marker_rejects(tmp_path, monkeypatch):
    output = tmp_path / "output"; emit(output)
    original = a.read_bytes
    def read(path, cap):
        data = original(path, cap)
        if path.name == "findings.md": (output / a.FAILURE).touch()
        return data
    monkeypatch.setattr(a, "read_bytes", read)
    with pytest.raises(ValueError, match="authoritative"): a.read_artifacts(output)
