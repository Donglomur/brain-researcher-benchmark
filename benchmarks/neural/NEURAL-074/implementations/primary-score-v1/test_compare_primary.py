"""Generated complete-panel controls; no authentic maps or programme fitting."""
import dataclasses
import hashlib
import gc
import os
from pathlib import Path
import struct
import sys
import unittest
import weakref

HERE = Path(__file__).resolve().parent
IMPLEMENTATIONS = Path(os.environ.get('N074_IMPLEMENTATIONS', str(HERE.parent)))
sys.path.insert(0, str(IMPLEMENTATIONS / 'agent-operator' / 'source'))
sys.path.insert(0, str(IMPLEMENTATIONS / 'primary-score-v1'))
sys.path.insert(0, str(HERE))

import compare_primary as comparison
from n074.contracts import ContractError, SelectedEvaluationSupport
from n074.evaluation import result_digest
from n074.maps import MapValue
from n074.models import ARMS
from n074.programme import Prediction, ProgrammeResult
from test_primary_score import population


def value(source, numbers):
    raw = struct.pack('<4d', *numbers)
    return MapValue(source, 'fixture-support', raw, 4, hashlib.sha256(raw).hexdigest())


def result(pop, first=True):
    predictions = []
    for person in pop.people:
        for endpoint in pop.endpoints:
            for arm in ARMS:
                good = arm == 'full_rank_ridge' or (
                    arm == 'shared_components' and first and endpoint.family == 'small')
                numbers = (0., 1., 2., 3.) if good else (3., 2., 1., 0.)
                source = 'P1:' + person + ':' + endpoint.identity + ':' + arm
                predictions.append(Prediction(person, endpoint.family, endpoint.identity, arm,
                                               'predicted', value(source, numbers), None))
    return ProgrammeResult('fixture-protocol', pop.taxonomy_pin, pop.eligibility_pin,
                           'fixture-support', tuple(predictions), (), (),
                           'generated fixture only', (), 'complete_source_attempt')


class Authority:
    def __init__(self, pop):
        self.pop, self.calls = pop, 0

    def authenticate_selected_support(self):
        self.calls += 1
        return SelectedEvaluationSupport('generated-issuer', 'fixture-protocol', self.pop.taxonomy_pin,
            self.pop.eligibility_pin, 'fixture-support', 4, '<f8')


class Reader:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def read_protected_target(self, person, endpoint, source):
        self.calls.append((person, endpoint))
        if (person, endpoint) == self.fail:
            raise OSError('generated target failure')
        if len(self.calls) != len(set(self.calls)):
            raise AssertionError('A protected target was requested twice')
        return value(source, (0., 1., 2., 3.))


class CompareControls(unittest.TestCase):
    def setUp(self):
        self.population = population()
        self.first, self.second = result(self.population), result(self.population, False)
        self.reader = Reader()
        self.authority = Authority(self.population)

    def run_compare(self, first=None, second=None, **kwargs):
        first = self.first if first is None else first
        second = self.second if second is None else second
        arguments = dict(expected_support_identity='fixture-support', expected_map_length=4,
                         support_authority=self.authority, maximum_target_panel_bytes=663 * 32)
        arguments.update(kwargs)
        return comparison.compare_primary(first, result_digest(first), second, result_digest(second),
            self.population, self.reader, 32, **arguments)

    def test_full_panel_uses_one_target_capture_and_original_balancing(self):
        first, second, report = self.run_compare()
        self.assertEqual((len(first), len(second), len(self.reader.calls)), (663, 663, 663))
        self.assertEqual(self.authority.calls, 1)
        self.assertEqual(len(report['target_captures']), 663)
        self.assertEqual(report['target_failures'], ())
        self.assertAlmostEqual(report['first']['primary_effect'], 1.)
        self.assertAlmostEqual(report['second']['primary_effect'], 0.)
        self.assertAlmostEqual(report['paired_primary_gain_difference'], 1.)
        self.assertNotAlmostEqual(report['paired_primary_gain_difference'], 2 / 51)
        self.assertEqual(report['paired_primary_status'], 'complete_descriptive')
        self.assertEqual(len(report['effects']), 6)
        self.assertIsNone(report['population_inference'])
        self.assertFalse(report['scientifically_qualified'])

    def test_reversed_conditions_preserve_negative_effect(self):
        _, _, report = self.run_compare(self.second, self.first)
        self.assertAlmostEqual(report['paired_primary_gain_difference'], -1.)

    def test_late_second_nonfinite_rejected_before_target(self):
        index = next(i for i in range(len(self.second.predictions) - 1, -1, -1)
                     if self.second.predictions[i].arm == 'shared_components')
        predictions = list(self.second.predictions)
        old = predictions[index]
        predictions[index] = dataclasses.replace(old, value=value(old.value.source_identity,
                                                                  (0., 1., 2., float('nan'))))
        with self.assertRaises(ContractError):
            self.run_compare(second=dataclasses.replace(self.second, predictions=tuple(predictions)))
        self.assertEqual(self.reader.calls, [])

    def test_missing_second_roster_rejected_before_target(self):
        with self.assertRaises(ContractError):
            self.run_compare(second=dataclasses.replace(self.second, predictions=self.second.predictions[:-1]))
        self.assertEqual(self.reader.calls, [])

    def test_changed_reference_rejected_before_target(self):
        predictions = list(self.second.predictions)
        index = next(i for i, row in enumerate(predictions) if row.arm == 'rank_matched_ridge')
        old = predictions[index]
        predictions[index] = dataclasses.replace(old, value=value(old.value.source_identity, (0., 1., 2., 3.)))
        with self.assertRaises(ContractError):
            self.run_compare(second=dataclasses.replace(self.second, predictions=tuple(predictions)))
        self.assertEqual(self.reader.calls, [])

    def test_target_failure_is_shared_and_never_retried(self):
        self.reader = Reader((self.population.people[0], self.population.endpoints[0].identity))
        a, b, report = self.run_compare()
        self.assertEqual(len(self.reader.calls), 663)
        self.assertEqual(a[0].status, 'target_or_score_failed')
        self.assertEqual(a[0], b[0])
        self.assertEqual(len(report['target_failures']), 1)
        self.assertIsNone(report['paired_primary_gain_difference'])
        self.assertEqual(report['paired_primary_status'], 'incomplete_no_pooled_effect')

    def test_rejected_target_is_not_retained_through_exception_traceback(self):
        class OversizedReader:
            calls = 0
            observed = None

            def read_protected_target(self, person, endpoint, source):
                self.calls += 1
                raw = b'x' * 64
                target = MapValue(source, 'fixture-support', raw, 8, hashlib.sha256(raw).hexdigest())
                self.observed = weakref.ref(target)
                return target

        reader = OversizedReader()
        cache = comparison._TargetCapture(reader, 'fixture-support', 4, 32)
        for _ in range(2):
            with self.assertRaises(Exception) as caught:
                cache.read_protected_target('p', 'e', 'source')
            self.assertEqual(type(caught.exception).__name__, 'ContractError')
            del caught
        gc.collect()
        self.assertIsNone(reader.observed())
        self.assertEqual(reader.calls, 1)
        self.assertEqual(cache.failures, {('p', 'e', 'source'): 'ContractError'})
        self.assertEqual(cache.values, {})

    def test_failed_prediction_retains_both_original_panel_scores(self):
        rows = list(self.first.predictions)
        index = next(i for i, row in enumerate(rows) if row.arm == 'shared_components')
        rows[index] = dataclasses.replace(rows[index], status='final_prediction_failed', value=None,
                                          reason='generated failure')
        a, b, report = self.run_compare(first=dataclasses.replace(self.first, predictions=tuple(rows)))
        self.assertEqual((len(a), len(b)), (663, 663))
        self.assertEqual(a[0].status, 'unpaired_support')
        self.assertEqual(b[0].status, 'paired')
        self.assertIsNone(report['first']['primary_effect'])
        self.assertAlmostEqual(report['second']['primary_effect'], 0.)
        self.assertIsNone(report['paired_primary_gain_difference'])
        self.assertEqual(len(self.reader.calls), 663)

    def test_constant_prediction_leaves_primary_undefined(self):
        rows = list(self.second.predictions)
        index = next(i for i, row in enumerate(rows) if row.arm == 'shared_components')
        rows[index] = dataclasses.replace(rows[index], value=value(rows[index].value.source_identity, (1., 1., 1., 1.)))
        _, _, report = self.run_compare(second=dataclasses.replace(self.second, predictions=tuple(rows)))
        self.assertIsNone(report['paired_primary_gain_difference'])
        self.assertIsNone(report['second']['primary_effect'])
        self.assertAlmostEqual(report['first']['primary_effect'], 1.)

    def test_insufficient_retention_bound_and_stale_commitment_prevent_target_access(self):
        with self.assertRaises(ContractError):
            self.run_compare(maximum_target_panel_bytes=663 * 32 - 1)
        with self.assertRaises(ContractError):
            comparison.compare_primary(self.first, result_digest(self.first), self.second, '0' * 64,
                self.population, self.reader, 32, expected_support_identity='fixture-support',
                expected_map_length=4, support_authority=self.authority,
                maximum_target_panel_bytes=663 * 32)
        self.assertEqual(self.reader.calls, [])


if __name__ == '__main__':
    unittest.main()
