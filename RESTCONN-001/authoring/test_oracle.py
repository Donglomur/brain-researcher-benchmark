"""Manufactured data only; no original/cache/network paths or verifier imports."""
import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import warnings

import nibabel as nib
import numpy as np
import pytest
from nilearn.signal import clean
from scipy import linalg
SOLUTION = Path(__file__).resolve().parents[1] / 'solution'
sys.path.insert(0, str(SOLUTION))
import core
import source_reader as sr
import compute


def digest(raw): return hashlib.sha256(raw).hexdigest()


def encoded(value): return (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()


def image(values, affine=None, endian='<', slope=None, intercept=None):
    a = np.asarray(values)
    h = nib.Nifti1Header(endianness=endian)
    h.set_data_dtype(a.dtype)
    obj = nib.Nifti1Image(a, np.eye(4) if affine is None else affine, header=h)
    raw = obj.to_bytes()
    if slope is not None:
        header = nib.Nifti1Header(binaryblock=raw[:348], check=False)
        header.set_slope_inter(slope, intercept)
        raw = header.binaryblock + raw[348:]
    return raw


def bundle(tmp_path, monkeypatch):
    root = tmp_path / 'source'; root.mkdir()
    rng = np.random.default_rng(193)
    maps = rng.normal(size=(2, 4, 5, 39))
    signal = rng.normal(size=(39, 64))
    bold = (maps.reshape(-1, 39) @ signal).reshape(2, 4, 5, 64)
    names = sorted(core.CONFOUND_SET)
    labels = [f'map-{i}' for i in range(39)]
    labels[1], labels[3] = core.TARGETS
    table = 'constant\t' + '\t'.join(names) + '\n'
    table += '\n'.join('1\t' + '\t'.join(map(str, row)) for row in rng.normal(size=(64, 13))) + '\n'
    lut = 'name,net name,x,y,z\n' + '\n'.join(f'{x},net,0,0,0' for x in labels) + '\n'
    payloads = {
        'bold': gzip.compress(image(bold)), 'atlas_image': image(maps),
        'confounds': table.encode(), 'atlas_labels': lut.encode(), 'cohort_ids': b'0010064\nother\n',
        'phenotype_metadata': b'id,age\n0010064,9\n', 'slice_timing_metadata': b'id,tr\n0010064,2\n',
        'provenance': b'Manufactured documentary bytes only.\n'}
    rows = []
    for path, role in sr.PATH_ROLES.items():
        data = payloads[role]
        target = root / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
        rows.append(dict(path=path, role=role, participant_id=core.PARTICIPANT if role in ('bold', 'confounds') else None,
            size_bytes=len(data), sha256=digest(data), md5=hashlib.md5(data).hexdigest(),
            git_blob_sha1=hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()))
    raw = encoded(dict(files=rows)); (root / 'source_manifest.json').write_bytes(raw)
    method = dict(task_id='RESTCONN-001', contract_status='frozen-manufactured',
        source=dict(participant_id=core.PARTICIPANT, n_frames=64, map_ids=list(range(39)),
                    target_labels=list(core.TARGETS), target_map_ids=[1, 3]),
        temporal_cleaning=dict(confound_columns=names))
    mp, sp = tmp_path / 'method.json', tmp_path / 'schema.json'
    mp.write_bytes(encoded(method)); sp.write_bytes(encoded(dict(files=['manufactured'])))
    monkeypatch.setattr(sr, 'SOURCE_SHA', digest(raw))
    monkeypatch.setattr(sr, 'METHOD_SHA', digest(mp.read_bytes()))
    monkeypatch.setattr(sr, 'SCHEMA_SHA', digest(sp.read_bytes()))
    return root, mp, sp


def args(tmp_path, bundle_paths, pilot=False):
    root, method, schema = bundle_paths
    return argparse.Namespace(data_dir=str(root), contract_path=str(method), schema_path=str(schema),
        output_dir=str(tmp_path / 'output'), private_dir=str(tmp_path / 'private'),
        report=str(tmp_path / 'report.json'), pilot_extraction_only=pilot)


@pytest.mark.parametrize('n', [40, 64, 176, 244])
def test_cleaning_official(n):
    rng = np.random.default_rng(n)
    raw, c = rng.normal(size=(n, 39)), rng.normal(size=(n, 13))
    out = core.clean_coefficients(raw, c)
    expected = clean(raw, confounds=c, detrend=True, standardize='zscore_sample',
        low_pass=.1, high_pass=.01, t_r=2., ensure_finite=False)
    np.testing.assert_allclose(out['cleaned'], expected, atol=1e-10, rtol=1e-10)


@pytest.mark.parametrize('kind', ['constant', 'tiny', 'nuisance'])
def test_activity(kind):
    rng = np.random.default_rng(1); raw = rng.normal(size=(64, 39)); c = rng.normal(size=(64, 13))
    raw[:, 0] = .1 if kind == 'constant' else rng.normal(size=64) * 1e-15 if kind == 'tiny' else c[:, 0]
    before = raw.copy(); out = core.clean_coefficients(raw, c)
    assert not out['active'][0] and np.array_equal(out['cleaned'][:, 0], np.zeros(64))
    np.testing.assert_array_equal(raw, before)


@pytest.mark.parametrize('rank', [0, 1, 13])
def test_nuisance_rank(rank):
    rng = np.random.default_rng(2); raw = rng.normal(size=(64, 39)); c = np.zeros((64, 13))
    if rank == 1: c[:, 0] = rng.normal(size=64)
    if rank == 13: c[:] = rng.normal(size=(64, 13))
    assert core.clean_coefficients(raw, c)['confound_rank'] == rank


def test_replicated_nuisance_declared_operator_not_ideal_rank():
    rng = np.random.default_rng(2)
    raw = rng.normal(size=(64, 39))
    c = np.repeat(rng.normal(size=(64, 1)), 13, axis=1)
    out = core.clean_coefficients(raw, c)
    q, r, _ = linalg.qr(out['standardized_confounds'], mode='economic', pivoting=True)
    keep = np.abs(np.diag(r)) > 100 * core.EPS
    q = q[:, keep]
    expected = out['filtered_coefficients'] - (q @ q.T) @ out['filtered_coefficients']
    expected -= expected.mean(axis=0)
    np.testing.assert_array_equal(out['residual_before_zscore'], expected)
    assert out['confound_rank'] == np.count_nonzero(keep)
    assert np.isfinite(out['nuisance_qr_diagonal']).all()


@pytest.mark.parametrize('n', [4, 20, 40, 61])
def test_circular_manual(n):
    rng = np.random.default_rng(n); y = rng.normal(size=(n, 2))
    result = core.circular_evidence(y, np.array([True, True]))
    x, _ = core.scaled_center(y[:, 0]); z, _ = core.scaled_center(y[:, 1])
    dots = [math.fsum(float(a) * float(b) for a, b in zip(np.roll(x, k), z)) for k in range(n)]
    count = sum(abs(v) >= abs(dots[0]) for v in dots[1:])
    assert result['inference']['n_exceedances'] == count
    assert result['significant'] == (20 * (count + 1) < n)
    assert result['p_value'] == (count + 1) / n
    assert result['r'] == pytest.approx(np.corrcoef(y.T)[0, 1], abs=1e-14)


def test_periodic_ties_all_offsets():
    x = np.tile([1., -1.], 20)
    r = core.circular_evidence(np.column_stack((x, x)), np.array([True, True]))
    assert len(r['inference']['shifts']) == 39
    assert r['inference']['exceeds'] == [True] * 39 and r['p_value'] == 1.


@pytest.mark.parametrize('active', [[False, True], [True, False], [False, False]])
def test_inactive_is_undefined(active):
    out = core.circular_evidence(np.zeros((40, 2)), np.asarray(active))
    assert out['status'] == 'inactive_target' and out['r'] is None
    assert out['inference']['null_r'] == [None] * 39 and out['inference']['denominator'] == 40


@pytest.mark.parametrize('values', [True, [1., True], [float('nan')], [float('inf')], ['1'], [1+2j]])
def test_numeric_guards(values):
    with pytest.raises(core.PreconditionError): core.real_array(values)


def test_active_constant_refused():
    with pytest.raises(core.PreconditionError): core.circular_evidence(np.ones((40, 2)), np.array([True, True]))


@pytest.mark.parametrize('big', [1e200, 1e-200])
def test_scale_first_correlation(big):
    x = np.arange(40, dtype=float) * big
    out = core.circular_evidence(np.column_stack((x, x[::-1])), np.array([True, True]))
    assert out['r'] == pytest.approx(-1.)


@pytest.mark.parametrize('rank', [1, 39])
def test_joint_minimum_norm(rank):
    rng = np.random.default_rng(3); maps = np.zeros((2, 4, 5, 39)); maps[..., :rank] = rng.normal(size=(2, 4, 5, rank))
    coeff = rng.normal(size=(39, 40)); y = (maps.reshape(-1, 39) @ coeff).reshape(2, 4, 5, 40)
    raw, measured, _ = core.extract_coefficients(maps, y)
    assert measured == rank
    np.testing.assert_allclose(maps.reshape(-1, 39) @ raw.T, y.reshape(-1, 40), atol=1e-12)


@pytest.mark.parametrize('endian', ['<', '>'])
@pytest.mark.parametrize('compressed', [False, True])
def test_decode_calibration(endian, compressed):
    a = np.arange(80, dtype=np.int16).reshape(2, 2, 2, 10)
    raw = image(a, endian=endian, slope=2., intercept=-3.)
    values, _, header = sr.decode_image(gzip.compress(raw) if compressed else raw, compressed)
    np.testing.assert_array_equal(values, a * 2. - 3.)
    assert header['effective_slope'] == 2 and header['effective_intercept'] == -3


@pytest.mark.parametrize('mutation', ['truncated', 'trailing', 'nonfinite', 'bad_magic'])
def test_decode_refusals(mutation):
    a = np.ones((2, 2, 2, 40))
    if mutation == 'nonfinite': a.flat[0] = np.nan
    raw = image(a)
    if mutation == 'truncated': raw = raw[:-1]
    if mutation == 'trailing': raw += b'x'
    if mutation == 'bad_magic': raw = raw[:344] + b'bad!' + raw[348:]
    with pytest.raises((ValueError, core.PreconditionError)): sr.decode_image(raw, False)


def test_non352_extension_offset_preserved():
    a = np.arange(320., dtype=np.float32).reshape(2, 2, 2, 40)
    obj = nib.Nifti1Image(a, np.eye(4))
    obj.header.extensions.append(nib.nifti1.Nifti1Extension(6, b'manufactured metadata ' * 300))
    raw = obj.to_bytes()
    header = nib.Nifti1Header(binaryblock=raw[:348], check=False)
    assert int(header['vox_offset']) > 352 and raw[348] == 1
    got, _, _ = sr.decode_image(gzip.compress(raw), True)
    np.testing.assert_array_equal(got, a)


@pytest.mark.parametrize('mutation', ['crc', 'truncated', 'extra_member'])
def test_gzip_integrity(mutation):
    raw = gzip.compress(image(np.ones((2, 2, 2, 40))))
    if mutation == 'crc': raw = raw[:-8] + bytes([raw[-8] ^ 1]) + raw[-7:]
    if mutation == 'truncated': raw = raw[:-3]
    if mutation == 'extra_member': raw += gzip.compress(b'additional logical data')
    with pytest.raises((ValueError, OSError, EOFError)): sr.decode_image(raw, True)


def test_identity_resample_no_library(monkeypatch):
    a = np.arange(2 * 2 * 2 * 39.).reshape(2, 2, 2, 39)
    monkeypatch.setattr(sr, 'resample_img', lambda *a, **k: pytest.fail('identity interpolation'))
    result = sr.resample_maps(a, np.eye(4), (2, 2, 2), np.eye(4))
    np.testing.assert_array_equal(result, a); assert result is not a


def test_resample_zero_outside_preserves_negative():
    a = -np.ones((2, 2, 2, 39)); a[0, 0, 0] = 2.
    affine = np.eye(4); affine[0, 3] = -1.
    result = sr.resample_maps(a, np.eye(4), (4, 2, 2), affine)
    assert np.min(result) == -1 and np.max(result) == 2
    np.testing.assert_array_equal(result[0], 0.)


def test_source_bundle_and_metadata(tmp_path, monkeypatch):
    root, method, schema = bundle(tmp_path, monkeypatch)
    before = {str(p): digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
    basis = sr.load(sr.authenticate(root, method, schema))
    assert basis['raw_coefficients'].shape == (64, 39) and basis['cleaned_series'].shape == (64, 2)
    assert basis['source_observed']['excluded_confound_columns'] == ['constant']
    assert basis['analysis_observed']['map_rank'] == 39
    assert before == {str(p): digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('mutation', ['extra_file', 'empty_dir', 'symlink', 'fifo', 'tamper', 'pin_unset', 'method_tamper'])
def test_authentication_refusals(tmp_path, monkeypatch, mutation):
    root, method, schema = bundle(tmp_path, monkeypatch)
    if mutation == 'extra_file': (root / 'extra').write_bytes(b'x')
    if mutation == 'empty_dir': (root / 'extra').mkdir()
    if mutation == 'symlink': (root / 'extra').symlink_to(method)
    if mutation == 'fifo': os.mkfifo(root / 'extra')
    if mutation == 'tamper': (root / next(iter(sr.PATH_ROLES))).write_bytes(b'x')
    if mutation == 'pin_unset': monkeypatch.setattr(sr, 'METHOD_SHA', None)
    if mutation == 'method_tamper': method.write_bytes(b'{}')
    with pytest.raises(core.PreconditionError): sr.authenticate(root, method, schema)


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":[1e999]}'])
def test_json_refusals(raw):
    with pytest.raises(core.PreconditionError): sr.strict_json(raw)


@pytest.mark.parametrize('pilot', [False, True])
def test_end_to_end_manufactured(tmp_path, monkeypatch, pilot):
    options = args(tmp_path, bundle(tmp_path, monkeypatch), pilot)
    receipt = compute.compute(options)
    assert set(receipt['files']) == {'raw_map_coefficients.npz', 'timeseries.csv', 'connectivity.json', 'run_metadata.json', 'findings.md'}
    assert receipt['status'] == ('resource_pilot' if pilot else 'ok')
    metadata = json.loads((tmp_path / 'output/run_metadata.json').read_text())
    assert isinstance(metadata['warnings'], list) and all(isinstance(w, str) for w in metadata['warnings'])
    report = json.loads((tmp_path / 'output/connectivity.json').read_text())
    if pilot: assert report['inference'] is None and report['status'] == 'resource_pilot'
    else: assert len(report['inference']['shifts']) == 63
    with np.load(tmp_path / 'output/raw_map_coefficients.npz', allow_pickle=False) as z:
        assert z['raw_coefficients'].shape == (64, 39) and z['participant_id'].item() == '0010064'


@pytest.mark.parametrize('pilot', [False, True])
def test_writer_retains_warnings(tmp_path, monkeypatch, pilot):
    options = args(tmp_path, bundle(tmp_path, monkeypatch), pilot)
    original = sr.load
    def warned(inputs):
        warnings.warn('manufactured diagnostic warning', UserWarning)
        return original(inputs)
    monkeypatch.setattr(sr, 'load', warned)
    receipt = compute.compute(options)
    metadata = json.loads((tmp_path / 'output/run_metadata.json').read_text())
    assert 'manufactured diagnostic warning' in metadata['warnings']
    assert any(w['message'] == 'manufactured diagnostic warning' for w in receipt['warnings'])


def test_failure_marker_preserved(tmp_path, monkeypatch):
    options = args(tmp_path, bundle(tmp_path, monkeypatch))
    monkeypatch.setattr(sr, 'load', lambda _: (_ for _ in ()).throw(ValueError('manufactured source failure')))
    with pytest.raises(ValueError): compute.compute(options)
    assert json.loads((tmp_path / 'output/failure_report.json').read_text())['status'] == 'failed_precondition'
    assert json.loads((tmp_path / 'report.json').read_text())['status'] == 'failed_precondition'


@pytest.mark.parametrize('kind', ['existing', 'source_overlap', 'private_overlap', 'symlink_ancestor', 'dotdot'])
def test_destination_refusals_no_mutation(tmp_path, monkeypatch, kind):
    options = args(tmp_path, bundle(tmp_path, monkeypatch)); marker = tmp_path / 'untouched'; marker.write_text('keep')
    if kind == 'existing': Path(options.output_dir).mkdir()
    if kind == 'source_overlap': options.output_dir = str(Path(options.data_dir) / 'output')
    if kind == 'private_overlap': options.private_dir = options.output_dir
    if kind == 'symlink_ancestor':
        (tmp_path / 'link').symlink_to(tmp_path, target_is_directory=True); options.output_dir = str(tmp_path / 'link/output')
    if kind == 'dotdot': options.output_dir = str(tmp_path / 'absent/../output')
    with pytest.raises(core.PreconditionError): compute.compute(options)
    assert marker.read_text() == 'keep' and not (tmp_path / 'private').exists()


def test_wrapper_print_contract(tmp_path):
    path = tmp_path / 'method.json'; path.write_text('{"manufactured":true}\n')
    result = subprocess.run(['bash', str(SOLUTION / 'solve.sh'), '--print-contract', '--contract-path', str(path)],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and json.loads(result.stdout) == {'manufactured': True}
