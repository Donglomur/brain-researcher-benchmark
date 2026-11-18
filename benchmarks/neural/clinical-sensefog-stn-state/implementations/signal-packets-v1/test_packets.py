"""Generated checks only; 2-Hz fixtures are not the clinical sampling rate."""
import copy
import importlib.util
import math
from pathlib import Path
import unittest

_spec = importlib.util.spec_from_file_location('sensefog_packets', Path(__file__).with_name('sensefog_packets.py'))
p = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(p)


def fixture(*, h=6, origin=80, length=200, stride=240):
    people = ['p%d' % i for i in range(12)]
    grid = {'schema': 'sensefog_target_free_pairing_input_v2', 'task': p.TASK,
            'participants': people, 'folds': [], 'recordings': [], 'segments': []}
    for index, person in enumerate(people):
        grid['folds'].append({'heldout_person': person,
            'training_people': [x for x in people if x != person],
            'lookback_samples_by_rate': {'2': h}, 'dependence_samples_by_rate': {'2': 20},
            'method_receipt_sha256': 'a' * 64})
        grid['recordings'].append({'recording_id': 'r%d' % index, 'participant': person,
            'day_id': 'd%d' % index, 'session_id': 't%d' % index,
            'sample_rate_hz': 2, 'sample_count': length,
            'window_stride_samples': stride, 'window_origin_sample': origin,
            'cases': [{'case_id': 'q%d' % index, 'start_sample': origin}]})
        grid['segments'].append({'segment_id': 's%d' % index, 'recording_id': 'r%d' % index,
            'acquisition_stratum': 'a%d' % index, 'recording_start_sample': 0,
            'sample_count': length, 'channels': ['L02', 'R13', 'L13'],
            'masks': {c: [[0, length, False, False]] for c in ['L02', 'R13', 'L13']}})
    metadata = {'schema': 'sensefog_signal_metadata_v1', 'task': p.TASK,
                'grid_sha256': p.canonical_sha256(grid), 'segments': []}
    for seg in grid['segments']:
        metadata['segments'].append({'segment_id': seg['segment_id'],
            'signal_sha256': 'b' * 64, 'calibration_receipt_sha256': 'c' * 64,
            'channels': [{'channel_id': cid, 'hemisphere': side, 'physical_unit': 'uV',
                          'montage': 'bipolar_' + cid}
                         for cid, side in zip(seg['channels'], ('left', 'right', 'left'))]})
    aliases = {'q%d' % i: '%032x' % (i + 1) for i in range(12)}
    return grid, metadata, aliases


def reader_for(grid):
    segments = {s['segment_id']: s for s in grid['segments']}
    calls = []
    def read(sid, channels, start, end):
        calls.append((sid, channels, start, end))
        seg = segments[sid]
        result = []
        for index, cid in enumerate(channels):
            vector = []
            for t in range(start, end):
                missing = next(m for a, b, m, _ in seg['masks'][cid] if a <= t < b)
                vector.append(None if missing else int(sid[1:]) * 10000 + index * 1000 + t)
            result.append(vector)
        return result
    return read, calls


def run(grid, meta, aliases, reader, **bounds):
    settings = {'max_cases': 12, 'max_packet_values': 100, 'max_total_values': 5000,
                'max_output_bytes': 1000000}
    settings.update(bounds)
    return p.project_packets(grid, meta, aliases, reader, **settings)


def row(result, *, cid='q0', role='original_core', multiple=None):
    return next(r for r in result['private_manifest'] if r['case_id'] == cid and
                r['role'] == role and r['multiple'] == multiple)


def packet(result, **kwargs):
    return result['packets'][row(result, **kwargs)['packet_sha256']]


class ProjectionChecks(unittest.TestCase):
    def test_full_census_and_exact_common_channel_lags(self):
        g, m, a = fixture()
        read, calls = reader_for(g)
        r = run(g, m, a, read)
        self.assertEqual(r['original_case_count'], 12)
        self.assertEqual(len(r['private_manifest']), 12 * 22)
        self.assertEqual(r['requested_lag_count'], 20)
        self.assertEqual(len(calls), 48)
        self.assertEqual(r['source_values_requested'], 12 * (4 * 3 + 3 * 6 * 3))
        self.assertEqual(len(calls), len(set(calls)))
        x = packet(r, role='lag_authorized_support', multiple=1)
        self.assertEqual(x['relative_sample_start'], -2)
        self.assertEqual(x['core_sample_interval'], [2, 6])
        self.assertEqual(x['channels'][0]['values'], list(range(138, 144)))
        self.assertEqual(x['channels'][1]['values'], list(range(1138, 1144)))
        self.assertEqual(x['channels'][2]['values'], list(range(2138, 2144)))
        self.assertEqual(row(r, role='lag_authorized_support', multiple=2)['status'], 'unavailable')
        self.assertEqual(row(r, role='lag_authorized_support', multiple=2)['reason'], 'donor_support_outside_segment')
        self.assertFalse(r['readiness'])

    def test_public_packet_excludes_donor_timing_and_private_labels(self):
        g, m, a = fixture()
        r = run(g, m, a, reader_for(g)[0])
        x = packet(r)
        self.assertEqual(set(x), {'schema', 'case_token', 'sample_rate_hz', 'relative_sample_start',
                                  'core_sample_interval', 'channels'})
        self.assertEqual(set(x['channels'][0]), {'channel_token', 'hemisphere', 'physical_unit',
                                                'montage', 'values', 'missing', 'artifact'})
        for forbidden in ['participant', 'recording_id', 'segment_id', 'multiple', 'lag_samples',
                          'source_signal_sha256', 'case_id', 'day_id', 'session_id', 'label']:
            self.assertNotIn('"' + forbidden + '"', p.canonical_bytes(x).decode())
        self.assertEqual(x['channels'][0]['physical_unit'], 'uV')
        self.assertEqual(x['channels'][0]['montage'], 'bipolar_L02')

    def test_missing_history_keeps_complete_original_core(self):
        g, m, a = fixture(h=None)
        read, calls = reader_for(g)
        r = run(g, m, a, read)
        self.assertEqual(len(calls), 12)
        self.assertEqual(packet(r)['channels'][0]['values'], [80, 81, 82, 83])
        self.assertEqual(row(r, role='original_authorized_support')['reason'], 'unestablished_lookback')
        self.assertEqual(sum(x['status'] == 'unavailable' for x in r['private_manifest']), 12 * 21)

    def test_boundary_history_does_not_drop_original_core(self):
        g, m, a = fixture(origin=0)
        read, calls = reader_for(g)
        r = run(g, m, a, read)
        self.assertEqual(len(calls), 12)
        self.assertEqual(packet(r)['channels'][0]['values'], [0, 1, 2, 3])
        self.assertEqual(row(r, role='original_authorized_support')['reason'], 'recipient_history_outside_segment')

    def test_no_gap_stitching_or_recording_omission(self):
        g, m, a = fixture()
        for s in g['segments']:
            s['recording_start_sample'] = 100
            s['sample_count'] = 100
            s['masks'] = {c: [[0, 100, False, False]] for c in s['channels']}
        m['grid_sha256'] = p.canonical_sha256(g)
        read, calls = reader_for(g)
        r = run(g, m, a, read)
        self.assertFalse(calls)
        self.assertFalse(r['packets'])
        self.assertEqual(len(r['private_manifest']), 264)
        self.assertEqual(row(r)['reason'], 'recipient_core_crosses_gap_or_acquisition_boundary')

    def test_full_missing_artifact_masks_and_all_three_channels(self):
        g, m, a = fixture()
        for s in g['segments']:
            s['masks']['L02'] = [[0, 200, True, False]]
            s['masks']['R13'] = [[0, 200, False, True]]
        m['grid_sha256'] = p.canonical_sha256(g)
        r = run(g, m, a, reader_for(g)[0])
        x = packet(r, role='lag_authorized_support', multiple=-1)
        self.assertEqual(len(x['channels']), 3)
        self.assertEqual(x['channels'][0]['values'], [None] * 6)
        self.assertEqual(x['channels'][0]['missing'], [True] * 6)
        self.assertEqual(x['channels'][1]['artifact'], [True] * 6)
        self.assertEqual(x['channels'][1]['values'], list(range(1018, 1024)))

    def test_mask_mismatch_refuses_donor_without_reader_fallback(self):
        g, m, a = fixture()
        g['segments'][0]['masks']['L02'] = [[0, 138, False, False], [138, 144, False, True], [144, 200, False, False]]
        m['grid_sha256'] = p.canonical_sha256(g)
        read, calls = reader_for(g)
        r = run(g, m, a, read)
        x = row(r, role='lag_authorized_support', multiple=1)
        self.assertEqual(x['reason'], 'full_support_channel_mask_mismatch')
        self.assertIsNone(x['packet_sha256'])
        self.assertFalse(any(sid == 's0' and start == 138 for sid, _, start, _ in calls))

    def test_complete_alias_and_channel_metadata(self):
        for mutate in (
            lambda g, m, a: a.pop('q0'),
            lambda g, m, a: a.update(q0=a['q1']),
            lambda g, m, a: m['segments'][0]['channels'].reverse(),
            lambda g, m, a: m['segments'].pop(),
            lambda g, m, a: m['segments'][0]['channels'][1].update(hemisphere='left'),
            lambda g, m, a: m['segments'][0]['channels'][0].update(physical_unit='arbitrary'),
            lambda g, m, a: m.update(grid_sha256='0' * 64),
        ):
            g, m, a = fixture(); mutate(g, m, a)
            read, calls = reader_for(g)
            with self.assertRaises(ValueError): run(g, m, a, read)
            self.assertFalse(calls)

    def test_strict_target_barrier_in_operator_declarations(self):
        for target in ('grid', 'metadata', 'channel'):
            g, m, a = fixture()
            obj = g if target == 'grid' else m if target == 'metadata' else m['segments'][0]['channels'][0]
            obj['clinical_state'] = 'freezing'
            read, calls = reader_for(g)
            with self.assertRaises(ValueError): run(g, m, a, read)
            self.assertFalse(calls)

    def test_reader_shape_nonfinite_and_missing_null_contract(self):
        for mutate in (lambda x: x.pop(), lambda x: x[0].pop(),
                       lambda x: x[0].__setitem__(0, math.nan),
                       lambda x: x[0].__setitem__(0, True),
                       lambda x: x[0].__setitem__(0, None)):
            g, m, a = fixture(); good, calls = reader_for(g)
            def bad(*args):
                x = good(*args); mutate(x); return x
            with self.assertRaises(ValueError): run(g, m, a, bad)
            self.assertEqual(len(calls), 1)

    def test_reader_exception_propagates_once(self):
        g, m, a = fixture(); calls = []
        def bad(*args):
            calls.append(args)
            raise RuntimeError('source read failed')
        with self.assertRaisesRegex(RuntimeError, 'source read failed'): run(g, m, a, bad)
        self.assertEqual(len(calls), 1)

    def test_whole_operation_caps_never_truncate_population(self):
        for cap in ({'max_cases': 11}, {'max_packet_values': 1}, {'max_total_values': 1}):
            g, m, a = fixture(); read, calls = reader_for(g)
            with self.assertRaises(ValueError): run(g, m, a, read, **cap)
            self.assertFalse(calls)
        g, m, a = fixture(); read, calls = reader_for(g)
        with self.assertRaisesRegex(ValueError, 'whole output'): run(g, m, a, read, max_output_bytes=1)
        self.assertEqual(len(calls), 48)

    def test_declarations_and_retained_callback_buffers_are_frozen(self):
        g, m, a = fixture(); original = copy.deepcopy((g, m, a))
        good, calls = reader_for(g); previous = []
        def mutate(*args):
            if previous:
                previous[0][0][0] = -999999
            values = good(*args)
            previous[:] = [values]
            g['folds'][0]['lookback_samples_by_rate']['2'] = None
            m['segments'][0]['channels'][0]['physical_unit'] = 'V'
            a['q0'] = 'f' * 32
            return values
        r = run(g, m, a, mutate)
        self.assertEqual(r['grid_sha256'], p.canonical_sha256(original[0]))
        self.assertEqual(r['signal_metadata_sha256'], p.canonical_sha256(original[1]))
        self.assertEqual(r['private_aliases_sha256'], p.canonical_sha256(original[2]))
        self.assertEqual(packet(r)['channels'][0]['values'], [80, 81, 82, 83])
        self.assertEqual(packet(r)['channels'][0]['physical_unit'], 'uV')

    def test_absent_recordings_stay_accounted(self):
        g, m, a = fixture(); g['segments'] = []; m['segments'] = []
        m['grid_sha256'] = p.canonical_sha256(g)
        read, calls = reader_for(g)
        r = run(g, m, a, read)
        self.assertEqual(len(r['private_manifest']), 264)
        self.assertFalse(r['packets']); self.assertFalse(calls)
        self.assertEqual(row(r)['reason'], 'recording_has_no_observed_segment')


if __name__ == '__main__':
    unittest.main(verbosity=2)
