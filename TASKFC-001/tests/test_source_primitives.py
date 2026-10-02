"""Manufactured bytes only: no original source path or bank is opened."""
import gzip
import hashlib
import io
from pathlib import Path
import struct

import nibabel as nib
import numpy as np
import pytest

import source_primitives as s


def toy_bytes(dtype='<i2', slope=2.5, intercept=-7., offset=352):
    shape = (40, 5, 5, 4)
    values = np.arange(np.prod(shape)).reshape(shape, order='F').astype(dtype)
    h = nib.Nifti1Header(endianness='>' if dtype.startswith('>') else '<')
    h.set_data_shape(shape); h.set_data_dtype(dtype)
    h.set_zooms((2., 2., 2., 1.5)); h.set_xyzt_units('mm', 'sec')
    a = np.array([[2., 0, 0, -40], [0, 2., 0, -94], [0, 0, 2., -10], [0, 0, 0, 1]])
    h.set_sform(a, code=4); h.set_qform(a, code=4)
    h['vox_offset'] = offset; h['scl_slope'] = slope; h['scl_inter'] = intercept
    logical = h.binaryblock+b'\0'*4+b'\0'*(offset-352)+values.tobytes(order='F')
    return logical, values, a


def save_toy(tmp_path, raw, name='image.nii.gz'):
    content = gzip.compress(raw) if name.endswith('.gz') else raw
    path = tmp_path/name; path.write_bytes(content)
    return path, dict(size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())


@pytest.mark.parametrize('dtype', ['<i2', '>i2', '<f4', '>f4', '<f8'])
@pytest.mark.parametrize('compressed', [True, False])
def test_stream_source_scaling_endian_fortran_and_float64(tmp_path, dtype, compressed):
    raw, values, affine = toy_bytes(dtype)
    path, row = save_toy(tmp_path, raw, 'image.nii.gz' if compressed else 'image.nii')
    observed, header, supports = s.extract_series(path, row)
    indices = s.sphere_support(values.shape[:3], affine)
    expected = np.array([[np.mean(values[..., t].astype(float).ravel(order='C')[idx]*2.5-7.)
                          for idx in indices] for t in range(4)])
    np.testing.assert_array_equal(observed, expected)
    assert observed.dtype == np.float64
    assert header['zooms'][-1] == 1.5 and header['spatial_units'] == 'mm'
    assert header['qform_code'] == header['sform_code'] == 4
    assert supports == s.support_records(indices)


def test_header_read_never_logical_sample(tmp_path, monkeypatch):
    raw, _, _ = toy_bytes()
    path, row = save_toy(tmp_path, raw)
    real = gzip.GzipFile
    reads = []
    class Guard:
        def __init__(self, *args, **kwargs): self.inner = real(*args, **kwargs)
        def __enter__(self): return self
        def __exit__(self, *args): self.inner.close()
        def read(self, n):
            reads.append(n)
            assert n == 352 and len(reads) == 1
            return self.inner.read(n)
    monkeypatch.setattr(s.gzip, 'GzipFile', Guard)
    assert s.read_header(path, row)[0]['shape'][-1] == 4
    assert reads == [352]


@pytest.mark.parametrize('offset', [352, 368, 512])
def test_data_offset_respected(tmp_path, offset):
    raw, _, _ = toy_bytes(offset=offset)
    path, row = save_toy(tmp_path, raw)
    out, header, _ = s.extract_series(path, row)
    assert header['vox_offset'] == offset and np.isfinite(out).all()


@pytest.mark.parametrize('change', ['short', 'trailing'])
def test_decoded_size_rejected(tmp_path, change):
    raw, _, _ = toy_bytes()
    path, row = save_toy(tmp_path, raw[:-1] if change == 'short' else raw+b'x')
    with pytest.raises(ValueError, match='truncated_volume|extra_decoded'):
        s.extract_series(path, row)


def test_header_mismatch_cannot_supply_other_geometry(tmp_path):
    raw, _, _ = toy_bytes()
    path, row = save_toy(tmp_path, raw)
    header = s.read_header(path, row)[0]; header['zooms'][-1] = 2.
    with pytest.raises(ValueError, match='header_changed'):
        s.extract_series(path, row, header)


def test_selected_finite_policy_not_whole_image_gate(tmp_path):
    raw, values, affine = toy_bytes('<f4', slope=1., intercept=0.)
    support = s.sphere_support(values.shape[:3], affine)
    outside = next(i for i in range(np.prod(values.shape[:3])) if all(i not in x for x in support))
    image = values.copy()
    xyz = np.unravel_index(outside, image.shape[:3], order='C'); image[xyz+(0,)] = np.nan
    path, row = save_toy(tmp_path, raw[:352]+image.tobytes(order='F'))
    assert np.isfinite(s.extract_series(path, row)[0]).all()
    xyz = np.unravel_index(int(support[0][0]), image.shape[:3], order='C'); image[xyz+(0,)] = np.inf
    path2, row2 = save_toy(tmp_path, raw[:352]+image.tobytes(order='F'), 'bad.nii.gz')
    with pytest.raises(ValueError, match='measured_voxel'):
        s.extract_series(path2, row2)


@pytest.mark.parametrize('slope', [0., float('nan')])
def test_unspecified_slope_uses_nifti_identity(slope):
    raw, _, _ = toy_bytes(slope=slope, intercept=10.)
    header, _, _ = s.header_from_bytes(raw[:352])
    assert header['effective_slope'] == 1. and header['effective_intercept'] == 0.
    assert header['raw_scl_slope'] == ('NaN' if np.isnan(slope) else 0.)


def test_invalid_effective_intercept_refused():
    raw, _, _ = toy_bytes(slope=2., intercept=float('nan'))
    with pytest.raises((ValueError, nib.spatialimages.HeaderDataError)):
        s.header_from_bytes(raw[:352])


@pytest.mark.parametrize('change', ['size', 'digest'])
def test_source_hash_or_size_before_parse(tmp_path, monkeypatch, change):
    raw, _, _ = toy_bytes(); path, row = save_toy(tmp_path, raw)
    if change == 'size': row['size_bytes'] += 1
    else: row['sha256'] = '0'*64
    monkeypatch.setattr(s, 'header_from_bytes', lambda _: pytest.fail('parsed before authentication'))
    with pytest.raises(ValueError): s.read_header(path, row)


@pytest.mark.parametrize('constant_stat_clock', [False, True])
def test_same_descriptor_change_detected(tmp_path, monkeypatch, constant_stat_clock):
    raw = b'1234'; path = tmp_path/'opaque'; path.write_bytes(raw)
    row = dict(size_bytes=4, sha256=hashlib.sha256(raw).hexdigest())
    if constant_stat_clock:
        monkeypatch.setattr(s, 'signature', lambda _: ('fixed_metadata_clock',))
    with pytest.raises(ValueError, match='changed_during'):
        with s.authenticated_stream(path, row) as stream:
            assert stream.read() == raw
            path.write_bytes(b'5678')


@pytest.mark.parametrize('path_type', ['symlink', 'fifo', 'ancestor'])
def test_unsafe_source_path(tmp_path, path_type):
    target = tmp_path/'real'; target.write_bytes(b'x')
    link = tmp_path/'link'
    if path_type == 'symlink': link.symlink_to(target)
    elif path_type == 'fifo':
        import os
        os.mkfifo(link)
    else:
        link.symlink_to(tmp_path, target_is_directory=True); link = link/'real'
    with pytest.raises(ValueError):
        with s.authenticated_stream(link, dict(size_bytes=1, sha256=hashlib.sha256(b'x').hexdigest())): pass


def test_geometric_boundary_and_chunk_invariance():
    for chunk in (1, 7, 100):
        support = s.sphere_support((5, 5, 5), np.eye(4), [(2, 2, 2)]*2, 1., chunk)
        expected = [i for i, xyz in enumerate(np.ndindex(5, 5, 5)) if sum((x-2)**2 for x in xyz) <= 1]
        np.testing.assert_array_equal(support[0], expected)
        assert len(expected) == 7


def test_no_nearest_voxel_rescue():
    with pytest.raises(ValueError, match='empty_sphere'):
        s.sphere_support((2, 2, 2), np.eye(4), [(0.5, 0.5, 0.5)]*2, .1)


def test_support_digest_is_little_endian_with_public_prefix():
    ids = [np.array([0, 2, 9]), np.array([1, 8])]
    result = s.support_records(ids)
    assert result[0]['support_sha256'] == hashlib.sha256(b'TASKFC_support_v2\n'+struct.pack('<3q', 0, 2, 9)).hexdigest()


@pytest.mark.parametrize('raw', [b'a\ta\n1\t2\n', b'a\tb\n1\n', b'\ta\n1\t2\n', b''])
def test_table_structure_rejected(raw):
    with pytest.raises(ValueError): s.table(raw)


def test_event_tokens_preserved_and_default_amplitude():
    raw = b'onset\tduration\ttrial_type\n01.00\t2e0\tlanguage\n3\t0\tstring\n'
    columns, parsed, records = s.events(raw)
    assert parsed[0]['onset'] == 1. and parsed[0]['modulation'] == 1.
    assert records[0]['original']['onset'] == '01.00'
    assert records[1]['numeric']['duration'] == 0.


@pytest.mark.parametrize('token', ['', 'n/a', 'NaN', 'Inf', '1e999', 'true'])
def test_invalid_numeric_tokens(token):
    with pytest.raises(ValueError): s.number(token)


def test_no_motion_fill_or_missing_column():
    raw = ('\t'.join(s.MOTION)+'\n'+'\t'.join(['0']*6)+'\n'+'\t'.join(['n/a']*6)+'\n').encode()
    with pytest.raises(ValueError): s.motion(raw, 2)
    with pytest.raises(ValueError): s.motion(b'X\tY\n1\t2\n', 1)


def test_motion_extra_columns_are_documentary():
    columns = [*s.MOTION, 'note']
    raw = ('\t'.join(columns)+'\n'+'\t'.join(['0']*6+['hello'])+'\n').encode()
    observed_columns, values = s.motion(raw, 1)
    assert observed_columns == columns
    np.testing.assert_array_equal(values, np.zeros((1, 6)))
