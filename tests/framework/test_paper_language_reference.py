"""Metadata-only controls for the fixed LANGUAGE reference successor."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ordinary = module('language_reference_catalog_controls', ROOT / 'tests/framework/test_paper_outcomes_catalog.py')
binder = module('language_reference_binder_controls', ROOT / 'scripts/maintenance/bind_paper_outcomes.py')
binding, catalog, cli = binder.binding, ordinary.catalog, ordinary.cli
successor = binding.primary_successor_module('PAPER-ROOT-ADD-001')


class LanguageReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / binding.REGISTRY).read_bytes())
        cls.original_row = next(row for row in cls.registry['tasks'] if row['id'] == successor.TASK)
        cls.reader = binder.checker.Reader(ROOT)
        cls.previous = binding.coverage(cls.registry, cls.read_pin)
        cls.current = cls.read_pin(successor.figure3b_pin('previous_task'), 'Archived LANGUAGE reference task')

    @classmethod
    def read_pin(cls, pin, label):
        if pin == successor.approved_pin('outcomes'):
            pin = successor.figure3b_pin('previous_outcomes')
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

    def test_current_reference_is_bound_without_scientific_promotion(self):
        bound = self.context()
        self.assertEqual(bound['improvement_contract_pin'], successor.approved_pin('improvement'))
        self.assertEqual(bound['retained_improvement_contract_pin'], successor.approved_pin('retained_improvement'))
        self.assertEqual(bound['reproduction_contract']['eligibility'], 'source_unresolved')
        self.assertEqual(bound['improvement_contract']['disposition'], 'design_ready')
        self.assertEqual(len(bound['reproduction_contract']['findings']), 171)
        self.assertTrue(all(cell['scientific_outcome'] == 'unknown' for cell in bound['summary']['cells']))
        self.assertTrue(all(value['protocol'] is None for value in bound['outcomes']['pairing'].values()))
        self.assertEqual(bound['outcomes']['original_task_sha256'], self.row['specification']['sha256'])
        self.assertEqual(self.current['evaluation']['contracts']['improvement'], successor.CURRENT_FILE)
        self.assertEqual(self.row['specification_revision'], self.previous[successor.TASK]['specification_revision'])
        scope = self.previous.scope_decisions['same_primary_corrections'][successor.TASK]
        self.assertEqual(bound['primary_scope_correction'], scope)

    def test_predecessor_reference_or_current_digest_tampering_is_refused(self):
        for name in ('archived_task.json', 'archived_reproduction.v2.json', 'archived_improvement.v1.json',
                     'archived_outcomes.v1.json', 'receipt', 'reference', 'improvement', 'reproduction', 'outcomes'):
            altered_path = successor.approved_pin(name)['path']
            def altered(pin, label):
                value = self.read_pin(pin, label)
                if pin['path'] == altered_path:
                    value = copy.deepcopy(value)
                    value['unreviewed_change'] = True
                return value
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'LANGUAGE parsed identity mismatch'):
                self.context(read_pin=altered)

    def test_explicit_selection_cannot_fall_back_or_move_to_another_task(self):
        for field in ('primary_policy_revision', 'primary_improvement_contract', 'reproduction_contract'):
            changed = copy.deepcopy(self.row)
            changed['paper_outcomes'].pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                binding.has_primary_successor(changed)
        changed = copy.deepcopy(self.row)
        changed['paper_outcomes']['primary_improvement_contract'] = successor.approved_pin('retained_improvement')
        with self.assertRaisesRegex(ValueError, 'Unreviewed LANGUAGE'):
            binding.has_primary_successor(changed)
        changed = copy.deepcopy(self.row)
        changed['id'] = 'PAPER-UNREVIEWED'
        with self.assertRaisesRegex(ValueError, 'restricted to reviewed tasks'):
            binding.has_primary_successor(changed)

    def test_projection_requires_authenticated_predecessor_and_exact_current_task(self):
        handle = self.handle()
        previous = handle.snapshot()['archived_task.json']
        self.assertEqual(successor.project(previous, handle), self.current)
        changed = copy.deepcopy(previous)
        changed['status'] = 'improvement_ready'
        with self.assertRaisesRegex(ValueError, 'deterministic predecessor'):
            successor.project(changed, handle)
        with self.assertRaisesRegex(ValueError, 'Authenticated LANGUAGE'):
            successor.project(previous, {})
        changed = copy.deepcopy(self.current)
        changed['evaluation']['contracts']['improvement'] = 'improvement.v1.json'
        with self.assertRaisesRegex(ValueError, 'deterministic dual-outcome projection'):
            self.context(document=changed)

    def test_catalog_navigation_and_cli_use_current_reference_policy(self):
        bound = self.context()
        public = binding.public_summary(self.row, bound)
        view = json.loads((ROOT / 'benchmarks/catalog/catalog.json').read_bytes())
        entry = next(row for row in view['tasks'] if row['id'] == successor.TASK)
        entry['specification'] = copy.deepcopy(self.row['specification'])
        entry['paper_outcomes'] = public
        entry['paper_improvement']['role'] = catalog.RETAINED_POLICY_ROLE
        view['paper_outcome_counts'] = catalog.paper_outcome_counts(view['tasks'])
        page = catalog.render_tracks(view)[successor.HOME + '/README.md'].decode()
        for text in ('Selected current improvement contract', 'improvement.reference.v1.json',
                     'Provided-author reference report', 'Reference recovery receipt',
                     'Retained scope-adjudication limits', 'Current reproduction/source limits',
                     'author-provided-array/current-runtime measurements'):
            self.assertIn(text, page)
        self.assertIn('LANGUAGE reference successor', catalog.paper_count_text(view))
        # This public view selects the archived reference stage. Its current-path
        # outcomes pin must resolve to those real archived bytes, independently
        # of the later Figure3b files in the repository under test.
        with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as temporary:
            reference_root = Path(temporary)
            for name in ('reproduction', 'improvement', 'outcomes'):
                selected_pin = successor.approved_pin(name)
                source_pin = (successor.figure3b_pin('previous_outcomes')
                              if name == 'outcomes' else selected_pin)
                raw = (ROOT / source_pin['path']).read_bytes()
                self.assertEqual(binding.pin(source_pin['path'], raw), source_pin)
                destination = reference_root / selected_pin['path']
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw)
            with patch.object(cli, 'public_catalog_module', return_value=catalog), patch.object(catalog, 'load', return_value=view):
                self.assertEqual(cli.paper_contract(successor.TASK, reference_root), bound['improvement_contract'])
                self.assertEqual(cli.paper_contract(successor.TASK, reference_root, outcome='reproduction'), bound['reproduction_contract'])
                result = cli.paper_outcomes(successor.TASK, reference_root)
                self.assertEqual(result['specification'], successor.approved_pin('task'))
                self.assertEqual(result['binding']['improvement_contract'], successor.approved_pin('improvement'))
                self.assertEqual(result['binding']['retained_improvement_contract'], successor.approved_pin('retained_improvement'))


if __name__ == '__main__':
    unittest.main()
