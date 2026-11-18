"""Focused metadata controls for complete original Deeprecon Figure 2 binding."""
import copy
import hashlib
import importlib.util
import io
import itertools
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), 'exec'), result.__dict__)
    return result


binding = module('complete_figure2_binding_controls', ROOT / 'src/neurobench/paper_outcomes_binding.py')
successor = binding.primary_successor_module('PAPER-paper-method-029')


class DeepreconFigure2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / binding.REGISTRY).read_bytes())
        cls.original_row = next(row for row in cls.registry['tasks'] if row['id'] == successor.TASK)
        cls.previous = binding.coverage(cls.registry, cls.read_pin)
        cls.current = json.loads((ROOT / successor.HOME / 'task.json').read_bytes())

    @classmethod
    def read_pin(cls, pin, label):
        payload = (ROOT / pin['path']).read_bytes()
        if len(payload) != pin['bytes'] or hashlib.sha256(payload).hexdigest() != pin['sha256']:
            raise ValueError('Test reader raw identity mismatch: ' + label)
        return json.loads(payload)

    def setUp(self):
        self.row = copy.deepcopy(self.original_row)
        self.row['specification'] = successor.approved_pin('task')
        self.row['paper_outcomes'].update(primary_policy_revision=successor.approved_pin('descriptor'),
            primary_improvement_contract=successor.approved_pin('improvement'),
            reproduction_contract=successor.approved_pin('reproduction'), outcomes=successor.approved_pin('outcomes'))

    def handle(self, reader=None):
        return successor.authenticate(task_id=successor.TASK,
            revision_pin=successor.approved_pin('descriptor'), primary_pin=successor.approved_pin('improvement'),
            reproduction_pin=successor.approved_pin('reproduction'), previous_pin=successor.approved_pin('pre_outcomes'),
            retained_improvement_pin=successor.approved_pin('retained_improvement'), read_pin=reader or self.read_pin)

    def context(self):
        return binding.context(self.row, self.current, self.previous, self.read_pin)

    def test_complete_vector_roles_and_source_companions(self):
        docs = self.handle().snapshot()
        panel = docs['descriptor']['panel_binding']
        self.assertEqual(panel['directed_pairs'], [list(p) for p in itertools.permutations(panel['subjects'], 2)])
        self.assertEqual((len(panel['subjects']), len(panel['directed_pairs']), len(panel['rois']), len(panel['axes'])), (5, 20, 6, 2))
        self.assertEqual(panel['primary_comparator']['method_key'], 'content_loss')
        self.assertEqual(panel['required_control']['method_key'], 'brain_loss')
        self.assertEqual(panel['primary_comparator']['pair_axis_values'], 240)
        self.assertEqual(panel['required_control']['pair_axis_values'], 240)
        self.assertEqual((panel['images'], panel['repeats'], panel['training_samples']), (50, 24, 6000))
        self.assertEqual(panel['published_source']['axis_columns'], {'pattern': 'pattern_mean', 'profile': 'profile_mean'})
        findings = {f['id']: f for f in docs['previous']['reproduction']['findings']}
        companions = panel['bootstrap_companions']['finding_ids']
        self.assertEqual(len(set(companions)), 72)
        self.assertTrue(all(findings[key]['expected'] is None for key in companions))
        self.assertEqual(panel['continuous_reporting']['pair_rows'], 480)
        self.assertEqual(panel['continuous_reporting']['roi_method_axis_groups'], 24)
        self.assertEqual(panel['continuous_reporting']['summary_role'], 'observed_equal_pair_mean_not_figure_bootstrap_mean')
        self.assertIsNone(panel['decision_policy']['combined_scalar'])
        self.assertIsNone(panel['decision_policy']['binary_threshold'])
        self.assertFalse(panel['decision_policy']['partial_panel_win'])

    def test_real_context_selects_current_policy_without_qualification(self):
        bound = self.context()
        docs = self.handle().snapshot()
        self.assertEqual(bound['improvement_contract'], docs['improvement'])
        self.assertEqual(bound['improvement_contract']['same_task'], docs['previous']['improvement']['same_task'])
        self.assertEqual(bound['reproduction_contract'], docs['previous']['reproduction'])
        self.assertEqual(bound['improvement_contract']['disposition'], 'source_unresolved')
        self.assertIsNone(bound['improvement_contract']['comparison']['published_baseline']['value'])
        self.assertIsNone(bound['candidate_interface'])
        self.assertIsNone(bound['author_reproduction_routes'])
        self.assertEqual(len(bound['summary']['cells']), 4)
        self.assertTrue(all(c['scientific_outcome'] == 'unknown' and not c['endpoint_eligible'] and c['receipt'] is None
                            for c in bound['summary']['cells']))
        self.assertTrue(all(p['protocol'] is None for p in bound['outcomes']['pairing'].values()))
        self.assertFalse(any(bound['summary']['paired_metadata_admitted'].values()))
        self.assertIsNone(self.current['evaluation']['executor_ref'])
        self.assertIsNone(self.current['evaluation']['scorer_ref'])
        self.assertFalse(self.current['evaluation']['binary_reward_registered'])

    def test_original_nine_edit_authentication_and_projection_remain_first_stage(self):
        handle = self.handle()
        docs = handle.snapshot()
        self.assertEqual(len(docs['previous']['descriptor']['improvement_replacements']), 9)
        self.assertEqual(docs['previous']['improvement']['same_task'], docs['improvement']['same_task'])
        self.assertEqual(successor.project(docs['previous']['archived_task.json'], handle), self.current)
        self.assertEqual(docs['previous_outcomes'], docs['previous']['outcomes'])
        self.assertEqual(docs['outcomes']['contracts']['reproduction'], docs['previous_outcomes']['contracts']['reproduction'])
        self.assertEqual(docs['outcomes']['pairing']['reproduction'], docs['previous_outcomes']['pairing']['reproduction'])
        self.assertEqual(len(handle.members), 4)
        self.assertEqual(len({p['path'] for p in handle.members}), 4)

    def test_panel_axis_roi_pair_method_and_bootstrap_tampering_refused(self):
        mutators = [lambda p: p['directed_pairs'].pop(), lambda p: p['rois'].pop(), lambda p: p['axes'].pop(),
                    lambda p: p['primary_comparator'].update(method_key='brain_loss'),
                    lambda p: p['bootstrap_companions']['finding_ids'].pop(),
                    lambda p: p.update(images=49), lambda p: p.update(repeats=23),
                    lambda p: p['decision_policy'].update(binary_threshold=0.0)]
        for mutation in mutators:
            def altered(pin, label):
                result = self.read_pin(pin, label)
                if pin == successor.approved_pin('descriptor'):
                    mutation(result['panel_binding'])
                return result
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'parsed identity mismatch'):
                self.handle(altered)

    def test_predecessor_and_current_document_tampering_refused(self):
        for name in ('descriptor', 'improvement', 'task', 'outcomes', 'previous_task', 'previous_outcomes',
                     'reproduction', 'retained_improvement', 'reference'):
            target = successor.approved_pin(name)
            def altered(pin, label):
                value = self.read_pin(pin, label)
                if pin == target:
                    value['unreviewed'] = True
                return value
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'parsed identity mismatch'):
                self.handle(altered)

    def test_wrong_owner_incomplete_selection_and_retained_policy_substitution_refused(self):
        for field in ('primary_policy_revision', 'primary_improvement_contract', 'reproduction_contract'):
            changed = copy.deepcopy(self.row)
            changed['paper_outcomes'].pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                binding.has_primary_successor(changed)
        changed = copy.deepcopy(self.row)
        changed['paper_outcomes']['primary_improvement_contract'] = successor.approved_pin('retained_improvement')
        with self.assertRaises(ValueError): binding.has_primary_successor(changed)
        changed = copy.deepcopy(self.row)
        changed['id'] = 'PAPER-UNREVIEWED'
        with self.assertRaises(ValueError): binding.has_primary_successor(changed)
        self.assertNotIn(successor.TASK, binding.endpoint_selection_module().TASKS)

    def test_predecessor_source_loader_checks_exact_identity(self):
        saved = successor._PREVIOUS
        try:
            successor._PREVIOUS = None
            with patch.object(Path, 'open', return_value=io.BytesIO(b'unreviewed metadata source')):
                with self.assertRaisesRegex(ValueError, 'authenticator identity mismatch'):
                    successor._previous()
        finally:
            successor._PREVIOUS = saved

    def test_immutable_handle_and_projection_preimage(self):
        handle = self.handle()
        docs = handle.snapshot()
        changed = copy.deepcopy(docs['previous']['archived_task.json'])
        changed['status'] = 'improvement_ready'
        with self.assertRaisesRegex(ValueError, 'deterministic predecessor'):
            successor.project(changed, handle)
        with self.assertRaises(ValueError): successor.project(docs['previous']['archived_task.json'], {})
        with self.assertRaises(AttributeError): handle._payload = b'{}'
        docs['improvement']['disposition'] = 'improvement_ready'
        self.assertEqual(handle.primary_improvement['disposition'], 'source_unresolved')


if __name__ == '__main__':
    unittest.main()
