"""Manufactured-only source/reference fixtures; no original files or bank.

Tiny two-person manifests explicitly repin module constants in this test
process. Production reconstruct exposes no test policy or environment bypass.
Focused arithmetic tests supply an identity filter object to process_person;
full reconstruct positives use the SHA-bound analytic FIR and MAT scanner.
"""
import hashlib
import io
import json
import os
import struct
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.io import savemat

import source_reference as sr


def encoded(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()


def set_bytes(subject, pnts, events, *, labels=None, overrides=None, inline=False):
    labels = list(sr.SCALP + sr.EOG) if labels is None else labels
    channels = np.empty(len(labels), dtype=[('labels', 'O'), ('type', 'O')])
    for i, label in enumerate(labels): channels[i] = (label, '')
    names = tuple(dict.fromkeys(name for event in events for name in event)) or ('type', 'latency')
    event_array = np.empty(len(events), dtype=[(name, 'O') for name in names])
    for i, event in enumerate(events):
        for name in names:
            value = event.get(name)
            event_array[name][i] = np.empty((0, 0)) if value is None else value
    fields = dict(nbchan=33, trials=1, pnts=pnts, srate=256., xmin=0.,
                  xmax=(pnts-1)/256., ref='common', history='manufactured only',
                  chanlocs=channels, event=event_array, times=np.arange(pnts),
                  icaweights=np.empty((0,0)), icasphere=np.empty((0,0)),
                  data=np.zeros((33,pnts)) if inline else f'{subject}_N170_shifted_ds.fdt')
    fields.update(overrides or {})
    out = io.BytesIO(); savemat(out, {'EEG': fields}, do_compression=True)
    return out.getvalue()


def fdt_bytes(values):
    return np.asarray(values, dtype='<f4').tobytes(order='F')


def make_bundle(tmp_path, monkeypatch, *, events=None, signals=None):
    root = tmp_path / 'source'; root.mkdir()
    subjects = ('2', '3')
    records, originals = [], {}
    for index, subject in enumerate(subjects):
        data = np.zeros((33, 768), dtype=np.float32)
        time = np.arange(768, dtype=float)
        data[27] = (1 + index) * np.sin(time / 11.)
        data[0] = -data[27]
        if signals and subject in signals: data = signals[subject]
        selected_events = (events or {}).get(subject, [dict(type=1, latency=151.), dict(type=41, latency=501.)])
        original_set = set_bytes(subject, data.shape[1], selected_events)
        originals[subject] = data.copy()
        for role, raw in [('set', original_set), ('fdt', fdt_bytes(data))]:
            path = f'{subject}_N170_shifted_ds.{role}'
            (root / path).write_bytes(raw)
            records.append(dict(subject=int(subject), role=role, path=path,
                                size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                                md5=hashlib.md5(raw).hexdigest()))
    total = sum(row['size_bytes'] for row in records)
    manifest = dict(task_id='N170PROFILE-001', subjects=[2,3], source_file_count=4,
                    source_bytes=total, files=records)
    manifest_raw = encoded(manifest)
    manifest_path = tmp_path / 'source_manifest.json'; manifest_path.write_bytes(manifest_raw)
    (root / 'source_manifest.json').write_bytes(manifest_raw)
    source_sha = hashlib.sha256(manifest_raw).hexdigest()
    method = dict(task_id='N170PROFILE-001', subjects=list(subjects), source_manifest_sha256=source_sha)
    schema = dict(task_id='N170PROFILE-001')
    method_path, schema_path = tmp_path/'method.json', tmp_path/'schema.json'
    method_path.write_bytes(encoded(method)); schema_path.write_bytes(encoded(schema))
    for name, value in dict(SUBJECTS=subjects, SOURCE_BYTES=total, SOURCE_SHA=source_sha,
                            METHOD_SHA=hashlib.sha256(encoded(method)).hexdigest(),
                            SCHEMA_SHA=hashlib.sha256(encoded(schema)).hexdigest()).items():
        monkeypatch.setattr(sr, name, value)
    return SimpleNamespace(root=root, manifest_path=manifest_path, method_path=method_path,
                           schema_path=schema_path, manifest=manifest, originals=originals)


def run(bundle, **kwargs):
    return sr.reconstruct(bundle.root, bundle.manifest_path, bundle.method_path, bundle.schema_path, **kwargs)


def original_hashes(root):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}


class IdentityFIR:
    def __init__(self): self.segments = []
    def filter_segment(self, data, fs):
        assert fs == 256.0
        self.segments.append(data.copy())
        return data.copy()


def arithmetic_header(events, pnts=700, labels=None):
    annotations, trials, segments, _, _ = sr.annotate_events('2', events, pnts)
    return dict(subject='2', pnts=pnts, labels=list(labels or sr.SCALP + sr.EOG),
                annotations=annotations, trials=trials, segments=segments)


def test_full_two_person_reconstruction_real_scanner_and_fir(tmp_path, monkeypatch):
    bundle = make_bundle(tmp_path, monkeypatch)
    before = original_hashes(bundle.root)
    result = run(bundle)
    assert result['status'] == 'complete' and result['subjects'] == ['2', '3']
    assert result['evoked_po8_uv'].shape == (2, 2, 154)
    assert result['condition_defined'].tolist() == [[True, True], [True, True]]
    assert result['epoch_peak_to_peak_uv'].shape == (4, 30)
    assert result['epoch_keys'] == [('2', 0), ('2', 1), ('3', 0), ('3', 1)]
    assert len(result['annotations']) == len(result['trials']) == 4
    assert [r['subject_id'] for r in result['source_observed']['persons']] == ['2', '3']
    assert all(row['accepted'] and row['rejection_reason'] == 'accepted' for row in result['trials'])
    assert set(result['pins']) == {'source_manifest_sha256', 'method_contract_sha256', 'output_schema_sha256'}
    assert original_hashes(bundle.root) == before


def test_pilot_authenticates_and_parses_every_person_but_decodes_only_first(tmp_path, monkeypatch):
    bundle = make_bundle(tmp_path, monkeypatch)
    called = []
    original = sr.process_person
    def record(raw, header, fir):
        called.append(header['subject']); return original(raw, header, fir)
    monkeypatch.setattr(sr, 'process_person', record)
    result = run(bundle, pilot=True)
    assert called == ['2'] and result['subjects'] == ['2']
    assert result['status'] == 'resource_pilot'
    assert len(result['source_files']) == 4 and len(result['annotations']) == 4
    assert len(result['source_observed']['persons']) == 2
    assert len(result['analysis_observed']['persons']) == 1
    assert {row['subject_id'] for row in result['trials']} == {'2'}


@pytest.mark.parametrize('pilot', [1, 'true', None, ['2']])
def test_pilot_is_only_an_explicit_boolean(tmp_path, monkeypatch, pilot):
    bundle = make_bundle(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='explicit_pilot'): run(bundle, pilot=pilot)


@pytest.mark.parametrize('target', ['source_manifest.json', '2_N170_shifted_ds.set', '3_N170_shifted_ds.fdt'])
def test_source_mismatch_rejected_before_any_metadata_decode(tmp_path, monkeypatch, target):
    bundle = make_bundle(tmp_path, monkeypatch)
    path = bundle.root / target
    raw = bytearray(path.read_bytes()); raw[-1] ^= 1; path.write_bytes(raw)
    monkeypatch.setattr(sr, '_bound_module', lambda *args: pytest.fail('metadata parsed before full authentication'))
    with pytest.raises(ValueError, match='sha256'): run(bundle, pilot=True)


@pytest.mark.parametrize('document', ['method_path', 'schema_path', 'manifest_path'])
def test_external_authority_document_is_individually_pinned(tmp_path, monkeypatch, document):
    bundle = make_bundle(tmp_path, monkeypatch)
    path = getattr(bundle, document); path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError, match='sha256'): run(bundle)


@pytest.mark.parametrize('kind', ['extra_file', 'extra_directory', 'symlink', 'fifo'])
def test_closed_inventory_and_regular_files(tmp_path, monkeypatch, kind):
    bundle = make_bundle(tmp_path, monkeypatch)
    extra = bundle.root / 'unexpected'
    if kind == 'extra_file': extra.write_bytes(b'x')
    elif kind == 'extra_directory': extra.mkdir()
    elif kind == 'symlink': extra.symlink_to(tmp_path / 'dangling')
    else: os.mkfifo(extra)
    with pytest.raises(ValueError, match='inventory|nonregular'): run(bundle)


def test_fdt_change_after_initial_authentication_rejected_at_consumption(tmp_path, monkeypatch):
    bundle = make_bundle(tmp_path, monkeypatch)
    original = sr.parse_header
    def changed(*args):
        result = original(*args)
        if result['subject'] == '3':
            path = bundle.root / '2_N170_shifted_ds.fdt'
            raw = bytearray(path.read_bytes()); raw[0] ^= 1; path.write_bytes(raw)
        return result
    monkeypatch.setattr(sr, 'parse_header', changed)
    with pytest.raises(ValueError, match='sha256'): run(bundle)


def test_bound_dependency_is_checked_before_source_compilation(tmp_path, monkeypatch):
    fake_module = tmp_path / 'source_reference.py'; fake_module.write_text('')
    (tmp_path / 'mat_metadata.py').write_text('raise AssertionError("must not execute")')
    monkeypatch.setattr(sr, '__file__', str(fake_module))
    with pytest.raises(ValueError, match='sha256'): sr._bound_module('mat_metadata.py', sr.SCANNER_SHA)


@pytest.mark.parametrize('value,code,role', [(1,1,'face'), (40.,40,'face'), (' +41 ',41,'car'),
    ('80',80,'car'), (True,None,'other'), ('1.0',None,'other'), ('S1',None,'other'),
    (81,81,'other'), (' -99 ',-99,'boundary'), (' Boundary ',None,'boundary')])
def test_exact_event_type_normalization(value, code, role):
    rows, _, _, _, _ = sr.annotate_events('2', [dict(type=value, latency=151)], 700)
    assert rows[0]['normalized_event_code'] == code and rows[0]['event_role'] == role
    assert json.loads(rows[0]['type_json']) == value


def test_fractional_target_ties_are_nearest_even_and_duplicates_not_dropped():
    _, trials, _, _, _ = sr.annotate_events('2', [
        dict(type=1, latency=101.5), dict(type=2, latency=102.5),
        dict(type=41, latency=103.5)], 700)
    assert [r['event_sample'] for r in trials] == [100, 102, 102]
    assert [r['epoch_status'] for r in trials] == ['ok', 'duplicate_target_sample', 'duplicate_target_sample']


def test_boundary_ceil_dedup_and_epoch_rejection_precedence():
    events = [dict(type=1, latency=1), dict(type=2, latency=1),
              dict(type=3, latency=201), dict(type=41, latency=201),
              dict(type=4, latency=301), dict(type=42, latency=401),
              dict(type=-99, latency=250.5, duration=float('nan')),
              dict(type='boundary', latency=250.5), dict(type=-99, latency=.5),
              dict(type=-99, latency=700.5)]
    annotations, trials, segments, boundaries, cuts = sr.annotate_events('2', events, 700)
    assert cuts == [0, 250, 700] and segments == [(0, 250), (250, 700)]
    assert boundaries == [6, 7, 8, 9]
    assert [r['epoch_status'] for r in trials] == ['out_of_bounds', 'out_of_bounds',
        'duplicate_target_sample', 'duplicate_target_sample', 'crosses_boundary', 'ok']
    assert json.loads(annotations[6]['duration_json']) == {'__nonfinite__': 'NaN'}


@pytest.mark.parametrize('typ', [1, 41, -99, 'boundary'])
@pytest.mark.parametrize('latency', [None, '150', True, float('nan'), float('inf')])
def test_bad_target_or_boundary_latencies_fail(typ, latency):
    with pytest.raises(ValueError, match='target_or_boundary_latency'):
        sr.annotate_events('2', [dict(type=typ, latency=latency)], 700)


def test_unknown_events_and_nonfinite_documentary_values_are_preserved():
    events = [dict(type='BAD_note', latency=float('nan'), duration=float('inf'), urevent=-float('inf')),
              dict(type=float('nan'), latency=5)]
    annotations, trials, segments, _, _ = sr.annotate_events('2', events, 700)
    assert len(annotations) == 2 and trials == [] and segments == [(0,700)]
    assert json.loads(annotations[0]['latency_json']) == {'__nonfinite__': 'NaN'}
    assert json.loads(annotations[0]['duration_json']) == {'__nonfinite__': 'Infinity'}
    assert json.loads(annotations[0]['urevent_json']) == {'__nonfinite__': '-Infinity'}
    assert annotations[1]['normalized_event_code'] is None


def test_epoch_endpoint_ownership_at_half_open_segment_cuts():
    events = [dict(type=-99,latency=250.5), dict(type=1,latency=148),
              dict(type=2,latency=149), dict(type=41,latency=302)]
    _, trials, _, _, _ = sr.annotate_events('2', events, 700)
    assert [r['epoch_status'] for r in trials] == ['ok', 'crosses_boundary', 'ok']
    assert trials[0]['epoch_last_sample'] == 249
    assert trials[1]['epoch_last_sample'] == 250
    assert trials[2]['epoch_first_sample'] == 250


def test_fdt_little_endian_channel_fastest_layout_without_numpy_writer():
    raw = b''.join(struct.pack('<f', channel*10+time) for time in range(4) for channel in range(33))
    fake = IdentityFIR()
    sr.process_person(raw, arithmetic_header([], pnts=4), fake)
    expected = np.array([[channel*10-145.] * 4 for channel in range(30)])
    np.testing.assert_array_equal(fake.segments[0], expected)


def test_full_reconstruction_missing_condition_remains_flagged_zero(tmp_path, monkeypatch):
    bundle = make_bundle(tmp_path, monkeypatch, events={
        '2':[dict(type=1,latency=151)], '3':[dict(type='other',latency=float('nan'))]})
    result = run(bundle)
    assert result['condition_defined'].tolist() == [[True,False],[False,False]]
    assert np.count_nonzero(result['evoked_po8_uv'][0,1]) == 0
    assert np.count_nonzero(result['evoked_po8_uv'][1]) == 0
    assert len(result['annotations']) == 2 and len(result['trials']) == 1


def test_reference_decoder_baseline_and_epoch_order_are_explicit():
    events = [dict(type=1, latency=401), dict(type=2, latency=101), dict(type=41, latency=550)]
    header = arithmetic_header(events)
    data = np.tile(np.arange(700, dtype=np.float32), (33, 1))
    data[27] += 0.25 * np.arange(700, dtype=np.float32)
    data[30:] = float('nan')  # excluded EOG cannot create a hidden gate
    original = fdt_bytes(data); fake = IdentityFIR()
    result = sr.process_person(original, header, fake)
    scalp = np.asarray(data[:30], dtype=np.float64)
    expected = scalp - np.mean(scalp, axis=0, keepdims=True)
    np.testing.assert_array_equal(fake.segments[0], expected)
    assert result['epoch_keys'] == [('2',0), ('2',1), ('2',2)]
    corrected = []
    for sample in (400,100):
        po8 = expected[27, sample-51:sample+103]
        corrected.append(po8 - np.mean(po8[:52]))
    np.testing.assert_allclose(result['evoked_po8_uv'][0], np.mean(np.stack(corrected), axis=0), atol=0, rtol=0)
    assert result['condition_defined'].tolist() == [True,True]
    assert fdt_bytes(data) == original


@pytest.mark.parametrize('amplitude,accepted', [(150., True), (150.0001, False)])
def test_ptp_threshold_equality_and_artifact_receipt_retention(amplitude, accepted):
    data = np.zeros((33,700), dtype=np.float32)
    data[27,150] = amplitude; data[0,150] = -amplitude
    result = sr.process_person(fdt_bytes(data), arithmetic_header([dict(type=1,latency=151)]), IdentityFIR())
    assert result['trials'][0]['accepted'] is accepted
    assert result['trials'][0]['rejection_reason'] == ('accepted' if accepted else 'peak_to_peak')
    assert result['epoch_peak_to_peak_uv'].shape == (1,30)
    assert result['epoch_po8_baseline_uv'].shape == (1,)
    assert result['condition_defined'].tolist() == [accepted,False]
    if not accepted: assert np.count_nonzero(result['evoked_po8_uv']) == 0


@pytest.mark.parametrize('position', [(0,0), (27,699), (29,301)])
def test_all_continuous_contributing_samples_finite_even_outside_epochs(position):
    data = np.zeros((33,700), dtype=np.float32); data[position] = np.nan
    with pytest.raises(ValueError, match='nonfinite_contributing_channel'):
        sr.process_person(fdt_bytes(data), arithmetic_header([dict(type=1,latency=151)]), IdentityFIR())


def test_zero_eligible_epochs_keep_empty_receipts_and_missing_conditions():
    result = sr.process_person(fdt_bytes(np.zeros((33,700))),
        arithmetic_header([dict(type=1,latency=1),dict(type=41,latency=700)]), IdentityFIR())
    assert result['epoch_keys'] == []
    assert result['epoch_peak_to_peak_uv'].shape == (0,30)
    assert result['epoch_po8_baseline_uv'].shape == (0,)
    assert result['condition_defined'].tolist() == [False,False]
    assert np.count_nonzero(result['evoked_po8_uv']) == 0


def test_channel_permutation_preserves_literal_label_extraction():
    data = np.zeros((33,700), dtype=np.float32); data[27] = np.arange(700) / 100.
    event = [dict(type=1,latency=151)]
    original = sr.process_person(fdt_bytes(data), arithmetic_header(event), IdentityFIR())
    permutation = np.arange(33)[::-1]
    labels = [list(sr.SCALP + sr.EOG)[i] for i in permutation]
    changed = sr.process_person(fdt_bytes(data[permutation]), arithmetic_header(event, labels=labels), IdentityFIR())
    np.testing.assert_array_equal(changed['evoked_po8_uv'], original['evoked_po8_uv'])
    np.testing.assert_array_equal(changed['epoch_peak_to_peak_uv'], original['epoch_peak_to_peak_uv'])


def test_boundary_segments_each_filtered_without_dropping_short_intervals():
    header = arithmetic_header([dict(type=-99,latency=2),dict(type=-99,latency=5)])
    fake = IdentityFIR()
    sr.process_person(fdt_bytes(np.zeros((33,700))), header, fake)
    assert [x.shape for x in fake.segments] == [(30,1),(30,3),(30,696)]


@pytest.mark.parametrize('overrides,inline,error', [
    ({'srate':128},False,'header_srate'), ({'nbchan':32},False,'header_nbchan'),
    ({'trials':2},False,'header_trials'), ({'xmin':-1},False,'header_xmin'),
    ({'ref':'average'},False,'reference_token'), ({'units':'uV'},False,'unit_field'),
    ({'icaweights':np.ones((1,1))},False,'source_ica'),
    ({'data':'other.fdt'},False,'fdt_pointer'), ({},True,'external_fdt_required'),
])
def test_header_preconditions_and_inline_data_stop_before_signal_decode(overrides, inline, error):
    scanner = sr._bound_module('mat_metadata.py', sr.SCANNER_SHA)
    raw = set_bytes('2',700,[dict(type=1,latency=151)],overrides=overrides,inline=inline)
    with pytest.raises(ValueError, match=error):
        sr.parse_header(raw,'2',{'path':'2_N170_shifted_ds.set'},
                        {'path':'2_N170_shifted_ds.fdt','size_bytes':33*700*4},scanner)


def test_mat_scanner_never_decodes_times_or_ica_arrays():
    scanner = sr._bound_module('mat_metadata.py', sr.SCANNER_SHA)
    seen = []
    parent = scanner.MatScan
    class RecordingScan(parent):
        def fields(self):
            fields, layout = super().fields()
            self.names = {id(v):k for k,v in fields.items()}; return fields, layout
        def decode(self,node):
            name = self.names[id(node)]; seen.append(name)
            assert name not in {'times', 'icaweights', 'icasphere'}
            return super().decode(node)
    scanner.MatScan = RecordingScan
    sr.parse_header(set_bytes('2',700,[dict(type=1,latency=151)]),'2',
        {'path':'2_N170_shifted_ds.set'}, {'path':'2_N170_shifted_ds.fdt','size_bytes':33*700*4}, scanner)
    assert seen[0] == 'data' and {'chanlocs','event'} <= set(seen)
