"""Metadata controls for the closed Deeprecon publisher-reference successor."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ordinary = module('deeprecon_reference_catalog_controls', ROOT / 'tests/framework/test_paper_outcomes_catalog.py')
binder = module('deeprecon_reference_binder_controls', ROOT / 'scripts/maintenance/bind_paper_outcomes.py')
binding, catalog, cli = binder.binding, ordinary.catalog, ordinary.cli
successor = module('retained_deeprecon_reference_stage', ROOT / 'src/neurobench/paper_deeprecon_reference.py')


class DeepreconReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / binding.REGISTRY).read_bytes())
        cls.original_row = next(row for row in cls.registry['tasks'] if row['id'] == successor.TASK)
        cls.reader = binder.checker.Reader(ROOT)
        cls.previous = binding.coverage(cls.registry, cls.read_pin)
        cls.current = json.loads((ROOT / successor.HOME / 'docs/provenance/pre-figure2-complete-20261117/task.json').read_bytes())

    @classmethod
    def read_pin(cls, pin, label):
        pin = copy.deepcopy(pin)
        for name, filename in (('task', 'task.json'), ('outcomes', 'outcomes.v1.json')):
            if pin == successor.approved_pin(name):
                pin['path'] = successor.HOME + '/docs/provenance/pre-figure2-complete-20261117/' + filename
        return binder.read_pinned(cls.reader, pin, label)

    def setUp(self):
        self.row = copy.deepcopy(self.original_row)
        self.row['specification'] = successor.approved_pin('task')
        self.row['paper_outcomes'].update(
            primary_policy_revision=successor.approved_pin('descriptor'),
            primary_improvement_contract=successor.approved_pin('improvement'),
            reproduction_contract=successor.approved_pin('reproduction'),
            outcomes=successor.approved_pin('outcomes'))

    def context(self, read_pin=None, document=None):
        return binding.context(self.row, self.current if document is None else document,
            self.previous, self.read_pin if read_pin is None else read_pin)

    def handle(self):
        return successor.authenticate(task_id=successor.TASK,
            revision_pin=successor.approved_pin('descriptor'), primary_pin=successor.approved_pin('improvement'),
            reproduction_pin=successor.approved_pin('reproduction'), previous_pin=successor.approved_pin('pre_outcomes'),
            retained_improvement_pin=successor.approved_pin('retained_improvement'), read_pin=self.read_pin)

    def test_reference_binding_preserves_scientific_limits_and_original_policy(self):
        bound = self.context()
        current, retained = bound['improvement_contract'], bound['retained_improvement_contract']
        self.assertEqual(bound['improvement_contract_pin'], successor.approved_pin('improvement'))
        self.assertEqual(bound['retained_improvement_contract_pin'], successor.approved_pin('retained_improvement'))
        self.assertEqual(current['same_task'], retained['same_task'])
        self.assertEqual(current['disposition'], 'source_unresolved')
        self.assertEqual(bound['reproduction_contract']['eligibility'], 'source_unresolved')
        self.assertEqual(current['comparison']['minimum_effect'], retained['comparison']['minimum_effect'])
        self.assertIsNone(current['comparison']['published_baseline']['value'])
        self.assertIsNone(bound['primary_scope_correction'])
        self.assertEqual(binding.public_summary(self.row, bound)['reproduction_contract'], successor.approved_pin('reproduction'))
        self.assertTrue(all(cell['scientific_outcome'] == 'unknown' for cell in bound['summary']['cells']))
        self.assertTrue(all(value['protocol'] is None for value in bound['outcomes']['pairing'].values()))
        self.assertEqual(self.row['specification_revision'], self.previous[successor.TASK]['specification_revision'])
        old = self.handle().snapshot()['archived_outcomes.v1.json']
        expected = copy.deepcopy(old)
        expected['original_task_sha256'] = successor.approved_pin('task')['sha256']
        expected['contracts']['improvement'] = binding.engine().contract_digest(current)
        for entry in expected['pairing'].values():
            entry['rationale'] = entry['rationale'].replace(
                ' Final current-task raw pin awaits integration wording correction.', '')
        self.assertEqual(bound['outcomes'], expected)

    def test_predecessor_source_current_or_descriptor_tampering_is_refused(self):
        for name in ('archived_task.json', 'archived_outcomes.v1.json', 'retained_improvement',
                     'pre_outcomes', 'reference', 'improvement', 'reproduction', 'outcomes', 'descriptor'):
            altered_path = successor.approved_pin(name)['path']
            def altered(pin, label):
                value = self.read_pin(pin, label)
                if pin['path'] == altered_path:
                    value = copy.deepcopy(value)
                    value['unreviewed_change'] = True
                return value
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Deeprecon parsed identity mismatch'):
                self.context(read_pin=altered)

    def test_explicit_selection_cannot_fall_back_or_move_to_another_task(self):
        for field in ('primary_policy_revision', 'primary_improvement_contract', 'reproduction_contract'):
            changed = copy.deepcopy(self.row)
            changed['paper_outcomes'].pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                binding.has_primary_successor(changed)
        changed = copy.deepcopy(self.row)
        changed['paper_outcomes']['primary_improvement_contract'] = successor.approved_pin('retained_improvement')
        with self.assertRaisesRegex(ValueError, 'Unreviewed Deeprecon'):
            binding.has_primary_successor(changed)
        changed = copy.deepcopy(self.row)
        changed['id'] = 'PAPER-UNREVIEWED'
        with self.assertRaisesRegex(ValueError, 'restricted to reviewed tasks'):
            binding.has_primary_successor(changed)
        self.assertEqual(binding.primary_successor_module('PAPER-ROOT-ADD-001').TASK, 'PAPER-ROOT-ADD-001')
        self.assertEqual(binding.primary_successor_module().TASK, 'PAPER-SMC-RNN-2024')

    def test_projection_requires_authenticated_predecessor_and_current_binding(self):
        handle = self.handle()
        documents = handle.snapshot()
        previous = documents['archived_task.json']
        self.assertEqual(successor.project(previous, handle), self.current)
        self.assertEqual(len(documents['descriptor']['improvement_replacements']), 9)
        self.assertEqual(self.current['episode']['improvement'], documents['improvement']['episode'])
        self.assertEqual(self.current['blocking_issues']['improvement'], documents['improvement']['blocking_issues'])
        changed = copy.deepcopy(previous)
        changed['status'] = 'improvement_ready'
        with self.assertRaisesRegex(ValueError, 'deterministic predecessor'):
            successor.project(changed, handle)
        with self.assertRaisesRegex(ValueError, 'Authenticated Deeprecon'):
            successor.project(previous, {})
        changed = copy.deepcopy(self.current)
        changed['evaluation']['contracts']['improvement'] = 'improvement.v1.json'
        with self.assertRaisesRegex(ValueError, 'deterministic dual-outcome projection'):
            self.context(document=changed)

    def test_catalog_and_cli_select_current_policy_with_reference_limits(self):
        bound = self.context()
        public = binding.public_summary(self.row, bound)
        view = json.loads((ROOT / 'benchmarks/catalog/catalog.json').read_bytes())
        entry = next(row for row in view['tasks'] if row['id'] == successor.TASK)
        entry['specification'] = copy.deepcopy(self.row['specification'])
        entry['paper_outcomes'] = public
        entry['paper_improvement']['role'] = catalog.RETAINED_POLICY_ROLE
        view['paper_outcome_counts'] = catalog.paper_outcome_counts(view['tasks'])
        page = catalog.render_tracks(view)[successor.HOME + '/README.md'].decode()
        for text in ('Selected current improvement contract', 'improvement.reference-recovery.v1.json',
                     'Published reference provenance', 'Unchanged reproduction/source limits',
                     '240 rows and 480 normalized pair means', 'not native replay or candidate results'):
            self.assertIn(text, page)
        self.assertIn('Deeprecon reference successor', catalog.paper_count_text(view))
        original_program_pin = cli._program_pin
        def retained_program_pin(root, relative, sha256, size, **options):
            for name, filename in (('task', 'task.json'), ('outcomes', 'outcomes.v1.json')):
                expected = successor.approved_pin(name)
                if (relative, sha256, size) == (expected['path'], expected['sha256'], expected['bytes']):
                    relative = successor.HOME + '/docs/provenance/pre-figure2-complete-20261117/' + filename
            return original_program_pin(root, relative, sha256, size, **options)
        with patch.object(cli, 'public_catalog_module', return_value=catalog), patch.object(catalog, 'load', return_value=view), patch.object(cli, '_program_pin', side_effect=retained_program_pin):
            self.assertEqual(cli.paper_contract(successor.TASK, ROOT), bound['improvement_contract'])
            self.assertEqual(cli.paper_contract(successor.TASK, ROOT, outcome='reproduction'), bound['reproduction_contract'])
            result = cli.paper_outcomes(successor.TASK, ROOT)
            self.assertEqual(result['specification'], successor.approved_pin('task'))
            self.assertEqual(result['binding']['improvement_contract'], successor.approved_pin('improvement'))
            self.assertEqual(result['binding']['retained_improvement_contract'], successor.approved_pin('retained_improvement'))


if __name__ == '__main__':
    unittest.main()
