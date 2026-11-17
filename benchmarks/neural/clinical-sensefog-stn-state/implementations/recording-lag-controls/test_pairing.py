"""Invented SenseFOG geometry only; imports no signal/native/model library."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import resource
import sys
import tempfile
import time
import unittest

S = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sensefog_pairing', S / 'sensefog_pairing.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixture():
    people = ['p%02d' % i for i in range(12)]
    value = {'schema': mod.SCHEMA, 'task': mod.TASK, 'participants': people,
            'folds': [{'heldout_person': p, 'training_people': [v for v in people if v != p],
                       'lookback_samples_by_rate': {'1': 2},
                       'dependence_samples_by_rate': {'1': 3},
                       'method_receipt_sha256': 'a' * 64} for p in people],
            'segments': [{'segment_id': p + '_seg', 'participant': p,
                          'recording_id': p + '_record', 'day_id': 'day', 'session_id': p + '_session',
                          'acquisition_stratum': 'invented_constant_stratum',
                          'sample_rate_hz': 1, 'sample_count': 1000, 'channels': ['chA', 'chB'],
                          'masks': {c: [[0, 1000, False, False]] for c in ['chA', 'chB']},
                          'window_stride_samples': 100, 'window_origin_sample': 0,
                          'cases': [{'case_id': p + '_case_%d' % i, 'start_sample': i}
                                    for i in range(0, 999, 100)]} for p in people]}

    value['recordings'] = []
    for seg in value['segments']:
        fields = ('recording_id', 'participant', 'day_id', 'session_id', 'sample_rate_hz', 'sample_count',
                  'window_stride_samples', 'window_origin_sample', 'cases')
        value['recordings'].append({k: copy.deepcopy(seg[k]) for k in fields})
        for k in fields:
            if k not in ('recording_id', 'sample_count'):
                del seg[k]
        seg['recording_start_sample'] = 0
    return value



def run(value):
    return mod.build_maps(value, max_cases=1000)


class PairingChecks(unittest.TestCase):
    def test_full_twelve_people_twenty_fixed_maps(self):
        d = fixture(); out = run(d)
        self.assertEqual(out['original_case_count'], 120)
        self.assertEqual(len(out['maps']), 2400)
        self.assertEqual(len(out['participants']), 12)
        self.assertEqual(out['multipliers'], list(mod.MULTIPLIERS))
        self.assertEqual(len(set(out['original_case_ids'])), 120)
        self.assertIsNone(out['primary_score'])
        for row in out['maps']:
            self.assertEqual(row['lag_samples'], row['multiple'] * 30)
            self.assertEqual(row['donor_core'][0] - row['recipient_core'][0], row['lag_samples'])
            self.assertEqual(row['donor_core'][1] - row['recipient_core'][1], row['lag_samples'])

    def test_nonwrapping_boundaries_and_consistent_shared_lag(self):
        out = run(fixture())
        rows = {(r['case_id'], r['multiple']): r for r in out['maps']}
        self.assertEqual(rows['p00_case_0', -1]['reason'], 'donor_support_outside_segment')
        self.assertEqual(rows['p00_case_0', 1]['status'], 'supported')
        self.assertEqual(rows['p00_case_900', 10]['status'], 'unsupported')
        self.assertEqual(rows['p00_case_500', 10]['status'], 'supported')
        self.assertEqual(rows['p00_case_500', -10]['status'], 'supported')

    def test_exact_all_channel_mask_match_and_rle_normalization(self):
        d = fixture()
        d['segments'][0]['masks']['chB'] = [[0, 30, False, False], [30, 32, False, True],
                                          [32, 1000, False, False]]
        rows = {(r['case_id'], r['multiple']): r for r in run(d)['maps']}
        self.assertEqual(rows['p00_case_0', 1]['reason'], 'full_support_channel_mask_mismatch')
        self.assertEqual(rows['p00_case_100', 1]['status'], 'supported')
        d = fixture(); d['segments'][0]['masks']['chA'] = [[0, 1, False, False], [1, 1000, False, False]]
        self.assertEqual(run(d), run(fixture()))

    def test_complete_lookback_not_only_two_second_core(self):
        d = fixture(); d['folds'][0]['lookback_samples_by_rate']['1'] = 40
        d['segments'][0]['masks']['chB'] = [[0, 165, False, False], [165, 166, True, False],
                                          [166, 1000, False, False]]
        out = run(d); rows = {(r['case_id'], r['multiple']): r for r in out['maps']}
        self.assertEqual(rows['p00_case_0', 1]['reason'], 'recipient_history_outside_segment')
        self.assertEqual(rows['p00_case_100', 1]['lag_samples'], 80)
        self.assertEqual(rows['p00_case_100', 1]['reason'], 'full_support_channel_mask_mismatch')
        self.assertEqual(out['original_case_count'], 120)

    def test_unestablished_dependence_retains_every_case(self):
        d = fixture(); d['folds'][0]['dependence_samples_by_rate']['1'] = None
        out = run(d); rows = [r for r in out['maps'] if r['participant'] == 'p00']
        self.assertEqual(len(rows), 200)
        self.assertTrue(all(r['reason'] == 'unestablished_lookback_or_training_dependence' for r in rows))
        self.assertEqual(out['original_case_count'], 120)

    def test_gap_all_three_constraints_and_no_selected_lags(self):
        d = fixture(); d['folds'][0]['lookback_samples_by_rate']['1'] = 40
        d['folds'][0]['dependence_samples_by_rate']['1'] = 95
        out = run(d)
        self.assertTrue(all(r['lag_samples'] == r['multiple'] * 95 for r in out['maps'] if r['participant'] == 'p00'))
        d['folds'][0]['selected_lags'] = [95]
        with self.assertRaises(ValueError): run(d)

    def test_no_held_person_in_training_and_all_folds_required(self):
        d = fixture(); d['folds'][0]['training_people'][0] = 'p00'
        with self.assertRaises(ValueError): run(d)
        d = fixture(); d['folds'].pop()
        with self.assertRaises(ValueError): run(d)
        d = fixture(); d['participants'].pop()
        with self.assertRaises(ValueError): run(d)

    def test_full_case_grid_duplicates_and_target_fields_rejected(self):
        for change in ('missing', 'duplicate', 'order', 'target', 'offset'):
            d = fixture(); cases = d['recordings'][0]['cases']
            if change == 'missing': cases.pop()
            if change == 'duplicate': cases[1]['case_id'] = cases[0]['case_id']
            if change == 'order': cases[0], cases[1] = cases[1], cases[0]
            if change == 'target': cases[0]['target'] = 'freezing'
            if change == 'offset': cases[1]['start_sample'] += 1
            with self.subTest(change=change), self.assertRaises(ValueError): run(d)

    def test_mask_completeness_and_bool_types(self):
        for spans in ([[1, 1000, False, False]], [[0, 900, False, False]],
                      [[0, 600, False, False], [500, 1000, False, False]],
                      [[0, 1000, 0, False]]):
            d = fixture(); d['segments'][0]['masks']['chA'] = spans
            with self.subTest(spans=spans), self.assertRaises(ValueError): run(d)
        d = fixture(); del d['segments'][0]['masks']['chB']
        with self.assertRaises(ValueError): run(d)

    def test_recording_group_and_channel_specific_shift_refused(self):
        d = fixture(); d['segments'][1]['recording_id'] = 'p00_record'
        with self.assertRaises(ValueError): run(d)
        d = fixture(); d['segments'][0]['channel_lags'] = {'chA': 30, 'chB': 60}
        with self.assertRaises(ValueError): run(d)

    def test_native_sampling_stratum_and_all_channels(self):
        d = fixture(); seg = d['segments'][0]
        d['recordings'][0]['sample_rate_hz'] = 2; seg['channels'].append('chC')
        seg['masks']['chC'] = [[0, 1000, False, False]]
        d['folds'][0]['lookback_samples_by_rate'] = {'2': 4}
        d['folds'][0]['dependence_samples_by_rate'] = {'2': 7}
        out = run(d); row = next(r for r in out['maps'] if r['case_id'] == 'p00_case_100' and r['multiple'] == 1)
        self.assertEqual(row['recipient_core'], [100, 104]); self.assertEqual(row['lag_samples'], 60)
        self.assertEqual(out['segments'][0]['channels'], ['chA', 'chB', 'chC'])

    def test_empty_participant_kept_without_fabricated_cases(self):
        d = fixture(); rec = d['recordings'][0]; rec['sample_count'] = 0; rec['cases'] = []
        d['segments'].pop(0)
        out = run(d)
        self.assertEqual(len(out['participants']), 12)
        self.assertEqual(out['original_case_count'], 110)
        self.assertTrue(all(v['counts'] == {} for v in out['participants'][0]['transforms']))

    def test_real_cli_hash_fresh_output_and_caps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); inp = root / 'input.json'; out = root / 'output.json'
            raw = json.dumps(fixture()).encode(); inp.write_bytes(raw)
            argv = ['--input', str(inp), '--output', str(out), '--expected-input-sha256', hashlib.sha256(raw).hexdigest(),
                    '--max-input-bytes', str(len(raw)), '--max-output-bytes', '2000000', '--max-cases', '120']
            mod.main(argv); result = json.loads(out.read_bytes())
            self.assertEqual(result['original_case_count'], 120)
            self.assertEqual(result['input_sha256'], hashlib.sha256(raw).hexdigest())
            with self.assertRaises(FileExistsError): mod.main(argv)
            bad = argv[:]; bad[-1] = '119'
            with self.assertRaises(ValueError): mod.main(bad)
            bad = argv[:]; bad[5] = 'b' * 64
            with self.assertRaises(ValueError): mod.main(bad)
            bad = argv[:]; bad[9] = '1'
            with self.assertRaises(ValueError): mod.main(bad)
            with self.assertRaises(ValueError): json.loads('{"x":1,"x":2}', object_pairs_hook=mod.strict_object)

    def test_requested_shifts_are_not_counted_as_supported_when_unavailable(self):
        d = fixture()
        for fold in d['folds']:
            fold['dependence_samples_by_rate']['1'] = None
        out = run(d)
        self.assertEqual(out['requested_transform_count'], 20)
        self.assertEqual(out['distinct_supported_transform_count'], 0)
        self.assertEqual(len(out['maps']), 2400)
        self.assertTrue(all(row['supported_cases'] == 0 for row in out['transform_coverage']))
        self.assertEqual(run(fixture())['distinct_supported_transform_count'], 20)


    def test_recording_boundary_census_never_reanchors_or_drops_windows(self):
        d = fixture()
        d['segments'] = []
        for rec in d['recordings']:
            rid = rec['recording_id']; rec['sample_count'] = 10
            rec['window_stride_samples'] = 1
            rec['cases'] = [{'case_id': rid + '_case_%d' % k, 'start_sample': k} for k in range(9)]
            for offset in (0, 5):
                d['segments'].append({'segment_id': rid + '_seg_%d' % offset, 'recording_id': rid,
                    'acquisition_stratum': 'regime_%d' % offset, 'recording_start_sample': offset,
                    'sample_count': 5, 'channels': ['chA'], 'masks': {'chA': [[0,5,False,False]]}})
        out = run(d)
        self.assertEqual(out['original_case_count'], 108)
        self.assertEqual(len(out['maps']), 2160)
        crossing = [r for r in out['maps'] if r['recipient_core'] == [4,6]]
        self.assertEqual(len(crossing), 240)
        self.assertTrue(all(r['reason'] == 'recipient_core_crosses_gap_or_acquisition_boundary' for r in crossing))
        self.assertTrue(all(r['segment_id'] is None for r in crossing))
        for seg in d['segments']:
            if seg['recording_start_sample'] == 5:
                seg['recording_start_sample'] = 6
            seg['sample_count'] = 4
            seg['masks'] = {'chA': [[0,4,False,False]]}
        gap_out = run(d)
        self.assertEqual(gap_out['original_case_count'], 108)
        gap_rows = [r for r in gap_out['maps'] if r['recipient_core'][0] in (3,4,5)]
        self.assertEqual(len(gap_rows), 720)
        self.assertTrue(all(r['reason'] == 'recipient_core_crosses_gap_or_acquisition_boundary' for r in gap_rows))

    def test_missing_recording_kept_when_person_has_another_recording(self):
        d = fixture(); rec = copy.deepcopy(d['recordings'][0]); rec['recording_id'] = 'p00_missing'
        rec['cases'] = [{'case_id': c['case_id'] + '_missing', 'start_sample': c['start_sample']} for c in rec['cases']]
        d['recordings'].append(rec)
        out = run(d); missing = [r for r in out['maps'] if r['recording_id'] == 'p00_missing']
        self.assertEqual(out['original_case_count'], 130)
        self.assertEqual(len(missing), 200)
        self.assertTrue(all(r['reason'] == 'recording_has_no_observed_segment' for r in missing))
        self.assertEqual(len(out['participants']), 12)

    def test_recording_origin_and_segment_offsets_keep_absolute_grid(self):
        d = fixture(); rec = d['recordings'][0]; rec['window_origin_sample'] = 7
        rec['cases'] = [{'case_id': 'origin_%d' % k, 'start_sample': k} for k in range(7,999,100)]
        seg = d['segments'][0]; seg['recording_start_sample'] = 105; seg['sample_count'] = 895
        seg['masks'] = {c:[[0,895,False,False]] for c in seg['channels']}
        out = run(d); rows = {(r['case_id'],r['multiple']):r for r in out['maps']}
        self.assertEqual(rows['origin_107',1]['recipient_core'], [107,109])
        self.assertEqual(rows['origin_107',1]['donor_core'], [137,139])
        self.assertEqual(rows['origin_7',1]['reason'], 'recipient_core_crosses_gap_or_acquisition_boundary')
        bad = copy.deepcopy(d); bad['segments'].append(copy.deepcopy(seg)); bad['segments'][-1]['segment_id']='overlap'
        with self.assertRaises(ValueError): run(bad)


if __name__ == '__main__':
    dest = Path(sys.argv[1]); dest.mkdir(parents=True, exist_ok=False)
    begin = time.monotonic(); start_cpu = time.process_time(); stream = io.StringIO()
    outcome = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PairingChecks))
    log = stream.getvalue(); (dest / 'TEST_LOG.txt').write_text(log)
    receipt = {'tests': outcome.testsRun, 'failures': len(outcome.failures), 'errors': len(outcome.errors),
               'invented_only': True, 'native_imports': False,
               'CPU_seconds': time.process_time() - start_cpu, 'wall_seconds': time.monotonic() - begin,
               'peak_RSS_Darwin_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (dest / 'RESULT.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(log); print(json.dumps(receipt)); sys.exit(0 if outcome.wasSuccessful() else 1)
