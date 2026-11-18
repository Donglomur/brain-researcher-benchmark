"""Metadata-only controls for the exact LANGUAGE Figure3b second stage."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    result = importlib.util.module_from_spec(importlib.util.spec_from_file_location(name, path))
    exec(compile(path.read_bytes(), str(path), 'exec'), result.__dict__)
    return result


ordinary = module('figure3b_catalog_controls', ROOT / 'tests/framework/test_paper_outcomes_catalog.py')
binder = module('figure3b_binder_controls', ROOT / 'scripts/maintenance/bind_paper_outcomes.py')
binding, catalog = binder.binding, ordinary.catalog
successor = binding.primary_successor_module('PAPER-ROOT-ADD-001')


class LanguageFigure3bTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / binding.REGISTRY).read_bytes())
        cls.reader = binder.checker.Reader(ROOT)
        cls.previous = binding.coverage(cls.registry, cls.read_pin)
        cls.row = next(row for row in cls.registry['tasks'] if row['id'] == successor.TASK)
        cls.current = cls.read_pin(cls.row['specification'], 'Current LANGUAGE')

    @classmethod
    def read_pin(cls, pin, label):
        return binder.read_pinned(cls.reader, pin, label)

    def handle(self, reader=None):
        declared = self.row['paper_outcomes']
        return successor.authenticate(task_id=successor.TASK,
            revision_pin=declared['primary_policy_revision'], primary_pin=declared['primary_improvement_contract'],
            reproduction_pin=declared['reproduction_contract'], previous_pin=declared['previous_specification'],
            retained_improvement_pin=self.row['specification_revision']['improvement_contract'],
            read_pin=self.read_pin if reader is None else reader)

    def context(self):
        return binding.context(self.row, self.current, self.previous, self.read_pin)

    def test_selected_quantity_and_four_unknown_cells(self):
        bound = self.context()
        self.assertEqual(bound['improvement_contract_pin'], successor.figure3b_pin('improvement'))
        selected = self.handle().snapshot()['descriptor']['selected_original_scope']
        self.assertEqual((selected['sessions'], selected['participants'], selected['job_correlations']), (14, 8, 42))
        self.assertEqual((selected['layer_index_zero_based'], selected['lag_indices']), (5, [17, 18, 19]))
        self.assertFalse(selected['binary_win_enabled'])
        self.assertIsNone(bound['improvement_contract']['comparison']['minimum_effect']['value'])
        self.assertEqual(len(bound['summary']['cells']), 4)
        for cell in bound['summary']['cells']:
            self.assertEqual(cell['scientific_outcome'], 'unknown')
            self.assertFalse(cell['condition_available'])
            self.assertFalse(cell['endpoint_eligible'])
            self.assertIsNone(cell['receipt'])
        self.assertTrue(all(v['protocol'] is None for v in bound['outcomes']['pairing'].values()))
        self.assertEqual(bound['outcomes']['original_task_sha256'], self.row['specification']['sha256'])

    def test_old_full_pair_and_generic_anchor_check_are_preserved(self):
        handle = self.handle()
        retained = handle._legacy.snapshot()
        engine = binding.engine(retained['reproduction'])
        self.assertEqual(engine.outcomes_validate(retained['outcomes'], retained['reproduction'], retained['improvement']), [])
        self.assertNotEqual(retained['improvement']['same_task']['target']['description'], handle.primary_improvement['same_task']['target']['description'])
        self.assertTrue(engine.outcomes_validate(handle.snapshot()['outcomes'], retained['reproduction'], handle.primary_improvement))
        self.assertEqual(len(retained['reproduction']['findings']), 171)
        self.assertEqual(successor.approved_pin('reproduction'), self.row['paper_outcomes']['reproduction_contract'])
        self.assertEqual({p['path'] for p in handle.members}, {
            successor.approved_pin('descriptor')['path'], successor.approved_pin('improvement')['path'],
            successor.figure3b_pin('descriptor')['path'], successor.figure3b_pin('improvement')['path']})

    def test_projection_replays_reference_before_selected_changes(self):
        handle = self.handle()
        old = handle._legacy.snapshot()
        self.assertEqual(successor.projection_improvement(handle), old['improvement'])
        self.assertEqual(successor.project(old['archived_task.json'], handle), self.current)
        self.assertEqual(successor.project(old['archived_task.json'], handle._legacy), handle.snapshot()['previous_task'])
        altered = copy.deepcopy(old['archived_task.json'])
        altered['status'] = 'improvement_ready'
        with self.assertRaises(ValueError): successor.project(altered, handle)
        with self.assertRaises(ValueError): successor.project(self.current, {})

    def test_archives_authority_and_construction_provenance_tampering_fail(self):
        for name in ('descriptor', 'improvement', 'previous_task', 'previous_outcomes', 'root_decision', 'selected_inputs', 'fixed_control'):
            def changed(pin, label):
                value = self.read_pin(pin, label)
                if pin == successor.figure3b_pin(name):
                    value = copy.deepcopy(value)
                    value['unreviewed'] = True
                return value
            with self.subTest(name=name), self.assertRaises(ValueError): self.handle(changed)

    def test_current_protocol_result_and_policy_promotion_fail(self):
        handle = self.handle()
        documents = handle.snapshot()
        reproduction = handle._legacy.snapshot()['reproduction']
        engine = binding.engine(reproduction)
        for alteration in ('protocol', 'receipt', 'task_identity', 'policy_promotion'):
            outcomes, policy = copy.deepcopy(documents['outcomes']), copy.deepcopy(documents['improvement'])
            if alteration == 'protocol': outcomes['pairing']['improvement'].update(status='specified', protocol={})
            elif alteration == 'receipt': outcomes['result'] = {'paper_win': True}
            elif alteration == 'task_identity': outcomes['original_task_sha256'] = '0' * 64
            else: policy['disposition'] = 'improvement_ready'
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                successor.figure3b_summary(handle, outcomes, reproduction, policy, engine)

    def test_mixed_or_incomplete_selection_has_no_fallback(self):
        for field in ('primary_policy_revision', 'primary_improvement_contract', 'reproduction_contract'):
            row = copy.deepcopy(self.row)
            row['paper_outcomes'].pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError): successor.has_primary_successor(row)
        row = copy.deepcopy(self.row)
        row['paper_outcomes']['primary_improvement_contract'] = successor.approved_pin('improvement')
        with self.assertRaises(ValueError): successor.has_primary_successor(row)

    def test_explicit_adoption_preserves_other_registry_fields(self):
        row = copy.deepcopy(self.row)
        row['specification'] = successor.approved_pin('task')
        row['paper_outcomes'].update(primary_policy_revision=successor.approved_pin('descriptor'),
            primary_improvement_contract=successor.approved_pin('improvement'), outcomes=successor.approved_pin('outcomes'))
        selected, task, outcomes = successor.adoption(row, self.read_pin)
        self.assertEqual(selected, self.row)
        self.assertEqual(task, self.current)
        self.assertEqual(outcomes, self.context()['outcomes'])
        row['specification']['sha256'] = '0' * 64
        with self.assertRaises(ValueError): successor.adoption(row, self.read_pin)

    def test_catalog_selects_scope_and_retains_reference_links(self):
        bound = self.context()
        view = json.loads((ROOT / 'benchmarks/catalog/catalog.json').read_bytes())
        entry = next(row for row in view['tasks'] if row['id'] == successor.TASK)
        entry['specification'] = copy.deepcopy(self.row['specification'])
        entry['paper_outcomes'] = binding.public_summary(self.row, bound)
        entry['paper_improvement']['role'] = catalog.RETAINED_POLICY_ROLE
        view['paper_outcome_counts'] = catalog.paper_outcome_counts(view['tasks'])
        page = catalog.render_tracks(view)[successor.HOME + '/README.md'].decode()
        for text in ('Selected original Figure3b improvement', 'improvement.figure3b.v1.json', 'Full 224-array reproduction', 'Provided-author reference report', 'All four cells remain unknown'):
            self.assertIn(text, page)


if __name__ == '__main__':
    unittest.main()
