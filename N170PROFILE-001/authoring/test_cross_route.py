"""Manufactured complete37 cross-route qualification; never original EEG.

This file creates 74 tiny SET/FDT members in pytest's fresh temporary directory.
Only their source/doc pins and aggregate bytes are monkeypatched. Neither the
fixed cohort nor any decoder, scientific operator, event rule or precision
threshold is replaced. MNE entry points are observed by forwarding wrappers,
not stubs. The independent route remains direct FDT + analytic FIR.

Run only after parent review in the pinned, network-none MNE image, with this
file and its installed tests/, solution/, and environment/ dependencies read-only.
No reference bank, original directory, endpoint calculator or grader is needed.
"""
import hashlib
import io
import json
from pathlib import Path
import sys
import types

import numpy as np
import pytest
from scipy.io import savemat


TASK = Path(__file__).resolve().parents[1]
PATHS = {
    'source_reference.py': TASK/'tests'/'source_reference.py',
    'oracle_source.py': TASK/'solution'/'oracle_source.py',
    'io_contract.py': TASK/'tests'/'io_contract.py',
    'mat_metadata.py': TASK/'solution'/'mat_metadata.py',
    'independent_fir.py': TASK/'tests'/'independent_fir.py',
    'method_contract.json': TASK/'environment'/'method_contract.json',
    'output_schema.json': TASK/'environment'/'output_schema.json',
}
HELD = {
    'source_reference.py': '6e8d1c8cae9262e55a4da2598edf29dc4bd58c1ffae173fccd8dee723bb2a097',
    'oracle_source.py': '36558dd21ce1722f2dd4be6d29a2215e988795b19d474611a29e92c8cdf5bb60',
    'io_contract.py': 'afe9f4daf4a4ac8829e735094af4abfc6ed7f98dd1be35a03bf6a2385a4ac082',
    'mat_metadata.py': '66fb278c78255e382b85359d26e76df2059c3f9c9dfb2b3ca73ec138148623f7',
    'independent_fir.py': '86e0886c018517ab37b887677de140cf477cfc3d1a5d08f82f3b1d5d91de143f',
    'method_contract.json': '549cf315f0175ab13c3007703cec298a6cc5080d695aecd9f93f49e98a08ce92',
    'output_schema.json': 'fab0dbf2ff1fb60f0596b065ff5f148d9d46da8c89c6e81203dbc346a2070814',
}
SUBJECTS = tuple(str(i) for i in range(1, 41) if i not in (1, 5, 16))
CHANNELS = ('FP1','F3','F7','FC3','C3','C5','P3','P7','P9','PO7','PO3','O1','Oz','Pz','CPz',
            'FP2','Fz','F4','F8','FC4','FCz','Cz','C4','C6','P4','P8','P10','PO8','PO4','O2',
            'HEOG_left','HEOG_right','VEOG_lower')


def held_bytes(name):
    raw = PATHS[name].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == HELD[name], name + ': reviewed closure changed'
    return raw


def load_code(name, filename, monkeypatch):
    module = types.ModuleType(name)
    module.__file__ = str(PATHS[filename])
    monkeypatch.setitem(sys.modules, name, module)
    exec(compile(held_bytes(filename), module.__file__, 'exec'), module.__dict__)
    return module


def event(code, latency, duration=0., urevent=1):
    return dict(type=code, latency=latency, duration=duration, urevent=urevent)


def fixture_events(subject, n):
    if subject == '2':
        return [event(1, 282.), event(' +41 ', 436.),
                event(2, 121.5), event(42, 121.49),
                event(3, 1.), event(43, 1.),
                event(' Boundary ', 384.2, 500.), event(-99, 385.),
                event('-99', 769.), event(4, 351.), event(44, 701.),
                event(45, 820.), event('BAD_noise', 501., urevent=np.nan),
                event('1.0', 701.), event(-99, 1.), event(-99, n + 1.)]
    if subject == '4':
        return [event(' +1 ', 121.), event(40, 301.), event('face41', 401.)]
    if subject == '6':
        return [event(1, 1.), event(41, n), event(2, 121.5), event(42, 121.49)]
    if subject == '8':
        return [event(-99, 2.), event('boundary', 3.), event(1, 121.), event(41, 301.)]
    if subject == '10':
        return [event(1, 701.), event(2, 201.), event(41, 451.)]
    if subject == '11':
        return [event(41, 121.), event(' +80 ', 301.)]
    if subject == '12':
        return [event('BAD_only_documentary', 121.), event(99, 301.)]
    if subject == '13':
        return [event(1, 121.), event(-99, 513.), event(41, 633.)]
    # Both nearest-even half-sample directions, without a duplicate sample.
    return [event(1, 121.5), event(41, 302.5)]


def fixture_values(subject, n):
    t = np.arange(n, dtype=np.float64)
    channel = np.arange(30, dtype=np.float64)[:, None]
    scale = (0.001, 1., 8.)[int(subject) % 3]
    scalp = scale * (np.sin(t[None, :] * (channel + 2) * 2*np.pi/256 + channel/7)
                     + 0.2*np.cos(t[None, :] * 2*np.pi*80/256 + channel/3))
    scalp += (channel - 14) / 8
    if subject == '3':
        # A large contributing-channel artifact, comfortably away from 150 uV.
        scalp[0] += 1024*np.sin(t*2*np.pi*10/256)
    if subject == '7':
        scalp[:] = 0  # Valid zero signals, not a fabricated missing-data flag.
    if subject == '10':
        scalp += 512*np.sin(t[None, :]*2*np.pi*2/256)  # Remove all30 common mode.
    if subject == '13':
        scalp[:, 512:] = scalp[:, :512]  # Identical independently filtered halves.
    # Layout is channel-fastest; excluded EOG is deliberately nonfinite.
    values = np.empty((33, n), dtype='<f4')
    values[:30] = scalp
    values[30], values[31], values[32] = np.nan, np.inf, -np.inf
    return values


def make_bundle(parent, monkeypatch, reference, oracle):
    root = parent / 'fabricated_sources'
    root.mkdir()
    members = []
    events_by_subject = {}
    for subject in SUBJECTS:
        n = 1024 if subject in ('2', '10', '13') else 512 + int(subject) % 2
        events = fixture_events(subject, n)
        events_by_subject[subject] = events
        eeg = dict(data=f'{subject}_N170_shifted_ds.fdt', nbchan=33, pnts=n,
                   trials=1, srate=256., xmin=0., xmax=(n-1)/256, ref='common',
                   history='MANUFACTURED cross-route fixture; never a source recording',
                   chanlocs=np.array([{'labels':label} for label in CHANNELS], dtype=object),
                   event=np.array(events, dtype=object), urevent=np.array(events, dtype=object),
                   icaweights=np.zeros((0, 0)))
        buffer = io.BytesIO()
        savemat(buffer, {'EEG':eeg}, do_compression=True)
        blobs = {'set':buffer.getvalue(), 'fdt':fixture_values(subject, n).tobytes(order='F')}
        for role, raw in blobs.items():
            name = f'{subject}_N170_shifted_ds.{role}'
            with (root / name).open('xb') as stream:
                stream.write(raw)
            members.append(dict(subject=int(subject), role=role, path=name, size_bytes=len(raw),
                                sha256=hashlib.sha256(raw).hexdigest(), md5=hashlib.md5(raw).hexdigest()))
    total = sum(row['size_bytes'] for row in members)
    manifest = dict(task_id='N170PROFILE-001', subjects=[int(s) for s in SUBJECTS],
                    files=members, source_file_count=74, source_bytes=total)
    manifest_raw = json.dumps(manifest, sort_keys=True, allow_nan=False).encode()
    source_pin = hashlib.sha256(manifest_raw).hexdigest()
    method = json.loads(held_bytes('method_contract.json'))
    assert method['subjects'] == list(SUBJECTS)
    method['source_manifest_sha256'] = source_pin  # Fixture provenance only.
    method_raw = json.dumps(method, sort_keys=True, allow_nan=False).encode()
    schema_raw = held_bytes('output_schema.json')
    documents = {'source_manifest.json':manifest_raw, 'method_contract.json':method_raw,
                 'output_schema.json':schema_raw}
    for name, raw in documents.items():
        with (parent / name).open('xb') as stream:
            stream.write(raw)
    with (root / 'source_manifest.json').open('xb') as stream:
        stream.write(manifest_raw)
    for module, suffix in ((reference, ''), (oracle, '256')):
        monkeypatch.setattr(module, 'SOURCE_SHA' + suffix, source_pin)
        monkeypatch.setattr(module, 'METHOD_SHA' + suffix, hashlib.sha256(method_raw).hexdigest())
        monkeypatch.setattr(module, 'SCHEMA_SHA' + suffix, hashlib.sha256(schema_raw).hexdigest())
        monkeypatch.setattr(module, 'SOURCE_BYTES', total)
        assert module.SUBJECTS == SUBJECTS  # Never replace the cohort/count guard.
    return (root, parent/'source_manifest.json', parent/'method_contract.json', parent/'output_schema.json'), events_by_subject


def fingerprint(parent):
    return {str(p.relative_to(parent)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in parent.rglob('*') if p.is_file()}


@pytest.fixture(scope='module')
def routes(tmp_path_factory):
    import mne
    assert mne.__version__ == '1.12.1'
    parent = tmp_path_factory.mktemp('n170-manufactured-cross-route')
    with pytest.MonkeyPatch.context() as patch:
        for name in ('io_contract', 'mat_metadata'):
            load_code(name, name + '.py', patch)
        reference = load_code('_n170_cross_reference', 'source_reference.py', patch)
        oracle = load_code('_n170_cross_oracle', 'oracle_source.py', patch)
        held_bytes('independent_fir.py')
        args, events = make_bundle(parent, patch, reference, oracle)
        before = fingerprint(parent)
        calls = {'read':[], 'filter':[]}
        original_read, original_filter = mne.io.read_raw_eeglab, mne.filter.filter_data
        def record_read(path, *positional, **keywords):
            assert Path(path).parent != args[0]
            calls['read'].append(Path(path).name)
            return original_read(path, *positional, **keywords)
        def record_filter(values, *positional, **keywords):
            calls['filter'].append((values.shape, dict(keywords)))
            return original_filter(values, *positional, **keywords)
        patch.setattr(mne.io, 'read_raw_eeglab', record_read)
        patch.setattr(mne.filter, 'filter_data', record_filter)
        direct = reference.reconstruct(*args)
        native = oracle.reconstruct(*args)
        after = fingerprint(parent)
        assert before == after, 'Either reconstruction modified manufactured source/doc bytes'
        yield dict(direct=direct, native=native, calls=calls, events=events,
                   before=before, after=after)


def assert_wave_bound(accepted, source):
    source = np.ascontiguousarray(source, dtype=np.float64)
    accepted = np.ascontiguousarray(accepted, dtype=np.float64)
    assert accepted.shape == source.shape and np.isfinite(accepted).all()
    magnitude = float(np.max(np.abs(source)))
    limit = 1e-8*magnitude + 64*np.finfo(np.float64).eps*max(1., magnitude)
    error = float(np.max(np.abs(accepted-source)))
    assert error <= limit, f'frozen supnorm gate: error={error!r}, limit={limit!r}'


def test_complete_fixed_cohort_real_mne_io_and_filter(routes):
    a, b = routes['direct'], routes['native']
    assert a['status'] == b['status'] == 'complete'
    assert a['subjects'] == b['subjects'] == list(SUBJECTS)
    assert len(a['source_files']) == len(b['source_files']) == 74
    assert routes['calls']['read'] == [f'{s}_N170_shifted_ds.set' for s in SUBJECTS]
    filters = routes['calls']['filter']
    assert len(filters) > 37 and any(shape == (30, 1) for shape, _ in filters)
    for shape, kw in filters:
        assert shape[0] == 30 and kw['sfreq'] == 256 and kw['pad'] == 'reflect_limited'
        assert kw['phase'] == 'zero' and kw['l_freq'] == .1 and kw['h_freq'] == 30
    assert any('filter_length' in warning['message'] for warning in b['warnings'])


@pytest.mark.parametrize('key', ['annotations', 'trials', 'epoch_keys', 'source_files', 'pins',
                                'source_observed', 'analysis_observed', 'condition_labels',
                                'rejection_channel_labels'])
def test_exact_complete_ledgers_metadata_and_axis_membership(routes, key):
    assert routes['direct'][key] == routes['native'][key]


@pytest.mark.parametrize('key', ['sample_offsets', 'condition_defined'])
def test_exact_numeric_axes_and_condition_support(routes, key):
    np.testing.assert_array_equal(routes['native'][key], routes['direct'][key])


@pytest.mark.parametrize('key', ['epoch_peak_to_peak_uv', 'epoch_po8_baseline_uv'])
def test_all_eligible_trial_receipts_keep_frozen_voltage_precision(routes, key):
    a, b = routes['direct'][key], routes['native'][key]
    assert a.shape == b.shape and np.isfinite(a).all() and np.isfinite(b).all()
    np.testing.assert_allclose(b, a, atol=1e-6, rtol=1e-6)
    assert len(a) == len(routes['direct']['epoch_keys'])


def test_all_defined_condition_and_rebased_difference_waveform_gates(routes):
    a, b = routes['direct'], routes['native']
    assert a['evoked_po8_uv'].shape == b['evoked_po8_uv'].shape == (37, 2, 154)
    for i, flags in enumerate(a['condition_defined']):
        for c, defined in enumerate(flags):
            if defined:
                assert_wave_bound(b['evoked_po8_uv'][i, c], a['evoked_po8_uv'][i, c])
            else:
                assert np.all(a['evoked_po8_uv'][i, c] == 0)
                assert np.all(b['evoked_po8_uv'][i, c] == 0)
        if flags.all():
            ad = np.ascontiguousarray(a['evoked_po8_uv'][i, 0]-a['evoked_po8_uv'][i, 1])
            bd = np.ascontiguousarray(b['evoked_po8_uv'][i, 0]-b['evoked_po8_uv'][i, 1])
            ad -= np.mean(ad[:52], dtype=np.float64)
            bd -= np.mean(bd[:52], dtype=np.float64)
            assert_wave_bound(bd, ad)


def test_boundary_duplicate_and_fractional_clock_known_answers(routes):
    rows = {r['source_event_index']:r for r in routes['direct']['trials'] if r['subject_id'] == '2'}
    assert rows[0]['event_sample'] == 281 and rows[0]['epoch_last_sample'] == 383
    assert rows[1]['event_sample'] == 435 and rows[1]['epoch_first_sample'] == 384
    assert rows[0]['accepted'] and rows[1]['accepted']
    assert rows[2]['event_sample'] == rows[3]['event_sample'] == 120
    assert rows[2]['rejection_reason'] == rows[3]['rejection_reason'] == 'duplicate_target_sample'
    assert rows[4]['rejection_reason'] == rows[5]['rejection_reason'] == 'out_of_bounds'
    assert rows[9]['rejection_reason'] == rows[10]['rejection_reason'] == 'crosses_boundary'
    assert rows[11]['accepted'] and rows[11]['epoch_first_sample'] == 768
    obs = next(p for p in routes['direct']['source_observed']['persons'] if p['subject_id'] == '2')
    assert obs['boundary_cut_samples'] == [0, 384, 768, 1024]
    assert obs['filter_segments'] == [[0, 384], [384, 768], [768, 1024]]
    assert len(obs['boundary_event_indices']) == 5  # Duplicate cuts retain both event rows.
    other = next(r for r in routes['direct']['annotations'] if r['subject_id'] == '2' and r['source_event_index'] == 12)
    assert other['event_role'] == 'other' and json.loads(other['urevent_json']) == {'__nonfinite__':'NaN'}


def test_artifact_rejection_missing_conditions_and_zero_signal_not_missing(routes):
    a = routes['direct']
    by_subject = dict(zip(a['subjects'], a['condition_defined'].tolist()))
    assert by_subject['3'] == [False, False]
    assert by_subject['4'] == [True, False] and by_subject['11'] == [False, True]
    assert by_subject['6'] == by_subject['12'] == [False, False]
    assert by_subject['7'] == [True, True]
    assert np.all(a['evoked_po8_uv'][a['subjects'].index('7')] == 0)
    rejected = [r for r in a['trials'] if r['subject_id'] == '3']
    assert rejected and all(r['epoch_status'] == 'ok' and r['rejection_reason'] == 'peak_to_peak' for r in rejected)
    keys = set(a['epoch_keys'])
    assert all(('3', r['source_event_index']) in keys for r in rejected)
    assert not any(subject in ('6', '12') for subject, _ in keys)


def test_exact_repeated_segment_difference_and_event_row_average_order(routes):
    for result in (routes['direct'], routes['native']):
        waves = result['evoked_po8_uv'][result['subjects'].index('13')]
        np.testing.assert_array_equal(waves[0], waves[1])
        assert np.max(np.abs(waves)) > 0
        rows = [r for r in result['trials'] if r['subject_id'] == '10']
        assert [r['event_sample'] for r in rows] == [700, 200, 450]
        assert [key for key in result['epoch_keys'] if key[0] == '10'] == [('10', 0), ('10', 1), ('10', 2)]


def test_complete_manufactured_inputs_immutable(routes):
    assert routes['before'] == routes['after'] and len(routes['before']) == 78
