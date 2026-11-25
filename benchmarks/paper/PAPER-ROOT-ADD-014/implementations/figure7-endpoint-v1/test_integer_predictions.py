"""Generated finite-integer admission controls; no authentic selections or data."""
import importlib.util
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).with_name('endpoint.py')
SPEC = importlib.util.spec_from_file_location('_figure7_integer_endpoint', SOURCE)
E = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = E
SPEC.loader.exec_module(E)


def selection():
    rows = []
    for j, person in enumerate(E.PARTICIPANTS):
        for i in range(41 if j < 6 else 40):
            rows.append({'participant': person, 'electrode_id': 'generated_' + str(i),
                         'wangarea': 'V1' if j == 0 and i < 31 else 'LO1',
                         'corrected_broadband_xval_percent': 35,
                         'raw_broadband_xval_percent': 36,
                         'corrected_broadband_ecc_pixels': 49,
                         'raw_broadband_ecc_pixels': 49})
    return E.compile_selection(rows, {'corrected': 31, 'raw': 32})


def predictions(sel, series):
    return [{'participant': p, 'electrode_id': ident,
             'predictions': {signal: list(series) for signal in E.SIGNALS}}
            for p, ident in sel.selected]


def ordinary_reference(*key):
    return {'observations': {signal: list(range(75)) for signal in E.SIGNALS},
            'author_predictions': {signal: [i / 2 for i in range(75)] for signal in E.SIGNALS}}


def score(sel, rows, reference=ordinary_reference):
    return E.evaluate_predictions(sel, rows, expected_selection_sha256=sel.selection_sha256,
                                  load_reference=reference)


class IntegerAdmissionControls(unittest.TestCase):
    def test_finite_unsigned_and_object_integer_predictions_match_binary64(self):
        sel = selection()
        for value in (2**63, 2**70):
            with self.subTest(value=value):
                integers = predictions(sel, [value] * 75)
                floats = predictions(sel, [float(value)] * 75)
                calls = []
                def reference(*key):
                    calls.append(key)
                    return ordinary_reference(*key)
                actual = score(sel, integers, reference)
                self.assertEqual(len(calls), 31)
                self.assertEqual(actual, score(sel, floats))
                self.assertEqual(type(integers[0]['predictions']['corrected_alpha'][0]), int)

    def test_finite_integer_reference_is_normalized_without_mutating_callback(self):
        sel = selection()
        series = [2**70 + i * 2**55 for i in range(75)]
        reference = {'observations': {s: list(series) for s in E.SIGNALS},
                     'author_predictions': {s: list(series) for s in E.SIGNALS}}
        rows = predictions(sel, [float(v) for v in series])
        report = score(sel, rows, lambda *key: reference)
        self.assertEqual(report['metrics']['source_cv']['corrected_alpha']['candidate_median_percent'], 100)
        self.assertEqual(report['metrics']['source_cv']['corrected_alpha']['difference_of_medians_pp'], 0)
        self.assertIs(type(reference['observations']['corrected_alpha'][0]), int)

    def test_normal_integer_and_float_results_are_identical(self):
        sel = selection()
        self.assertEqual(score(sel, predictions(sel, list(range(75)))),
                         score(sel, predictions(sel, [float(i) for i in range(75)])))

    def test_invalid_last_candidate_precedes_every_reference_callback(self):
        sel = selection()
        for bad in (True, float('nan'), float('inf'), 10**400):
            rows = predictions(sel, list(range(75)))
            rows[-1]['predictions']['broadband'][-1] = bad
            calls = []
            with self.subTest(value=type(bad).__name__), self.assertRaises(ValueError):
                score(sel, rows, lambda *key: calls.append(key))
            self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
