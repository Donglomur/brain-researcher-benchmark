"""Bounded manufactured I/O only; no original sources or task imports."""
import io
import os
import zipfile

import numpy as np
import pytest

import artifact_reader as a
def emit(output):
    output.mkdir()
    for name in a.REQUIRED:
        path = output / name
        if name.endswith(".csv"): path.write_bytes(b"a,b\n1,2\n")
        elif name.endswith(".json"): path.write_bytes(b"{}")
        elif name.endswith(".npz"): np.savez(path, x=np.ones(1))
        else: path.write_text("Manufactured bounded I/O fixture.\n")


def npz_bytes(**arrays):
    handle = io.BytesIO(); np.savez(handle, **arrays); return handle.getvalue()


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


def test_exact_large_integer_and_integral_npz_float():
    assert a.integer(str(2**53+1)) == 2**53+1
    assert a.integer(2**63-1) == 2**63-1
    assert np.array_equal(a.integer_array(np.array([0., 1.])), [0, 1])


@pytest.mark.parametrize("array", [np.array([True]), np.array([.5]), np.array([np.inf]), np.array([2**63], dtype=np.uint64)])
def test_bad_numeric_axes(array):
    with pytest.raises(ValueError): a.integer_array(array)


@pytest.mark.parametrize("array", [np.array([np.nan]), np.array([np.inf]), np.array([1+2j]), np.array([object()], dtype=object)])
def test_npz_dtypes_and_nonfinite(array):
    with pytest.raises(ValueError): a.parse_npz(npz_bytes(x=array))


def test_bounded_highdim_optional_npz_member_is_accepted():
    value = np.ones((1,) * 12)
    assert a.parse_npz(npz_bytes(extra=value))["extra"].shape == value.shape


def test_duplicate_zip_member_rejected():
    payload = npz_bytes(x=np.array([1.])); stream = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(payload)) as source: member = source.read("x.npy")
    with zipfile.ZipFile(stream, "w") as dest:
        dest.writestr("x.npy", member)
        with pytest.warns(UserWarning): dest.writestr("x.npy", member)
    with pytest.raises(ValueError, match="duplicate"): a.parse_npz(stream.getvalue())


@pytest.mark.parametrize("name", ["../x.npy", "folder/x.npy", "\\x.npy", ".npy"])
def test_unsafe_member_names(name):
    array = io.BytesIO(); np.save(array, np.ones(1)); output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive: archive.writestr(name, array.getvalue())
    with pytest.raises(ValueError, match="unsafe"): a.parse_npz(output.getvalue())


def test_claimed_enormous_shape_rejected_before_array_allocation():
    header = io.BytesIO(); np.lib.format.write_array_header_1_0(header, dict(descr="<f8", fortran_order=False, shape=(10**12,)))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive: archive.writestr("x.npy", header.getvalue())
    with pytest.raises(ValueError, match="cap"): a.parse_npz(stream.getvalue())


def test_same_buffer_small_file_and_oversize_guard(tmp_path):
    path = tmp_path / "tiny"; path.write_bytes(b"abc")
    assert a.read_bytes(path, 3) == b"abc"
    with pytest.raises(ValueError, match="oversized"): a.read_bytes(path, 2)
