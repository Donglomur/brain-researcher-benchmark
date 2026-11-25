"""Generated complete-cohort controls; no authentic identities or observations."""
import copy
import importlib.util
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('delivery_under_test', HERE / 'delivery.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def fixture():
    mice, cells, context = [], [], []
    for group_index, (group, (nmice, ncells)) in enumerate(d.s.GROUPS.items()):
        for mouse_index in range(nmice):
            mid = f'generated-group{group_index}-mouse{mouse_index}'
            mice.append({'mouse_id': mid, 'group': group})
            context.append({'mouse_id': mid, 'sessions': [
                {'session': session, 'acquisition_seconds_relative_to_session9':
                 (session - 9) * 3600, 'zeitgeber_hours': None}
                for session in range(1, 22)]})
            for neuron in range(ncells // nmice + (mouse_index < ncells % nmice)):
                cells.append({'mouse_id': mid, 'neuron_id': f'generated-neuron{neuron}',
                              'valid_stable_seconds': [20] * 63,
                              'event_counts': [0] * 27 + [1] * 36,
                              'missing_reasons': [None] * 63})
    targets = {'schema': 'hypodrift-targets-v1', 'task_id': d.s.TASK_ID,
               'states': d.s.STATES[:], 'sessions': list(range(1, 22)),
               'producer_receipt_sha256': 'a' * 64, 'cohort_receipt_sha256': 'b' * 64,
               'mice': mice, 'cells': cells}
    contexts = {'schema': 'hypodrift-context-v1', 'task_id': d.s.TASK_ID,
                'source_receipt_sha256': 'c' * 64, 'mice': context}
    return targets, contexts


def forecast(binding):
    return {'schema': 'hypodrift-held-forecast-v1', 'task_id': d.s.TASK_ID,
            'mouse_id': binding['held_mouse']['mouse_id'],
            'packet_sha256': binding['packet_sha256'],
            'sessions': list(range(10, 22)), 'states': d.s.STATES[:],
            'cells': [{'neuron_id': nid, 'log_rates': [math.log(4)] * 36}
                      for nid in binding['neuron_ids']]}


class DeliveryControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.targets, cls.context = fixture()
        cls.th = d.digest(d.canonical_bytes(cls.targets))
        cls.ch = d.digest(d.canonical_bytes(cls.context))
        cls.bindings = []
        for mouse in cls.targets['mice']:
            packet = d.build_packet(cls.targets, cls.context, mouse['mouse_id'])
            cls.bindings.append(d.make_binding(packet, cls.targets, cls.context, cls.th, cls.ch))
        cls.forecasts = [forecast(binding) for binding in cls.bindings]
        cls.mid = cls.targets['mice'][0]['mouse_id']

    def packet(self, targets=None, context=None):
        return d.build_packet(self.targets if targets is None else targets,
                              self.context if context is None else context, self.mid)

    def test_complete_same_group_training_and_only_nine_held_sessions(self):
        packet = self.packet()
        training, calibration = packet['training'], packet['calibration']
        held_group = packet['held_mouse']['group']
        self.assertEqual(len(training['mice']), d.s.GROUPS[held_group][0] - 1)
        self.assertTrue(all(m['group'] == held_group for m in training['mice']))
        self.assertNotIn(self.mid, [m['mouse_id'] for m in training['mice']])
        self.assertTrue(all(c['mouse_id'] != self.mid for c in training['cells']))
        self.assertTrue(all(c['mouse_id'] == self.mid for c in calibration['cells']))
        self.assertEqual(len(training['cells']) + len(calibration['cells']),
                         d.s.GROUPS[held_group][1])
        for binding in self.bindings:
            mid = binding['held_mouse']['mouse_id']
            group = binding['held_mouse']['group']
            self.assertEqual(set(binding['training_mouse_ids']),
                             {m['mouse_id'] for m in self.targets['mice']
                              if m['mouse_id'] != mid and m['group'] == group})
        self.assertTrue(all(len(c['event_counts']) == 63 for c in training['cells']))
        self.assertTrue(all(c['event_counts'] == [0] * 27 for c in calibration['cells']))
        self.assertEqual(calibration['sessions'], list(range(1, 10)))
        self.assertEqual(packet['forecast_request']['sessions'], list(range(10, 22)))
        self.assertNotIn(self.th.encode(), d.canonical_bytes(packet))

    def test_held_future_counts_exposure_missingness_and_receipts_do_not_change_packet(self):
        changed = copy.deepcopy(self.targets)
        changed['producer_receipt_sha256'] = 'f' * 64
        changed['cohort_receipt_sha256'] = 'e' * 64
        for cell in changed['cells']:
            if cell['mouse_id'] == self.mid:
                cell['event_counts'][27:] = [None, 7654321, 0] * 12
                cell['valid_stable_seconds'][27:] = [None, 50, 0] * 12
                cell['missing_reasons'][27:] = ['future-secret-marker', None, None] * 12
        first, second = self.packet(), self.packet(changed)
        self.assertEqual(d.canonical_bytes(first), d.canonical_bytes(second))
        self.assertNotIn(b'future-secret-marker', d.canonical_bytes(second))
        self.assertNotEqual(d.digest(d.canonical_bytes(changed)), self.th)

    def test_other_groups_observations_and_context_do_not_change_packet(self):
        targets, context = copy.deepcopy(self.targets), copy.deepcopy(self.context)
        group = next(m['group'] for m in targets['mice'] if m['mouse_id'] == self.mid)
        others = {m['mouse_id'] for m in targets['mice'] if m['group'] != group}
        for cell in targets['cells']:
            if cell['mouse_id'] in others:
                cell['event_counts'] = [None] * 63
                cell['valid_stable_seconds'] = [None] * 63
                cell['missing_reasons'] = ['other-group-not-permitted'] * 63
        for mouse in context['mice']:
            if mouse['mouse_id'] in others:
                for session in mouse['sessions']:
                    session['acquisition_seconds_relative_to_session9'] = None
                    session['zeitgeber_hours'] = 7.5
        self.assertEqual(d.canonical_bytes(self.packet()),
                         d.canonical_bytes(self.packet(targets, context)))

    def test_calibration_missing_is_null_and_copy_does_not_alias_source(self):
        changed = copy.deepcopy(self.targets)
        changed['cells'][0]['event_counts'][0] = None
        changed['cells'][0]['valid_stable_seconds'][0] = None
        changed['cells'][0]['missing_reasons'][0] = 'known calibration missing'
        packet = self.packet(changed)
        first = next(c for c in packet['calibration']['cells']
                     if c['neuron_id'] == changed['cells'][0]['neuron_id'])
        self.assertIsNone(first['event_counts'][0])
        first['event_counts'][1] = 54321
        self.assertEqual(changed['cells'][0]['event_counts'][1], 0)

    def test_context_unknowns_not_imputed_and_injection_refused(self):
        context = copy.deepcopy(self.context)
        context['mice'][0]['sessions'][9]['acquisition_seconds_relative_to_session9'] = None
        row = self.packet(context=context)['forecast_request']['context'][0]
        self.assertIsNone(row['acquisition_seconds_relative_to_session9'])
        self.assertIsNone(row['zeitgeber_hours'])
        self.assertEqual(row['condition'], 'acute_recovery')
        context['mice'][0]['sessions'][9]['future_exposure_seconds'] = 100
        with self.assertRaises(d.s.ContractError):
            self.packet(context=context)

    def test_context_clock_units_identity_and_chronology_are_checked(self):
        cases = [
            ('session', 10.0), ('zeitgeber_hours', 24), ('zeitgeber_hours', True),
            ('zeitgeber_hours', float('nan')),
            ('acquisition_seconds_relative_to_session9', -1),
            ('acquisition_seconds_relative_to_session9', 7200),
        ]
        for key, value in cases:
            context = copy.deepcopy(self.context)
            context['mice'][0]['sessions'][9][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(d.s.ContractError):
                self.packet(context=context)
        context = copy.deepcopy(self.context)
        context['mice'][1]['mouse_id'] = self.mid
        with self.assertRaises(d.s.ContractError):
            self.packet(context=context)

    def test_all31_case_outputs_join_into_unchanged_scorer(self):
        # Reversal is intentional: collection must use biological identity, not position.
        prediction = d.join_forecasts(list(reversed(self.forecasts)), self.bindings)
        comparator = {'schema': 'hypodrift-comparator-v1', 'reference_id': 'generated-only',
                      'selection_receipt_sha256': 'd' * 64,
                      'prediction': copy.deepcopy(prediction)}
        for cell in comparator['prediction']['cells']:
            cell['log_rates'] = [0.0] * 36
        result = d.s.score(prediction, self.targets, comparator)
        self.assertEqual(result['candidate_mse'], 0)
        self.assertAlmostEqual(result['reference_mse'], math.log(4) ** 2)
        self.assertEqual(result['cohort']['eligible_future_state_slots'], 59796)
        self.assertEqual(sum(m['eligible_neuron_denominator'] for m in result['mice']), 1661)

    def test_foreign_packet_cell_and_cohort_refused(self):
        forecasts = copy.deepcopy(self.forecasts)
        forecasts[0]['packet_sha256'] = '0' * 64
        with self.assertRaises(d.s.ContractError):
            d.join_forecasts(forecasts, self.bindings)
        forecasts = copy.deepcopy(self.forecasts)
        forecasts[0]['cells'][0]['neuron_id'] = 'foreign'
        with self.assertRaises(d.s.ContractError):
            d.join_forecasts(forecasts, self.bindings)
        bindings = copy.deepcopy(self.bindings)
        bindings[0]['targets_document_sha256'] = '0' * 64
        with self.assertRaises(d.s.ContractError):
            d.join_forecasts(self.forecasts, bindings)
        bindings = copy.deepcopy(self.bindings)
        # Same count is insufficient: replacing one peer with a foreign-group
        # mouse must fail even with otherwise coherent public packet hashes.
        foreign = next(m['mouse_id'] for m in self.targets['mice']
                       if m['group'] != bindings[0]['held_mouse']['group'])
        bindings[0]['training_mouse_ids'][0] = foreign
        with self.assertRaises(d.s.ContractError):
            d.join_forecasts(self.forecasts, bindings)

    def test_no_missing_future_vectors_and_no_duplicate_outer_mouse(self):
        for value in (None, True, -1, float('inf')):
            forecasts = copy.deepcopy(self.forecasts)
            forecasts[0]['cells'][0]['log_rates'][0] = value
            with self.subTest(value=value), self.assertRaises(d.s.ContractError):
                d.admit_forecasts(forecasts)
        forecasts = copy.deepcopy(self.forecasts)
        forecasts[0]['cells'][0]['log_rates'].pop()
        with self.assertRaises(d.s.ContractError):
            d.admit_forecasts(forecasts)
        forecasts = copy.deepcopy(self.forecasts)
        forecasts[-1] = forecasts[0]
        with self.assertRaises(d.s.ContractError):
            d.admit_forecasts(forecasts)

    def test_invalid_submission_precedes_private_binding_open(self):
        calls = []
        def read(path, expected=None):
            calls.append(path)
            if path != 'PUBLIC':
                self.fail('opened private binding before output syntax admission')
            return [], '0' * 64
        with patch.object(d.s, 'read_document', read), self.assertRaises(d.s.ContractError):
            d.main(['join', '--forecasts', 'PUBLIC', '--bindings', 'PRIVATE',
                    '--bindings-sha256', 'a' * 64, '--output', 'OUT'])
        self.assertEqual(calls, ['PUBLIC'])

    def test_real_cli_export_and_join_from_different_cwd_private_create_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = {'targets': self.targets, 'context': self.context,
                    'forecasts': self.forecasts, 'bindings': self.bindings}
            for name, doc in docs.items():
                (root / name).write_bytes(d.canonical_bytes(doc))
            export = [sys.executable, '-I', '-S', '-B', str(HERE / 'delivery.py'), 'export',
                      '--targets', str(root / 'targets'), '--targets-sha256', self.th,
                      '--context', str(root / 'context'), '--context-sha256', self.ch,
                      '--held-mouse', self.mid, '--packet-output', str(root / 'packet'),
                      '--binding-output', str(root / 'binding')]
            old = os.umask(0)
            try:
                subprocess.run(export, cwd=tmp, check=True, capture_output=True, timeout=20)
            finally:
                os.umask(old)
            self.assertEqual((root / 'packet').read_bytes(), d.canonical_bytes(self.packet()))
            for name in ('packet', 'binding'):
                self.assertEqual((root / name).stat().st_mode & 0o777, 0o600)
            repeated = subprocess.run(export, cwd=tmp, capture_output=True, timeout=20)
            self.assertNotEqual(repeated.returncode, 0)
            join = [sys.executable, '-I', '-S', '-B', str(HERE / 'delivery.py'), 'join',
                    '--forecasts', str(root / 'forecasts'), '--bindings', str(root / 'bindings'),
                    '--bindings-sha256', d.digest(d.canonical_bytes(self.bindings)),
                    '--output', str(root / 'joined')]
            subprocess.run(join, cwd=tmp, check=True, capture_output=True, timeout=20)
            got, _ = d.s.read_document(root / 'joined')
            self.assertEqual(got, d.join_forecasts(self.forecasts, self.bindings))


class SourceAuthenticationControls(unittest.TestCase):
    """Generated source replacements, without authentic neural observations."""

    def load_consumer(self, root, name):
        path = root / name / ('delivery.py' if name == 'fixed-origin-delivery-v1'
                              else 'uncertainty.py')
        spec = importlib.util.spec_from_file_location('generated_source_consumer', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def prepared(self, root, name):
        source = root / 'fixed-origin-forecast' / 'scorer.py'
        source.parent.mkdir(parents=True)
        source.write_bytes((HERE.parent / 'fixed-origin-forecast' / 'scorer.py').read_bytes())
        consumer = root / name
        consumer.mkdir()
        filename = 'delivery.py' if name == 'fixed-origin-delivery-v1' else 'uncertainty.py'
        (consumer / filename).write_bytes((HERE.parent / name / filename).read_bytes())
        return source

    def test_replacement_after_hash_uses_authenticated_source(self):
        for name in ('fixed-origin-delivery-v1', 'paired-mouse-resampling-v1'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = self.prepared(root, name)
                original_read = Path.read_bytes
                replaced = []

                def captured_read(path):
                    raw = original_read(path)
                    if path.resolve() == source.resolve() and not replaced:
                        source.write_text("raise RuntimeError('unverified replacement executed')\n")
                        replaced.append(True)
                    return raw

                with patch.object(Path, 'read_bytes', captured_read):
                    module = self.load_consumer(root, name)
                self.assertEqual(replaced, [True])
                self.assertEqual(module.s.TASK_ID, d.s.TASK_ID)
                self.assertEqual(module.s.loss(2.0, 1.0), 1.0)

    def test_stale_timestamp_bytecode_cannot_override_verified_source(self):
        import py_compile
        for name in ('fixed-origin-delivery-v1', 'paired-mouse-resampling-v1'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = self.prepared(root, name)
                original = source.read_bytes()
                marker = b"raise RuntimeError('unverified bytecode executed')\n"
                source.write_bytes(marker + b'#' * (len(original) - len(marker)))
                stamp = source.stat()
                py_compile.compile(str(source), doraise=True,
                                   invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
                source.write_bytes(original)
                os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
                module = self.load_consumer(root, name)
                self.assertEqual(module.s.TASK_ID, d.s.TASK_ID)
                self.assertEqual(module.s.loss(2.0, 1.0), 1.0)

    def test_wrong_source_pin_is_rejected_before_execution(self):
        for name in ('fixed-origin-delivery-v1', 'paired-mouse-resampling-v1'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = self.prepared(root, name)
                source.write_text("raise RuntimeError('unverified source executed')\n")
                with self.assertRaisesRegex(RuntimeError, '^fixed-origin scorer source mismatch$'):
                    self.load_consumer(root, name)


if __name__ == '__main__':
    unittest.main(verbosity=2)
