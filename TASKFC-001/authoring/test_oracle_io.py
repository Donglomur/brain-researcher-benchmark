"""Manufactured-only reader/writer fixtures; no original paths or loaders."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import warnings

import nibabel as nib
import numpy as np
import pytest

import compute
import oracle_core as core
import source_reader as source

COHORT_FIELDS = ('subject', 'bold_path', 'events_path', 'confounds_path', 'n_frames',
    'operational_TR_s', 'operational_frame_origin_s', 'left_n_voxels', 'right_n_voxels',
    'left_support_sha256', 'right_support_sha256')
EVENT_FIELDS = ('subject', 'source_event_index', 'trial_type', 'onset_token', 'duration_token',
                'modulation_token', 'onset_s', 'duration_s', 'modulation')
CONNECTIVITY_FIELDS = ('subject', 'region_a', 'region_b', 'raw_status', 'background_status',
    'connectivity', 'background_connectivity', 'raw_fisher_z', 'background_fisher_z',
    'paired_status', 'raw_minus_background_z')


def encoded(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def image(values=None, endian='<', slope=1., intercept=0., offset=352):
    if values is None:
        values = np.arange(15*3*3*40, dtype=np.float32).reshape((15, 3, 3, 40))
    header = nib.Nifti1Header(endianness=endian)
    header.set_data_shape(values.shape)
    header.set_data_dtype(np.dtype(endian+'f4'))
    affine = np.diag([5., 5., 5., 1.]); affine[:3, 3] = [-35., -95., -11.]
    header.set_sform(affine, code=2)
    header.set_zooms((5., 5., 5., 1.5)); header.set_xyzt_units('mm', 'sec')
    header['vox_offset'] = offset
    header.set_slope_inter(slope, intercept)
    raw = header.binaryblock+b'\0'*4+b'\0'*(offset-352)
    return raw+np.asarray(values, dtype=endian+'f4').tobytes(order='F')


def bundle(tmp_path, monkeypatch):
    root = tmp_path/'data'; root.mkdir()
    rows = []
    for sid in source.PARTICIPANTS:
        for role in source.PERSON_ROLES:
            if role == 'bold':
                path, raw = f'{sid}/bold.nii.gz', gzip.compress(image(), mtime=0)
            elif role == 'events':
                path = f'{sid}/events.tsv'
                raw = b'onset\tduration\ttrial_type\n2\t1\tlanguage\n12\t1\tstring\n'
            elif role == 'confounds':
                path = f'{sid}/motion.tsv'
                raw = ('\t'.join(core.MOTION_NAMES)+'\n'+('0\t0\t0\t0\t0\t0\n'*40)).encode()
            else:
                path, raw = f'{sid}/bold.json', b'{"RepetitionTime":1.5}'
            member = root/path; member.parent.mkdir(parents=True, exist_ok=True); member.write_bytes(raw)
            rows.append(dict(path=path, role=role, participant_id=sid, size_bytes=len(raw),
                             sha256=hashlib.sha256(raw).hexdigest(), md5=hashlib.md5(raw).hexdigest()))
    for role in source.DOCUMENT_ROLES:
        path, raw = f'provenance/{role}.txt', b'inert manufactured source document\n'
        member = root/path; member.parent.mkdir(exist_ok=True); member.write_bytes(raw)
        rows.append(dict(path=path, role=role, participant_id=None, size_bytes=len(raw),
                         sha256=hashlib.sha256(raw).hexdigest()))
    manifest = dict(task_id='TASKFC-001', participant_ids=list(source.PARTICIPANTS), files=rows)
    method = dict(task_id='TASKFC-001', status='frozen_manufactured', cohort=dict(n_expected=10),
        source=dict(n_frames_by_participant={s: 40 for s in source.PARTICIPANTS}),
        clock=dict(TR_s=1.5, frame_origin_s=.75),
        design=dict(hrf=dict(min_onset_s=-24, oversampling=50), cosine=dict(high_pass_hz=.01)))
    schema = dict(task_id='TASKFC-001', status='frozen_manufactured', artifacts={
        name: dict(required_columns={key: 'manufactured' for key in fields})
        for name, fields in (('cohort.csv', COHORT_FIELDS), ('events.csv', EVENT_FIELDS),
                             ('connectivity.csv', CONNECTIVITY_FIELDS))})
    paths = []
    for name, value, pin in (('manifest.json', manifest, 'SOURCE_SHA'),
                             ('method.json', method, 'METHOD_SHA'), ('schema.json', schema, 'SCHEMA_SHA')):
        raw = encoded(value); path = tmp_path/name; path.write_bytes(raw); paths.append(path)
        monkeypatch.setattr(source, pin, hashlib.sha256(raw).hexdigest())
    (root/'source_manifest.json').write_bytes(paths[0].read_bytes())
    return root, *paths


@pytest.mark.parametrize('endian', ['<', '>'])
@pytest.mark.parametrize('compressed', [False, True])
def test_calibrated_fortran_decode(endian, compressed):
    values = np.arange(15*3*3*5, dtype=np.float32).reshape((15, 3, 3, 5))
    raw = image(values, endian, 2.5, -7., offset=384)
    h, affine, decoded = source.image_from_buffer(gzip.compress(raw) if compressed else raw, compressed, True)
    assert h['storage_dtype'] == endian+'f4'
    assert h['effective_slope'] == 2.5 and h['effective_intercept'] == -7.
    np.testing.assert_array_equal(decoded, values.astype(np.float64)*2.5-7.)
    assert affine.shape == (4, 4)


@pytest.mark.parametrize('tail', [b'x', b'\0'*8])
def test_extra_decoded_bytes_rejected(tail):
    with pytest.raises(ValueError, match='exact_decoded'):
        source.image_from_buffer(gzip.compress(image()+tail), True, True)


def test_truncated_and_header_only():
    raw = image()
    with pytest.raises(ValueError, match='exact_decoded'):
        source.image_from_buffer(raw[:-4], False, True)
    header, _, values = source.image_from_buffer(raw[:352], False, False)
    assert header['shape'] == [15, 3, 3, 40] and values is None


def test_only_selected_voxels_finite():
    raw = image()
    _, affine, values = source.image_from_buffer(raw, False, True)
    indices = core.sphere_support(values.shape[:3], affine)
    outside = next(i for i in range(values[..., 0].size) if all(i not in a for a in indices))
    vol = values[..., 0].copy(); vol[np.unravel_index(outside, vol.shape)] = np.nan
    assert np.isfinite(core.voxel_mean(vol, indices[0]))
    vol[np.unravel_index(indices[0][0], vol.shape)] = np.nan
    with pytest.raises(ValueError, match='nonfinite_selected'):
        core.voxel_mean(vol, indices[0])


def test_all48_auth_and_sub01_only(tmp_path, monkeypatch):
    paths = bundle(tmp_path, monkeypatch)
    inputs = source.authenticate(*paths)
    calls = []; original = source.image_from_buffer
    def observe(raw, compressed, decode=False):
        calls.append(decode)
        return original(raw, compressed, decode)
    monkeypatch.setattr(source, 'image_from_buffer', observe)
    basis = source.load_primitives(inputs, ['sub-01'])
    assert calls == [True]+[False]*9
    assert basis['participant_ids'] == ['sub-01']
    assert len(basis['cohort']) == 10 and len(basis['events']) == 20
    assert len(basis['source_observed']['headers']) == 10
    assert basis['participants']['sub-01']['raw'].shape == (40, 2)


@pytest.mark.parametrize('kind', ['different_manifest', 'extra_file', 'empty_dir', 'symlink', 'fifo', 'changed_payload'])
def test_source_inventory_refuses_before_decode(tmp_path, monkeypatch, kind):
    paths = bundle(tmp_path, monkeypatch); root = paths[0]
    if kind == 'different_manifest': (root/'source_manifest.json').write_bytes(b'{}')
    elif kind == 'extra_file': (root/'extra').write_bytes(b'x')
    elif kind == 'empty_dir': (root/'extra').mkdir()
    elif kind == 'symlink': (root/'extra').symlink_to(tmp_path/'missing')
    elif kind == 'fifo': os.mkfifo(root/'extra')
    else: (root/'sub-01'/'events.tsv').write_bytes(b'changed')
    monkeypatch.setattr(source, 'image_from_buffer', lambda *a, **k: pytest.fail('unexpected decode'))
    with pytest.raises(ValueError): source.authenticate(*paths)


@pytest.mark.parametrize('path', ['relative', '/tmp/x/../y', '/tmp/./x'])
def test_lexical_path_rejection(path):
    with pytest.raises(ValueError, match='absolute_lexical'): source.safe_path(path)


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"v":NaN}', b'{"v":1e999}'])
def test_strict_json(raw):
    with pytest.raises(ValueError): source.strict_json(raw)


def test_source_table_literals_and_duplicates():
    raw = b'onset\tduration\ttrial_type\tmodulation\n02.0\t0\tlanguage\t1\n02.0\t0\tlanguage\t2\n4\t1\tstring\t3\n'
    cols, rows, ledger = source.event_table(raw, 'sub-01')
    assert len(rows) == 3 and ledger[0]['onset_token'] == '02.0'
    assert ledger[1]['source_event_index'] == 1 and rows[1]['modulation'] == 2.
    assert cols[-1] == 'modulation'


@pytest.mark.parametrize('raw', [b'onset,duration,trial_type\n2,1,language\n',
    b'onset\tonset\tduration\ttrial_type\n2\t2\t1\tlanguage\n',
    b'onset\tduration\ttrial_type\nNaN\t1\tlanguage\n2\t1\tstring\n',
    b'onset\tduration\ttrial_type\n2\t-1\tlanguage\n2\t1\tstring\n'])
def test_bad_event_tables(raw):
    with pytest.raises(ValueError): source.event_table(raw, 'sub-01')


def fake_basis():
    participants = {}
    for i, sid in enumerate(source.PARTICIPANTS):
        n = 40+i if i < 9 else 80
        t = np.arange(n, dtype=float)
        raw = np.column_stack((np.sin(t*.71)+t*.1, np.cos(t*.53)-t*.03))
        events = [dict(trial_type='language', onset=2., duration=1.), dict(trial_type='string', onset=12., duration=1.)]
        design = core.build_design(n, 1.5, .75, events, np.zeros((n, 6)))
        participants[sid] = dict(raw=raw, designs=design, **core.analyze_person(raw, design))
    return dict(participant_ids=list(source.PARTICIPANTS), participants=participants, source_observed={},
        cohort=[{k: 'manufactured' for k in COHORT_FIELDS}], events=[{k: 'manufactured' for k in EVENT_FIELDS}])


def test_union_design_padding_and_masks():
    basis = fake_basis(); packed = compute.pack_arrays(basis)
    assert packed['residuals'].shape == (476, 2, 2)
    assert packed['design_included'].shape[:2] == (10, 2)
    for i, sid in enumerate(basis['participant_ids']):
        rows = packed['frame_participant_id'] == sid
        for j, name in enumerate(packed['design_column_ids']):
            if name not in basis['participants'][sid]['designs']['full_names']:
                assert not packed['design_included'][i, :, j].any()
                assert not packed['design_values'][rows, j].any()
        assert packed['design_included'][i, 1, -2:].all()
        assert not packed['design_included'][i, 0, -2:].any()


@pytest.mark.parametrize('pilot', [False, True])
def test_writer_warnings_and_pilot_no_endpoint(tmp_path, monkeypatch, pilot):
    paths = bundle(tmp_path, monkeypatch); basis = fake_basis()
    if pilot:
        basis['participant_ids'] = ['sub-01']
        basis['participants'] = {'sub-01': basis['participants']['sub-01']}
        monkeypatch.setattr(core, 'derive', lambda *a, **k: pytest.fail('pilot endpoint replay'))
    def load(*a, **k):
        warnings.warn('manufactured reader warning', RuntimeWarning)
        return basis
    monkeypatch.setattr(source, 'load_primitives', load)
    args = argparse.Namespace(data_dir=str(paths[0]), manifest_path=str(paths[1]), contract_path=str(paths[2]),
        schema_path=str(paths[3]), output_dir=str(tmp_path/'output'), private_dir=str(tmp_path/'private'),
        report=str(tmp_path/'report.json'), pilot_first_subject=pilot)
    receipt = compute.compute(args)
    metadata = json.loads((tmp_path/'output'/'run_metadata.json').read_text())
    assert metadata['warnings'] == ['manufactured reader warning']
    assert len(list((tmp_path/'output').iterdir())) == 7
    assert receipt['endpoints_computed'] is not pilot
    assert metadata['status'] == ('resource_pilot' if pilot else 'ok')
    if pilot:
        result = json.loads((tmp_path/'output'/'connectivity_summary.json').read_text())
        assert result['raw'] is None and result['paired_z_sensitivity'] is None


def test_failure_marker_and_fresh_nonoverwrite(tmp_path, monkeypatch):
    paths = bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(source, 'load_primitives', lambda *a, **k: (_ for _ in ()).throw(ValueError('manufactured failure')))
    args = argparse.Namespace(data_dir=str(paths[0]), manifest_path=str(paths[1]), contract_path=str(paths[2]),
        schema_path=str(paths[3]), output_dir=str(tmp_path/'output'), private_dir=None,
        report=str(tmp_path/'report.json'), pilot_first_subject=False)
    with pytest.raises(ValueError, match='manufactured failure'): compute.compute(args)
    marker = tmp_path/'output'/'failure_report.json'; before = marker.read_bytes()
    with pytest.raises(ValueError, match='fresh_destination'): compute.compute(args)
    assert marker.read_bytes() == before


def test_late_report_failure_keeps_success_files_and_authoritative_marker(tmp_path, monkeypatch):
    paths = bundle(tmp_path, monkeypatch)
    basis = fake_basis()
    monkeypatch.setattr(source, 'load_primitives', lambda *a, **k: basis)
    report = tmp_path/'report.json'
    original_writer = compute.write_json
    def write(path, value):
        if Path(path) == report and value['status'] == 'ok':
            assert (tmp_path/'output'/'run_metadata.json').is_file()
            raise OSError('manufactured late report failure')
        return original_writer(path, value)
    monkeypatch.setattr(compute, 'write_json', write)
    args = argparse.Namespace(data_dir=str(paths[0]), manifest_path=str(paths[1]), contract_path=str(paths[2]),
        schema_path=str(paths[3]), output_dir=str(tmp_path/'output'), private_dir=None,
        report=str(report), pilot_first_subject=False)
    with pytest.raises(OSError, match='manufactured late report failure'): compute.compute(args)
    assert json.loads((tmp_path/'output'/'run_metadata.json').read_text())['status'] == 'ok'
    assert json.loads((tmp_path/'output'/'failure_report.json').read_text())['status'] == 'failed_precondition'
    assert json.loads(report.read_text())['status'] == 'failed_precondition'
    assert len(list((tmp_path/'output').iterdir())) == 8


def test_protected_source_and_symlink(tmp_path):
    original = tmp_path/'original'; original.mkdir()
    with pytest.raises(ValueError, match='overlapping'):
        compute.prepare_destinations(original/'output', None, None, [original])
    assert list(original.iterdir()) == []
    alias = tmp_path/'alias'; alias.symlink_to(original, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        compute.prepare_destinations(alias/'output', None, None, [original])
    assert list(original.iterdir()) == []


@pytest.mark.parametrize('kind', ['duplicate_path', 'duplicate_role', 'wrong_id', 'traversal', 'unmeasured', 'reserved'])
def test_manifest_semantics(tmp_path, monkeypatch, kind):
    paths = bundle(tmp_path, monkeypatch)
    manifest = json.loads(paths[1].read_bytes())
    row = manifest['files'][0]
    if kind == 'duplicate_path': row['path'] = manifest['files'][1]['path']
    elif kind == 'duplicate_role': row['role'] = manifest['files'][1]['role']
    elif kind == 'wrong_id': row['participant_id'] = 'sub-1'
    elif kind == 'traversal': row['path'] = '../outside'
    elif kind == 'reserved': row['path'] = 'source_manifest.json'
    else: row['sha256'] = None
    raw = encoded(manifest)
    paths[1].write_bytes(raw); (paths[0]/'source_manifest.json').write_bytes(raw)
    monkeypatch.setattr(source, 'SOURCE_SHA', hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError): source.authenticate(*paths)


def test_source_mutation_after_auth_rechecked(tmp_path, monkeypatch):
    paths = bundle(tmp_path, monkeypatch)
    inputs = source.authenticate(*paths)
    (paths[0]/'sub-01'/'bold.nii.gz').write_bytes(b'changed after auth')
    with pytest.raises(ValueError): source.load_primitives(inputs, ['sub-01'])


def test_unfrozen_pins_and_frame_identity(tmp_path, monkeypatch):
    paths = bundle(tmp_path, monkeypatch)
    inputs = source.authenticate(*paths)
    inputs['method']['source']['n_frames_by_participant']['sub-01'] = 41
    with pytest.raises(ValueError, match='frozen_frame_count'):
        source.load_primitives(inputs, ['sub-01'])
    monkeypatch.setattr(source, 'METHOD_SHA', None)
    with pytest.raises(ValueError, match='pins_not_frozen'): source.authenticate(*paths)


def test_supported_pilot_identity_only(tmp_path, monkeypatch):
    inputs = source.authenticate(*bundle(tmp_path, monkeypatch))
    with pytest.raises(ValueError, match='full_or_fixed_first_pilot'):
        source.load_primitives(inputs, ['sub-02'])
