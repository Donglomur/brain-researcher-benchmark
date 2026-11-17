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
