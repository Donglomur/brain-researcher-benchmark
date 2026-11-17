"""Generated software controls; no data, models, targets, or native workloads."""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parent / 'neural061-persistent-state' / 'science' / 'runtime'
sys.path.insert(0, str(RUNTIME))
from n061 import catalogue, policy, outputs, support, production

spec = importlib.util.spec_from_file_location('n061_participant_endpoint', HERE / 'endpoint.py')
endpoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(endpoint)


class NeverRead:
    def __iter__(self): raise AssertionError('private object traversed')
    def __repr__(self): raise AssertionError('private object represented')
    def __deepcopy__(self, memo): return self


def fixture():
    """Full counts, with intentionally uneven animal/session support.

    The first evaluation animal has 17 sessions and each remaining animal one.
    Region generated_a loses session 0 because one reference B seed is absent;
    generated_b has no scientific support. All identities are invented here.
    """
    public = {}
    for i in range(423):
        public[f'generated_source_{i}'] = {'ordinal': i, 'role': 'source', 'animal': f'source_mouse_{i % 126}'}
    for i in range(29):
        animal = 0 if i < 17 else i - 16
        public[f'generated_eval_{i}'] = {'ordinal': 423 + i, 'role': 'evaluation', 'animal': f'eval_mouse_{animal:02d}'}
    cat = catalogue.build(policy.policy(), ('generated_a', 'generated_b'), public)
    collection = outputs.Collection(cat)
    for key in cat.expected:
        missing = key.cell[1] == 'generated_b' or (key.session == cat.evaluation[0] and
                  key.cell[3] == 0 and key.panel == 'REFERENCE' and key.arm == 'B')
        if missing:
            cause = {'status': 'unavailable', 'reason': 'generated_support', 'details': NeverRead()}
            collection.put(key, cause, None, cause)
        else:
            collection.put(key, {'status': 'complete', 'windows': NeverRead()}, NeverRead())
    collection.freeze()
    common = support.build(collection)
    product = production.Production(cat, collection, common, tuple((cell, None) for cell in cat.cells),
                                    (), types.SimpleNamespace(catalogue=cat), {})
    panel = 'F/T0/0'
    records = {'REFERENCE': [], panel: []}
    for ss in common.sessions:
        session_index = cat.evaluation.index(ss.session)
        base = 1000 if session_index == 0 else 2 if session_index < 17 else 15
        for seed in range(10):
            for p in records:
                losses = None
                if ss.status is outputs.Disposition.COMPLETE:
                    if p == 'REFERENCE':
                        losses = {arm: base + seed + {'B': 30, 'BR': 10, 'BC': 20, 'R': 40, 'C': 50, 'ZERO': 60}[arm]
                                  for arm in cat.required_arms(p)}
                    else:
                        losses = {'BR': base + seed, 'BC': base + seed + 100}
                records[p].append({'session': ss.session, 'animal': ss.animal, 'panel': p,
                                   'head': 'wheel_velocity', 'region': ss.region, 'budget': 10,
                                   'match_seed': seed, 'realization': 'anatomy', 'support': ss,
                                   'status': ss.status.value, 'arm_losses': losses, 'values': NeverRead()})
    scored = {'task': 'NEURAL-061', 'policy': cat.policy, 'support': common, 'session_records': records,
              'protected_axis_joins': NeverRead(), 'primary_family': NeverRead(), 'private_target_values': NeverRead()}
    return product, scored


def copy_score(scored):
    """Copy only test-mutated summaries, preserving actual support identities."""
    return {**scored, 'session_records': {
        panel: [{**row, 'arm_losses': None if row['arm_losses'] is None else dict(row['arm_losses'])}
                for row in rows] for panel, rows in scored['session_records'].items()}}


class EndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.product, cls.original = fixture()

    def setUp(self):
        self.scored = copy_score(self.original)

    def report(self):
        return endpoint.participant_report(self.product, self.scored)

    def test_actual_common_reducer_has_equal_animals_not_sessions_or_seeds(self):
        result = self.report()
        region = result['regions'][0]
        # Independent hand calculation: (2 + 12*15)/13 + mean(0..9) = 18.5.
        # A pooled session mean would be (16*2 + 12*15)/28 + 4.5 = 12.0714...
        self.assertEqual(region['primary'], 18.5)
        self.assertEqual(region['metrics']['candidate_BC_loss'], 118.5)
        self.assertEqual(region['metrics']['reference_BR_loss'], 28.5)
        self.assertEqual(region['metrics']['reference_BC_loss'], 38.5)
        self.assertEqual(region['metrics']['BR_improvement'], 10)
        self.assertEqual(region['metrics']['BC_improvement'], -80)
        self.assertEqual(region['n_animals'], 13)
        self.assertEqual(region['animals'][0]['included_session_count'], 16)
        self.assertEqual(region['animals'][0]['metrics']['candidate_BR_loss'], 6.5)

    def test_one_missing_reference_seed_removes_whole_common_session(self):
        region = self.report()['regions'][0]
        row = region['session_coverage'][0]
        self.assertEqual(row['status'], 'scientific_unavailable')
        self.assertEqual(row['completed_seed_count'], 9)
        self.assertEqual(row['complete_seeds'], list(range(1, 10)))
        self.assertEqual(row['unavailable_operands'], [{'seed': 0, 'panel': 'REFERENCE', 'arm': 'B'}])
        self.assertEqual(len(region['session_coverage']), 29)

    def test_empty_region_keeps_all_planned_animals_and_null_metrics(self):
        region = self.report()['regions'][1]
        self.assertIsNone(region['primary'])
        self.assertEqual(region['n_animals'], 0)
        self.assertEqual(len(region['animals']), 13)
        self.assertTrue(all(a['metrics'] is None for a in region['animals']))
        self.assertTrue(all(v is None for v in region['metrics'].values()))
        self.assertEqual(len(region['session_coverage']), 29)

    def test_degrading_bc_cannot_improve_primary(self):
        before = self.report()
        for row in self.scored['session_records']['F/T0/0']:
            if row['arm_losses'] is not None: row['arm_losses']['BC'] += 10000
        after = self.report()
        self.assertEqual(after['regions'][0]['primary'], before['regions'][0]['primary'])
        self.assertEqual(after['regions'][0]['metrics']['candidate_BC_loss'], 10118.5)
        self.assertEqual(after['regions'][0]['metrics']['BC_improvement'], -10080)

    def test_better_br_changes_primary_even_when_reference_family_unchanged(self):
        for row in self.scored['session_records']['F/T0/0']:
            if row['arm_losses'] is not None: row['arm_losses']['BR'] = 0
        report = self.report()
        self.assertEqual(report['regions'][0]['primary'], 0)
        self.assertFalse(report['operator_reference_inference']['is_participant_score'])

    def test_output_does_not_traverse_or_serialize_targets_predictions_or_raw_ids(self):
        body = endpoint.report_bytes(self.product, self.scored)
        report = json.loads(body)
        for private in (b'generated_eval_', b'eval_mouse_', b'generated_source_', b'private_target',
                        b'protected_axis_joins', b'generated_support'):
            self.assertNotIn(private, body)
        self.assertEqual(report['condition'], 'frozen_program')
        self.assertEqual(report['primary']['reporting_unit'], 'region')
        self.assertNotIn('pooled_score', report)
        self.assertFalse(report['qualification']['scientific_qualification'])

    def test_missing_duplicate_and_extra_session_seed_rows_rejected(self):
        for mode in ('missing', 'duplicate', 'extra'):
            self.scored = copy_score(self.original)
            rows = self.scored['session_records']['F/T0/0']
            if mode == 'missing': rows.pop()
            elif mode == 'duplicate': rows.append(rows[0])
            else: rows.append({**rows[0], 'session': 'invented_extra'})
            with self.subTest(mode=mode), self.assertRaises(ValueError): self.report()

    def test_nonfinite_boolean_negative_loss_or_missing_arm_rejected(self):
        for value in (float('nan'), float('inf'), True, -1, 10**1000, '3'):
            self.scored = copy_score(self.original)
            row = next(r for r in self.scored['session_records']['F/T0/0'] if r['arm_losses'] is not None)
            row['arm_losses']['BR'] = value
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError): self.report()
        self.scored = copy_score(self.original)
        row = next(r for r in self.scored['session_records']['REFERENCE'] if r['arm_losses'] is not None)
        del row['arm_losses']['ZERO']
        with self.assertRaises(ValueError): self.report()

    def test_swapped_animal_arm_support_and_wrong_scope_rejected(self):
        mutations = ({'animal': 'wrong_animal'}, {'support': object()}, {'budget': 5},
                     {'head': 'wheel_speed'}, {'realization': 'stratified_anatomy_shuffle'},
                     {'panel': 'I/T0/0'}, {'match_seed': True})
        for mutation in mutations:
            self.scored = copy_score(self.original)
            self.scored['session_records']['F/T0/0'][0].update(mutation)
            with self.subTest(fields=tuple(mutation)), self.assertRaises(ValueError): self.report()

    def test_unavailable_session_cannot_retain_selected_losses(self):
        self.scored['session_records']['F/T0/0'][0]['arm_losses'] = {'BR': 1, 'BC': 2}
        with self.assertRaises(ValueError): self.report()

    def test_distinct_policy_support_or_task_rejected(self):
        for field, value in (('policy', policy.policy()), ('support', object()), ('task', 'NEURAL-other')):
            self.scored = copy_score(self.original)
            self.scored[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.report()

    def test_failed_collection_is_not_a_scientific_exclusion(self):
        product, scored = fixture()
        product.collection.fail(RuntimeError('generated fit failure'))
        with self.assertRaises(ValueError): endpoint.participant_report(product, scored)


if __name__ == '__main__':
    unittest.main(verbosity=2)
