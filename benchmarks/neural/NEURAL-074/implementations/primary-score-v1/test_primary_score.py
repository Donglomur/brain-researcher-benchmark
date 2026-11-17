"""Generated metric/roster controls only; no authentic maps or model execution."""
import dataclasses
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'agent-operator' / 'source'))
sys.path.insert(0, str(HERE))
import primary_score as scorer
from n074.catalogue import DECLARED_ENDPOINTS, DECLARED_PEOPLE
from n074.contracts import Case, ContractError, Endpoint, Population
from n074.evaluation import CaseEvaluation
from n074.models import ARMS


def population():
    # Deliberately unequal family sizes (1 versus 50) expose micro averaging.
    endpoints = tuple(Endpoint(identity, task, contrast, 'small' if i == 0 else 'large', identity)
                      for i, (identity, task, contrast) in enumerate(DECLARED_ENDPOINTS))
    cases = tuple(Case(person, endpoint.identity, 'present', 'generated fixture',
                       'generated:' + person + ':' + endpoint.identity)
                  for person in DECLARED_PEOPLE for endpoint in endpoints)
    return Population(DECLARED_PEOPLE, endpoints, cases, 'fixture-declaration',
                      'fixture-taxonomy', 'fixture-eligibility').validate()


def quantities(correlation, mse, mae):
    return tuple(sorted({'map_correlation': correlation,
                         'correlation_status': 'defined' if correlation is not None else 'undefined_constant_map',
                         'mean_squared_error': mse, 'mean_absolute_error': mae,
                         'mean_bias': 0.0, 'prediction_mean': 0.0, 'target_mean': 0.0}.items()))


def row(person, endpoint, correlation, reference=0.0, full=-0.25):
    values = {'shared_components': quantities(correlation, 2.0, 1.0),
              'rank_matched_ridge': quantities(reference, 3.0, 1.5),
              'full_rank_ridge': quantities(full, 1.0, 0.5)}
    effects = []
    for ref in scorer.REFERENCES:
        for metric in scorer.METRICS:
            a, b = dict(values['shared_components'])[metric], dict(values[ref])[metric]
            effects.append((ref, metric, None if a is None or b is None else
                            (a - b if metric == 'map_correlation' else b - a)))
    return CaseEvaluation(person, endpoint.family, endpoint.identity, 'paired',
                          tuple((arm, values[arm]) for arm in ARMS), tuple(effects), None)


def complete(pop):
    return tuple(row(person, endpoint, 0.8 if endpoint.family == 'small' else -0.2)
                 for person in pop.people for endpoint in pop.endpoints)


class PrimaryControls(unittest.TestCase):
    def setUp(self):
        self.population = population()
        self.rows = complete(self.population)

    def test_registered_primary_is_family_balanced_and_signed(self):
        summary = scorer.summarize_primary(self.rows, self.population)
        # (0.8 + (-0.2))/2 = 0.3, not (0.8 - 0.2*50)/51.
        self.assertAlmostEqual(summary['primary_effect'], 0.3)
        self.assertNotAlmostEqual(summary['primary_effect'], (0.8 - 0.2 * 50) / 51)
        self.assertEqual(summary['primary_reference'], 'rank_matched_ridge')
        self.assertEqual(summary['primary_metric'], 'map_correlation')
        self.assertEqual(summary['declared_cases'], 663)
        self.assertEqual(summary['declared_people'], 13)
        self.assertEqual(len(summary['case_dispositions']), 663)
        self.assertIsNone(summary['primary_decision'])
        self.assertIsNone(summary['population_inference'])
        self.assertFalse(summary['scientifically_qualified'])
        # Retain all six contrasts and their direction-aligned signs.
        effects = {(r['reference'], r['metric']): r['balanced_effect'] for r in summary['effects']}
        self.assertAlmostEqual(effects['full_rank_ridge', 'map_correlation'], 0.55)
        self.assertAlmostEqual(effects['rank_matched_ridge', 'mean_squared_error'], 1.0)
        self.assertAlmostEqual(effects['full_rank_ridge', 'mean_squared_error'], -1.0)

    def test_person_balance_and_negative_gain(self):
        rows = tuple(row(person, endpoint, 0.8 if person == self.population.people[0] else -0.2)
                     for person in self.population.people for endpoint in self.population.endpoints)
        result = scorer.summarize_primary(rows, self.population)
        self.assertAlmostEqual(result['primary_effect'], (0.8 - 12 * 0.2) / 13)
        self.assertLess(result['primary_effect'], 0)

    def test_undefined_correlation_preserves_all_cells_without_pooled_score(self):
        bad = row(self.population.people[0], self.population.endpoints[0], None)
        result = scorer.summarize_primary((bad,) + self.rows[1:], self.population)
        self.assertIsNone(result['primary_effect'])
        self.assertEqual(result['primary_status'], 'incomplete_no_pooled_effect')
        selected = next(r for r in result['effects'] if r['reference'] == 'rank_matched_ridge'
                        and r['metric'] == 'map_correlation')
        self.assertEqual(len(selected['cells']), 26)
        self.assertEqual(len(selected['person_effects']), 13)
        self.assertEqual(sum(v is None for _, v in selected['person_effects']), 1)
        self.assertEqual(result['declared_cases'], 663)

    def test_failures_never_shrink_panel(self):
        for status in ('unpaired_support', 'target_or_score_failed'):
            with self.subTest(status=status):
                bad = dataclasses.replace(self.rows[0], status=status, metrics=(), effects=(), reason='fixture failure')
                result = scorer.summarize_primary((bad,) + self.rows[1:], self.population)
                self.assertIsNone(result['primary_effect'])
                self.assertEqual(result['case_dispositions'][0][-2:], (status, 'fixture failure'))
                self.assertTrue(all(e['balanced_effect'] is None for e in result['effects']))

    def test_missing_duplicate_extra_family_and_wrong_condition_rejected(self):
        variants = [self.rows[:-1], self.rows[:-1] + self.rows[:1], self.rows + self.rows[:1],
                    (dataclasses.replace(self.rows[0], family='changed'),) + self.rows[1:],
                    (object(),) + self.rows[1:]]
        for rows in variants:
            with self.subTest(kind=repr(rows[0])[:50]):
                with self.assertRaises(ContractError):
                    scorer.summarize_primary(rows, self.population)

    def test_nonfinite_bool_out_of_range_and_inconsistent_gain_rejected(self):
        for invalid in (math.nan, math.inf, -math.inf, True, 1.01):
            with self.subTest(invalid=invalid):
                bad = row(self.population.people[0], self.population.endpoints[0], invalid)
                with self.assertRaises(ContractError):
                    scorer.summarize_primary((bad,) + self.rows[1:], self.population)
        bad = dataclasses.replace(self.rows[0], effects=self.rows[0].effects[:-1] +
                                  (('rank_matched_ridge', 'mean_absolute_error', 99.0),))
        with self.assertRaises(ContractError):
            scorer.summarize_primary((bad,) + self.rows[1:], self.population)

    def test_duplicate_arm_or_effect_and_bad_correlation_status_rejected(self):
        original = self.rows[0]
        values = dict(original.metrics)
        q = dict(values['shared_components'])
        q['correlation_status'] = 'undefined_constant_map'
        values['shared_components'] = tuple(sorted(q.items()))
        variants = [dataclasses.replace(original, metrics=original.metrics[:-1] + original.metrics[:1]),
                    dataclasses.replace(original, effects=original.effects[:-1] + original.effects[:1]),
                    dataclasses.replace(original, metrics=tuple(values.items()))]
        for bad in variants:
            with self.assertRaises(ContractError):
                scorer.summarize_primary((bad,) + self.rows[1:], self.population)

    def test_selection_disposition_and_population_identity(self):
        absent = dataclasses.replace(self.population.cases[0], status='absent', source_identity=None)
        population2 = dataclasses.replace(self.population, cases=(absent,) + self.population.cases[1:])
        with self.assertRaises(ContractError):
            scorer.summarize_primary(self.rows, population2)
        summary = scorer.summarize_primary(self.rows, self.population)
        self.assertEqual(summary['population_identity']['taxonomy'], 'fixture-taxonomy')

    def test_input_order_does_not_change_effect(self):
        a = scorer.summarize_primary(self.rows, self.population)
        b = scorer.summarize_primary(tuple(reversed(self.rows)), self.population)
        self.assertEqual(a['effects'], b['effects'])
        self.assertEqual(a['primary_effect'], b['primary_effect'])

    def test_existing_preflight_rejects_malformed_result_before_target(self):
        class SupportAuthority:
            def authenticate_selected_support(self):
                from n074.contracts import SelectedEvaluationSupport
                return SelectedEvaluationSupport('fixture', 'fixture-protocol', 'fixture-taxonomy',
                    'fixture-eligibility', 'fixture-support', 4, '<f8')
        class TargetReader:
            reads = 0
            def read_protected_target(self, *args):
                self.reads += 1
                raise AssertionError('Target must not be read')
        reader = TargetReader()
        with self.assertRaises(ContractError):
            scorer.evaluate_primary(object(), '0' * 64, self.population, reader, 32,
                                    expected_support_identity='fixture-support', expected_map_length=4,
                                    support_authority=SupportAuthority())
        self.assertEqual(reader.reads, 0)

    def test_wrapper_preserves_existing_evaluator_and_attaches_commitment(self):
        @dataclasses.dataclass
        class Result:
            protocol_identity: str = 'fixture-protocol'
            support_identity: str = 'fixture-support'
        marker, authority = object(), object()
        result = Result()
        with patch.object(scorer.evaluation, 'evaluate', return_value=self.rows) as existing:
            rows, summary = scorer.evaluate_primary(result, 'a' * 64, self.population, marker, 32,
                expected_support_identity='fixture-support', expected_map_length=4, support_authority=authority)
        existing.assert_called_once_with(result, 'a' * 64, self.population, marker, 32,
                expected_support_identity='fixture-support', expected_map_length=4, support_authority=authority)
        self.assertIs(rows, self.rows)
        self.assertEqual(summary['prediction_commitment'], 'a' * 64)
        self.assertEqual(summary['support_identity'], 'fixture-support')


if __name__ == '__main__':
    unittest.main(verbosity=2)
