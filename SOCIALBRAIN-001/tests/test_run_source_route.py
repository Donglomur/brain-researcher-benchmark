"""Manufactured primitive-route runner; no original arrays or source helpers."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('route_runner_fixture', Path(__file__).with_name('run_source_route.py'))
w = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = w
spec.loader.exec_module(w)


def sha(raw): return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def fixture(tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    paths = [tmp_path / name for name in ('manifest.json', 'method.json', 'schema.json')]
    for path in paths: path.write_bytes(b'{"manufactured":true}\n')
    pins = dict(zip(('source_manifest_sha256', 'method_sha256', 'output_schema_sha256'), [sha(p.read_bytes()) for p in paths]))
    pins['reporting_kernel_sha256'] = 'a' * 64
    ids = ('sub-pixar001', 'sub-pixar002')
    people = {}
    for i, sid in enumerate(ids):
        n = i + 4
        people[sid] = dict(raw_roi=np.arange(n * 12, dtype=np.float64).reshape(n, 12),
            global_signal=np.arange(n, dtype=np.float64), cleaned_roi=np.ones((n, 2, 12)),
            canonical_active=np.ones((2, 12), dtype=bool), frame_indices=np.arange(n, dtype=np.int64))
    reference = dict(status='complete', subject_ids=list(ids), roi_ids=[f'ROI{i}' for i in range(12)],
        pipeline_ids=['without_GSR', 'with_GSR'], persons=people, covariates={sid: {'age': 8. + i} for i, sid in enumerate(ids)},
        cohort=[dict(subject_id=sid, age=8. + i) for i, sid in enumerate(ids)], pins=pins,
        roi_definitions=[dict(roi_id=f'ROI{i}') for i in range(12)], source_files=[],
        source_observed=dict(persons=[dict(subject_id=sid) for sid in ids]), analysis_observed=dict(persons=[]),
        method={'manufactured': True}, schema={'manufactured': True}, warnings=[])
    return dict(source=source, paths=paths, pins=pins, ids=ids, reference=reference,
                output=tmp_path / 'evidence', code_pins={'fake_adapter.py': 'b' * 64})


def run(f, adapter=None, *, pilot=False, route='private'):
    if adapter is None:
        def adapter(*paths, pilot):
            result = copy.deepcopy(f['reference'])
            if pilot:
                result['status'] = 'resource_pilot'; result['subject_ids'] = [f['ids'][0]]
                result['persons'] = {f['ids'][0]: result['persons'][f['ids'][0]]}
            return result
    return w.run_route(adapter, f['source'], *f['paths'], f['output'], route=route, pilot=pilot,
        expected_subjects=f['ids'], _document_pins=f['pins'], _code_pins=f['code_pins'])


@pytest.mark.parametrize('route', ['private', 'oracle'])
@pytest.mark.parametrize('pilot', [False, True])
def test_complete_save_load_roundtrip_without_pickle(fixture, route, pilot):
    result = run(fixture, route=route, pilot=pilot)
    assert result['status'] == ('resource_pilot' if pilot else 'complete')
    assert result['n_subjects'] == (1 if pilot else 2)
    assert result['endpoints_computed'] is result['production_artifacts_written'] is False
    assert result['elapsed_seconds'] >= 0 and result['peak_rss_kib'] > 0
    assert set(p.name for p in fixture['output'].iterdir()) == {'attempt.json', 'report.json', 'canonical.json', 'primitives.npz'}
    metadata = json.loads((fixture['output'] / 'canonical.json').read_bytes())
    assert 'persons' not in metadata and len(metadata['cohort']) == 2
    with np.load(fixture['output'] / 'primitives.npz', allow_pickle=False) as archive:
        assert set(archive.files) == {'subject_ids', 'roi_ids', 'pipeline_ids', 'frame_subject_ids',
            'frame_indices', 'raw_roi', 'global_signal', 'cleaned_roi', 'canonical_active'}
        for index, slice_ in enumerate(metadata['person_slices']):
            sid, start, stop = (slice_[key] for key in ('subject_id', 'start', 'stop'))
            person = fixture['reference']['persons'][sid]
            for key in ('raw_roi', 'global_signal', 'cleaned_roi', 'frame_indices'):
                np.testing.assert_array_equal(archive[key][start:stop], person[key])
            np.testing.assert_array_equal(archive['canonical_active'][index], person['canonical_active'])
            assert all(v == sid for v in archive['frame_subject_ids'][start:stop])
        assert all(archive[name].dtype.kind != 'O' for name in archive.files)
    for row in result['files']:
        raw = (fixture['output'] / row['path']).read_bytes()
        assert len(raw) == row['size_bytes'] and sha(raw) == row['sha256']


def test_existing_empty_output_accepted(fixture):
    fixture['output'].mkdir()
    assert run(fixture)['status'] == 'complete'


@pytest.mark.parametrize('kind', ['nonempty', 'symlink', 'dangling', 'parent_link_dotdot', 'source_child', 'source_parent', 'code_child', 'document'])
def test_no_output_mutation_on_unsafe_target(fixture, kind):
    root = fixture['output'].parent
    if kind == 'nonempty':
        fixture['output'].mkdir(); (fixture['output'] / 'keep').write_bytes(b'preserve')
    elif kind in ('symlink', 'dangling'):
        fixture['output'].symlink_to(fixture['source'] if kind == 'symlink' else root / 'absent', target_is_directory=True)
    elif kind == 'parent_link_dotdot':
        link = root / 'link'; link.symlink_to(fixture['source'], target_is_directory=True)
        fixture['output'] = str(link) + '/../evidence'
    elif kind == 'source_child': fixture['output'] = fixture['source'] / 'output'
    elif kind == 'source_parent': fixture['output'] = root
    elif kind == 'code_child': fixture['output'] = Path(w.__file__).absolute().parent / 'DO_NOT_CREATE'
    else: fixture['output'] = fixture['paths'][0]
    before = {p: p.read_bytes() for p in fixture['paths']}
    with pytest.raises(ValueError): run(fixture)
    assert {p: p.read_bytes() for p in fixture['paths']} == before
    assert not list(fixture['source'].iterdir())


def test_failure_receipt_redacts_original_exception_and_stops(fixture):
    calls = []
    def adapter(*args, **kwargs):
        calls.append(1); raise ValueError('ORIGINAL VALUE 314159 MUST NOT BE LOGGED')
    result = run(fixture, adapter)
    assert result['status'] == 'failed' and result['phase'] == 'reconstruction' and calls == [1]
    text = ''.join(p.read_text() for p in fixture['output'].iterdir())
    assert '314159' not in text and 'ValueError' in text
    assert (fixture['output'] / 'failure_report.json').is_file()
    with pytest.raises(ValueError, match='fresh_or_empty'): run(fixture, adapter)
    assert calls == [1]


@pytest.mark.parametrize('mutation', ['status', 'subject', 'person_extra', 'frames', 'bool_frames',
    'object', 'nan', 'active_dtype', 'active_shape', 'raw_shape', 'pipeline', 'roi_duplicate', 'pins', 'metadata_array', 'metadata_nan'])
def test_malformed_primitive_or_metadata_preserved_failure(fixture, mutation):
    def adapter(*args, **kwargs):
        value = copy.deepcopy(fixture['reference']); first = value['persons'][fixture['ids'][0]]
        if mutation == 'status': value['status'] = 'resource_pilot'
        elif mutation == 'subject': value['subject_ids'].reverse()
        elif mutation == 'person_extra': first['endpoint'] = 0.
        elif mutation == 'frames': first['frame_indices'][0] = 1
        elif mutation == 'bool_frames': first['frame_indices'] = first['frame_indices'].astype(bool)
        elif mutation == 'object': first['raw_roi'] = first['raw_roi'].astype(object)
        elif mutation == 'nan': first['cleaned_roi'][0, 0, 0] = np.nan
        elif mutation == 'active_dtype': first['canonical_active'] = first['canonical_active'].astype(int)
        elif mutation == 'active_shape': first['canonical_active'] = np.ones((12, 2), bool)
        elif mutation == 'raw_shape': first['raw_roi'] = first['raw_roi'][:, :-1]
        elif mutation == 'pipeline': value['pipeline_ids'] = ['with_GSR', 'without_GSR']
        elif mutation == 'roi_duplicate': value['roi_ids'][0] = value['roi_ids'][1]
        elif mutation == 'pins': value['pins']['method_sha256'] = '0' * 64
        elif mutation == 'metadata_array': value['source_observed']['forbidden'] = np.ones(3)
        elif mutation == 'metadata_nan': value['cohort'][0]['age'] = float('nan')
        return value
    result = run(fixture, adapter)
    assert result['status'] == 'failed'
    assert (fixture['output'] / 'failure_report.json').exists()
    assert not (fixture['output'] / 'network_connectivity.csv').exists()
    if mutation in ('metadata_array', 'metadata_nan'):
        assert (fixture['output'] / 'primitives.npz').exists()  # preserve earlier evidence


def test_pilot_cannot_masquerade_as_full(fixture):
    def adapter(*args, **kwargs): return copy.deepcopy(fixture['reference'])
    assert run(fixture, adapter, pilot=True)['status'] == 'failed'


def test_preexisting_failure_marker_from_adapter_is_authoritative(fixture):
    def adapter(*args, **kwargs):
        (fixture['output'] / 'failure_report.json').write_bytes(b'owned upstream failure\n')
        return copy.deepcopy(fixture['reference'])
    assert run(fixture, adapter)['status'] == 'failed'
    assert (fixture['output'] / 'failure_report.json').read_bytes() == b'owned upstream failure\n'
    assert not (fixture['output'] / 'primitives.npz').exists()


def test_document_auth_before_adapter(fixture):
    fixture['paths'][1].write_bytes(b'changed')
    def adapter(*args, **kwargs): pytest.fail('called before document authentication')
    result = run(fixture, adapter)
    assert result['status'] == 'failed' and result['phase'] == 'binding'


def test_unfrozen_wrapper_refuses_owned_failure(fixture):
    result = w.run_route(None, fixture['source'], *fixture['paths'], fixture['output'], route='private')
    assert result['status'] == 'failed' and result['phase'] == 'binding'
    assert (fixture['output'] / 'failure_report.json').exists()


def test_array_cap_before_archive(fixture, monkeypatch):
    monkeypatch.setattr(w, 'MAX_ARRAY_BYTES', 100)
    assert run(fixture)['status'] == 'failed'
    assert not (fixture['output'] / 'primitives.npz').exists()


def test_complete_closure_before_adapter_compile(tmp_path, monkeypatch):
    directory = tmp_path / 'code'; directory.mkdir()
    monkeypatch.setattr(w, '__file__', str(directory / 'run_source_route.py'))
    payload = b'raise AssertionError("must not compile before all identities pass")\n'
    pins = {}
    for name in w.ROUTE_PINS['private']:
        raw = payload if name == 'source_reference.py' else b'# manufactured dependency\n'
        (directory / name).write_bytes(raw); pins[name] = sha(raw)
    pins['reporting_kernel.py'] = '0' * 64
    monkeypatch.setitem(w.ROUTE_PINS, 'private', pins)
    with pytest.raises(ValueError, match='input_sha256'): w.load_adapter('private')


def test_cli_does_not_print_values_or_invent_success(fixture, monkeypatch, capsys):
    def result(*args, **kwargs):
        return dict(status='failed', route='private', pilot=True, original_value='DO_NOT_PRINT')
    monkeypatch.setattr(w, 'run_route', result)
    args = ['--route', 'private', '--data-dir', str(fixture['source']), '--manifest', str(fixture['paths'][0]),
            '--method', str(fixture['paths'][1]), '--schema', str(fixture['paths'][2]), '--output', str(fixture['output']), '--pilot']
    assert w.main(args) == 1
    value = capsys.readouterr().out
    assert 'DO_NOT_PRINT' not in value and json.loads(value)['status'] == 'failed'
