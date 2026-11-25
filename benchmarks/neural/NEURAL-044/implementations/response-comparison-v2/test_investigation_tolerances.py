"""Generated tolerance-admission controls; no recordings, fits or target files."""
import copy
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'registered-runtime' / 'source'
sys.path.insert(0, str(SOURCE))
from alm.contracts import Refusal
from alm.grading import grade_investigation


def fixture():
    truth = {'task': 'NEURAL-044',
             'estimand': 'conditional_tuning_response_association',
             'source_digest': 'a' * 64, 'disposition_digest': 'b' * 64,
             'mouse_values': [{'mouse': 'generated', 'effect': 1.0, 'improvement': 2.0}],
             'controls': ['generated_control'],
             'control_results': {'generated_control': {'value': 3.0}},
             'interpretation': 'inconclusive'}
    return truth, copy.deepcopy(truth)


class InvestigationToleranceTests(unittest.TestCase):
    def test_finite_tolerances_preserve_declared_acceptance_and_rejection(self):
        truth, report = fixture()
        for absolute, relative in ((0, 0), (0.0, 0.0), (0.125, 0), (0, 0.125)):
            with self.subTest(absolute=absolute, relative=relative):
                accepted = grade_investigation(report, truth,
                    {'absolute': absolute, 'relative': relative})
                self.assertTrue(accepted['numerical_reproduction_pass'])
                self.assertFalse(accepted['scientific_qualification'])
        report['mouse_values'][0]['effect'] += 0.125
        grade_investigation(report, truth, {'absolute': 0.125, 'relative': 0})
        grade_investigation(report, truth, {'absolute': 0, 'relative': 0.125})
        with self.assertRaisesRegex(Refusal, 'numerical claim differs'):
            grade_investigation(report, truth, {'absolute': 0.0625, 'relative': 0})

    def test_invalid_tolerances_refused_even_for_an_exact_report(self):
        truth, report = fixture()
        invalid = (True, False, '0', None, float('nan'), float('inf'),
                   -float('inf'), -0.125, -1, 10 ** 400)
        for name in ('absolute', 'relative'):
            for value in invalid:
                with self.subTest(name=name, value=repr(value)):
                    tolerances = {'absolute': 0.0, 'relative': 0.0, name: value}
                    with self.assertRaisesRegex(Refusal, 'finite nonnegative numerical tolerance'):
                        grade_investigation(report, truth, tolerances)

    def test_unbounded_tolerance_cannot_certify_wrong_effect_or_control(self):
        for name in ('absolute', 'relative'):
            for target in ('effect', 'control'):
                with self.subTest(name=name, target=target):
                    truth, report = fixture()
                    if target == 'effect':
                        report['mouse_values'][0]['effect'] = 1e100
                    else:
                        report['control_results']['generated_control']['value'] = 1e100
                    with self.assertRaisesRegex(Refusal, 'finite nonnegative numerical tolerance'):
                        grade_investigation(report, truth,
                            {'absolute': 0.0, 'relative': 0.0, name: float('inf')})

    def test_missing_or_nondictionary_tolerances_refuse(self):
        truth, report = fixture()
        for tolerances in (None, [], {}, {'absolute': 0}, {'relative': 0}):
            with self.subTest(tolerances=tolerances):
                with self.assertRaisesRegex(Refusal, 'numerical tolerance fields'):
                    grade_investigation(report, truth, tolerances)


if __name__ == '__main__':
    unittest.main(verbosity=2)
