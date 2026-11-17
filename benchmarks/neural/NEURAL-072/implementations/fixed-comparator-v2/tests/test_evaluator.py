"""Generated controls only; no authentic responses, checkpoints or model trials."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fixed_comparator_evaluator', ROOT / 'evaluator.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)
fixture_spec = importlib.util.spec_from_file_location(
    'generated_previous_fixture', ROOT.parent / 'initial-evaluator-v1' / 'tests' / 'test_evaluator.py')
fixtures = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixtures)


class FixedComparatorControls(unittest.TestCase):
    def setUp(self):
        self.p, self.c, self.f, self.train, self.test = fixtures.fixture()
        self.reference = e.freeze_reference(self.p, self.c, self.f, self.train)
        self.raw = e.encode(self.reference)
        self.expected = e.sha256(self.raw)
        self.candidate = {
            'schema': e.CANDIDATE_SCHEMA, 'task_id': 'NEURAL-072',
            'protocol_sha256': e.legacy.digest(self.p), 'cases_sha256': e.legacy.digest(self.c),
            'contextual': {rid: copy.deepcopy(values['lexical'])
                           for rid, values in self.reference['predictions'].items()},
        }

    def grade(self):
        return e.score(self.p, self.c, self.test, self.candidate, self.raw, self.expected)

    def test_reference_is_fitted_with_identical_preserved_recipe(self):
        previous = e.legacy.fit_predict(self.p, self.c, self.f, self.train)
        for rid, values in self.reference['predictions'].items():
            self.assertEqual(set(values), {'nuisance', 'lexical'})
            for arm in e.COMPARATORS:
                self.assertEqual(values[arm], previous['predictions'][rid][arm])
        self.assertEqual(self.reference['fit_ledger'], previous['fit_ledger'])
        self.assertEqual(self.reference['fit_inputs']['train_dev_targets_sha256'], e.legacy.digest(self.train))

    def test_legacy_degradation_exploit_and_new_rejection(self):
        previous = e.legacy.fit_predict(self.p, self.c, self.f, self.train)
        before = e.legacy.score(self.p, self.c, self.test, previous)
        for values in previous['predictions'].values():
            values['lexical'] = (e.legacy.np.asarray(values['lexical']) + 100).tolist()
        after = e.legacy.score(self.p, self.c, self.test, previous)
        self.assertGreater(after['listener_macro_contrasts']['contextual_minus_lexical'],
                           before['listener_macro_contrasts']['contextual_minus_lexical'] + 1)
        with self.assertRaisesRegex(e.ContractError, 'contextual predictions only'):
            e.score(self.p, self.c, self.test, previous, self.raw, self.expected)

    def test_candidate_cannot_supply_any_comparator_or_fit_ledger(self):
        for key in ('lexical', 'nuisance', 'predictions', 'fit_ledger', 'reference_sha256'):
            bad = copy.deepcopy(self.candidate)
            bad[key] = 'candidate-controlled'
            with self.subTest(key=key), self.assertRaisesRegex(e.ContractError, 'contextual predictions only'):
                e.score(self.p, self.c, self.test, bad, self.raw, self.expected)

    def test_tampered_predictions_ledger_and_features_fail_original_commitment(self):
        variants = []
        changed = copy.deepcopy(self.reference)
        changed['predictions']['s1_3']['lexical'][0][0] += 100
        variants.append(changed)
        changed = copy.deepcopy(self.reference)
        changed['fit_ledger'][0]['alpha'] = 100000
        variants.append(changed)
        changed = copy.deepcopy(self.reference)
        changed['fit_inputs']['evaluator_features_sha256'] = '0' * 64
        variants.append(changed)
        for changed in variants:
            with self.assertRaisesRegex(e.ContractError, 'commitment mismatch'):
                e.score(self.p, self.c, self.test, self.candidate, e.encode(changed), self.expected)

    def test_expected_digest_is_required_not_derived_from_artifact(self):
        for digest in (None, '', '0' * 64, self.reference):
            with self.assertRaises(e.ContractError):
                e.score(self.p, self.c, self.test, self.candidate, self.raw, digest)

    def test_reference_schema_and_source_are_checked_after_authentication(self):
        for field, value, message in [('source', {}, 'source differs'), ('fit_ledger', [], 'ledger incomplete'),
                                      ('predictions', {}, 'inventory differs')]:
            changed = copy.deepcopy(self.reference)
            changed[field] = value
            raw = e.encode(changed)
            with self.assertRaisesRegex(e.ContractError, message):
                e.score(self.p, self.c, self.test, self.candidate, raw, e.sha256(raw))

    def test_equal_predictions_have_zero_increment_and_absolute_errors(self):
        report = self.grade()
        self.assertEqual(report['listener_macro_contrasts']['contextual_minus_lexical'], 0.)
        self.assertEqual(report['listener_macro_r2']['contextual'], report['listener_macro_r2']['lexical'])
        for cell in report['cells']:
            self.assertEqual(cell['sse_by_target']['contextual'], cell['sse_by_target']['lexical'])
            for arm in e.legacy.ARMS:
                expected = [1 - error / total for error, total in
                            zip(cell['sse_by_target'][arm], cell['sst_by_target'])]
                self.assertEqual(cell['r2_by_target'][arm], expected)
        self.assertFalse(report['scientific_qualified'])
        self.assertFalse(report['submission_ready'])

    def test_candidate_accuracy_changes_score_without_changing_references(self):
        self.candidate['contextual'] = copy.deepcopy(self.test)
        best = self.grade()
        self.assertEqual(best['listener_macro_r2']['contextual'], 1.)
        for rid, values in self.candidate['contextual'].items():
            self.candidate['contextual'][rid] = (e.legacy.np.asarray(values) + 100).tolist()
        worse = self.grade()
        self.assertLess(worse['listener_macro_contrasts']['contextual_minus_lexical'], 0.)
        self.assertEqual(best['comparator_authentication'], worse['comparator_authentication'])
        self.assertEqual(best['listener_macro_r2']['lexical'], worse['listener_macro_r2']['lexical'])

    def test_fit_rejects_hidden_targets_and_preserves_test_feature_nonselection(self):
        with self.assertRaisesRegex(e.ContractError, 'hidden targets'):
            e.freeze_reference(self.p, self.c, self.f, {**self.train, **self.test})
        changed = copy.deepcopy(self.f)
        for rid in self.test:
            changed[rid]['contextual'] = (e.legacy.np.asarray(changed[rid]['contextual']) * 7).tolist()
        ref = e.freeze_reference(self.p, self.c, changed, self.train)
        self.assertEqual(ref['fit_ledger'], self.reference['fit_ledger'])
        self.assertEqual(ref['predictions'], self.reference['predictions'])

    def test_candidate_wrong_run_target_shape_nonfinite_and_case_pin(self):
        mutations = [lambda x: x['contextual'].pop('s1_3'),
                     lambda x: x['contextual'].__setitem__('s1_3', [[0]]),
                     lambda x: x['contextual']['s1_3'][0].__setitem__(0, float('nan')),
                     lambda x: x.__setitem__('cases_sha256', '0' * 64)]
        for mutate in mutations:
            bad = copy.deepcopy(self.candidate)
            mutate(bad)
            with self.assertRaises(e.ContractError):
                e.score(self.p, self.c, self.test, bad, self.raw, self.expected)

    def test_duplicate_keys_and_nonfinite_json_rejected(self):
        for data in (b'{"a": 1, "a": 2}', b'{"a": NaN}'):
            with self.assertRaises(e.ContractError):
                e.decode(data)

    def test_cli_freeze_score_exclusive_output_and_pre_target_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name, value in [('p', self.p), ('c', self.c), ('f', self.f), ('train', self.train),
                                ('test', self.test), ('candidate', self.candidate)]:
                (root / name).write_bytes(e.encode(value))
            base = [sys.executable, '-I', '-B', str(ROOT / 'evaluator.py')]
            freeze = base + ['freeze-reference', '--protocol', str(root / 'p'), '--cases', str(root / 'c'),
                             '--features', str(root / 'f'), '--targets', str(root / 'train'), '--output', str(root / 'ref')]
            completed = subprocess.run(freeze, check=True, capture_output=True, text=True)
            digest = json.loads(completed.stdout)['artifact_sha256']
            self.assertEqual(digest, e.sha256((root / 'ref').read_bytes()))
            duplicate = subprocess.run(freeze, capture_output=True, text=True)
            self.assertEqual(duplicate.returncode, 2)
            self.assertEqual(digest, e.sha256((root / 'ref').read_bytes()))
            grade = base + ['score', '--protocol', str(root / 'p'), '--cases', str(root / 'c'),
                            '--candidate', str(root / 'candidate'), '--reference', str(root / 'ref'),
                            '--expected-reference-sha256', digest, '--targets', str(root / 'test'),
                            '--output', str(root / 'report')]
            subprocess.run(grade, check=True, capture_output=True, text=True)
            report = e.decode((root / 'report').read_bytes())
            self.assertEqual(report['listener_macro_contrasts']['contextual_minus_lexical'], 0.)
            # A bad comparator is rejected before trying to open missing targets.
            (root / 'ref').write_bytes(b'{}')
            (root / 'test').unlink()
            failed = subprocess.run(grade, capture_output=True, text=True)
            self.assertEqual(failed.returncode, 2)
            self.assertIn('commitment mismatch', failed.stderr)
            self.assertNotIn('No such file', failed.stderr)


if __name__ == '__main__':
    unittest.main()
