"""Manufactured PR200 I/O regressions only; no originals, banks or endpoints.

These fixtures extend the unchanged PR190 numerical suites. They exercise
byte consumption, allocation order and writer failures, not a second estimator.
Execution is parent-gated; importing this file opens only explicit code modules.
Install this fixture under authoring/, never in the production module closure.
"""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
from types import ModuleType, SimpleNamespace
import zipfile

import nibabel as nib
import numpy as np
import pytest

HERE = Path(__file__).absolute().parent
PRIVATE_ROOT = HERE if HERE.name == 'runtime_draft' else HERE.parent / 'tests'
ORACLE_ROOT = HERE if HERE.name == 'runtime_draft' else HERE.parent / 'solution'


def code_module(name, directory):
    # Authoring-only explicit module setup, independent of cwd and cached names.
    # The production entrypoint separately authenticates its complete closure.
    path = directory / (name + '.py')
    raw = path.read_bytes()
    module = ModuleType(name)
    module.__file__, module.__package__ = str(path), ''
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


for name in ('artifact_reader', 'gradient_math', 'source_numerics',
             'source_reference', 'gradient_reporting', 'proof_of_work'):
    code_module(name, PRIVATE_ROOT)
for name in ('core', 'source_reader', 'compute'):
    code_module(name, ORACLE_ROOT)
a, private, proof = (sys.modules[name] for name in
                     ('artifact_reader', 'source_reference', 'proof_of_work'))
oracle, compute = (sys.modules[name] for name in ('source_reader', 'compute'))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def nifti(stored, dtype='<i2', slope=1., intercept=0., extension=False):
    stored = np.asarray(stored)
    header = nib.Nifti1Header(endianness='>' if dtype.startswith('>') else '<')
    header.set_data_shape(stored.shape); header.set_data_dtype(np.dtype(dtype))
    header.set_sform(np.diag([2., 3., 4., 1.]), code=1)
    header.set_slope_inter(slope, intercept); header['magic'] = b'n+1'
    header['vox_offset'] = 384 if extension else 352
    extra = (struct.pack('>ii' if dtype.startswith('>') else '<ii', 32, 6) + b'x' * 24) if extension else b''
    return header.binaryblock + (b'\1\0\0\0' if extension else b'\0' * 4) + extra + stored.astype(dtype).tobytes(order='F')


@pytest.mark.parametrize('endian', ['<', '>'])
@pytest.mark.parametrize('compressed', [False, True])
@pytest.mark.parametrize('extension', [False, True])
@pytest.mark.parametrize('scaling', [(1., 0.), (2., -7.), (-.5, 10.)])
def test_immutable_proxy_preserves_original_nibabel_calibration_layout(tmp_path, endian, compressed, extension, scaling):
    stored = np.arange(48).reshape(2, 3, 2, 4)
    logical = nifti(stored, endian + 'i2', *scaling, extension=extension)
    raw = gzip.compress(logical) if compressed else logical
    path = tmp_path / ('fake.nii.gz' if compressed else 'fake.nii'); path.write_bytes(raw)
    old = nib.load(path).get_fdata(dtype=np.float64)
    image = private.decoded_image(raw, compressed, 4)
    got = image.get_fdata(dtype=np.float64)
    np.testing.assert_array_equal(got, old)
    np.testing.assert_array_equal(got, stored.astype(np.float64) * scaling[0] + scaling[1])
    assert got.flags.c_contiguous == old.flags.c_contiguous
    assert got.flags.f_contiguous == old.flags.f_contiguous
    other, affine, _ = oracle.decode_image(raw, compressed, 4)
    np.testing.assert_array_equal(other, old)
    np.testing.assert_array_equal(image.affine, affine)
    assert all(holder.filename is None for holder in image.file_map.values())


@pytest.mark.parametrize('compressed', [False, True])
def test_authenticated_image_no_longer_reads_changed_source_path(tmp_path, compressed):
    raw = nifti(np.arange(16).reshape(2, 2, 2, 2))
    body = gzip.compress(raw) if compressed else raw
    path = tmp_path / ('fake.nii.gz' if compressed else 'fake.nii'); path.write_bytes(body)
    row = dict(path=path.name, role='bold', size_bytes=len(body), sha256=digest(body))
    identities = {path.name: private.verify_file(path, row)}
    image, _ = private.image(tmp_path, row, identities)
    path.write_bytes(b'x' * len(body))
    np.testing.assert_array_equal(image.get_fdata(dtype=np.float64), np.arange(16).reshape(2, 2, 2, 2))
    # Do not depend on timestamp resolution for detecting a same-size rewrite.
    with pytest.raises(ValueError): private.verify_file(path, row)


@pytest.mark.parametrize('route', ['private', 'oracle'])
@pytest.mark.parametrize('failure', ['header_short', 'huge_shape', 'huge_offset', 'truncated', 'trailing', 'pair_magic'])
def test_bounded_nifti_precheck_precedes_image_construction(route, failure, monkeypatch):
    body = nifti(np.zeros((2, 2, 2, 2)))
    if failure == 'header_short': body = body[:100]
    elif failure == 'truncated': body = body[:-1]
    elif failure == 'trailing': body += b'x'
    else:
        header = nib.Nifti1Header.from_fileobj(io.BytesIO(body[:348]))
        if failure == 'huge_shape': header.set_data_shape((32767, 32767, 2, 2))
        elif failure == 'huge_offset': header['vox_offset'] = 2**30
        else: header['magic'] = b'ni1'
        body = header.binaryblock + body[348:]
    def forbidden(*args, **kwargs): pytest.fail('image constructed before bounded structural precheck')
    monkeypatch.setattr(nib.Nifti1Image, 'from_bytes', forbidden)
    function = private.decoded_image if route == 'private' else oracle.decode_image
    with pytest.raises((ValueError, OSError)): function(body, False, 4)


def fake_source(tmp_path, monkeypatch):
    root = tmp_path / 'source'; root.mkdir(); rows = []
    for i in range(46):
        name, body = 'member_%02d' % i, ('manufactured-%02d' % i).encode()
        (root / name).write_bytes(body)
        rows.append(dict(path=name, role='provenance', participant_id=None,
                         size_bytes=len(body), sha256=digest(body)))
    raw = json.dumps({'files': rows}).encode(); (root / 'source_manifest.json').write_bytes(raw)
    monkeypatch.setattr(private, 'SOURCE_SHA256', digest(raw))
    docs = []
    for name, pin in [('method', 'METHOD_SHA256'), ('schema', 'SCHEMA_SHA256')]:
        path = tmp_path / (name + '.json'); body = json.dumps({'fake': name}).encode(); path.write_bytes(body)
        monkeypatch.setattr(private, pin, digest(body)); docs.append(path)
    return root, rows, docs


@pytest.mark.parametrize('mutation', ['same_size', 'replacement', 'extra', 'method', 'schema'])
def test_private_final_authentication_rejects_post_consumption_change(tmp_path, monkeypatch, mutation):
    root, rows, docs = fake_source(tmp_path, monkeypatch)
    _, identities = private.authenticate_source(root)
    private.final_authentication(root, identities, *docs)
    path = root / rows[0]['path']
    if mutation == 'same_size':
        before = path.stat(); path.write_bytes(b'x' * before.st_size)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    elif mutation == 'replacement':
        fresh = tmp_path / 'replacement'; fresh.write_bytes(path.read_bytes()); fresh.replace(path)
    elif mutation == 'extra': (root / 'extra').write_bytes(b'x')
    else: docs[0 if mutation == 'method' else 1].write_bytes(b'{}')
    with pytest.raises(ValueError): private.final_authentication(root, identities, *docs)


@pytest.mark.parametrize('which', ['method', 'schema'])
def test_oracle_consumed_document_hash_rejects_transient_swap(tmp_path, monkeypatch, which):
    root = tmp_path / 'source'; root.mkdir()
    method, schema = tmp_path / 'method.json', tmp_path / 'schema.json'
    original = b'{"original":true}'
    for path in (method, schema): path.write_bytes(original)
    monkeypatch.setattr(oracle, 'METHOD_SHA256', digest(original))
    monkeypatch.setattr(oracle, 'SCHEMA_SHA256', digest(original))
    real = oracle.stable_bytes
    selected = method if which == 'method' else schema
    def swapped(path, cap, sha256=None):
        if Path(path) != selected: return real(path, cap, sha256)
        assert sha256 == digest(original)
        selected.write_bytes(b'{"attacker":true}')
        try: return real(path, cap, sha256)
        finally: selected.write_bytes(original)
    monkeypatch.setattr(oracle, 'stable_bytes', swapped)
    monkeypatch.setattr(oracle, 'strict_json', lambda *_: pytest.fail('changed document parsed'))
    with pytest.raises(ValueError, match='SHA256 mismatch'): oracle.authenticate(root, method, schema)
    assert method.read_bytes() == schema.read_bytes() == original


@pytest.mark.parametrize('name', ['METHOD_SHA256', 'SCHEMA_SHA256'])
def test_oracle_none_pin_cannot_disable_consumed_buffer_authentication(monkeypatch, name):
    monkeypatch.setattr(oracle, name, None)
    monkeypatch.setattr(oracle, 'stable_bytes', lambda *_: pytest.fail('unfrozen pin opened a file'))
    with pytest.raises(ValueError, match='unfrozen public document pin'):
        oracle.authenticate('/unused', '/unused_method', '/unused_schema')


def test_oracle_final_authentication_compares_original_document_identity(monkeypatch):
    inputs = {'root': Path('/manufactured'), 'identity': {'method_sha256': 'a'}, 'manifest': {'files': []}}
    monkeypatch.setattr(oracle, 'authenticate', lambda *args: dict(inputs, identity={'method_sha256': 'b'}))
    with pytest.raises(ValueError, match='changed through consumption'):
        oracle.reauthenticate(inputs, '/method', '/schema')


def archive_header(name, shape, dtype):
    stream = io.BytesIO()
    np.lib.format.write_array_header_1_0(stream, {'descr': dtype, 'fortran_order': False, 'shape': shape})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive: archive.writestr(name + '.npy', stream.getvalue())
    return buffer.getvalue()


@pytest.mark.parametrize('name', tuple(a.REQUIRED_AXIS_SHAPES))
@pytest.mark.parametrize('dtype', ['|S0', '<U0'])
def test_required_axis_header_rejected_before_numpy_allocation(name, dtype, monkeypatch):
    raw = archive_header(name, (100000000,), dtype)
    monkeypatch.setattr(a.np, 'frombuffer', lambda *args, **kwargs: pytest.fail('allocated before required-axis shape check'))
    with pytest.raises(ValueError, match='required axis shape'): a.parse_npz(raw)


@pytest.mark.parametrize('integer', [False, True])
def test_direct_proof_axis_shape_precedes_conversion(monkeypatch, integer):
    values = np.array(['wrong']) if not integer else np.array([1])
    def forbidden(*args, **kwargs): pytest.fail('converted before fixed shape')
    monkeypatch.setattr(proof, 'strings', forbidden)
    monkeypatch.setattr(a, 'integer_array', forbidden)
    with pytest.raises(ValueError, match='axis size'): proof.axis(values, ['a', 'b'], 'manufactured', integer)


def test_required_axis_byte_ids_and_integral_float_axes_still_accepted():
    arrays = {'participant_ids': np.array([('sub-%02d' % i).encode() for i in range(20)]),
              'frame_indices': np.arange(168, dtype=np.float64), 'harmless_extra': np.zeros((2, 1, 1, 2))}
    stream = io.BytesIO(); np.savez_compressed(stream, **arrays)
    got = a.parse_npz(stream.getvalue())
    assert set(got) == set(arrays)
    np.testing.assert_array_equal(proof.axis(got['participant_ids'], ['sub-%02d' % i for i in reversed(range(20))], 'ids'), np.arange(20)[::-1])
    np.testing.assert_array_equal(a.integer_array(got['frame_indices']), np.arange(168))


def test_proof_late_failure_after_metadata_is_authoritative(tmp_path, monkeypatch):
    # Control-flow unit only. Existing full synthetic numerical integration
    # suites qualify the untouched certificate/report computations separately.
    output = tmp_path / 'output'; output.mkdir()
    reference = {'pilot': False, 'source_bases': [None],
                 'arrays': {'participant_ids': np.empty(20), 'parcel_ids': np.empty(400)}}
    submitted = {name: [] for name in ('cohort.csv', 'parcels.csv', 'configurations.csv', 'per_subject.csv')}
    submitted.update({'gradient_arrays.npz': {}, 'results.json': {'configuration_summaries': [], 'claim_scope': 'fake'},
                      'run_metadata.json': {}})
    monkeypatch.setattr(a, 'read_artifacts', lambda _: submitted)
    monkeypatch.setattr(proof, 'canonical_arrays', lambda *args: {'operator_valid': np.zeros(24, bool)})
    monkeypatch.setattr(proof, 'source_receipts', lambda *args: None)
    monkeypatch.setattr(proof, 'certified_coordinates', lambda *args: ([], None))
    monkeypatch.setattr(proof.r, 'derive', lambda *args: {'arrays': {}, 'configurations': [], 'per_subject': [],
                                                     'results': {'configuration_summaries': []}})
    reference.update(cohort=[], parcels=[])
    monkeypatch.setattr(proof, 'table', lambda *args, **kwargs: None)
    monkeypatch.setattr(proof, 'match', lambda *args, **kwargs: None)
    def late(*args): (output / 'failure_report.json').symlink_to(output / 'absent')
    monkeypatch.setattr(proof, 'metadata', late)
    with pytest.raises(ValueError, match='failure_report'): proof.validate(output, reference)


@pytest.mark.parametrize('precreated', [False, True])
def test_absent_or_precreated_empty_output_is_accepted(tmp_path, precreated):
    out = tmp_path / 'output'
    if precreated: out.mkdir()
    got, _, _ = compute.prepare_destinations(out, None, None, [tmp_path / 'source'])
    assert got == out and list(out.iterdir()) == []


@pytest.mark.parametrize('kind', ['nonempty', 'symlink', 'file', 'source', 'code', 'doc_ancestor'])
def test_precreated_output_never_overwrites_or_touches_protected_input(tmp_path, kind):
    source, code, docs = (tmp_path / x for x in ('source', 'code', 'docs'))
    for p in (source, code, docs): p.mkdir()
    doc = docs / 'method.json'; doc.write_text('{}')
    out = tmp_path / 'output'
    if kind == 'nonempty': out.mkdir(); (out / 'keep').write_text('unchanged')
    elif kind == 'symlink': out.symlink_to(source, target_is_directory=True)
    elif kind == 'file': out.write_text('unchanged')
    elif kind == 'source': out = source
    elif kind == 'code': out = code
    else: out = docs
    with pytest.raises(ValueError): compute.prepare_destinations(out, None, None, [source, code, doc])
    assert not (source / 'failure_report.json').exists() and not (code / 'failure_report.json').exists()
    assert doc.read_text() == '{}'
    if kind == 'nonempty': assert (out / 'keep').read_text() == 'unchanged'
    if kind == 'file': assert out.read_text() == 'unchanged'


def fake_compute(tmp_path, monkeypatch, *, precreated=False):
    out = tmp_path / 'output'
    if precreated: out.mkdir()
    ids = ['manufactured-%02d' % i for i in range(20)]
    names = list(a.REQUIRED)
    inputs = {'identity': {'method_sha256': 'm'}, 'manifest': {'files': []},
              'method': {'source': {'participant_ids': ids}, 'configurations': []},
              'schema': {'files': names, 'serialization': {'limits': {'total_artifact_bytes': 256 * 2**20}}}}
    header = {'shape': [1, 1, 1, 168], 'affine': np.eye(4).tolist(), 'source_dtype': '<f4',
              'spatial_units': 'unknown', 'temporal_units': 'unknown', 'raw_TR': 1., 'raw_toffset': 0.,
              'effective_scaling_slope': 1., 'effective_scaling_intercept': 0.}
    common = {'participant_columns': ['id'], 'atlas_header': header, 'labels': []}
    monkeypatch.setattr(oracle, 'authenticate', lambda *args: inputs)
    monkeypatch.setattr(oracle, 'load_common', lambda *args: common)
    monkeypatch.setattr(oracle, 'load_person', lambda _, __, sid: {'header': header, 'confound_columns': [],
        'support_metadata': [], 'cohort': {'participant_id': sid}, 'parcel_rows': [{'participant_id': sid}]})
    rows = [{'fake': 'row'}]
    arrays = {'operator_valid': np.zeros(24, bool), 'embedding_valid': np.zeros(24, bool)}
    result = {'unaligned_signed': {'value': None}, 'aligned_signed': {'value': None},
              'principal_gradient_identity_robust': None, 'configuration_summaries': [], 'gpa': {'status': 'fake'}}
    monkeypatch.setattr(compute, 'analyze', lambda *args: (arrays, rows, rows, result))
    monkeypatch.setattr(compute, 'software_versions', lambda: {'python': 'manufactured'})
    args = SimpleNamespace(data_dir=tmp_path / 'source', contract_path=tmp_path / 'method.json',
                           schema_path=tmp_path / 'schema.json', output_dir=out, private_dir=None, report=None)
    return out, args


@pytest.mark.parametrize('precreated', [False, True])
@pytest.mark.parametrize('late', ['source_change', 'extra', 'failure_marker'])
def test_oracle_end_auth_and_late_inventory_fail_with_authoritative_marker(tmp_path, monkeypatch, precreated, late):
    out, args = fake_compute(tmp_path, monkeypatch, precreated=precreated)
    def finish(*args):
        if late == 'source_change': raise ValueError('manufactured final authentication failure')
        if late == 'extra': (out / 'late-extra').write_text('unexpected')
        else: (out / 'failure_report.json').symlink_to(out / 'missing')
    monkeypatch.setattr(oracle, 'reauthenticate', finish)
    with pytest.raises(ValueError): compute.run(args)
    assert os.path.lexists(out / 'failure_report.json')
    if late == 'failure_marker': assert (out / 'failure_report.json').is_symlink()
    else: assert json.loads((out / 'failure_report.json').read_text())['status'] == 'failed_precondition'


@pytest.mark.parametrize('precreated', [False, True])
def test_oracle_io_only_emission_succeeds_for_both_empty_destination_forms(tmp_path, monkeypatch, precreated):
    out, args = fake_compute(tmp_path, monkeypatch, precreated=precreated)
    monkeypatch.setattr(oracle, 'reauthenticate', lambda *args: None)
    assert compute.run(args)['status'] == 'ok'
    assert {p.name for p in out.iterdir()} == set(a.REQUIRED)
