"""Source-free output parser boundaries only; no production reference imports."""
import importlib.util
import io
import json
from pathlib import Path
import struct
import zipfile

import numpy as np
import pytest

PATH = Path(__file__).resolve().parents[1]/'tests'/'artifact_reader.py'
SPEC = importlib.util.spec_from_file_location('petvt_artifact_reader', PATH)
r = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(r)


def archive(array):
    buffer = io.BytesIO(); np.savez_compressed(buffer, value=array); return buffer.getvalue()


def header_only(descr, shape):
    header = repr(dict(descr=descr, fortran_order=False, shape=shape)).encode()+b'\n'
    return b'\x93NUMPY\x01\x00'+struct.pack('<H', len(header))+header


def fixture_output(tmp_path):
    (tmp_path/'vt_estimates.csv').write_text('subject_id,value\n'+''.join(f's{i},1\n' for i in range(28)))
    (tmp_path/'kinetic_evidence.npz').write_bytes(archive(np.arange(4.)))
    for name in ('sensitivity_summary.json', 'run_metadata.json'): (tmp_path/name).write_text('{}')
    (tmp_path/'findings.md').write_text('Manufactured parser fixture, not scientific evidence.')
    return tmp_path


def test_bounded_own_buffers_roundtrip(tmp_path):
    out = r.read_output(fixture_output(tmp_path))
    assert len(out['rows']) == 28 and set(out['file_sha256']) == set(r.CAPS)
    np.testing.assert_array_equal(out['arrays']['value'], np.arange(4.))


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}', b'[]', b'\xff'])
def test_json_strict(raw):
    with pytest.raises(r.ContractError): r.json_bytes(raw)


def test_json_depth():
    raw = b'{"x":'+b'['*65+b'0'+b']'*65+b'}'
    with pytest.raises(r.ContractError): r.json_bytes(raw)


@pytest.mark.parametrize('array', [np.array([object()], dtype=object), np.array([1+0j]),
    np.array([np.nan]), np.array([np.inf]), np.array([(1,)], dtype=[('x', 'i4')]), np.array(['2000'], dtype='datetime64[Y]')])
def test_unsafe_arrays(array):
    with pytest.raises(r.ContractError): r.npz_bytes(archive(array))


@pytest.mark.parametrize('dtype', ['U0', 'S0'])
def test_zero_width_huge_logical_shape_rejected_before_load(dtype, monkeypatch):
    monkeypatch.setattr(r.np, 'load', lambda *a, **k: (_ for _ in ()).throw(AssertionError('load reached')))
    with pytest.raises(r.ContractError, match='shape domain'):
        r.npy_bytes(header_only(dtype, (r.NPY_ELEMENTS+1,)))


def test_duplicate_npz_name_and_traversal():
    for names in (['x.npy', 'x.npy'], ['../x.npy']):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as z:
            for name in names: z.writestr(name, header_only('f8', (0,)))
        with pytest.raises(r.ContractError): r.npz_bytes(buffer.getvalue())


@pytest.mark.parametrize('bad', ['a,a\n1,2\n', 'a,b\n1\n', 'a\n1\x00\n', 'a\n1\n'])
def test_csv_strict(bad):
    with pytest.raises(r.ContractError): r.csv_bytes(bad.encode())


def test_csv_extra_column_and_reordered_rows_allowed():
    raw = 'value,subject_id,extra\n'+''.join(f'1,s{i},note\n' for i in reversed(range(28)))
    assert r.csv_bytes(raw.encode())[0]['subject_id'] == 's27'


@pytest.mark.parametrize('mutation', ['failure', 'symlink', 'hardlink', 'empty_findings', 'directory'])
def test_output_namespace_and_file_boundaries(tmp_path, mutation):
    out = tmp_path/'out'; out.mkdir(); fixture_output(out)
    if mutation == 'failure': (out/'failure_report.json').write_text('{}')
    if mutation == 'symlink':
        (out/'findings.md').rename(tmp_path/'outside'); (out/'findings.md').symlink_to(tmp_path/'outside')
    if mutation == 'hardlink': (tmp_path/'linked').hardlink_to(out/'findings.md')
    if mutation == 'empty_findings': (out/'findings.md').write_text(' ')
    if mutation == 'directory': (out/'findings.md').unlink(); (out/'findings.md').mkdir()
    with pytest.raises(r.ContractError): r.read_output(out)


def test_harmless_extra_scripts_and_nested_reports_are_not_parsed(tmp_path):
    fixture_output(tmp_path)
    (tmp_path/'working.py').write_text('This is not imported or executed')
    (tmp_path/'plots').mkdir(); (tmp_path/'plots'/'plot.bin').write_bytes(b'\xff')
    assert len(r.read_output(tmp_path)['rows']) == 28


def test_extra_symlink_is_not_followed(tmp_path):
    fixture_output(tmp_path); (tmp_path/'extra').symlink_to('/absent')
    with pytest.raises(r.ContractError, match='regular'):
        r.read_output(tmp_path)


def test_no_write_or_atime_identity_requirement(tmp_path):
    path = tmp_path/'file'; path.write_bytes(b'abc'); before = path.stat()
    assert r.read_file(path, 3) == b'abc'
    assert before.st_mtime_ns == path.stat().st_mtime_ns
