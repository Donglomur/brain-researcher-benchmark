"""New generated join controls only; no authentic data, producer runs or fits."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
PINS = {
    'whole-trial-preparation/trial_preparation.py': 'c11d1afeb8a32a8d0984c656ffb5e98b092dc4a3bf60a7c0b9af566bb9f02a5e',
    'whole-trial-inference-v1/trial_inference.py': '83e84c35c6c1fb8d2bbb8f87ef04f692417c36da8d3ce76e0faf7823aaad931d',
    'endpoint-kernels/endpoint_kernels.py': 'aa827fbb110bdee9cde70e19706ca7bf9fcbca440851dd6643437b9cb2897fc7',
}
for relative, expected in PINS.items():
    dependency = HERE.parent / relative
    if hashlib.sha256(dependency.read_bytes()).hexdigest() != expected:
        raise RuntimeError('reviewed dependency hash mismatch: ' + relative)
    sys.path.insert(0, str(dependency.parent))
sys.path.insert(0, str(HERE))
import paired_scoring as api


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def stream(records):
    return b''.join(encode(r) for r in records)


def field(index, method):
    def pixel(p):
        truth = index + p % 3
        if method == 'candidate':
            return truth + (index + 1) * (p % 5 + 1) / 2
        if method == 'comparator':
            return truth - (index + 1) * (p % 5 + 2)
        return truth
    return [[[pixel(r * 128 + c) for c in range(128)] for r in range(128)]]


def behavior(index, method):
    return [10 * index + c + ((index + 1) * (c + 1) / 4 if method == 'candidate' else
                              -(index + 1) * (c + 2) / 2 if method == 'comparator' else 0)
            for c in range(14)]


def metadata():
    census = {'schema': 'sbind-complete-widefield-census-v1', 'task_id': api.TASK, 'assays': []}
    split = {'schema': 'sbind-prospective-whole-trial-folds-v1', 'task_id': api.TASK,
             'census_sha256': None, 'assays': []}
    for name, count, width in (('WFCI1', 248, 14), ('WFCI2', 412, 4)):
        rows, start = [], 0
        for i in range(count):
            length = i + 2 if name == 'WFCI1' and i < 2 else 1
            rows.append({'trial_id': name + '-trial-' + str(i), 'source_start': start, 'length': length})
            start += length
        ids = [r['trial_id'] for r in rows]
        tests = [ids[:2], *[ids[2 + i::4] for i in range(4)]]
        folds = []
        for f, test in enumerate(tests):
            other = [x for x in ids if x not in test]
            folds.append({'fold': f, 'train': other[1:], 'validation': other[:1], 'test': test})
        census['assays'].append({'assay_id': name, 'source_sha256': 'a' * 64,
            'representation_sha256': 'b' * 64, 'neural_shape': [1, 128, 128],
            'behavior_channels': ['behavior-' + str(i) for i in range(width)], 'trials': rows})
        split['assays'].append({'assay_id': name, 'folds': folds})
    raw = encode(census)
    split['census_sha256'] = digest(raw)
    return raw, encode(split)


def fixture(role='test'):
    census, split = metadata()
    # Full metadata support is 245 train frames, one validation, five test.
    stats = {'policy': api.inference.POLICY, 'training_frames': 245,
             'neural_mean': [0] * 16384, 'neural_sd': 1,
             'behavior_mean': [0] * 14, 'behavior_sd': [1] * 14}
    common = {'schema': 'sbind-normalized-fold-stream-v1', 'task_id': api.TASK,
              'policy': api.inference.POLICY, 'assay_id': 'WFCI1', 'fold': 0,
              'census_sha256': digest(census), 'split_sha256': digest(split),
              'representations_sha256': 'c' * 64, 'normalization_sha256': digest(encode(stats)),
              'neural_shape': [1, 128, 128], 'behavior_channels': ['behavior-' + str(i) for i in range(14)],
              'model_call_policy': api.inference.CALL_POLICY}
    identities = {
        'test': [{'role': 'test', 'trial_id': 'WFCI1-trial-' + str(int(i >= 2)),
                  'source_index': i, 'trial_offset': i if i < 2 else i - 2} for i in range(5)],
        'validation': [{'role': 'validation', 'trial_id': 'WFCI1-trial-2',
                        'source_index': 5, 'trial_offset': 0}]}
    source_records = {r: [dict(common, role=r, record='header', includes_behavior=False)] +
        [dict(identity, record='frame', reset=identity['trial_offset'] == 0,
              neural=field(identity['source_index'], 'truth')) for identity in identities[r]]
        for r in ('validation', 'test')}
    target_records = [dict(common, role='owner-held-targets', record='header', includes_behavior=True)]
    for r in ('validation', 'test'):
        target_records.extend(dict(identity, record='target', reset=identity['trial_offset'] == 0,
                                   behavior=behavior(identity['source_index'], 'truth'))
                              for identity in identities[r])
    source_sha = digest(stream(source_records[role]))
    prediction_header = {'schema': 'sbind-prospective-wfci1-predictions-v1', 'task_id': api.TASK,
        'assay_id': 'WFCI1', 'fold': 0, 'role': role, 'input_sha256': source_sha,
        'census_sha256': digest(census), 'split_sha256': digest(split),
        'normalization_sha256': common['normalization_sha256'],
        'representations_sha256': 'c' * 64, 'behavior_channels': common['behavior_channels'],
        'model_call_policy': api.inference.CALL_POLICY, 'record': 'header',
        'historical_reproduction_qualified': False}
    predictions = {name: [dict(prediction_header)] +
        [dict(identity, record='prediction', neural=field(identity['source_index'], name),
              behavior=behavior(identity['source_index'], name)) for identity in identities[role]]
        for name in ('candidate', 'comparator')}
    return dict(census=census, split=split, stats=stats, common=common, role=role,
                source_records=source_records, target_records=target_records, predictions=predictions,
                receipt_changes={}, norm_changes={}, binding_changes={},
                mask={'schema': 'sbind-owner-brain-pixel-selection-v1', 'task_id': api.TASK,
                      'assay_id': 'WFCI1', 'source_sha256': 'a' * 64,
                      'representation_sha256': 'b' * 64, 'pixel_indices': [16383, 0, 131]})


def freeze(f):
    role = f['role']
    raw_sources = {r: stream(rows) for r, rows in f['source_records'].items()}
    raw_targets = stream(f['target_records'])
    def sr(raw, count):
        return {'bytes': len(raw), 'sha256': digest(raw), 'records': count + 1}
    norm = {'schema': 'sbind-owner-normalization-result-v1', 'task_id': api.TASK,
        'assay_id': 'WFCI1', 'fold': 0, 'normalization': f['stats'],
        'normalization_sha256': f['common']['normalization_sha256'],
        'participant_streams': {'train': {'bytes': 1, 'sha256': '1' * 64, 'records': 246},
                               'test': sr(raw_sources['test'], 5),
                               'validation': sr(raw_sources['validation'], 1)},
        'owner_targets': sr(raw_targets, 6),
        'complete_selected_fold_frames': {'train': 245, 'validation': 1, 'test': 5},
        'historical_reproduction_qualified': False, 'runtime_isolation_qualified': False,
        'durable_publication_qualified': False, 'whole_grid_execution_qualified': False}
    norm.update(f['norm_changes'])
    norm_raw, mask_raw = encode(norm), encode(f['mask'])
    output_raw = {name: stream(rows) for name, rows in f['predictions'].items()}
    receipt_raw = {}
    count, trials = (5, 2) if role == 'test' else (1, 1)
    for name in ('candidate', 'comparator'):
        receipt = {'schema': 'sbind-prospective-wfci1-inference-receipt-v1', 'task_id': api.TASK,
            'assay_id': 'WFCI1', 'fold': 0, 'role': role,
            'input_sha256': digest(raw_sources[role]), 'input_bytes': len(raw_sources[role]),
            'output_sha256': digest(output_raw[name]), 'output_bytes': len(output_raw[name]),
            'output_records': count + 1, 'trials': trials, 'frames': count,
            'model_calls': trials, 'reset_true_calls': trials,
            'historical_reproduction_qualified': False, 'runtime_isolation_qualified': False}
        receipt.update(f['receipt_changes'].get(name, {}))
        receipt_raw[name] = encode(receipt)
    binding = {'schema': 'sbind-owner-paired-evaluation-v1', 'task_id': api.TASK,
        'assay_id': 'WFCI1', 'fold': 0, 'role': role,
        'candidate_method_id': 'generated-candidate', 'comparator_method_id': 'generated-comparator',
        'census_sha256': digest(f['census']), 'split_sha256': digest(f['split']),
        'representations_sha256': 'c' * 64, 'normalization_sha256': f['common']['normalization_sha256'],
        'normalization_receipt_sha256': digest(norm_raw), 'mask_sha256': digest(mask_raw),
        'candidate_receipt_sha256': digest(receipt_raw['candidate']),
        'comparator_receipt_sha256': digest(receipt_raw['comparator'])}
    binding.update(f['binding_changes'])
    binding_raw = encode(binding)
    return dict(owner_binding_bytes=binding_raw, owner_binding_sha256=digest(binding_raw),
                census_bytes=f['census'], split_bytes=f['split'], normalization_receipt_bytes=norm_raw,
                mask_bytes=mask_raw, candidate_receipt_bytes=receipt_raw['candidate'],
                comparator_receipt_bytes=receipt_raw['comparator'],
                source_stream=io.BytesIO(raw_sources[role]), owner_targets_stream=io.BytesIO(raw_targets),
                candidate_stream=io.BytesIO(output_raw['candidate']),
                comparator_stream=io.BytesIO(output_raw['comparator']),
                max_total_stream_bytes=4 * 1024 * 1024, max_role_frames=5)


class NoTargets:
    def seek(self, *args):
        raise AssertionError('private targets accessed before prediction admission')
    def read(self, *args):
        raise AssertionError('private targets read before prediction admission')
    def readline(self, *args):
        raise AssertionError('private targets read before prediction admission')


ERRORS = (api.ScoringError, api.inference.InferenceError, api.inference.trials.AdmissionError,
          api.kernels.MetricError)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = fixture()

    def case(self):
        return copy.deepcopy(self.original)

    def rejected(self, f, *, early=False, arguments=None):
        args = freeze(f) if arguments is None else arguments
        if early:
            args['owner_targets_stream'] = NoTargets()
        with self.assertRaises(ERRORS):
            api.score_pair(**args)

    def assert_metrics(self, result, mean_square):
        self.assertEqual(result['frames'], 5 if result['role'] == 'test' else 1)
        for name in ('candidate', 'comparator'):
            b, n = result['scores'][name]['behavior'], result['scores'][name]['neural']
            self.assertEqual(b['output_ids'], tuple('behavior-' + str(i) for i in range(14)))
            self.assertEqual(n['output_ids'], ('pixel:16383', 'pixel:0', 'pixel:131'))
            self.assertEqual((b['metric'], n['metric']), ('MSE', 'MSE'))
            self.assertEqual(b['support_sha256'], n['support_sha256'])
            self.assertEqual(b['n_samples'], result['frames'])
            for c, value in enumerate(b['values']):
                expected = mean_square * ((c + 1) ** 2 / 16 if name == 'candidate' else (c + 2) ** 2 / 4)
                self.assertAlmostEqual(value, expected, places=10)
            for p, value in zip((16383, 0, 131), n['values']):
                expected = mean_square * ((p % 5 + 1) ** 2 / 4 if name == 'candidate' else (p % 5 + 2) ** 2)
                self.assertAlmostEqual(value, expected, places=10)
        for key in ('historical_reproduction_qualified', 'comparator_competence_qualified',
                    'runtime_isolation_qualified', 'authentic_execution_qualified', 'paper_win_qualified'):
            self.assertIs(result[key], False)
        self.assertNotIn('win', result)

    def test_pair_scores_complete_unequal_trials_against_independent_arithmetic(self):
        args = freeze(self.case())
        result = api.score_pair(**args)
        # Independent closed form mean(1^2,...,5^2)=11, no kernel call as oracle.
        self.assert_metrics(result, 11)
        self.assertEqual(result['binding_sha256'], args['owner_binding_sha256'])
        self.assertEqual(result['source_sha256'], digest(args['source_stream'].getvalue()))
        self.assertEqual(result['owner_targets_sha256'], digest(args['owner_targets_stream'].getvalue()))
        self.assertEqual(result['mask_sha256'], digest(args['mask_bytes']))
        self.assertNotIn('targets', result)

    def test_validation_role_still_authenticates_both_target_roles(self):
        result = api.score_pair(**freeze(fixture('validation')))
        self.assert_metrics(result, 36)
        f = fixture('validation')
        f['target_records'][-1]['behavior'].pop()
        self.rejected(f)

    def test_prediction_and_receipt_byte_hashes_fail_before_targets(self):
        for name in ('candidate', 'comparator'):
            for kind in ('stream', 'receipt', 'receipt_pin'):
                with self.subTest(name=name, kind=kind):
                    args = freeze(self.case())
                    if kind == 'stream':
                        raw = args[name + '_stream'].getvalue()
                        args[name + '_stream'] = io.BytesIO(raw.replace(b'"record":"prediction"', b'"record":"predictioX"', 1))
                    elif kind == 'receipt':
                        args[name + '_receipt_bytes'] += b' '
                    else:
                        binding = json.loads(args['owner_binding_bytes'])
                        binding[name + '_receipt_sha256'] = '0' * 64
                        args['owner_binding_bytes'] = encode(binding)
                        args['owner_binding_sha256'] = digest(args['owner_binding_bytes'])
                    self.rejected(None, early=True, arguments=args)

    def test_receipt_pair_identity_counts_and_qualifications(self):
        changes = ({'input_sha256': 'e' * 64}, {'input_bytes': True}, {'fold': False},
                   {'role': 'validation'}, {'frames': 4}, {'output_records': 5}, {'trials': 1},
                   {'reset_true_calls': 1}, {'historical_reproduction_qualified': True}, {'MSE': 0.0})
        for name in ('candidate', 'comparator'):
            for change in changes:
                f = self.case()
                f['receipt_changes'][name] = change
                with self.subTest(name=name, change=change):
                    self.rejected(f, early=True)

    def test_prediction_headers_cannot_change_source_split_units_or_outputs(self):
        changes = ({'input_sha256': '0' * 64}, {'split_sha256': '0' * 64},
                   {'normalization_sha256': '0' * 64}, {'representations_sha256': '0' * 64},
                   {'census_sha256': '0' * 64}, {'fold': False}, {'role': 'validation'},
                   {'behavior_channels': ['behavior-' + str(i) for i in range(13)]},
                   {'historical_reproduction_qualified': True}, {'mean_mse': 0})
        for i, change in enumerate(changes):
            f = self.case()
            name = ('candidate', 'comparator')[i % 2]
            f['predictions'][name][0].update(change)
            with self.subTest(change=change):
                self.rejected(f, early=True)

    def test_prediction_support_rejects_missing_duplicate_extra_and_shifted_frames(self):
        mutations = [lambda r: r.pop(), lambda r: r.append(copy.deepcopy(r[-1])),
                     lambda r: r.__setitem__(2, copy.deepcopy(r[1])),
                     lambda r: r[3].update(trial_offset=2), lambda r: r[1].update(source_index=False),
                     lambda r: r[1].update(role='validation'), lambda r: r[1].update(trial_id='wrong'),
                     lambda r: r[1].update(mean_mse=0)]
        for i, mutate in enumerate(mutations):
            f = self.case()
            mutate(f['predictions'][('candidate', 'comparator')[i % 2]])
            with self.subTest(mutation=i):
                self.rejected(f, early=True)

    def test_shapes_all_pixels_numeric_and_json_record_integrity(self):
        mutations = [lambda r: r[1]['behavior'].pop(),
                     lambda r: r[1]['neural'][0][0].pop(),
                     lambda r: r[1]['neural'][0][-1].__setitem__(-1, True),
                     lambda r: r[1]['behavior'].__setitem__(0, True)]
        for i, mutate in enumerate(mutations):
            f = self.case()
            mutate(f['predictions'][('candidate', 'comparator')[i % 2]])
            with self.subTest(mutation=i):
                self.rejected(f, early=True)
        for replace in (lambda b: b.replace(b'"source_index":0', b'"source_index":0,"source_index":0', 1),
                        lambda b: b.replace(b'"behavior":[0.25', b'"behavior":[NaN', 1),
                        lambda b: b[:-1], lambda b: b + b'\n'):
            args = freeze(self.case())
            raw = replace(args['candidate_stream'].getvalue())
            args['candidate_stream'] = io.BytesIO(raw)
            # Re-freeze byte receipt deliberately, so structural admission is tested.
            receipt = json.loads(args['candidate_receipt_bytes'])
            receipt.update(output_bytes=len(raw), output_sha256=digest(raw))
            args['candidate_receipt_bytes'] = encode(receipt)
            binding = json.loads(args['owner_binding_bytes'])
            binding['candidate_receipt_sha256'] = digest(args['candidate_receipt_bytes'])
            args['owner_binding_bytes'] = encode(binding)
            args['owner_binding_sha256'] = digest(args['owner_binding_bytes'])
            self.rejected(None, early=True, arguments=args)

    def test_source_authentication_support_and_no_private_target_access(self):
        for mutation in ('hash', 'identity', 'held_behavior'):
            f = self.case()
            args = freeze(f)
            if mutation == 'hash':
                args['source_stream'] = io.BytesIO(args['source_stream'].getvalue() + b' ')
            else:
                if mutation == 'identity':
                    f['source_records']['test'][1]['source_index'] = 1
                else:
                    f['source_records']['test'][1]['behavior'] = [0] * 14
                # Bind predictions to the modified input so source validation is reached.
                h = digest(stream(f['source_records']['test']))
                for name in ('candidate', 'comparator'):
                    f['predictions'][name][0]['input_sha256'] = h
                args = freeze(f)
            with self.subTest(mutation=mutation):
                self.rejected(None, early=True, arguments=args)

    def test_entire_owner_target_stream_including_nonselected_role_is_required(self):
        mutations = [lambda r: r[1]['behavior'].pop(), lambda r: r[1].update(role='test'),
                     lambda r: r[1].update(reset=False), lambda r: r.pop(1),
                     lambda r: r.append(copy.deepcopy(r[-1])),
                     lambda r: r[2].update(source_index=1),
                     lambda r: r[2].update(neural=[]), lambda r: r[0].update(includes_behavior=False)]
        for i, mutate in enumerate(mutations):
            f = self.case()
            mutate(f['target_records'])
            with self.subTest(mutation=i):
                self.rejected(f)
        args = freeze(self.case())
        args['owner_targets_stream'] = io.BytesIO(args['owner_targets_stream'].getvalue() + b' ')
        self.rejected(None, arguments=args)

    def test_owner_mask_and_normalization_binding_are_not_participant_choices(self):
        for change in ({'pixel_indices': []}, {'pixel_indices': [0, 0]}, {'pixel_indices': [True]},
                       {'pixel_indices': [16384]}, {'source_sha256': '0' * 64},
                       {'representation_sha256': '0' * 64}, {'weights': [1]}):
            f = self.case()
            f['mask'].update(change)
            with self.subTest(change=change):
                self.rejected(f, early=True)
        for change in ({'fold': True}, {'historical_reproduction_qualified': True},
                       {'normalization_sha256': '0' * 64},
                       {'complete_selected_fold_frames': {'train': 245, 'validation': 0, 'test': 5}}):
            f = self.case()
            f['norm_changes'].update(change)
            self.rejected(f, early=True)
        f = self.case()
        f['stats']['neural_mean'][0] = 2
        self.rejected(f, early=True)
        f = self.case()
        f['stats']['behavior_sd'][0] = 0
        self.rejected(f, early=True)

    def test_owner_limits_and_full_protocol_admission_never_subset(self):
        for change in ({'max_role_frames': 4}, {'max_total_stream_bytes': 1},
                       {'max_role_frames': True}):
            args = freeze(self.case())
            args.update(change)
            self.rejected(None, early=True, arguments=args)
        for change in ({'role': 'train'}, {'fold': False}, {'assay_id': 'WFCI2'},
                       {'candidate_method_id': ''}, {'split_sha256': '0' * 64}):
            f = self.case()
            f['binding_changes'].update(change)
            self.rejected(f, early=True)
        f = self.case()
        census = json.loads(f['census'])
        census['assays'][1]['trials'].pop()
        f['census'] = encode(census)
        self.rejected(f, early=True)

    def test_owner_binding_hash_and_duplicate_metadata_members(self):
        args = freeze(self.case())
        args['owner_binding_sha256'] = '0' * 64
        self.rejected(None, early=True, arguments=args)
        args = freeze(self.case())
        raw = args['owner_binding_bytes'].replace(b'"fold":0', b'"fold":0,"fold":0', 1)
        args.update(owner_binding_bytes=raw, owner_binding_sha256=digest(raw))
        self.rejected(None, early=True, arguments=args)


class BoundedReport:
    """Bound this suite's failure-inclusive diagnostic stream to 12 KiB."""
    def __init__(self):
        self.remaining = 12288
    def write(self, text):
        raw = text.encode('utf-8', errors='replace')[:self.remaining]
        sys.stderr.buffer.write(raw)
        self.remaining -= len(raw)
    def flush(self):
        sys.stderr.buffer.flush()


if __name__ == '__main__':
    unittest.main(testRunner=unittest.TextTestRunner(stream=BoundedReport(), verbosity=2))
