"""Generated complete-panel controls only; no authentic packets or provider calls."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import observation as o
import numpy as np

WRITTEN = 0
_REAL_PUBLISH = o.publish


def write(path, body):
    global WRITTEN
    path.write_bytes(body)
    WRITTEN += len(body)
    return o.pin(body)


def counted_publish(root, name, raw):
    global WRITTEN
    result = _REAL_PUBLISH(root, name, raw)
    WRITTEN += len(raw)
    return result


class ObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_sha = hashlib.sha256((o.HERE / 'SOURCE.json').read_bytes()).hexdigest()
        cls.rt = o.source(cls.source_sha)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='neural022-generated-')
        self.root = Path(self.temp.name).resolve()
        self.packet = self.root / 'packet'; self.packet.mkdir()
        self.training = {
            'ids': np.array([f'{i:024x}' for i in range(141)], dtype='<U24'),
            'counts': np.arange(141 * 390, dtype='<i8').reshape(141, 390),
            'velocity': np.array([[i / 71, -i / 33] for i in range(141)], dtype='<f8'),
            'directions': (np.arange(141) % 8 * 45).astype('<i8')}
        self.training['velocity'][0, 0] = -0.0
        self.query = {
            'ids': np.array([f'{i + 1000:024x}' for i in range(92)], dtype='<U24'),
            'counts': np.arange(141 * 390, 233 * 390, dtype='<i8').reshape(92, 390),
            'directions': (np.arange(92) % 8 * 45).astype('<i8'),
            'modes': np.array(['active'] * 52 + ['passive'] * 40, dtype='<U7')}
        self.cases = {'schema': 'neural022_public_cases_v1', 'cases': [
            {'id': str(self.query['ids'][i]), 'mode': str(self.query['modes'][i]),
             'direction': int(self.query['directions'][i])} for i in range(92)]}
        producer = self.rt['dependencies']['packet_producer']
        self.meta = {'schema': 'neural022_delivery_packet_v1', 'source': producer['source'],
                     'source_contract': producer['source_contract'], 'files': {},
                     'public_training_rows': 141, 'public_query_rows': 92,
                     'projection_resources_absent': True,
                     'projection_closure': {'phase': 'f' * 32, 'receipt': {'bytes': 1, 'sha256': 'a' * 64},
                         'source': producer['source'], 'producer_removed_before_capture': True,
                         'all_native_resources_closed': True},
                     'new_model_fits': 0, 'new_reference_predictions': 0,
                     'runtime_qualified': False, 'scientific_qualification': False}
        self.refresh()
        self.patch = mock.patch.object(o, 'publish', side_effect=counted_publish)
        self.patch.start()

    def tearDown(self):
        self.patch.stop(); self.temp.cleanup()

    def refresh(self):
        public = {'training.npz': self.rt['io_support'].encoded_npz(self.training),
                  'queries.npz': self.rt['io_support'].encoded_npz(self.query),
                  'cases.json': o.encoded(self.cases), 'TASK.md': (o.HERE / 'ORIGINAL_TASK.md').read_bytes()}
        self.meta['files'] = {name: write(self.packet / name, raw) for name, raw in public.items()}
        # These private paths deliberately do not exist: no stat/open is necessary.
        self.meta['files'].update({name: {'bytes': 37, 'sha256': 'b' * 64}
                                  for name in ('reference.private.npz', 'receipt.json')})
        self.packet_pin = write(self.packet / 'PACKET.json', o.encoded(self.meta))
        return public

    def export(self, suffix='export'):
        target = self.root / suffix
        identity = o.export(self.packet, self.packet_pin['sha256'], target, self.rt)
        return target, identity

    def response(self):
        value = {'schema': 'neural022_predictions_v1', 'predictions': [
            {'id': row['id'], 'velocity': [i / 100, -i / 300]} for i, row in enumerate(self.cases['cases'])]}
        path = self.root / 'response.json'
        return value, path, write(path, o.encoded(value))

    def test_01_full_panel_roundtrip_and_original_artifact_contract(self):
        target, identity = self.export()
        observed = o.strict((target / 'OBSERVATION.json').read_bytes())
        self.assertEqual(len(observed['training']), 141); self.assertEqual(len(observed['queries']), 92)
        for key, original in (('training', self.training), ('queries', self.query)):
            self.assertEqual([r['id'] for r in observed[key]], original['ids'].tolist())
            reconstructed = np.asarray([r['counts'] for r in observed[key]], dtype=np.int64).reshape(-1, 390)
            np.testing.assert_array_equal(reconstructed, original['counts'])
        self.assertEqual(observed['training'][0]['counts'][1][0], 65)
        self.assertEqual(observed['queries'][-1]['counts'][5][64], 90869)
        np.testing.assert_array_equal(np.asarray([r['velocity'] for r in observed['training']]), self.training['velocity'])
        self.assertTrue(np.signbit(observed['training'][0]['velocity'][0]))
        value, response, response_pin = self.response()
        out = self.root / 'collected'
        o.collect(target, identity['sha256'], response, response_pin['sha256'], out, self.rt)
        submission = o.strict((out / 'submission.json').read_bytes())
        self.assertEqual(submission, {'schema_version': 1, 'task_id': 'NEURAL-022',
                                     'file': {'path': 'predictions.json', **response_pin}})
        self.assertEqual((out / 'predictions.json').read_bytes(), o.encoded(value))
        self.rt['candidate'].validate((out / 'predictions.json').read_bytes(), self.cases)
        report = o.strict((out / 'COLLECTION.json').read_bytes())
        self.assertFalse(report['provider_session_verified']); self.assertFalse(report['no_tools_boundary_verified'])
        self.assertFalse(report['training_only_method_verified']); self.assertEqual(report['complete_prediction_rows'], 92)

    def test_02_private_operands_never_inspected_or_released(self):
        calls = []; original = o.capture
        def tracked(path, *args, **kwargs):
            calls.append(Path(path).name)
            self.assertNotIn(Path(path).name, ('reference.private.npz', 'receipt.json'))
            return original(path, *args, **kwargs)
        with mock.patch.object(o, 'capture', side_effect=tracked):
            target, identity = self.export()
            _, response, response_pin = self.response()
            o.collect(target, identity['sha256'], response, response_pin['sha256'], self.root / 'result', self.rt)
        self.assertEqual(calls[:5], ['PACKET.json', *o.PUBLIC])
        text = (target / 'OBSERVATION.json').read_text()
        for forbidden in ('source_rows', 'reference.private.npz', 'PACKET.json', 'sha256', str(self.root)):
            self.assertNotIn(forbidden, text)
        observation = o.strict(text.encode())
        self.assertTrue(all(set(r) == {'id', 'direction', 'counts', 'velocity'} for r in observation['training']))
        self.assertTrue(all(set(r) == {'id', 'mode', 'direction', 'counts'} for r in observation['queries']))
        self.assertIn('0.009045253242801947', observation['original_public_scientific_contract'])
        self.assertNotIn('Write a Python', observation['instructions'] + observation['original_public_scientific_contract'])

    def test_03_int64_extreme_preserved_with_complete_byte_bound(self):
        self.training['counts'].fill(np.iinfo(np.int64).max)
        self.query['counts'].fill(np.iinfo(np.int64).max)
        self.refresh(); target, _ = self.export()
        raw = (target / 'OBSERVATION.json').read_bytes()
        self.assertLess(len(raw), o.OBSERVATION_CAP)
        observed = o.strict(raw)
        self.assertEqual(observed['training'][140]['counts'][5][64], 9223372036854775807)
        self.assertEqual(observed['queries'][91]['counts'][5][64], 9223372036854775807)
        print(json.dumps({'generated_int64_max_observation_bytes': len(raw)}))

    def test_04_training_source_rows_or_missing_unit_rejected(self):
        self.training['source_rows'] = np.arange(141, dtype='<i8'); self.refresh()
        with self.assertRaises(ValueError): self.export()
        del self.training['source_rows']; self.training['counts'] = self.training['counts'][:, :-1]
        self.refresh()
        with self.assertRaises(ValueError): self.export()
        self.assertFalse((self.root / 'export').exists())

    def test_05_full_query_order_context_and_disjoint_identity(self):
        self.query['ids'][[0, 1]] = self.query['ids'][[1, 0]]; self.refresh()
        with self.assertRaises(ValueError): self.export()
        self.query['ids'][[0, 1]] = self.query['ids'][[1, 0]]
        self.query['ids'][0] = self.training['ids'][0]; self.cases['cases'][0]['id'] = str(self.query['ids'][0]); self.refresh()
        with self.assertRaises(ValueError): self.export()
        self.assertFalse((self.root / 'export').exists())

    def test_06_changed_packet_pin_refuses_before_decode(self):
        write(self.packet / 'queries.npz', b'changed generated bytes')
        with mock.patch.object(self.rt['io_support'], 'npz', side_effect=AssertionError('No decode')):
            with self.assertRaises(ValueError): self.export()
        self.assertFalse((self.root / 'export').exists())

    def test_07_incomplete_or_reordered_answers_refuse_without_partial_score(self):
        target, identity = self.export(); value, response, _ = self.response()
        full = value['predictions'][:]
        for altered in (full[:-1], [full[1], full[0], *full[2:]]):
            value['predictions'] = altered; identity_response = write(response, o.encoded(value))
            with self.assertRaises(ValueError):
                o.collect(target, identity['sha256'], response, identity_response['sha256'], self.root / 'result', self.rt)
            self.assertFalse((self.root / 'result').exists())

    def test_08_observation_and_response_commitments_are_required(self):
        target, identity = self.export(); _, response, response_pin = self.response()
        with self.assertRaises(ValueError):
            o.collect(target, identity['sha256'], response, '0' * 64, self.root / 'result', self.rt)
        # Export-owned snapshot is immutable by convention; simulate operator corruption deliberately.
        (target / 'OBSERVATION.json').chmod(0o600)
        write(target / 'OBSERVATION.json', b'{}\n')
        with self.assertRaises(ValueError):
            o.collect(target, identity['sha256'], response, response_pin['sha256'], self.root / 'result', self.rt)
        self.assertFalse((self.root / 'result').exists())

    def test_09_existing_output_is_not_overwritten(self):
        out = self.root / 'export'; out.mkdir(); write(out / 'sentinel', b'keep')
        with self.assertRaises(ValueError): self.export()
        self.assertEqual((out / 'sentinel').read_bytes(), b'keep')

    def test_10_wrong_source_or_producer_or_open_projection_refused(self):
        with self.assertRaises(ValueError): o.source('0' * 64)
        self.meta['projection_closure']['all_native_resources_closed'] = False
        self.packet_pin = write(self.packet / 'PACKET.json', o.encoded(self.meta))
        with self.assertRaises(ValueError): self.export()
        self.meta['projection_closure']['all_native_resources_closed'] = True
        self.meta['source'] = {'bytes': 4998, 'sha256': '0' * 64}
        self.packet_pin = write(self.packet / 'PACKET.json', o.encoded(self.meta))
        with self.assertRaises(ValueError): self.export()

    def test_11_negative_count_and_nonfinite_training_label_refused(self):
        self.training['counts'][140, 389] = -1; self.refresh()
        with self.assertRaises(ValueError): self.export()
        self.training['counts'][140, 389] = 0; self.training['velocity'][140, 1] = np.nan; self.refresh()
        with self.assertRaises(ValueError): self.export()

    def test_12_source_cache_not_used_for_canonical_modules(self):
        # Actual source execution is from bytes; the source-only loader never asks Python to import these names.
        poison = types.SimpleNamespace()
        with mock.patch.dict(sys.modules, {'candidate': poison, 'packet': poison, 'io_support': poison}):
            runtime = o.source(self.source_sha)
        self.assertTrue(callable(runtime['candidate'].validate))
        self.assertEqual(runtime['identity']['sha256'], self.source_sha)


if __name__ == '__main__':
    try:
        unittest.main(verbosity=2)
    finally:
        print(json.dumps({'known_cumulative_generated_file_body_bytes': WRITTEN,
                          'fixtures_cleaned_by_temporary_directory': True,
                          'authentic_inputs': 0, 'provider_calls': 0}))
