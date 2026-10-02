"""Manufactured closed 48-file source tree; no original input path is opened."""
import hashlib
import json
from pathlib import Path

import pytest
import numpy as np
import sensitivity_math as m

import source_reference as r
import source_primitives as p
from test_source_primitives import toy_bytes


@pytest.fixture
def source(tmp_path):
    root = tmp_path/'source'; root.mkdir()
    files = []
    def add(path, role, sid, raw):
        target = root/path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        files.append(dict(path=path, role=role, participant_id=sid, size_bytes=len(raw),
                          sha256=hashlib.sha256(raw).hexdigest()))
    raw, _, _ = toy_bytes()
    for sid in r.IDS:
        add(f'{sid}/bold.nii', 'bold', sid, raw)
        add(f'{sid}/events.tsv', 'events', sid,
            b'onset\tduration\ttrial_type\n0\t1\tlanguage\n2\t1\tstring\n')
        motion = ('\t'.join(p.MOTION)+'\n'+('\t'.join(['0']*6)+'\n')*4).encode()
        add(f'{sid}/confounds.tsv', 'confounds', sid, motion)
        add(f'{sid}/bold.json', 'bold_json', sid, b'{"RepetitionTime":1.5}')
    for role in sorted(r.DOC_ROLES):
        name = role+'.json' if role in ('dataset_description', 'derivative_description') else role+'.txt'
        body = b'{}' if name.endswith('.json') else b'raise RuntimeError("inert")' if role == 'source_access_script_inert' else b'documentary fixture'
        add(name, role, None, body)
    manifest = dict(task_id='TASKFC-001', participant_ids=list(r.IDS), files=files)
    def write_manifest():
        raw = json.dumps(manifest).encode(); (root/'source_manifest.json').write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()
    return root, manifest, write_manifest, write_manifest()


def test_closed48_authenticated(source):
    root, _, _, pin = source
    _, manifest, keys = r.authenticate_sources(root, pin)
    assert len(manifest['files']) == 48 and len(keys) == 48
    assert set(r.source_identities(manifest)[0]) == {'path','role','participant_id','size_bytes','sha256'}


def test_structure_never_reads_bold_samples_or_fits(source, monkeypatch):
    root, _, _, pin = source
    monkeypatch.setattr(p, 'extract_series', lambda *a, **k: pytest.fail('BOLD values read'))
    monkeypatch.setattr(r, 'reconstruct', lambda *a, **k: pytest.fail('model fitting'))
    report = r.source_structure(root, pin)
    assert report['bold_samples_read'] == 0 and not report['designs_fitted']
    assert report['participant_ids'] == list(r.IDS)
    assert report['participants']['sub-01']['motion_rows'] == 4
    assert report['documents']['source_access_script_inert']['executed'] is False


@pytest.mark.parametrize('change', ['missing','extra_file','extra_dir','symlink','changed_bytes'])
def test_closed_inventory_or_hash_failure(source, change):
    root, manifest, _, pin = source
    target = root/manifest['files'][0]['path']
    if change == 'missing': target.unlink()
    elif change == 'extra_file': (root/'unexpected').write_bytes(b'x')
    elif change == 'extra_dir': (root/'unexpected').mkdir()
    elif change == 'symlink': (root/'link').symlink_to(target)
    else: target.write_bytes(b'x'*target.stat().st_size)
    with pytest.raises(ValueError): r.authenticate_sources(root, pin)


@pytest.mark.parametrize('change', ['duplicate_path','duplicate_role','alias_subject','missing_row','unsafe_path'])
def test_manifest_closed_keys(source, change):
    root, manifest, rewrite, _ = source
    if change == 'duplicate_path': manifest['files'][0]['path'] = manifest['files'][1]['path']
    elif change == 'duplicate_role': manifest['files'][0]['role'] = manifest['files'][1]['role']
    elif change == 'alias_subject': manifest['files'][0]['participant_id'] = '1'
    elif change == 'missing_row': manifest['files'].pop()
    else: manifest['files'][0]['path'] = '../other'
    with pytest.raises(ValueError): r.authenticate_sources(root, rewrite())


def test_manifest_pin_before_any_source_bytes(source, monkeypatch):
    root, _, _, _ = source
    with pytest.raises(ValueError, match='digest'):
        r.authenticate_sources(root, '0'*64)


def test_production_pins_unfrozen_refuse_before_sources(source, monkeypatch):
    root, _, _, _ = source
    monkeypatch.setattr(r, 'METHOD_SHA', 'UNFROZEN')
    with pytest.raises(ValueError, match='frozen_pin'):
        r.reconstruct(root, root/'source_manifest.json', root/'source_manifest.json')


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}'])
def test_strict_manifest_json(raw):
    with pytest.raises(ValueError): r.strict_json(raw)


@pytest.fixture
def frozen(source, tmp_path, monkeypatch):
    root, manifest, rewrite, pin = source
    method = dict(task_id='TASKFC-001', status='frozen_manufactured',
        source=dict(source_manifest_sha256=pin, shape=[40, 5, 5, 4],
            n_frames_by_participant={s: 4 for s in r.IDS}, event_columns=['onset', 'duration', 'trial_type'],
            confound_source_columns=list(p.MOTION), events_per_participant=2,
            conditions_per_participant={'language': 1, 'string': 1}), cohort=dict(n_expected=10),
        clock=dict(TR_s=1.5, frame_origin_s=.75), design=dict(motion_columns=list(p.MOTION),
            conditions=['language', 'string'], cosine=dict(high_pass_hz=.02),
            hrf=dict(oversampling=25, min_onset_s=-12)),
        tolerances=dict(header=dict(atol=1e-9, rtol=1e-9)))
    schema = dict(task_id='TASKFC-001', status='frozen_manufactured')
    method_path, schema_path = tmp_path/'method.json', tmp_path/'schema.json'
    def freeze():
        pin = rewrite(); method['source']['source_manifest_sha256'] = pin
        monkeypatch.setattr(r, 'SOURCE_SHA', pin)
        for path, value, name in ((method_path, method, 'METHOD_SHA'), (schema_path, schema, 'SCHEMA_SHA')):
            raw = json.dumps(value).encode(); path.write_bytes(raw)
            monkeypatch.setattr(r, name, hashlib.sha256(raw).hexdigest())
    freeze()
    return root, manifest, method, schema, method_path, schema_path, freeze


def update_member(frozen, sid, role, data):
    root, manifest, _, _, _, _, freeze = frozen
    row = next(x for x in manifest['files'] if (x['participant_id'], x['role']) == (sid, role))
    (root/row['path']).write_bytes(data)
    row.update(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    freeze()


def test_prepare_all48_all10_no_signal(frozen, monkeypatch):
    root, manifest, _, _, mp, sp, _ = frozen
    calls, original = [], p.authenticated_stream
    from contextlib import contextmanager
    @contextmanager
    def traced(path, row):
        calls.append(str(path))
        with original(path, row) as stream: yield stream
    monkeypatch.setattr(p, 'authenticated_stream', traced)
    monkeypatch.setattr(p, 'extract_series', lambda *a, **k: pytest.fail('sample decode'))
    prepared = r.prepare_reference(root, mp, sp)
    assert {str(root/row['path']) for row in manifest['files']} <= set(calls)
    assert list(prepared['structures']) == list(r.IDS)


@pytest.mark.parametrize('field', ['shape', 'frames', 'event_count', 'conditions', 'event_columns',
                                 'motion_columns', 'source_pin', 'cohort', 'fit_motion_order'])
def test_frozen_contract_mismatches_before_samples(frozen, monkeypatch, field):
    root, _, method, _, mp, sp, freeze = frozen
    if field == 'shape': method['source']['shape'][0] += 1
    elif field == 'frames': method['source']['n_frames_by_participant']['sub-10'] += 1
    elif field == 'event_count': method['source']['events_per_participant'] += 1
    elif field == 'conditions': method['source']['conditions_per_participant']['language'] += 1
    elif field == 'event_columns': method['source']['event_columns'].reverse()
    elif field == 'motion_columns': method['source']['confound_source_columns'].reverse()
    elif field == 'cohort': method['cohort']['n_expected'] = 9
    elif field == 'fit_motion_order': method['design']['motion_columns'].reverse()
    freeze()
    if field == 'source_pin':
        method['source']['source_manifest_sha256'] = '0'*64
        raw = json.dumps(method).encode(); mp.write_bytes(raw)
        monkeypatch.setattr(r, 'METHOD_SHA', hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(p, 'extract_series', lambda *a, **k: pytest.fail('sample decode'))
    with pytest.raises(ValueError): r.prepare_reference(root, mp, sp)


@pytest.mark.parametrize('value', [2., None, True, '1.5'])
def test_sidecar_clock_refused_before_samples(frozen, monkeypatch, value):
    update_member(frozen, 'sub-10', 'bold_json', json.dumps({'RepetitionTime': value}).encode())
    root, _, _, _, mp, sp, _ = frozen
    monkeypatch.setattr(p, 'extract_series', lambda *a, **k: pytest.fail('sample decode'))
    with pytest.raises(ValueError, match='sidecar_TR'): r.prepare_reference(root, mp, sp)


@pytest.mark.parametrize('field,value', [('zooms', [2., 2., 2., 2.]), ('temporal_units', 'unknown')])
def test_header_clock_refused(frozen, monkeypatch, field, value):
    root, _, _, _, mp, sp, _ = frozen
    original = p.read_header
    def changed(*args):
        header, dtype, affine = original(*args); header[field] = value
        return header, dtype, affine
    monkeypatch.setattr(p, 'read_header', changed)
    with pytest.raises(ValueError, match='header_TR'): r.prepare_reference(root, mp, sp)


def test_early_event_on_unselected_person_blocks_pilot(frozen, monkeypatch):
    update_member(frozen, 'sub-10', 'events', b'onset\tduration\ttrial_type\n-50\t1\tlanguage\n2\t1\tstring\n')
    root, _, _, _, mp, sp, _ = frozen
    monkeypatch.setattr(p, 'extract_series', lambda *a, **k: pytest.fail('sample decode'))
    with pytest.raises(ValueError, match='event_before'): r.reconstruct(root, mp, sp, subjects=['sub-01'])


def test_pilot_only_first_decode_and_no_endpoints(frozen, monkeypatch):
    root, _, method, _, mp, sp, _ = frozen
    decoded, design_calls = [], []
    original_extract, original_design = p.extract_series, m.build_design
    def extract(path, row, **kwargs):
        decoded.append(row['participant_id']); assert 'expected_header' in kwargs
        return original_extract(path, row, **kwargs)
    def design(*args, **kwargs):
        design_calls.append(kwargs)
        return original_design(*args, **kwargs)
    monkeypatch.setattr(p, 'extract_series', extract); monkeypatch.setattr(m, 'build_design', design)
    for name in ('replay', 'derive', 'summarize', 'pearson'):
        if hasattr(m, name): monkeypatch.setattr(m, name, lambda *a, **k: pytest.fail('endpoint'))
    result = r.reconstruct(root, mp, sp, subjects=['sub-01'])
    assert decoded == ['sub-01'] and result['participant_ids'] == ['sub-01']
    assert result['status'] == 'resource_pilot' and result['endpoints_computed'] is False
    assert len(result['cohort']) == 10 and len(result['events']) == 20
    assert design_calls == [dict(high_pass=.02, oversampling=25, min_onset=-12)]
    person = result['participants']['sub-01']
    assert person['raw'].shape == (4, 2) and person['residuals'].shape == (4, 2, 2)
    np.testing.assert_array_equal(person['frame_times'], np.arange(4)*1.5+.75)


def test_full_reuses_identical_participant_api(frozen):
    root, _, _, _, mp, sp, _ = frozen
    prepared = r.prepare_reference(root, mp, sp)
    one = r.reconstruct_participant(prepared, 'sub-01')
    full = r.reconstruct(root, mp, sp)
    assert full['participant_ids'] == list(r.IDS) and full['status'] == 'complete_primitives'
    np.testing.assert_array_equal(one['residuals'], full['participants']['sub-01']['residuals'])


@pytest.mark.parametrize('ids', [[], ['sub-02'], ['sub-01', 'sub-02'], ['1']])
def test_pilot_scope_before_source_reads(monkeypatch, ids):
    monkeypatch.setattr(r, 'prepare_reference', lambda *a: pytest.fail('source read'))
    with pytest.raises(ValueError, match='full_or_fixed'): r.reconstruct('/none', '/none', '/none', subjects=ids)


def test_late_source_mutation_rehashed(frozen):
    root, _, _, _, mp, sp, _ = frozen
    prepared = r.prepare_reference(root, mp, sp)
    row = prepared['keyed'][('sub-01', 'bold')]; path = root/row['path']
    raw = bytearray(path.read_bytes()); raw[-1] ^= 1; path.write_bytes(raw)
    with pytest.raises(ValueError, match='digest'): r.reconstruct_participant(prepared, 'sub-01')
