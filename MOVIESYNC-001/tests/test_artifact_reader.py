"""Manufactured byte/parser fixtures only; no task/source/bank inputs."""
from decimal import Decimal
import io
import os
import stat
import warnings
import zipfile

import numpy as np
import pytest

import artifact_reader as a


def npz_bytes(**arrays):
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    return buffer.getvalue()


def manufactured_output(root):
    root.mkdir()
    for name in a.REQUIRED:
        path = root / name
        if name.endswith(".csv"):
            path.write_text("participant_id,value\nsub-pixar001,1.25\n", encoding="utf-8")
        elif name.endswith(".json"):
            path.write_text('{"status":"complete","descriptive_extra":{"x":1.25}}')
        elif name.endswith(".npz"):
            path.write_bytes(npz_bytes(axis=np.array([1, 2]), values=np.array([[1., 2.]])))
        else:
            path.write_text("Any honest interpretation, including null or opposite effects.\n")
    return root


def single_zip(name, payload, *, mode=None, compression=zipfile.ZIP_STORED):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        info = zipfile.ZipInfo(name)
        info.compress_type = compression
        if mode is not None:
            info.external_attr = mode << 16
        archive.writestr(info, payload)
    return stream.getvalue()


def npy_bytes(array):
    stream = io.BytesIO()
    np.save(stream, array, allow_pickle=True)
    return stream.getvalue()


def test_import_and_reader_have_no_scientific_authority(tmp_path):
    root = manufactured_output(tmp_path / "output")
    # The I/O helper deliberately accepts a tiny schema-incomplete fake. It must
    # never be presented as proof of source identity or science/completeness.
    result = a.read_artifacts(root)
    assert set(result) == set(a.REQUIRED)
    assert result["isc_results.json"]["descriptive_extra"]["x"] == Decimal("1.25")


# Public output_schema.json is not frozen yet. The schema integration fixture
# is deliberately deferred, not conditionally skipped or guessed here.


@pytest.mark.parametrize("kind", ["empty", "json", "dangling", "directory"])
def test_authoritative_failure_always_rejected(tmp_path, kind):
    root = manufactured_output(tmp_path / "output")
    failure = root / a.FAILURE
    if kind == "dangling":
        failure.symlink_to(root / "missing")
    elif kind == "directory":
        failure.mkdir()
    else:
        failure.write_text("" if kind == "empty" else '{"failed":true}')
    with pytest.raises(a.ArtifactError, match="failure_report"):
        a.read_artifacts(root)


@pytest.mark.parametrize("name", a.REQUIRED)
def test_missing_required_file(tmp_path, name):
    root = manufactured_output(tmp_path / "output")
    (root / name).unlink()
    with pytest.raises(a.ArtifactError, match="missing"):
        a.read_artifacts(root)


@pytest.mark.parametrize("kind", ["symlink", "dangling", "fifo", "directory"])
def test_nonregular_input_rejected_without_blocking(tmp_path, kind):
    file = tmp_path / "field"
    if kind in ("symlink", "dangling"):
        target = tmp_path / "target"
        if kind == "symlink":
            target.write_text("valid")
        file.symlink_to(target)
    elif kind == "fifo":
        os.mkfifo(file)
    else:
        file.mkdir()
    with pytest.raises(a.ArtifactError):
        a.read_bytes(file, 100)


def test_symlink_ancestor_even_with_dotdot(tmp_path):
    real = tmp_path / "real"; real.mkdir()
    link = tmp_path / "link"; link.symlink_to(real, target_is_directory=True)
    (real / "data").write_text("safe")
    (tmp_path / "data").write_text("safe")
    for path in (link / "data", link / ".." / "data"):
        with pytest.raises(a.ArtifactError, match="symlink"):
            a.read_bytes(path, 100)


@pytest.mark.parametrize("size", [0, 101])
def test_empty_or_overcap_file(tmp_path, size):
    path = tmp_path / "file"; path.write_bytes(b"x" * size)
    with pytest.raises(a.ArtifactError, match="empty/oversized"):
        a.read_bytes(path, 100)


def test_source_replaced_during_artifact_read(tmp_path, monkeypatch):
    path = tmp_path / "file"; path.write_bytes(b"old")
    original_fdopen = a.os.fdopen
    class SwapAfterRead:
        def __init__(self, handle): self.handle = handle
        def __enter__(self): return self
        def __exit__(self, *args): self.handle.close()
        def fileno(self): return self.handle.fileno()
        def read(self, maximum):
            result = self.handle.read(maximum)
            replacement = tmp_path / "replacement"; replacement.write_bytes(b"new")
            replacement.replace(path)
            return result
    monkeypatch.setattr(a.os, "fdopen", lambda *args: SwapAfterRead(original_fdopen(*args)))
    with pytest.raises(a.ArtifactError, match="changed|replaced"):
        a.read_bytes(path, 100)


@pytest.mark.parametrize("payload", [b'{"a":1,"a":2}', b'{"x":{"a":1,"a":2}}',
                                       b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}',
                                       b'{"extra":{"deep":[1e999]}}', b'[]', b'null', b'\xff', b'{'])
def test_invalid_json(payload):
    with pytest.raises((a.ArtifactError, ValueError)):
        a.parse_json(payload)


def test_json_depth_and_bom(monkeypatch):
    assert a.parse_json(b'\xef\xbb\xbf{"x":1}') == {"x": 1}
    monkeypatch.setitem(a.CAPS, "depth", 3)
    with pytest.raises(a.ArtifactError, match="nesting"):
        a.parse_json(b'{"x":[[[[1]]]]}')


@pytest.mark.parametrize("value,expected", [("9007199254740993", 9007199254740993),
                                          ("9.007199254740993e15", 9007199254740993),
                                          (str(2**63-1), 2**63-1), (str(-(2**63)), -(2**63)),
                                          ("1.0", 1), ("-2e0", -2)])
def test_exact_integer_tokens(value, expected):
    assert a.integer(value) == expected


@pytest.mark.parametrize("value", [True, np.bool_(False), "1.5", "nan", "inf", "1e100000000",
                                  str(2**63), str(-(2**63)-1), complex(1, 0), None])
def test_invalid_integer(value):
    with pytest.raises(a.ArtifactError):
        a.integer(value)


def test_json_numeric_not_text_or_boolean():
    for func in (a.integer, a.real):
        for value in ("1", True, None):
            with pytest.raises(a.ArtifactError):
                func(value, json_number=True)
    assert a.integer(Decimal("9007199254740993"), json_number=True) == 9007199254740993
    assert a.real(Decimal("1.25"), json_number=True) == 1.25


@pytest.mark.parametrize("token,expected", [("0", False), ("1", True), ("TRUE", True), ("false", False)])
def test_boolean_literals(token, expected):
    assert a.csv_boolean(token) is expected


@pytest.mark.parametrize("token", ["1e0", "0.0", "yes", "", " true", 1])
def test_invalid_boolean_literals(token):
    with pytest.raises(a.ArtifactError): a.csv_boolean(token)


def test_csv_reorder_extras_scientific_bom():
    rows = a.parse_csv(b'\xef\xbb\xbfdescription,id,value\nharmless,B,1e-2\nalso harmless,A,0.0\n')
    keyed = a.keyed_rows(rows, ["id"])
    assert list(keyed) == [("B",), ("A",)]
    assert a.real(keyed[("B",)]["value"]) == .01


@pytest.mark.parametrize("payload", [b'a,a\n1,2\n', b'a,\n1,2\n', b'a,b\n1\n',
                                       b'a,b\n1,2,3\n', b'a\n\x00\n', b'\xff', b'a\n"unclosed'])
def test_invalid_csv(payload):
    with pytest.raises(a.ArtifactError): a.parse_csv(payload)


def test_csv_caps_and_duplicate_keys(monkeypatch):
    monkeypatch.setitem(a.CAPS, "rows", 1)
    with pytest.raises(a.ArtifactError, match="row cap"):
        a.parse_csv(b'a\n1\n2\n')
    with pytest.raises(a.ArtifactError, match="duplicate"):
        a.keyed_rows([{"id": "a"}, {"id": "a"}], ["id"])
    with pytest.raises(a.ArtifactError, match="key columns"):
        a.keyed_rows([{"x": "a"}], ["id"])


def test_integer_csv_key_collision_but_literal_subject_ids():
    rows = [{"subject": "sub-pixar001", "row": "1"}, {"subject": "sub-pixar001", "row": "1e0"}]
    with pytest.raises(a.ArtifactError, match="duplicate"):
        a.keyed_rows(rows, ["subject", "row"], integer_columns=["row"])
    keyed = a.keyed_rows([{"subject": "sub-pixar001", "row": "0"},
                         {"subject": "sub-pixar1", "row": "0.0"}],
                        ["subject", "row"], integer_columns=["row"])
    assert set(keyed) == {("sub-pixar001", 0), ("sub-pixar1", 0)}


@pytest.mark.parametrize("dtype", [np.int8, np.int64, np.uint64, np.float32, np.float64])
def test_integral_axis_dtypes(dtype):
    np.testing.assert_array_equal(a.integer_array(np.array([2, 0, 1], dtype=dtype)), [2, 0, 1])


@pytest.mark.parametrize("array", [np.array([True]), np.array([1.25]), np.array([np.nan]),
                                  np.array([float(2**63)]), np.array([2**63], dtype=np.uint64),
                                  np.array(["1"])])
def test_bad_axis(array):
    with pytest.raises(a.ArtifactError): a.integer_array(array)


def test_npz_float32_byte_text_fortran_and_coherent_permutations():
    values = np.array([[1.25, 2.5], [3.75, 5]], dtype=np.float32)
    result = a.parse_npz(npz_bytes(ids=np.array([b"B", b"A"]),
                                  values=np.asfortranarray(values[::-1, ::-1])))
    assert result["values"].dtype == np.float32
    np.testing.assert_array_equal(result["values"], values[::-1, ::-1])


@pytest.mark.parametrize("array", [np.array([object()], dtype=object), np.array([1+2j]),
                                  np.array([(1,)], dtype=[("field", "i4")]),
                                  np.array([np.nan]), np.array([np.inf]),
                                  np.array([b'\xff'], dtype='S1')])
def test_disallowed_npz_array(array):
    with pytest.raises(a.ArtifactError):
        a.parse_npz(single_zip("a.npy", npy_bytes(array)))


def test_duplicate_npz_members():
    stream = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("a.npy", npy_bytes(np.array([1])))
            archive.writestr("a.npy", npy_bytes(np.array([2])))
    with pytest.raises(a.ArtifactError, match="duplicate"):
        a.parse_npz(stream.getvalue())


def test_higher_dimensional_harmless_extra_is_allowed():
    arrays=a.parse_npz(npz_bytes(diagnostic=np.zeros((1,2,1,2))))
    assert arrays["diagnostic"].shape==(1,2,1,2)


@pytest.mark.parametrize("name", ["../a.npy", "/a.npy", "dir/a.npy", "dir\\a.npy", ".npy", "a.txt"])
def test_unsafe_zip_name(name):
    with pytest.raises(a.ArtifactError):
        a.parse_npz(single_zip(name, npy_bytes(np.array([1]))))


@pytest.mark.parametrize("mode", [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFDIR])
def test_nonregular_zip_member(mode):
    with pytest.raises(a.ArtifactError):
        a.parse_npz(single_zip("a.npy", npy_bytes(np.array([1])), mode=mode))


def test_declared_huge_shape_before_allocation():
    stream = io.BytesIO()
    np.lib.format.write_array_header_1_0(stream, {"descr": "<f8", "fortran_order": False,
                                               "shape": (10**12,)})
    with pytest.raises(a.ArtifactError, match="cap"):
        a.parse_npz(single_zip("a.npy", stream.getvalue()))


def test_npz_caps_and_length_mismatch(monkeypatch):
    payload = npz_bytes(a=np.ones(100))
    monkeypatch.setitem(a.CAPS, "expanded", 100)
    with pytest.raises(a.ArtifactError, match="expanded cap"):
        a.parse_npz(payload)
    monkeypatch.setitem(a.CAPS, "expanded", 100000)
    raw = npy_bytes(np.array([1.]))
    with pytest.raises(a.ArtifactError, match="payload/shape"):
        a.parse_npz(single_zip("a.npy", raw + b"extra"))


@pytest.mark.parametrize("payload", [b"", b"garbage", b"PK\x03\x04"])
def test_corrupt_npz(payload):
    with pytest.raises(a.ArtifactError): a.parse_npz(payload)


def test_blank_findings_and_harmless_unread_extra(tmp_path):
    root = manufactured_output(tmp_path / "output")
    (root / "harmless_description.txt").write_text("not used as evidence")
    assert a.read_artifacts(root)
    (root / "findings.md").write_text(" \n")
    with pytest.raises(a.ArtifactError, match="empty findings"):
        a.read_artifacts(root)
