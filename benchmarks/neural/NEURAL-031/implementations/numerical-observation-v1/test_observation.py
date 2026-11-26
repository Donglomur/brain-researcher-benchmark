"""Invented complete-context controls; no authentic inputs, targets or scoring."""
import argparse
import copy
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('numeric031_observation', HERE / 'observation.py')
ob = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ob)
SCRATCH = None
WRITTEN = 0


def write(path, body):
    global WRITTEN
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.chmod(0o644)
    path.write_bytes(body)
    WRITTEN += len(body)


def account(result):
    global WRITTEN
    WRITTEN += result['written_bytes']
    return result


class ObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='generated-neural031-numeric-', dir=SCRATCH)
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.source_sha = ob.pin((HERE / 'SOURCE.json').read_bytes())['sha256']
        cls.engine = ob.Engine(cls.source_sha)
        cls.io = cls.engine.io
        cls.counts = [37, 23, 52, 94, 50, 21, 33, 64, 53, 24, 67, 18, 23, 31, 57, 22, 28, 24, 31, 22]
        ids = np.arange(774, dtype=np.int64)
        cls.groups = np.repeat(np.arange(20, dtype=np.int64), cls.counts)
        common = np.column_stack((1 + ids / 1000, ids % 2, ids % 7 == 0, ids % 11 == 0)).astype(np.float64)
        common[0, 1] = -0.0
        activity = np.column_stack((100 + ids / 31, -200 + ids / 17))
        activity[common[:, 2:].astype(bool)] = np.nan
        activity[5, 0] = -0.0
        cls.y = 1 + ids / 1000
        cls.y[np.arange(0, 731, 17)] = np.nan
        cls.y[1] = -0.0
        assert np.isnan(cls.y).sum() == 43 and np.isfinite(cls.y).sum() == 731
        cls.inputs = cls.root / 'inputs'
        cls.presentations = cls.root / 'presentations'
        cls.captures = cls.root / 'captures'
        cls.support = {'schema': 'neural031_ordinary_public_support_v1', 'candidate_id': 'NEURAL-031',
                       'folds': [], 'request_rows': 774, 'query_targets_included': False}
        cls.synthetic = copy.deepcopy(cls.engine.source_inputs())
        cls.packets, cls.presentation_pins, cls.capture_pins = {}, {}, []
        for fold in range(20):
            train, query = cls.groups != fold, cls.groups == fold
            support_fold = {'fold': fold, 'rowids': ids[query].tolist(), 'views': {}}
            for offset, view in enumerate(('baseline', 'neural')):
                features = common if view == 'baseline' else np.column_stack((common, activity))
                packet = {'train_x': features[train], 'train_y': cls.y[train], 'train_mouse': cls.groups[train],
                          'train_rowid': ids[train], 'query_x': features[query], 'query_rowid': ids[query]}
                cls.packets[fold, view] = packet
                data = cls.io.archive(np, packet)
                manifest = {'schema': 'neural031_ordinary_public_view_v1', 'candidate_id': 'NEURAL-031',
                            'fold': fold, 'held_mouse': cls.engine.endpoint.MICE[fold], 'view': view,
                            'data': ob.pin(data), 'features': ob.COMMON + (
                                ['local_coactivity_norm', 'dendrite_coincident_norm'] if view == 'neural' else []),
                            'training_mouse_indices': [i for i in range(20) if i != fold],
                            'train_rows': int(train.sum()), 'query_rows': int(query.sum()),
                            'training_target': 'next_day_ratio_with_NaN_unavailable',
                            'query_target_or_followup_metadata': False,
                            'neural_activity_values_physically_present': view == 'neural',
                            'prediction_time': 'after_complete_Early_recording_for_next_day_size'}
                manifest_body = cls.io.encoded(manifest)
                directory = cls.inputs / f'fold{fold:02d}' / view
                write(directory / 'data.npz', data)
                write(directory / 'manifest.json', manifest_body)
                selected = {'fold': fold, 'view': view, 'data': ob.pin(data), 'manifest': ob.pin(manifest_body)}
                cls.synthetic['paired_views'][2 * fold + offset] = selected
                support_fold['views'][view] = {k: selected[k] for k in ('data', 'manifest')}
            cls.support['folds'].append(support_fold)
        support_body = cls.io.encoded(cls.support)
        cls.synthetic['support'] = ob.pin(support_body)
        cls.support_path = cls.root / 'support.json'
        write(cls.support_path, support_body)
        # Test-only in-memory source replacement. The production CLI has no
        # alternate-roster argument and retains its exact original public pins.
        cls.engine._source_inputs = cls.synthetic
        for fold in range(20):
            for view in ('baseline', 'neural'):
                relative = f'fold{fold:02d}/{view}'
                present = cls.presentations / relative
                present.parent.mkdir(parents=True, exist_ok=True)
                result = account(cls.engine.present(cls.inputs / relative, fold, view, present))
                cls.presentation_pins[fold, view] = result['presentation']
                observation = cls.io.decode((present / 'OBSERVATION.json').read_bytes())
                response = cls.io.encoded({'schema': 'neural031_direct_response_v1',
                                          'request_id': observation['request_id'],
                                          'rows': [{'row_id': row, 'prediction': 1.0}
                                                   for row in observation['arrays']['query_rowid']]})
                response_path = cls.root / 'incoming' / relative / 'response.json'
                write(response_path, response)
                destination = cls.captures / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                result = account(cls.engine.capture(present, result['presentation'], response_path,
                                                    ob.pin(response), fold, view, destination))
                cls.capture_pins.append({'fold': fold, 'view': view, 'capture': result['capture']})
        cls.inventory = {'schema': 'neural031_numeric_capture_inventory_v1', 'condition': ob.CONDITION,
                         'source_sha256': cls.source_sha, 'captures': cls.capture_pins}
        body = cls.io.encoded(cls.inventory)
        cls.inventory_path = cls.root / 'inventory.json'
        cls.inventory_pin = ob.pin(body)
        write(cls.inventory_path, body)

    @classmethod
    def tearDownClass(cls):
        retained = sum(p.stat().st_size for p in cls.root.rglob('*') if p.is_file())
        failed_writes = sum(p.stat().st_size for failure in cls.root.rglob('FAILED.json')
                            for p in failure.parent.iterdir() if p.is_file())
        print(json.dumps({'scope': 'invented_complete_panel_only', 'contexts': 40,
                          'requested_rows_per_view': 774, 'predictions': 1548,
                          'underlying_observed_ratios': 731, 'underlying_unavailable_ratios': 43,
                          'fixture_write_bytes': WRITTEN + failed_writes, 'retained_before_cleanup': retained,
                          'private_target_reads': 0, 'scores_computed': 0,
                          'model_calls': 0, 'native_or_Docker_runs': 0}))

    def collect(self, name, inventory_path=None, inventory_pin=None):
        return self.engine.collect(self.support_path, self.presentations, self.captures,
                                   inventory_path or self.inventory_path, inventory_pin or self.inventory_pin,
                                   self.root / name)

    def synthetic_context(self, packet=None, manifest_changes=None, extra_array=False):
        engine = ob.Engine(self.source_sha)
        engine._source_inputs = copy.deepcopy(self.synthetic)
        packet = copy.deepcopy(self.packets[0, 'neural']) if packet is None else packet
        if extra_array:
            packet['query_y'] = np.ones(len(packet['query_x']))
        data = self.io.archive(np, packet)
        manifest = self.io.decode((self.inputs / 'fold00/neural/manifest.json').read_bytes())
        manifest['data'] = ob.pin(data)
        manifest.update(manifest_changes or {})
        body = self.io.encoded(manifest)
        engine._source_inputs['paired_views'][1].update(data=ob.pin(data), manifest=ob.pin(body))
        return engine, packet, data, body

    def test_complete_forty_context_roundtrip_and_original_submission_validation(self):
        for (fold, view), packet in self.packets.items():
            body = (self.presentations / f'fold{fold:02d}/{view}/OBSERVATION.json').read_bytes()
            observation = self.io.decode(body)
            self.assertEqual(set(observation), {'schema', 'candidate_id', 'access_condition', 'request_id',
                                               'instructions', 'context', 'arrays'})
            self.assertEqual(set(observation['arrays']), set(ob.KEYS))
            self.assertNotIn(str(self.root).encode(), body)
            self.assertNotIn(b'support.json', body)
            self.assertEqual(observation['context']['training_mouse_indices'], [i for i in range(20) if i != fold])
            for key, original in packet.items():
                restored = np.asarray(observation['arrays'][key], dtype=original.dtype)
                self.assertTrue(np.array_equal(restored, original, equal_nan=True), (fold, view, key))
                if original.dtype.kind == 'f':
                    finite = np.isfinite(original)
                    self.assertTrue(np.array_equal(np.signbit(restored[finite]), np.signbit(original[finite])))
            self.assertLessEqual(len(body), ob.OBSERVATION_CAP)
        result = account(self.collect('complete'))
        directory = self.root / 'complete'
        bundle = self.io.decode((directory / 'submission.json').read_bytes())
        self.assertEqual(len(self.engine.endpoint.validate_all(bundle, self.support)), 40)
        self.assertEqual(sum(len(row['rows']) for row in bundle['outputs']), 1548)
        self.assertEqual(sum(np.isnan(p['train_y']).sum() for p in self.packets.values()), 1634)
        record = self.io.decode((directory / 'COLLECTION.json').read_bytes())
        self.assertEqual(record['capture_inventory'], self.inventory_pin)
        self.assertFalse(record['fresh_model_contexts_verified'])
        self.assertFalse(record['no_tools_enforced'])
        self.assertEqual(record['scores_computed'], 0)
        self.assertEqual(ob.pin((directory / 'COLLECTION.json').read_bytes()), result['collection'])

    def test_finite_extremes_signed_zero_and_missing_values_roundtrip(self):
        packet = copy.deepcopy(self.packets[0, 'neural'])
        finite = np.where(np.isfinite(packet['train_x'][:, 4]))[0][:3]
        packet['train_x'][finite, 4] = [np.finfo(np.float64).max, np.nextafter(0.0, 1.0), -0.0]
        packet['train_y'][0] = -0.0
        engine, _, data, manifest = self.synthetic_context(packet)
        first = engine.presentation(data, manifest, 0, 'neural')
        self.assertEqual(first, engine.presentation(data, manifest, 0, 'neural'))
        value = self.io.decode(first)['arrays']
        restored = np.asarray(value['train_x'], dtype=np.float64)
        self.assertTrue(np.array_equal(restored, packet['train_x'], equal_nan=True))
        self.assertTrue(np.signbit(restored[finite[2], 4]))
        self.assertTrue(np.signbit(value['train_y'][0]))
        self.assertTrue(any(v is None for v in value['train_y']))
        self.assertNotIn(b':NaN', first)
        self.assertNotIn(b',NaN', first)

    def test_wrong_input_pins_and_cross_context_refuse_before_decode(self):
        directory = self.inputs / 'fold00/baseline'
        data, manifest = (directory / 'data.npz').read_bytes(), (directory / 'manifest.json').read_bytes()
        with patch.object(self.engine.io, 'arrays', side_effect=AssertionError('must not decode')):
            for changed, body, fold, view in ((data + b'x', manifest, 0, 'baseline'),
                                             (data, manifest + b' ', 0, 'baseline'),
                                             (data, manifest, 1, 'baseline'),
                                             (data, manifest, 0, 'neural')):
                with self.subTest(fold=fold, view=view), self.assertRaises(ValueError):
                    self.engine.presentation(changed, body, fold, view)

    def test_physical_view_semantics_refuse_added_targets_and_changed_missingness(self):
        mutations = ['query_y', 'missingness', 'infinity', 'held_training_group', 'training_label', 'query_order']
        for mutation in mutations:
            packet = copy.deepcopy(self.packets[0, 'neural'])
            if mutation == 'missingness': packet['query_x'][0, 2] = 0
            if mutation == 'infinity': packet['train_x'][0, 4] = np.inf
            if mutation == 'held_training_group': packet['train_mouse'][0] = 0
            if mutation == 'training_label': packet['train_y'][0] = np.inf
            if mutation == 'query_order': packet['query_rowid'] = packet['query_rowid'][::-1]
            engine, _, data, manifest = self.synthetic_context(packet, extra_array=mutation == 'query_y')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                engine.presentation(data, manifest, 0, 'neural')
        engine, _, data, manifest = self.synthetic_context(manifest_changes={'query_target_or_followup_metadata': True})
        with self.assertRaises(ValueError): engine.presentation(data, manifest, 0, 'neural')

    def test_one_context_presentation_reads_only_its_two_public_files(self):
        opened = []
        real = self.engine.io.read
        def record(path, *args):
            opened.append(Path(path))
            return real(path, *args)
        selected = self.inputs / 'fold00/baseline'
        with patch.object(self.engine.io, 'read', side_effect=record):
            account(self.engine.present(selected, 0, 'baseline', self.root / 'isolated-presentation'))
        self.assertEqual(opened, [selected / 'manifest.json', selected / 'data.npz'])
        alias = self.root / 'input-alias'; alias.symlink_to(selected, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.engine.present(alias, 0, 'baseline', self.root / 'bad-symlink')
        self.assertFalse((self.root / 'bad-symlink').exists())

    def test_malformed_first_response_is_retained_and_cannot_be_replaced(self):
        path = self.root / 'malformed-response.json'
        write(path, b'{not JSON')
        output = self.root / 'failed-first'
        with self.assertRaises(ValueError):
            self.engine.capture(self.presentations / 'fold00/baseline', self.presentation_pins[0, 'baseline'],
                                path, ob.pin(path.read_bytes()), 0, 'baseline', output)
        self.assertEqual((output / 'FIRST_RESPONSE.bin').read_bytes(), b'{not JSON')
        self.assertTrue((output / 'FAILED.json').is_file())
        self.assertFalse((output / 'CAPTURE.json').exists())
        valid = self.root / 'incoming/fold00/baseline/response.json'
        with self.assertRaises(FileExistsError):
            self.engine.capture(self.presentations / 'fold00/baseline', self.presentation_pins[0, 'baseline'],
                                valid, ob.pin(valid.read_bytes()), 0, 'baseline', output)

    def test_cross_context_and_invalid_response_rows_are_retained_failures(self):
        original = self.io.decode((self.root / 'incoming/fold00/baseline/response.json').read_bytes())
        cases = []
        for relative in ['fold01/baseline', 'fold00/neural']:
            cases.append(self.io.decode((self.root / 'incoming' / relative / 'response.json').read_bytes()))
        for mutation in ['missing', 'order', 'duplicate', 'boolean', 'negative', 'extra']:
            value = copy.deepcopy(original)
            if mutation == 'missing': value['rows'].pop()
            if mutation == 'order': value['rows'].reverse()
            if mutation == 'duplicate': value['rows'][1] = value['rows'][0]
            if mutation == 'boolean': value['rows'][0]['prediction'] = True
            if mutation == 'negative': value['rows'][0]['prediction'] = -1
            if mutation == 'extra': value['query_targets'] = []
            cases.append(value)
        for index, value in enumerate(cases):
            body = self.io.encoded(value)
            response = self.root / f'rejected-response-{index}.json'; write(response, body)
            destination = self.root / f'rejected-capture-{index}'
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.engine.capture(self.presentations / 'fold00/baseline', self.presentation_pins[0, 'baseline'],
                                    response, ob.pin(body), 0, 'baseline', destination)
            self.assertEqual((destination / 'FIRST_RESPONSE.bin').read_bytes(), body)
            self.assertTrue((destination / 'FAILED.json').exists())

    def test_complete_collection_rejects_missing_extra_and_changed_contexts(self):
        directory = self.captures / 'fold00/baseline'
        capture_path = directory / 'CAPTURE.json'
        saved = capture_path.read_bytes()
        try:
            capture_path.unlink()
            with self.assertRaises(ValueError): self.collect('missing-capture')
            write(capture_path, saved)
            extra = directory / 'extra.json'; write(extra, b'{}')
            with self.assertRaises(ValueError): self.collect('extra-capture')
            extra.unlink()
            write(capture_path, (self.captures / 'fold01/baseline/CAPTURE.json').read_bytes())
            with self.assertRaises(ValueError): self.collect('swapped-capture')
        finally:
            write(capture_path, saved)
        for name in ['missing-capture', 'extra-capture', 'swapped-capture']:
            self.assertFalse((self.root / name).exists())

    def test_consistent_replacement_cannot_borrow_selected_capture_inventory(self):
        directory = self.captures / 'fold00/baseline'
        saved = {name: (directory / name).read_bytes() for name in
                 ['FIRST_RESPONSE.bin', 'predictions.json', 'CAPTURE.json']}
        response = self.io.decode(saved['FIRST_RESPONSE.bin'])
        response['rows'][0]['prediction'] = 99.0
        response_body = self.io.encoded(response)
        prediction = self.io.decode(saved['predictions.json'])
        prediction['rows'] = response['rows']
        prediction_body = self.io.encoded(prediction)
        capture = self.io.decode(saved['CAPTURE.json'])
        capture.update(response=ob.pin(response_body), prediction=ob.pin(prediction_body))
        try:
            write(directory / 'FIRST_RESPONSE.bin', response_body)
            write(directory / 'predictions.json', prediction_body)
            write(directory / 'CAPTURE.json', self.io.encoded(capture))
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                self.collect('rewritten-first')
        finally:
            for name, body in saved.items(): write(directory / name, body)
        self.assertFalse((self.root / 'rewritten-first').exists())

    def test_inventory_must_be_complete_ordered_and_externally_selected(self):
        for label in ['missing', 'reordered', 'duplicate', 'changed_pin']:
            value = copy.deepcopy(self.inventory)
            if label == 'missing': value['captures'].pop()
            if label == 'reordered': value['captures'].reverse()
            if label == 'duplicate': value['captures'][1] = value['captures'][0]
            if label == 'changed_pin': value['captures'][0]['capture']['sha256'] = '0' * 64
            body = self.io.encoded(value)
            path = self.root / ('inventory-' + label + '.json'); write(path, body)
            with self.subTest(label=label), self.assertRaises(ValueError):
                self.collect('bad-inventory-' + label, path, ob.pin(body))
            with self.assertRaises(ValueError): self.collect('unselected-' + label, path, self.inventory_pin)

    def test_selected_source_and_presentation_pins_are_required(self):
        with self.assertRaisesRegex(ValueError, 'source manifest'): ob.Engine('0' * 64)
        original = ob.raw_read
        def changed(path, cap):
            body = original(path, cap)
            return body + b' ' if str(path).endswith('paired-delivery-v1/io031.py') else body
        with patch.object(ob, 'raw_read', side_effect=changed), self.assertRaisesRegex(ValueError, 'dependency'):
            ob.Engine(self.source_sha)
        response = self.root / 'never-read-response'
        with self.assertRaises(ValueError):
            self.engine.capture(self.presentations / 'fold00/baseline', {'bytes': 1, 'sha256': '0' * 64},
                                response, {'bytes': 1, 'sha256': '0' * 64}, 0, 'baseline', self.root / 'wrong-presentation')
        self.assertFalse((self.root / 'wrong-presentation').exists())

    def test_cli_routes_complete_collection_and_rejects_unselected_source(self):
        args = ['--source-sha256', self.source_sha, 'collect', '--support', str(self.support_path),
                '--presentations', str(self.presentations), '--captures', str(self.captures),
                '--inventory', str(self.inventory_path), '--inventory-bytes', str(self.inventory_pin['bytes']),
                '--inventory-sha256', self.inventory_pin['sha256'], '--output', str(self.root / 'cli-collected')]
        with patch.object(ob, 'Engine', return_value=self.engine), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(ob.main(args), 0)
        account(json.loads(out.getvalue()))
        with redirect_stderr(io.StringIO()) as err:
            self.assertEqual(ob.main(['--source-sha256', '0' * 64, 'present', '--input', '/never-read',
                                      '--fold', '0', '--view', 'baseline', '--output', str(self.root / 'no-output')]), 2)
        self.assertIn('source manifest', err.getvalue())
        self.assertFalse((self.root / 'no-output').exists())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch-root', type=Path)
    args, remaining = parser.parse_known_args()
    SCRATCH = args.scratch_root
    if SCRATCH is not None and not SCRATCH.is_dir():
        parser.error('--scratch-root must be an existing directory')
    unittest.main(argv=[sys.argv[0]] + remaining, verbosity=2)
