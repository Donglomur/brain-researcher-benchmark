"""Ordinary generated controls for program freezing and post-closure collection.

These tests simulate trusted lifecycle observations. They do not run a program,
container, model, authentic data export, or scientific metric.
"""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import collect as collector
import contract as c
import materials as m
from test_materials import generated_arrays, generated_bank


def source_tree(root, label):
    root.mkdir()
    (root / 'program.py').write_bytes(('"""Generated program ' + label + '."""\n').encode())
    (root / 'helpers').mkdir()
    (root / 'helpers' / 'settings.py').write_bytes(('LABEL = ' + repr(label) + '\n').encode())
    return root


def npy_bytes(vector):
    stream = io.BytesIO()
    np.save(stream, np.asarray(vector, dtype='<f8'), allow_pickle=False)
    return stream.getvalue()


def output_metadata(binding):
    return {'schema': 'spinal_current_fold_prediction_v1', 'condition_id': c.CONDITION,
            'held_neuron': binding['held_neuron'], 'arm': binding['arm'], 'purpose': binding['purpose'],
            'program_seal_sha256': binding['program_seal']['sha256'],
            'binding_sha256': c.pin(c.encoded(binding))['sha256'],
            'unit': binding['output_unit'],
            'query_recording_ids': [row['recording_id'] for row in binding['query_records']]}


def successful_closure():
    return {'status': 'captured', 'all_resources_closed': True, 'cli_reaped': True,
            'candidate_closed_before_capture': True,
            'natural_exit': {'Status': 'exited', 'Running': False, 'Dead': False,
                             'Pid': 0, 'ExitCode': 0, 'OOMKilled': False},
            'closures': [{'kind': 'container', 'closed': True}, {'kind': 'container', 'closed': True},
                         {'kind': 'volume', 'closed': True}]}


class FreezePairControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='spinal-freeze-generated-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.a = source_tree(self.root / 'a', 'arm_a')
        self.b = source_tree(self.root / 'b', 'arm_b')
        self.pair, self.contents = c.freeze_pair(self.a, self.b, 'improvement', 'hz')

    def test_both_complete_source_trees_and_configs_are_frozen(self):
        c.check_pair(self.pair, self.contents)
        self.assertEqual(set(self.pair['arms']), {'paper_data', 'paper_data_author_code'})
        for arm in c.ARMS:
            seal = self.pair['arms'][arm]['seal']
            self.assertEqual({row['path'] for row in seal['files']}, {'program.py', 'helpers/settings.py'})
            self.assertEqual(set(self.contents[arm]), {'program.py', 'helpers/settings.py', 'config.json'})
            config = json.loads(self.contents[arm]['config.json'])
            self.assertEqual(config, seal['configuration'])
            self.assertEqual(config['arm'], arm)
            self.assertEqual(config['purpose'], 'improvement')
            self.assertEqual(config['output_unit'], 'hz')
            self.assertEqual(config['training_policy'], 'eligible_same_cohort_except_entire_held_neuron')
        self.assertNotEqual(self.contents[c.ARMS[0]]['program.py'], self.contents[c.ARMS[1]]['program.py'])

    def test_source_changes_do_not_rewrite_snapshot_and_recapture_is_refused(self):
        original = self.contents['paper_data']['helpers/settings.py']
        (self.a / 'helpers' / 'settings.py').write_bytes(b'LABEL = "changed_after_freeze"\n')
        self.assertEqual(self.contents['paper_data']['helpers/settings.py'], original)
        c.check_pair(self.pair, self.contents)
        recaptured = deepcopy(self.contents)
        recaptured['paper_data'] = c.source_files(self.a) | {'config.json': self.contents['paper_data']['config.json']}
        with self.assertRaises(ValueError):
            c.check_pair(self.pair, recaptured)

    def test_changed_or_missing_frozen_source_file_refused_in_either_arm(self):
        for arm in c.ARMS:
            for change in ('changed', 'missing'):
                contents = deepcopy(self.contents)
                if change == 'changed':
                    contents[arm]['program.py'] += b'# updated program\n'
                else:
                    del contents[arm]['helpers/settings.py']
                with self.subTest(arm=arm, change=change), self.assertRaises(ValueError):
                    c.check_pair(self.pair, contents)

    def test_changed_config_bytes_or_sealed_configuration_refused(self):
        for arm in c.ARMS:
            contents = deepcopy(self.contents)
            cfg = json.loads(contents[arm]['config.json'])
            cfg['output_unit'] = 'expected_spikes_per_bin'
            contents[arm]['config.json'] = c.encoded(cfg)
            with self.subTest(arm=arm, change='bytes'), self.assertRaises(ValueError):
                c.check_pair(self.pair, contents)
            pair = deepcopy(self.pair)
            pair['arms'][arm]['seal']['configuration']['purpose'] = 'reproduction'
            with self.subTest(arm=arm, change='seal'), self.assertRaises(ValueError):
                c.check_pair(pair, self.contents)

    def test_single_arm_cannot_satisfy_paired_freeze(self):
        pair = deepcopy(self.pair)
        del pair['arms']['paper_data_author_code']
        with self.assertRaises(ValueError):
            c.check_pair(pair, self.contents)

    def test_supported_reproduction_count_unit_is_bound_in_both_configs(self):
        pair, contents = c.freeze_pair(self.a, self.b, 'reproduction', 'expected_spikes_per_bin')
        c.check_pair(pair, contents)
        for arm in c.ARMS:
            cfg = pair['arms'][arm]['seal']['configuration']
            self.assertEqual((cfg['purpose'], cfg['output_unit']), ('reproduction', 'expected_spikes_per_bin'))


class FoldCollectorControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = m.load_current()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='spinal-collect-generated-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        a = source_tree(self.root / 'a', 'a')
        b = source_tree(self.root / 'b', 'b')
        self.pair, self.contents = c.freeze_pair(a, b, 'improvement', 'hz')
        self.bank = generated_bank()
        packet = m.build_materials(self.bank, 'g00', 'paper_data', 'improvement', array_loader=generated_arrays)
        files = {'FOLD.json': c.encoded(packet['manifest']), 'paper.xml': b'<article>generated</article>'}
        for role in ('training', 'query'):
            stream = io.BytesIO()
            np.savez(stream, **packet[role])
            files[role + '.npz'] = stream.getvalue()
        self.binding = c.fold_binding(self.pair, 'paper_data', packet['manifest'], files)
        self.total = sum(row['samples'] for row in self.binding['query_records'])
        self.vector = np.arange(self.total, dtype='<f8') / 10
        self.capture = self.root / 'captured'
        self.capture.mkdir()
        self.result = self.write_capture(self.binding, self.vector)

    def write_capture(self, binding, vector, metadata=None):
        bodies = {'fold.json': c.encoded(output_metadata(binding) if metadata is None else metadata),
                  'predictions.npy': npy_bytes(vector)}
        result = successful_closure()
        result['outputs'] = []
        for name, body in bodies.items():
            (self.capture / name).write_bytes(body)
            result['outputs'].append({'path': name, **c.pin(body)})
        return result

    def collect(self, binding=None, result=None):
        return collector.collect_fold(self.binding if binding is None else binding,
                                      self.result if result is None else result, self.capture, self.current)

    def test_complete_fold_vectors_are_split_at_original_record_boundaries(self):
        values = self.collect()
        self.assertEqual(list(values), [row['recording_id'] for row in self.binding['query_records']])
        for row in self.binding['query_records']:
            start = row['offset']
            np.testing.assert_array_equal(values[row['recording_id']], self.vector[start:start + row['samples']])
            self.assertEqual(values[row['recording_id']].shape, (row['samples'],))
            self.assertEqual(values[row['recording_id']].dtype, np.dtype('<f8'))

    def test_unclosed_or_failed_lifecycle_refused_before_any_capture_read(self):
        for key, value in (('status', 'failed'), ('all_resources_closed', False),
                           ('cli_reaped', False), ('candidate_closed_before_capture', False)):
            result = deepcopy(self.result)
            result[key] = value
            with self.subTest(key=key), patch.object(self.current, 'read_pinned') as reader:
                with self.assertRaises(ValueError):
                    self.collect(result=result)
                reader.assert_not_called()

    def test_nonzero_oom_or_missing_resource_closure_refused(self):
        cases = []
        for field, value in (('ExitCode', 1), ('OOMKilled', True), ('Running', True)):
            result = deepcopy(self.result)
            result['natural_exit'][field] = value
            cases.append(result)
        result = deepcopy(self.result)
        result['closures'].pop()
        cases.append(result)
        result = deepcopy(self.result)
        result['closures'][1]['closed'] = False
        cases.append(result)
        for index, result in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                self.collect(result=result)

    def test_candidate_metadata_must_match_program_binding_arm_unit_and_order(self):
        changes = {'program_seal_sha256': 'b' * 64, 'binding_sha256': 'c' * 64,
                   'arm': 'paper_data_author_code', 'purpose': 'reproduction',
                   'unit': 'expected_spikes_per_bin', 'held_neuron': 'g01',
                   'query_recording_ids': list(reversed(output_metadata(self.binding)['query_recording_ids']))}
        for key, value in changes.items():
            metadata = output_metadata(self.binding)
            metadata[key] = value
            result = self.write_capture(self.binding, self.vector, metadata)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.collect(result=result)

    def test_missing_or_extra_full_vector_samples_refused(self):
        for vector in (self.vector[:-1], np.append(self.vector, 999.)):
            result = self.write_capture(self.binding, vector)
            with self.subTest(samples=len(vector)), self.assertRaises(ValueError):
                self.collect(result=result)

    def test_nonfinite_context_bins_preserved_without_changing_fixed_support(self):
        vector = self.vector.copy()
        for row in self.binding['query_records']:
            start, n = row['offset'], row['samples']
            vector[start:start + 32] = np.nan
            vector[start + n - 32:start + n] = np.nan
        result = self.write_capture(self.binding, vector)
        values = self.collect(result=result)
        for row in self.binding['query_records']:
            prediction = values[row['recording_id']]
            self.assertTrue(np.isnan(prediction[:32]).all())
            self.assertTrue(np.isnan(prediction[-32:]).all())
            self.assertTrue(np.isfinite(prediction[32:-32]).all())
            self.assertEqual(len(prediction), row['samples'])

    def test_first_and_last_scored_bins_must_be_finite_for_each_record(self):
        for row in self.binding['query_records']:
            for within in (32, row['samples'] - 33):
                vector = self.vector.copy()
                vector[row['offset'] + within] = np.nan
                result = self.write_capture(self.binding, vector)
                with self.subTest(record=row['recording_id'], bin=within), self.assertRaises(ValueError):
                    self.collect(result=result)

    def test_boundary_offsets_and_short_recording_cannot_change_support(self):
        for change in ('offset', 'short'):
            binding = deepcopy(self.binding)
            if change == 'offset':
                binding['query_records'][1]['offset'] += 1
            else:
                binding['query_records'][0]['samples'] = 64
                binding['query_records'][1]['offset'] = 64
            total = sum(row['samples'] for row in binding['query_records'])
            result = self.write_capture(binding, np.arange(total, dtype=float))
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.collect(binding=binding, result=result)

    def test_changed_captured_prediction_bytes_refused(self):
        (self.capture / 'predictions.npy').write_bytes(npy_bytes(self.vector + 1))
        with self.assertRaises(ValueError):
            self.collect()


class CandidateManifestControls(unittest.TestCase):
    def setUp(self):
        self.bank = generated_bank()
        self.bank.eligible = [row for row in self.bank.metadata['recordings'] if row['status'] == 'prepared']
        self.rows = [{'recording_id': row['recording_id'],
                      'payload': {'path': f'prediction-{index:03d}.npz', 'bytes': 123, 'sha256': 'd' * 64}}
                     for index, row in enumerate(self.bank.eligible)]

    def test_complete116_manifest_preserves_bank_and_candidate_only_role(self):
        manifest = collector.manifest(self.bank, 'hz', self.rows, 'Generated collector control only')
        self.assertEqual(manifest['recordings'], self.rows)
        self.assertEqual(manifest['bank_manifest_sha256'], self.bank.manifest_sha256)
        self.assertEqual(manifest['role'], 'candidate')
        self.assertEqual(manifest['methods'], {'candidate': 'hz'})
        self.assertEqual(len(manifest['recordings']), 116)
        self.assertEqual(manifest['condition_id'], m.CONDITION_ID)

    def test_incomplete_duplicate_extra_or_source_excluded_record_refused(self):
        duplicate = deepcopy(self.rows)
        duplicate[-1] = deepcopy(duplicate[0])
        excluded = deepcopy(self.rows)
        excluded[-1]['recording_id'] = next(row['recording_id'] for row in self.bank.metadata['recordings']
                                            if row['status'] != 'prepared')
        for label, rows in (('missing', self.rows[:-1]), ('duplicate', duplicate),
                            ('extra', self.rows + [deepcopy(self.rows[0])]), ('excluded', excluded)):
            with self.subTest(case=label), self.assertRaises(ValueError):
                collector.manifest(self.bank, 'hz', rows, 'Generated control')

    def test_manifest_unit_is_an_explicit_rate_unit(self):
        value = collector.manifest(self.bank, 'expected_spikes_per_bin', self.rows, 'Generated control')
        self.assertEqual(value['methods'], {'candidate': 'expected_spikes_per_bin'})
        with self.assertRaises(ValueError):
            collector.manifest(self.bank, 'arbitrary', self.rows, 'Generated control')


if __name__ == '__main__':
    unittest.main()
