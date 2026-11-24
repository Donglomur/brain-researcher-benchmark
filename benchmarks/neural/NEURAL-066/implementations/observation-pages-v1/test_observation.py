"""Generated observation delivery controls; no authentic data or model execution."""
import copy
import importlib.util
import json
import io
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import observation as view

WRITTEN = 0


def token(text):
    return view.pin(text.encode())['sha256']


def save(root, name, raw):
    global WRITTEN
    (root / name).write_bytes(raw)
    WRITTEN += len(raw)
    return {'path': name, **view.pin(raw)}


def docsave(root, name, value):
    return save(root, name, view.encoded(value))


def matrix(root, name, rows, cols, training=False):
    header = repr({'descr': '<f4', 'fortran_order': False, 'shape': (rows, cols)}).encode('latin1')
    pad = 16 - ((10 + len(header) + 1) % 16)
    header += b' ' * pad + b'\n'
    values = []
    for row in range(rows):
        for col in range(cols):
            if training and col == cols - 2:
                value = row % 29
            elif training and col == cols - 1:
                value = 0.5
            else:
                value = row * 10000 + col / 8
            values.append(float(value))
    raw = b'\x93NUMPY\x01\x00' + struct.pack('<H', len(header)) + header
    raw += struct.pack('<' + 'f' * len(values), *values)
    return {**save(root, name, raw), 'shape': [rows, cols], 'dtype': '<f4'}


def fixture(root, arm, modality='EEG'):
    names = [] if arm == 'TIMING' else ['eye<&>'] if arm == 'EOG' else [f'C{i}' for i in range(view.CHANNELS[modality])]
    types = [] if arm == 'TIMING' else ['eog'] if arm == 'EOG' else ['eeg' if modality == 'EEG' else 'mag'] * len(names)
    if arm == 'TIMING':
        spec = {'kind': 'timing3', 'dimensions': 3, 'features': view.TIMING,
                'units': ['seconds', 'seconds', 'indicator'], 'samples_per_key': 1, 'geometry': None}
    else:
        spec = {'kind': 'channel_window', 'dimensions': len(names) * 25, 'channel_names': names,
                'channel_types': types, 'samples_per_key': 25, 'window_seconds': view.WINDOWS[arm],
                'geometry': None if arm == 'EOG' else 'source_authenticated_neural'}
    d = spec['dimensions']
    arrays = {'train.npy': matrix(root, 'train.npy', 3, d + 2, training=True),
              'query.npy': matrix(root, 'query.npy', 3, d)}
    geo = {'schema': 'neural066_nonspatial_features_v1', 'modality': modality,
           'channel_names': names, 'channel_types': types, 'positions': None,
           'kind': spec['kind'], 'R2_supported': False}
    if arm not in ('TIMING', 'EOG'):
        geo = {'schema': 'neural066_geometry_v1', 'modality': modality, 'channel_names': names,
               'channel_types': types, 'positions': [[i / (len(names) - 1), 1 - i / (len(names) - 1)] for i in range(len(names))],
               'source_method': 'MNE1.11.0 minimalInfo/find_layout per-axis minmax; fullcoverage',
               'layout_kind': 'generated-control-only'}
    rows = [{'id': token('train0'), 'person': token('person0'), 'session': token('session0'),
             'template': token('template0'), 'begin': 0, 'n_keys': 1},
            {'id': token('train1'), 'person': token('person1'), 'session': token('session1'),
             'template': token('template1'), 'begin': 1, 'n_keys': 2}]
    doc = {'schema': 'neural066_candidate_input_v3', 'task': 'NEURAL-066', 'case': token('case'),
           'generation': token('generation'), 'condition': arm, 'arm': arm, 'mode': view.MODES[0],
           'modality': modality, 'channels': names, 'feature_dimensions': d,
           'samples_per_key': spec['samples_per_key'], 'feature_spec': spec,
           'support_commitment': token('support'), 'source_contract_pin': view.pin(b'source'),
           'projection_pin': view.pin(b'projection'), 'language_policy_pin': view.pin(b'language'),
           'realm': 'diagnostic', 'arrays': arrays, 'geometry': docsave(root, 'GEOMETRY.json', geo),
           'training_layout': docsave(root, 'TRAIN_LAYOUT.json', {'schema': 'neural066_train_layout_v1', 'sentences': rows}),
           'queries': [{'id': token('query0'), 'begin': 0, 'n_keys': 1},
                       {'id': token('query1'), 'begin': 1, 'n_keys': 2}],
           'event_assisted': True, 'full_current_case_batch': True,
           'zero_labeled_target_person_calibration': True}
    docsave(root, 'INPUT.json', doc)
    return doc


class ObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='generated-', dir=HERE)
        cls.root = Path(cls.temp.name)
        cls.packets = {}
        for arm in view.ARMS:
            root = cls.root / arm
            root.mkdir()
            cls.packets[arm] = (root, fixture(root, arm))
        root = cls.root / 'MEG'
        root.mkdir()
        cls.packets['MEG'] = (root, fixture(root, 'NEURAL', 'MEG'))
        cls.limits = {'read_bytes': 4 * 1024**2, 'metadata_bytes': 1024**2,
                      'response_bytes': 128 * 1024, 'wall_seconds': 30}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        print(json.dumps({'generated_fixture_cumulative_write_bytes': WRITTEN,
                          'authentic_or_model_runs': 0, 'temporary_fixtures_removed': True}))

    def present(self, kind, action, doc=None, limits=None):
        root, original = self.packets[kind]
        return view.present(root, view.pin(view.encoded(original if doc is None else doc)),
                            action, limits or self.limits)

    def values(self, doc, realm='query', **kw):
        return {'action': 'values', 'realm': realm, 'sentence': token('query1' if realm == 'query' else 'train1'),
                'key_offset': 1, 'key_count': 1, 'feature_offset': doc['feature_dimensions'] - 1,
                'feature_count': 1, **kw}

    def altered(self, kind, transform, action):
        root, original = self.packets[kind]
        changed = copy.deepcopy(original)
        transform(changed)
        docsave(root, 'INPUT.json', changed)
        try:
            with self.assertRaises((ValueError, OSError)):
                self.present(kind, action, changed)
        finally:
            docsave(root, 'INPUT.json', original)

    def test_all_six_arms_and_full_meg_last_coordinates(self):
        for arm, (_, doc) in self.packets.items():
            with self.subTest(arm=arm):
                answer = self.present(arm, self.values(doc))
                value = 20000 + (doc['feature_dimensions'] - 1) / 8
                self.assertIn(repr(value), answer['html'])
                self.assertEqual(answer['offered_features'], doc['feature_dimensions'])
                self.assertTrue(answer['complete_matrix_hash_checked'])
                self.assertFalse(answer['query_targets_delivered'])
                self.assertNotIn('Observed training class', answer['html'])
                self.assertFalse(answer['direct_interpretation_measured'])
                self.assertFalse(answer['campaign_complete'])
                if arm not in ('TIMING',):
                    self.assertIn('bin 24', answer['html'])
                    self.assertIn('physical unit not encoded', answer['html'])
                if arm == 'EOG':
                    self.assertIn('eye&lt;&amp;&gt;', answer['html'])
                    self.assertNotIn('eye<&>', answer['html'])

    def test_training_calibration_group_labels_and_original_weights(self):
        _, doc = self.packets['NEURAL']
        answer = self.present('NEURAL', self.values(doc, 'train'))
        self.assertIn('Observed training class index', answer['html'])
        self.assertIn('<td>2.0</td><td>0.5</td>', answer['html'])
        catalog = self.present('NEURAL', {'action': 'sentences', 'realm': 'train', 'offset': 0, 'count': 2})
        self.assertIn(token('person0'), catalog['html'])
        self.assertIn(token('template1'), catalog['html'])
        self.assertIsNone(catalog['next_offset'])
        query = self.present('NEURAL', {'action': 'sentences', 'realm': 'query', 'offset': 0, 'count': 2})
        self.assertNotIn('<th>person</th>', query['html'])

    def test_overview_class_order_and_nonspatial_features(self):
        overview = self.present('SHUFFLE', {'action': 'overview'})
        self.assertIn('training neural vectors are permuted', overview['html'])
        self.assertIn('<td>28</td><td>9</td>', overview['html'])
        timing = self.present('TIMING', {'action': 'features', 'offset': 0, 'count': 3})
        self.assertIn('duration_seconds (seconds)', timing['html'])
        self.assertNotIn('normalized layout', timing['html'])
        neural = self.present('NEURAL_PRE', {'action': 'features', 'offset': 0, 'count': 1})
        self.assertIn('[-700,-680) ms', neural['html'])
        self.assertIn('normalized layout', neural['html'])

    def test_complete_response_and_every_query_required(self):
        _, doc = self.packets['NEURAL']
        body = {'format': 'typing_predictions_v1', 'task': 'NEURAL-066',
                'generation': doc['generation'], 'case': doc['case'], 'arm': doc['arm'],
                'sentences': [{'id': r['id'], 'p': [[1.0] + [0.0] * 28 for _ in range(r['n_keys'])]}
                              for r in doc['queries']]}
        answer = self.present('NEURAL', {'action': 'check_response', 'predictions': body})
        self.assertEqual((answer['query_sentences'], answer['query_keys']), (2, 3))
        self.assertTrue(answer['complete_case_response'])
        self.assertIsNone(answer['score'])
        changes = [lambda b: b['sentences'].pop(),
                   lambda b: b['sentences'].__setitem__(1, copy.deepcopy(b['sentences'][0])),
                   lambda b: b['sentences'][1]['p'].pop(),
                   lambda b: b.__setitem__('case', token('other')),
                   lambda b: b.__setitem__('target', 'forbidden'),
                   lambda b: b['sentences'][0]['p'][0].__setitem__(0, True),
                   lambda b: b['sentences'][0]['p'][0].__setitem__(0, float('nan')),
                   lambda b: b['sentences'][0]['p'][0].__setitem__(0, 0.5)]
        for change in changes:
            bad = copy.deepcopy(body)
            change(bad)
            with self.assertRaises(ValueError):
                self.present('NEURAL', {'action': 'check_response', 'predictions': bad})

    def test_private_fields_bad_support_and_query_target_column_rejected(self):
        self.altered('NEURAL', lambda d: d.__setitem__('private_queries', []), {'action': 'overview'})
        self.altered('NEURAL', lambda d: d['queries'][0].__setitem__('source_key', 'private'), {'action': 'overview'})
        self.altered('NEURAL', lambda d: d['queries'][1].__setitem__('begin', 0), {'action': 'overview'})
        self.altered('NEURAL', lambda d: d['queries'].pop(), {'action': 'overview'})
        self.altered('NEURAL', lambda d: d['arrays']['query.npy']['shape'].__setitem__(1, d['feature_dimensions'] + 1), {'action': 'overview'})
        self.altered('NEURAL', lambda d: d['arrays']['query.npy'].__setitem__('path', '../private.npy'), {'action': 'overview'})
        self.altered('NEURAL', lambda d: d['feature_spec']['channel_names'].pop(), {'action': 'overview'})
        self.altered('NEURAL', lambda d: d.__setitem__('realm', 'train'), {'action': 'overview'})

    def test_hash_nonfinite_truncation_and_budgets_fail_closed(self):
        root, doc = self.packets['TIMING']
        path = root / 'query.npy'
        original = path.read_bytes()
        bads = [original[:-4], original + b'extra', original[:-4] + struct.pack('<f', float('inf')),
                original[:-4] + struct.pack('<f', 42.0)]
        for raw in bads:
            save(root, 'query.npy', raw)
            try:
                with self.assertRaises(ValueError):
                    self.present('TIMING', self.values(doc, feature_offset=0))
            finally:
                save(root, 'query.npy', original)
        for changes in ({'read_bytes': 1}, {'metadata_bytes': 1}, {'response_bytes': 1}):
            with self.assertRaises(ValueError):
                self.present('TIMING', {'action': 'overview'}, limits={**self.limits, **changes})
        with self.assertRaises(ValueError):
            self.present('TIMING', {'action': 'execute', 'code': 'anything'})
        with self.assertRaises(ValueError):
            self.present('TIMING', self.values(doc, key_offset=True))

    def test_html_builder_rejects_lazily_before_repeated_label_expansion(self):
        consumed = []
        def headers():
            for i in range(64):
                consumed.append(i)
                yield '<' * 1000
        with self.assertRaisesRegex(ValueError, 'response ceiling'):
            view.table(headers(), [], 1024)
        self.assertEqual(consumed, [0])

    def test_cli_positive_path_and_ingress_charge(self):
        root, doc = self.packets['TIMING']
        input_pin = view.pin(view.encoded(doc))
        action_pin = docsave(root, 'ACTION.json', {'action': 'overview'})
        argv = ['observation.py', '--input-root', str(root), '--input-bytes', str(input_pin['bytes']),
                '--input-sha256', input_pin['sha256'], '--read-bytes', '100000',
                '--metadata-bytes', '10000', '--response-bytes', '10000', '--wall-seconds', '10']
        output = io.BytesIO()
        with (root / 'ACTION.json').open('rb') as stream:
            with mock.patch.object(sys, 'argv', argv), mock.patch.object(sys, 'stdin', stream), \
                    mock.patch.object(sys, 'stdout', types.SimpleNamespace(buffer=output)):
                view.main()
        answer = json.loads(output.getvalue())
        self.assertEqual(answer['case'], doc['case'])
        expected = 10001 + input_pin['bytes'] + doc['geometry']['bytes'] + doc['training_layout']['bytes']
        self.assertEqual(answer['reserved_read_bytes'], expected)
        self.assertFalse(answer['restricted_transport_qualified'])

    def test_failed_page_preserves_read_reservations(self):
        _, doc = self.packets['TIMING']
        with self.assertRaises(ValueError) as caught:
            self.present('TIMING', {'action': 'overview'},
                         limits={**self.limits, 'response_bytes': 1})
        expected = len(view.encoded(doc)) + doc['geometry']['bytes'] + doc['training_layout']['bytes']
        self.assertEqual(caught.exception.observation_costs['reserved_read_bytes'], expected)

    def test_cli_rejects_bad_caps_before_stdin(self):
        root, doc = self.packets['TIMING']
        input_pin = view.pin(view.encoded(doc))
        argv = ['observation.py', '--input-root', str(root), '--input-bytes', str(input_pin['bytes']),
                '--input-sha256', input_pin['sha256'], '--read-bytes', '100000',
                '--metadata-bytes', '-2', '--response-bytes', '1000', '--wall-seconds', '10']
        with mock.patch.object(sys, 'argv', argv), mock.patch.object(sys, 'stdin') as stdin:
            with self.assertRaisesRegex(ValueError, 'Positive integer limit'):
                view.main()
            stdin.fileno.assert_not_called()
            stdin.buffer.read.assert_not_called()

    def test_static_public_contract_constants_match_retained_source(self):
        # Source-only dependency. During candidate review the checkout is passed
        # explicitly; integrated CI resolves the sibling retained public source.
        import os
        legacy = Path(os.environ.get('NEURAL066_LEGACY_SOURCE', str(
            HERE.parent / 'neural-066' / 'typing-s3-public-v1' / 'source')))
        abi = json.loads((legacy / 'PUBLIC_ABI.json').read_text())
        self.assertEqual(list(view.CHARS), abi['input']['class_order'])
        info = json.loads((legacy / 'design' / 'INFORMATION_VIEWS.json').read_text())
        self.assertEqual(set(view.ARMS), set(info['arms']))
        for arm in ('EOG', 'NEURAL', 'NEURAL_PRE', 'NEURAL_POST'):
            self.assertEqual(view.WINDOWS[arm], info['arms'][arm]['window'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
