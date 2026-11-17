"""Public-report navigation controls; no raw data, model or native scoring runs."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('recorded_evidence_tests', ROOT / 'src/neurobench/evidence.py')
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def install(self, name, document=None):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if document is None:
            path.write_bytes((ROOT / name).read_bytes())
        else:
            path.write_text(json.dumps(document, indent=2) + '\n')
        return path

    def document(self, name):
        return json.loads((ROOT / name).read_text())

    def test_absent_optional_reports_are_empty(self):
        result = evidence.load(self.root, task_ids={'SYNTHETIC-TASK'})
        self.assertEqual(result['records'], {})
        self.assertEqual(result['reports'], [])
        self.assertTrue(all(value == 0 for value in result['counts'].values()))
        self.assertIn('selected public reports only', result['scope'])

    def test_current_public_evidence_is_scoped_and_overlapping(self):
        result = evidence.load(ROOT)
        self.assertEqual(result['counts']['tasks_with_recorded_evidence'], 5)
        self.assertEqual(result['counts']['pilot_attempts'], 8)
        self.assertEqual(result['counts']['paper_calibration_attempts'], 4)
        self.assertEqual(result['counts']['neural_programme_attempts'], 4)
        self.assertEqual(result['counts']['direct_interpretation_attempts'], 0)
        self.assertEqual(result['counts']['viewer_interpretation_attempts'], 0)
        self.assertEqual(result['counts']['historical_profiles'], 3)
        self.assertEqual(result['counts']['historical_programme_controls'], 4)
        self.assertEqual(result['counts']['authentic_engineering_reports'], 2)
        for rows in result['records'].values():
            for row in rows:
                self.assertEqual(row['qualification_effect'], 'none')
                self.assertNotIn('scientific_readiness', row)
                self.assertTrue(row['scope'])
                self.assertTrue(row['limits'])
                raw = (ROOT / row['source']['path']).read_bytes()
                self.assertEqual(row['source']['bytes'], len(raw))
                self.assertEqual(row['source']['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result, evidence.load(ROOT))

    def test_metrics_preserve_eeg_tradeoff_and_sleep_deviation(self):
        self.install(evidence.PILOT)
        result = evidence.load(self.root)
        eeg = [row for row in result['records']['NEURAL-077'] if row['attempt_id'] == 'neural077-1'][0]
        primary, secondary = eeg['metrics']
        self.assertEqual(primary['direction'], 'higher')
        self.assertGreater(primary['value'], primary['comparators']['eeg'])
        self.assertEqual(secondary['direction'], 'lower')
        self.assertGreater(secondary['value'], secondary['comparators']['prior'])
        sleep = {row['attempt_id']: row for row in result['records']['NEURAL-007']}
        self.assertIn('Exploratory:', sleep['neural007-1']['protocol_note'])
        self.assertIn('No sequencing deviation', sleep['neural007-2']['protocol_note'])
        self.assertEqual(sleep['neural007-1']['coverage']['scored_epochs'], 5450)
        self.assertEqual(sleep['neural007-2']['condition'], 'features_and_shared_pretrained_YASA')

    def test_only_explicit_public_reports_are_opened(self):
        document = self.document(evidence.PILOT)
        document['operator_evidence_pins']['/private-ledger-sentinel/receipt.json'] = {'bytes': 10, 'sha256': 'a' * 64}
        self.install(evidence.PILOT, document)
        self.install('candidate.py', {'executable': True})
        self.install('docs/other/EVIDENCE.json', {'status': 'qualified'})
        original = Path.open
        observed = []
        def guarded(path, *args, **kwargs):
            self.assertIn(path.relative_to(self.root).as_posix(), evidence.PUBLIC_REPORTS)
            observed.append(path.relative_to(self.root).as_posix())
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded):
            result = evidence.load(self.root)
        self.assertEqual(observed, [evidence.PILOT])
        self.assertEqual(result['counts']['pilot_attempts'], 8)
        self.assertNotIn('private-ledger-sentinel', json.dumps(result))

    def test_unregistered_task_receipt_refuses_instead_of_disappearing(self):
        self.install(evidence.PILOT)
        with self.assertRaisesRegex(ValueError, 'unregistered task'):
            evidence.load(self.root, {'NEURAL-077'})
        allowed = set(evidence.PILOT_TASKS)
        self.assertEqual(evidence.load(self.root, allowed)['counts']['pilot_attempts'], 8)

    def test_pilot_duplicates_counts_conditions_and_failures_refuse(self):
        mutations = {
            'duplicate': lambda d: d['attempts'].append(copy.deepcopy(d['attempts'][0])),
            'count': lambda d: d['counts'].update(fresh_solver_attempts=99),
            'condition': lambda d: d['attempts'][4].update(condition='zero_shot'),
            'failure': lambda d: d['attempts'][0].update(status='failed'),
            'population': lambda d: d['attempts'][-1].update(all400_trials_validated=False),
            'sleep-subset': lambda d: d['attempts'][4].update(scored_epochs=12),
            'paper-subset': lambda d: d['attempts'][0]['metrics'].update(all_regions=2),
            'boolean-schema': lambda d: d.update(schema_version=True),
            'boolean-metric': lambda d: d['attempts'][0]['metrics'].update(score=True),
            'missing': lambda d: d.pop('limits'),
            'dropped-comparator': lambda d: d['reference_scores']['NEURAL-077'].pop('gross_amplitude'),
            'impossible-f1': lambda d: d['attempts'][4]['metrics'].update(person_mean_macro_f1=1.2),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                document = self.document(evidence.PILOT)
                mutate(document)
                self.install(evidence.PILOT, document)
                with self.assertRaises(ValueError):
                    evidence.load(self.root)

    def test_engineering_reports_do_not_become_model_trials(self):
        for name, key in ((evidence.DIRECT, 'model_calls'), (evidence.VIEWER, 'model_trials')):
            with self.subTest(name=name):
                document = self.document(name)
                document[key] = 1
                self.install(name, document)
                with self.assertRaisesRegex(ValueError, 'cannot assert model performance'):
                    evidence.load(self.root)
                (self.root / name).unlink()

    def test_historical_cross_task_join_refuses(self):
        document = self.document(evidence.HISTORY)
        document['profiles'][0]['evidence'] = ['rtt-program-controls']
        self.install(evidence.HISTORY, document)
        with self.assertRaisesRegex(ValueError, 'another task'):
            evidence.load(self.root)

    def test_historical_controls_cannot_come_from_unselected_record(self):
        document = self.document(evidence.HISTORY)
        original = next(row for row in document['evidence'] if row['evidence_id'] == 'rtt-program-controls')
        replacement = copy.deepcopy(original)
        replacement['evidence_id'] = 'replacement-rtt'
        document['evidence'].append(replacement)
        profile = next(row for row in document['profiles'] if row['canonical_task_id'] == 'NEURAL-023')
        profile['evidence'] = ['replacement-rtt']
        original['selected_fields']['/candidate_id'] = 'PAPER-FIND-REP-013'
        self.install(evidence.HISTORY, document)
        with self.assertRaisesRegex(ValueError, 'selected profile evidence'):
            evidence.load(self.root)

    def test_native_controls_are_separate_from_pilot_and_historical_attempts(self):
        for name in evidence.PUBLIC_REPORTS:
            self.install(name)
        result = evidence.load(self.root)
        self.assertEqual(result['counts']['native_operator_controls'], 8)
        self.assertEqual(result['counts']['native_operator_control_reports'], 1)
        self.assertEqual(result['counts']['native_control_tasks'], 2)
        self.assertEqual(result['counts']['pilot_attempts'], 8)
        self.assertEqual(result['counts']['historical_programme_controls'], 4)
        self.assertEqual(result['counts']['public_reports'], 5)
        self.assertEqual(result['counts']['tasks_with_recorded_evidence'], 5)
        rows = [row for items in result['records'].values() for row in items
                if row['category'] == 'native_operator_control']
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(control['owned_containers'] for row in rows for control in row['controls']), 12)
        for row in rows:
            self.assertEqual(row['qualification_effect'], 'none')
            self.assertEqual(row['model_attempts_recorded'], 0)
            self.assertEqual(row['coverage']['development_people'], 2)
            self.assertEqual(sum(control['expected_refusal'] for control in row['controls']), 2)
            self.assertTrue(row['primary_metric'])
            self.assertTrue(row['companion_metric'])
            self.assertEqual(len(row['controls']), 4)
            self.assertFalse(row['original_records_in_publication'])
        eeg = next(row for row in rows if row['task_id'] == 'NEURAL-077')
        sleep = next(row for row in rows if row['task_id'] == 'NEURAL-007')
        self.assertEqual(eeg['coverage']['development_rows'], 400)
        self.assertEqual(sleep['coverage']['development_rows'], 5450)
        self.assertEqual(set(sleep['fixed_reference_arms']), {'YASA', 'RF'})
        self.assertEqual(len(eeg['fixed_reference_arms']), 6)

    def test_native_contradictory_counts_access_refusals_and_environment_refuse(self):
        mutations = {
            'totals': lambda d: d['totals'].update(native_attempts=7),
            'containers': lambda d: d['totals'].update(owned_containers=11),
            'cleanup': lambda d: d['controls'][0].update(all_owned_containers_absent=False),
            'incomplete-private-access': lambda d: d['controls'][1].update(target_loader_attempts=1),
            'wrong-target-pass': lambda d: d['controls'][3].update(expected_exit=0, observed_exit=0),
            'sleep-wrong-target': lambda d: d['controls'][-1].update(status='scored'),
            'missing-control': lambda d: d['controls'].pop(),
            'duplicate-control': lambda d: d['controls'].__setitem__(1, copy.deepcopy(d['controls'][0])),
            'cross-task-control': lambda d: d['controls'][0].update(task_id='NEURAL-007'),
            'subset-panel': lambda d: d['panels'][0].update(development_rows=399),
            'dropped-reference': lambda d: d['panels'][0]['fixed_reference_arms'].pop(),
            'metric': lambda d: d['panels'][0].update(primary_metric='trial-weighted accuracy'),
            'model-trial': lambda d: d['totals'].update(new_model_calls=1),
            'network': lambda d: d['native_environment'].update(network='host'),
            'root': lambda d: d['native_environment'].update(non_root=False),
            'no-memory-bound': lambda d: d['native_environment'].update(memory_bytes_per_container=0),
            'source-revision': lambda d: d.update(source_commit='unknown'),
            'source-path': lambda d: d['operator_source_inventory'].update(path='/private/source.json'),
            'private-locator': lambda d: d['controls'][0]['retained_receipt'].update(path='/private/receipt.json'),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                document = self.document(evidence.NATIVE)
                mutate(document)
                self.install(evidence.NATIVE, document)
                with self.assertRaises(ValueError):
                    evidence.load(self.root)

    def test_native_provenance_is_historical_and_does_not_follow_locators(self):
        document = self.document(evidence.NATIVE)
        document['source_commit'] = 'a' * 40
        document['operator_source_inventory']['sha256'] = 'b' * 64
        document['native_environment']['image'] = 'sha256:' + 'c' * 64
        document['private_receipt_path'] = '/private-ledger-sentinel/receipt.json'
        self.install(evidence.NATIVE, document)
        # There is deliberately no current source inventory or private receipt.
        original = Path.open
        def guarded(path, *args, **kwargs):
            self.assertEqual(path.relative_to(self.root).as_posix(), evidence.NATIVE)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded):
            result = evidence.load(self.root, {'NEURAL-007', 'NEURAL-077'})
        row = result['records']['NEURAL-077'][0]
        self.assertEqual(row['source_provenance']['source_commit'], 'a' * 40)
        self.assertEqual(row['native_environment']['image'], 'sha256:' + 'c' * 64)
        self.assertNotIn('private-ledger-sentinel', json.dumps(result))
        self.assertEqual(result['counts']['native_operator_control_reports'], 1)
        self.assertEqual(result['counts']['pilot_attempts'], 0)

    def test_malformed_duplicate_and_nonfinite_json_refuse(self):
        path = self.install(evidence.PILOT)
        for raw in ('not json', '{"schema_version":1,"schema_version":1}', '{"schema_version":NaN}', '{"ignored":1e309}'):
            with self.subTest(raw=raw):
                path.write_text(raw)
                with self.assertRaises(ValueError):
                    evidence.load(self.root)

    def test_symlink_hardlink_oversize_and_directory_refuse(self):
        path = self.install(evidence.PILOT)
        target = self.root / 'external.json'
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            evidence.load(self.root)
        path.unlink()
        os.link(target, path)
        with self.assertRaisesRegex(ValueError, 'single-link'):
            evidence.load(self.root)
        path.unlink()
        path.write_bytes(b' ' * (evidence.MEMBER_LIMIT + 1))
        with self.assertRaisesRegex(ValueError, 'bounded'):
            evidence.load(self.root)
        path.unlink()
        path.mkdir()
        with self.assertRaisesRegex(ValueError, 'bounded'):
            evidence.load(self.root)

    def test_symlink_parent_cannot_supply_optional_report(self):
        real = self.root / 'outside'
        real.mkdir()
        (self.root / 'docs').symlink_to(real, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            evidence.load(self.root)


if __name__ == '__main__':
    unittest.main()
