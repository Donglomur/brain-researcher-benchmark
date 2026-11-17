"""Generated-only packet leakage and complete-fold controls; no authentic arrays."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

import numpy as np

import materials as m


def generated_bank():
    neurons = {f'g{i:02d}': 'glutamatergic' for i in range(21)}
    neurons.update({f'b{i:02d}': 'gabaergic' for i in range(23)})
    rows = []
    for neuron_index, (neuron, cohort) in enumerate(neurons.items()):
        for ordinal in range(3):
            eligible = not (neuron_index < 16 and ordinal == 2)
            rows.append({'recording_id': f'{neuron}/recording-{ordinal:03d}', 'neuron_id': neuron,
                         'cohort': cohort, 'source_recording_index_zero_based': ordinal,
                         'status': 'prepared' if eligible else 'unavailable',
                         'reason': None if eligible else 'native_noise_exceeds_requested_noise',
                         'output_samples': 80 + ordinal if eligible else 0,
                         'source_glob_training_eligible': neuron_index >= 4,
                         'operator_payload': {'path': f'private-{neuron_index}-{ordinal}.npz',
                                              'sha256': 'e' * 64, 'bytes': 123},
                         'events_in_source_bins': 999001 + neuron_index,
                         'events_outside_source_bins': 999002 + neuron_index,
                         'private_note': 'DO_NOT_RELEASE_OPERATOR_METADATA'})
    metadata = {'recordings': rows, 'expected_neurons': neurons, 'source_recordings': 132,
                'condition': {'name': 'current_source_recipe_single_realization_v1',
                              'nominal_rate_hz': 30., 'requested_noise_level': 7.,
                              'target_sigma_seconds': .05, 'context_window_bins': 64,
                              'historical_paper_realization': False}}
    return SimpleNamespace(metadata=metadata, manifest_sha256='a' * 64)


def generated_arrays(bank, row):
    n = row['output_samples']
    index = next(i for i, value in enumerate(bank.metadata['recordings'])
                 if value['recording_id'] == row['recording_id'])
    support = np.zeros(n, dtype=bool)
    support[32:-32] = True
    return {'fluorescence': (np.arange(n, dtype='<f8') / 100 + index),
            'target_hz': np.full(n, 10000 + index, dtype='<f8'),
            'counts': np.full(n, index, dtype='<i8'), 'support': support,
            'bin_centers_seconds': np.arange(n, dtype='<f8') / 30}


def generated_asset_tree(root):
    # Only the checked-in source manifest is read; all asset bodies are invented.
    descriptor = json.loads((m.HERE / 'ASSETS.json').read_text())
    bodies = {}
    for row in descriptor['paper'] + descriptor['author_code']:
        body = ('generated inert source: ' + row['path'] + '\n').encode()
        row.update(bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        path = root / row['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        bodies[row['path']] = body
    return descriptor, bodies


class FoldSelectionControls(unittest.TestCase):
    def setUp(self):
        self.bank = generated_bank()

    def test_all44_folds_preserve116_queries_and132_operator_census(self):
        query_ids = []
        for held, cohort in self.bank.metadata['expected_neurons'].items():
            with self.subTest(held=held):
                plan = m.select_fold(self.bank, held)
                self.assertEqual(len(plan['source_census']), 132)
                self.assertEqual(len(plan['expected_neurons']), 44)
                self.assertEqual(len(plan['held_source_excluded_ids']), 3)
                expected = [row['recording_id'] for row in self.bank.metadata['recordings']
                            if row['status'] == 'prepared' and row['cohort'] == cohort and row['neuron_id'] != held]
                self.assertEqual([row['recording_id'] for row in plan['training_rows']], expected)
                self.assertTrue(all(row['neuron_id'] == held for row in plan['query_rows']))
                self.assertTrue(all(row['recording_id'] not in plan['held_source_excluded_ids']
                                    for row in plan['training_rows']))
                query_ids.extend(row['recording_id'] for row in plan['query_rows'])
        self.assertEqual(len(query_ids), 116)
        self.assertEqual(len(set(query_ids)), 116)

    def test_nonmini_cells_are_retained_and_ineligible_records_never_train(self):
        plan = m.select_fold(self.bank, 'g20')
        self.assertIn('g00', {row['neuron_id'] for row in plan['training_rows']})
        self.assertNotIn('g00/recording-002', {row['recording_id'] for row in plan['training_rows']})
        self.assertIn('g00/recording-002', m.select_fold(self.bank, 'g00')['held_source_excluded_ids'])

    def test_missing_duplicate_reordered_or_unknown_exclusion_refused(self):
        mutations = [lambda bank: bank.metadata['recordings'].pop(),
                     lambda bank: bank.metadata['recordings'].__setitem__(1, deepcopy(bank.metadata['recordings'][0])),
                     lambda bank: bank.metadata['recordings'].reverse(),
                     lambda bank: bank.metadata['recordings'][2].update(reason='model_failure'),
                     lambda bank: bank.metadata['recordings'][0].update(cohort='gabaergic')]
        for index, mutate in enumerate(mutations):
            bank = deepcopy(self.bank)
            mutate(bank)
            with self.subTest(case=index), self.assertRaises(ValueError):
                m.select_fold(bank, 'g00')

    def test_unknown_held_cell_and_incomplete_neuron_cohort_refused(self):
        with self.assertRaises(ValueError):
            m.select_fold(self.bank, 'unknown')
        for change in ('remove', 'cohort'):
            bank = deepcopy(self.bank)
            if change == 'remove':
                del bank.metadata['expected_neurons']['b22']
            else:
                bank.metadata['expected_neurons']['b22'] = 'glutamatergic'
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.select_fold(bank, 'g00')

    def test_different_sampling_noise_or_smoothing_condition_refused(self):
        for field, value in (('nominal_rate_hz', 2.5), ('requested_noise_level', 2),
                             ('target_sigma_seconds', .4), ('historical_paper_realization', True)):
            bank = deepcopy(self.bank)
            bank.metadata['condition'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                m.select_fold(bank, 'g00')


class MaterialProjectionControls(unittest.TestCase):
    def setUp(self):
        self.bank = generated_bank()

    def build(self, held='g00', arm='paper_data', purpose='improvement', loader=generated_arrays):
        return m.build_materials(self.bank, held, arm, purpose, array_loader=loader)

    def test_all44_participant_manifests_have_no_other_cohort_or_private_metadata(self):
        for held, cohort in self.bank.metadata['expected_neurons'].items():
            with self.subTest(held=held):
                packet = self.build(held)
                manifest = packet['manifest']
                self.assertEqual(set(manifest), m.MANIFEST_FIELDS)
                encoded = json.dumps(manifest)
                for neuron, other_cohort in self.bank.metadata['expected_neurons'].items():
                    if other_cohort != cohort:
                        self.assertNotIn(neuron + '/', encoded)
                        self.assertNotIn('"' + neuron + '"', encoded)
                for forbidden in ('operator_payload', 'events_in_source_bins', 'events_outside_source_bins',
                                  'private_note', 'source_census', 'bank_manifest_sha256', 'DO_NOT_RELEASE'):
                    self.assertNotIn(forbidden, encoded)
                self.assertEqual(set(packet['query']), {'fluorescence', 'support', 'bin_centers_seconds'})
                self.assertEqual(set(packet['training']), set(m.TRAINING_FIELDS))

    def test_loader_receives_only_allowed_training_and_held_query_rows(self):
        seen = []
        def loader(bank, row):
            seen.append(row['recording_id'])
            return generated_arrays(bank, row)
        packet = self.build(loader=loader)
        plan = packet['operator_plan']
        self.assertEqual(seen, [row['recording_id'] for row in plan['training_rows'] + plan['query_rows']])
        self.assertNotIn('g00/recording-002', seen)
        self.assertFalse(any(identity.startswith('b') for identity in seen))

    def test_arrays_preserve_explicit_record_boundaries_and_counts(self):
        packet = self.build()
        for role, fields in (('training', m.TRAINING_FIELDS), ('query', m.QUERY_FIELDS)):
            offset = 0
            for row, original in zip(packet['manifest'][role + '_records'], packet['operator_plan'][role + '_rows']):
                expected = generated_arrays(self.bank, original)
                self.assertEqual(row['offset'], offset)
                self.assertEqual(set(row), {'recording_id', 'neuron_id', 'offset', 'samples'})
                for field in fields:
                    np.testing.assert_array_equal(packet[role][field][offset:offset + row['samples']], expected[field])
                    self.assertFalse(packet[role][field].flags.writeable)
                offset += row['samples']
            self.assertEqual(len(packet[role]['fluorescence']), offset)

    def test_label_mutation_cannot_enter_held_observation_packet(self):
        first = self.build()
        def changed_held(bank, row):
            arrays = generated_arrays(bank, row)
            if row['neuron_id'] == 'g00':
                arrays['target_hz'][:] = 987654321
                arrays['counts'][:] = 987654321
            return arrays
        second = self.build(loader=changed_held)
        self.assertEqual(first['manifest'], second['manifest'])
        for key in m.QUERY_FIELDS:
            np.testing.assert_array_equal(first['query'][key], second['query'][key])
        for key in m.TRAINING_FIELDS:
            np.testing.assert_array_equal(first['training'][key], second['training'][key])

    def test_arms_and_purposes_share_identical_observations(self):
        a = self.build(arm='paper_data', purpose='reproduction')
        b = self.build(arm='paper_data_author_code', purpose='improvement')
        self.assertEqual({k: v for k, v in a['manifest'].items() if k not in ('arm', 'purpose')},
                         {k: v for k, v in b['manifest'].items() if k not in ('arm', 'purpose')})
        for role in ('training', 'query'):
            for key in a[role]:
                np.testing.assert_array_equal(a[role][key], b[role][key])

    def test_invalid_arm_and_legacy_purpose_fail_before_array_access(self):
        for arm, purpose in (('A', 'improvement'), ('paper_data', 'reconstruction'), ('paper_data', 'unknown')):
            loader = Mock(side_effect=AssertionError('array loaded before condition admission'))
            with self.subTest(arm=arm, purpose=purpose):
                with self.assertRaises(ValueError):
                    self.build(arm=arm, purpose=purpose, loader=loader)
                loader.assert_not_called()

    def test_material_memory_budget_is_checked_before_loader(self):
        for row in self.bank.metadata['recordings']:
            if row['status'] == 'prepared':
                row['output_samples'] = 1_000_000
        loader = Mock(side_effect=AssertionError('large arrays loaded before budget check'))
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.build(loader=loader)
        loader.assert_not_called()

    def test_malformed_source_array_shape_dtype_clock_and_support_refused(self):
        mutations = [lambda a: a.update(target_hz=np.zeros(3)),
                     lambda a: a.update(counts=a['counts'].astype(float)),
                     lambda a: a['support'].__setitem__(0, True),
                     lambda a: a['bin_centers_seconds'].__setitem__(1, 0),
                     lambda a: a['fluorescence'].__setitem__(1, np.nan),
                     lambda a: a.update(extra=np.zeros(len(a['counts'])))]
        for index, mutate in enumerate(mutations):
            def loader(bank, row):
                arrays = generated_arrays(bank, row)
                mutate(arrays)
                return arrays
            with self.subTest(case=index), self.assertRaises(ValueError):
                self.build(loader=loader)


class AssetsAndSerializationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='spinal-materials-generated-')
        cls.root = Path(cls.temp.name).resolve()
        cls.asset_spec, cls.asset_bodies = generated_asset_tree(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.bank = generated_bank()
        self.patch = patch.object(m, '_asset_manifest', return_value=self.asset_spec)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def packet(self, arm='paper_data'):
        return m.build_materials(self.bank, 'g00', arm, 'improvement', array_loader=generated_arrays)

    def test_capture_only_pinned_paper_and_B_code_assets(self):
        a = m.capture_assets(self.root, 'paper_data')
        b = m.capture_assets(self.root, 'paper_data_author_code')
        self.assertEqual(set(a), {'paper.xml'})
        self.assertEqual(len(b), 19)
        self.assertEqual(a['paper.xml'], b['paper.xml'])
        self.assertTrue(all(type(value) is bytes for value in b.values()))
        self.assertTrue(all(name == 'paper.xml' or name.startswith('author-code/') for name in b))

    def test_tampered_or_symlinked_asset_refused(self):
        row = self.asset_spec['paper'][0]
        path = self.root / row['path']
        original = path.read_bytes()
        try:
            path.write_bytes(b'x' * len(original))
            with self.assertRaises(ValueError):
                m.capture_assets(self.root, 'paper_data')
            path.unlink()
            path.symlink_to(self.root / self.asset_spec['author_code'][0]['path'])
            with self.assertRaises(ValueError):
                m.capture_assets(self.root, 'paper_data')
        finally:
            path.unlink()
            path.write_bytes(original)

    def test_serialization_has_no_operator_plan_or_query_targets(self):
        packet = self.packet()
        files = m.material_bytes(packet, m.capture_assets(self.root, 'paper_data'))
        self.assertEqual(set(files), {'FOLD.json', 'training.npz', 'query.npz', 'paper.xml'})
        manifest = json.loads(files['FOLD.json'])
        self.assertNotIn('operator_plan', manifest)
        self.assertNotIn('source_census', manifest)
        with zipfile.ZipFile(io.BytesIO(files['query.npz'])) as archive:
            self.assertEqual(set(archive.namelist()), {name + '.npy' for name in m.QUERY_FIELDS})
            self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist()))
        with np.load(io.BytesIO(files['training.npz']), allow_pickle=False) as arrays:
            self.assertEqual(set(arrays.files), set(m.TRAINING_FIELDS))
        self.assertLess(sum(map(len, files.values())), 2 * 1024 * 1024)

    def test_serialized_A_B_arrays_and_paper_match_exactly(self):
        a = m.material_bytes(self.packet(), m.capture_assets(self.root, 'paper_data'))
        b = m.material_bytes(self.packet('paper_data_author_code'), m.capture_assets(self.root, 'paper_data_author_code'))
        for name in ('training.npz', 'query.npz', 'paper.xml'):
            self.assertEqual(a[name], b[name])
        self.assertEqual(set(b) - set(a), {'author-code/' + row['path'].split('public/author-code/', 1)[1]
                                         for row in self.asset_spec['author_code']})

    def test_serialization_rejects_private_extra_fields_and_changed_boundaries(self):
        assets = m.capture_assets(self.root, 'paper_data')
        mutations = [lambda p: p['manifest'].update(targets='private'),
                     lambda p: p['manifest']['query_records'][0].update(events=3),
                     lambda p: p['manifest']['training_records'][0].update(offset=99),
                     lambda p: p['query'].update(target_hz=np.zeros(len(p['query']['fluorescence']))),
                     lambda p: p['training'].update(extra=np.array([1]))]
        for index, mutate in enumerate(mutations):
            packet = self.packet()
            mutate(packet)
            with self.subTest(case=index), self.assertRaises(ValueError):
                m.material_bytes(packet, assets)

    def test_wrong_arm_extra_asset_and_changed_asset_bytes_refused(self):
        packet = self.packet()
        assets = m.capture_assets(self.root, 'paper_data')
        cases = [{**assets, 'private/BANK.json': b'private'}, {**assets, 'paper.xml': b'changed'},
                 m.capture_assets(self.root, 'paper_data_author_code')]
        for index, candidate in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                m.material_bytes(packet, candidate)


class PinnedLoaderControls(unittest.TestCase):
    def test_pinned_current_loader_ignores_ambient_artifact_io_and_restores_path(self):
        before_path = list(sys.path)
        fake = SimpleNamespace(read_json=lambda *a, **k: self.fail('ambient reader imported'))
        with patch.dict(sys.modules, {'artifact_io': fake}):
            current = m.load_current()
            self.assertEqual(current.CONDITION_ID, m.CONDITION_ID)
            self.assertIsNot(current.read_json, fake.read_json)
            self.assertIs(sys.modules['artifact_io'], fake)
        self.assertEqual(sys.path, before_path)

    def test_current_evaluator_and_reader_source_pins_cannot_be_bypassed(self):
        for constant in ('EVALUATOR_SHA256', 'ARTIFACT_IO_SHA256'):
            with self.subTest(constant=constant), patch.object(m, constant, '0' * 64):
                with self.assertRaises(ValueError):
                    m.load_current()

    def test_frozen_asset_manifest_authenticates_and_has_only_source_assets(self):
        descriptor = m._asset_manifest()
        self.assertEqual(len(descriptor['paper']), 1)
        self.assertEqual(len(descriptor['author_code']), 18)
        with patch.object(m, 'ASSETS_SHA256', '0' * 64), self.assertRaises(ValueError):
            m._asset_manifest()


if __name__ == '__main__':
    unittest.main()
