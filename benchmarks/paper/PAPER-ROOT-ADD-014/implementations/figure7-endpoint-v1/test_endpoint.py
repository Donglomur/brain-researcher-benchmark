"""Generated controls only: no source response, selection or author-fit data."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).resolve().parent / 'endpoint.py'
SPEC = importlib.util.spec_from_file_location('figure7_endpoint_controls', PATH)
E = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = E
SPEC.loader.exec_module(E)


def source_rows():
    rows = []
    for j, person in enumerate(E.PARTICIPANTS):
        for i in range(41 if j < 6 else 40):
            selected = (j == 0 and i < 20) or (j == 1 and i < 11)
            rows.append({'participant': person, 'electrode_id': 'invented_' + str(i),
                         'wangarea': 'V1' if selected else 'LO1',
                         'corrected_broadband_xval_percent': 35,
                         'raw_broadband_xval_percent': 36,
                         'corrected_broadband_ecc_pixels': 49,
                         'raw_broadband_ecc_pixels': 49})
    return rows


def selection():
    return E.compile_selection(source_rows(), {'corrected': 31, 'raw': 32})


def waveform(scale, offset=0):
    # Unequal fold lengths, nonzero fold means and signed response values.
    return [scale * (i - 100) + offset for i in range(75)]


def candidate(sel):
    return [{'participant': p, 'electrode_id': e,
             'predictions': {'corrected_alpha': waveform(1 if i < 16 else 0),
                             'raw_alpha': waveform(.5), 'broadband': waveform(1)}}
            for i, (p, e) in enumerate(sel.selected)]


def reference(p, e):
    return {'observations': {s: waveform(1) for s in E.SIGNALS},
            'author_predictions': {'corrected_alpha': waveform(.5),
                                   'raw_alpha': waveform(0), 'broadband': waveform(1)}}


class EndpointControls(unittest.TestCase):
    def test_original_median_and_companion_contrasts(self):
        sel = selection()
        report = E.evaluate_predictions(sel, candidate(sel), expected_selection_sha256=sel.selection_sha256,
                                        load_reference=reference)
        # Independently: slope1 => 100%, slope0 => 0%, slope.5 => 75% COD.
        # Sixteen100s among31 gives100% median; equal-person means would be40%.
        primary = report['metrics']['source_cv']['corrected_alpha']
        self.assertEqual(primary['candidate_median_percent'], 100)
        self.assertEqual(primary['author_median_percent'], 75)
        self.assertEqual(primary['difference_of_medians_pp'], 25)
        self.assertEqual(primary['per_participant']['p02']['candidate_median_percent'], 0)
        self.assertEqual(report['metrics']['source_cv']['broadband']['difference_of_medians_pp'], 0)
        self.assertEqual(report['baseline_correction_contrasts']['source_cv'],
                         {'candidate_corrected_minus_raw_medians_pp': 25,
                          'author_corrected_minus_raw_medians_pp': 75})
        self.assertEqual(report['selected_participants'], 2)

    def test_complete_granular_distribution_retains_identity_and_pairing(self):
        sel = selection()
        report = E.evaluate_predictions(sel, candidate(sel), expected_selection_sha256=sel.selection_sha256,
                                        load_reference=reference)
        rows = report['per_electrode']
        self.assertEqual([(r['participant'], r['electrode_id']) for r in rows], list(sel.selected))
        self.assertEqual(len(rows), 31)
        for i, row in enumerate(rows):
            self.assertEqual(set(row), {'participant', 'electrode_id', 'metrics',
                                        'baseline_correction_contrasts'})
            self.assertEqual(set(row['metrics']), {'source_cv', 'literal_eq6'})
            for metric in row['metrics'].values():
                # Analytic proportional waveforms: COD is 100, 75 or 0 percent.
                expected = 100 if i < 16 else 0
                self.assertEqual(metric['corrected_alpha'], {
                    'candidate_percent': expected, 'author_percent': 75,
                    'paired_difference_pp': expected - 75})
                self.assertEqual(metric['raw_alpha'], {
                    'candidate_percent': 75, 'author_percent': 0, 'paired_difference_pp': 75})
                self.assertEqual(metric['broadband'], {
                    'candidate_percent': 100, 'author_percent': 100, 'paired_difference_pp': 0})
            for contrast in row['baseline_correction_contrasts'].values():
                self.assertEqual(contrast, {'candidate_corrected_minus_raw_pp': expected - 75,
                                            'author_corrected_minus_raw_pp': 75})
        # Reconstruct every summary from the complete table without response access.
        for metric, signals in report['metrics'].items():
            for signal, summary in signals.items():
                for method in ('candidate', 'author'):
                    vector = [r['metrics'][metric][signal][method + '_percent'] for r in rows]
                    self.assertEqual(E._median(vector), summary[method + '_median_percent'])
                differences = [r['metrics'][metric][signal]['paired_difference_pp'] for r in rows]
                self.assertEqual(E._median(differences), summary['median_paired_difference_pp'])

    def test_identity_join_not_candidate_order(self):
        sel = selection()
        direct = E.evaluate_predictions(sel, candidate(sel), expected_selection_sha256=sel.selection_sha256,
                                        load_reference=reference)
        reversed_order = E.evaluate_predictions(sel, list(reversed(candidate(sel))),
                                               expected_selection_sha256=sel.selection_sha256,
                                               load_reference=reference)
        self.assertEqual(direct, reversed_order)

    def test_fold_dc_removed_separately_literal_retained(self):
        sel = selection()
        pred = candidate(sel)
        for row in pred:
            row['predictions']['corrected_alpha'] = [i - 100 + (1000 if i < 38 else -2000)
                                                     for i in range(75)]
        report = E.evaluate_predictions(sel, pred, expected_selection_sha256=sel.selection_sha256,
                                        load_reference=reference)
        self.assertEqual(report['metrics']['source_cv']['corrected_alpha']['candidate_median_percent'], 100)
        self.assertLess(report['metrics']['literal_eq6']['corrected_alpha']['candidate_median_percent'], -100)
        for row in report['per_electrode']:
            self.assertEqual(row['metrics']['source_cv']['corrected_alpha']['candidate_percent'], 100)
            self.assertLess(row['metrics']['literal_eq6']['corrected_alpha']['candidate_percent'], -100)

    def test_source_strict_boundaries_and_both_branches(self):
        for field, value in [('corrected_broadband_xval_percent', 31),
                             ('raw_broadband_xval_percent', 32),
                             ('corrected_broadband_ecc_pixels', 50),
                             ('raw_broadband_ecc_pixels', 50), ('wangarea', 'V1d')]:
            with self.subTest(field=field):
                rows = source_rows()
                rows[0][field] = value
                with self.assertRaisesRegex(ValueError, '31-electrode'):
                    E.compile_selection(rows, {'corrected': 31, 'raw': 32})

    def test_source_nonfinite_must_not_pass_negated_comparison(self):
        for value in (float('nan'), float('inf'), -float('inf')):
            rows = source_rows()
            rows[0]['corrected_broadband_xval_percent'] = value
            with self.assertRaisesRegex(ValueError, 'nonfinite'):
                E.compile_selection(rows, {'corrected': 31, 'raw': 32})
        with self.assertRaisesRegex(ValueError, 'source-rounded'):
            E.compile_selection(source_rows(), {'corrected': float('nan'), 'raw': 32})

    def test_original_population_required_and_ids_are_nested(self):
        rows = source_rows()
        self.assertEqual(len(rows), 366)
        # Same electrode labels in distinct participants are legitimate.
        self.assertEqual(len(selection().selected), 31)
        for wrong in (rows[:-1], rows + rows[:67]):
            with self.assertRaisesRegex(ValueError, '366-row'):
                E.compile_selection(wrong, {'corrected': 31, 'raw': 32})
        rows[-1] = dict(rows[0])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            E.compile_selection(rows, {'corrected': 31, 'raw': 32})

    def test_all_admission_precedes_reference_access(self):
        sel = selection()
        for damage in ('nonfinite_last', 'missing_control', 'duplicate_identity', 'score_injection'):
            calls = []
            pred = candidate(sel)
            if damage == 'nonfinite_last':
                pred[-1]['predictions']['broadband'][-1] = float('nan')
            elif damage == 'missing_control':
                del pred[-1]['predictions']['raw_alpha']
            elif damage == 'duplicate_identity':
                pred[-1] = pred[0]
            else:
                pred[-1]['score'] = 100
            with self.subTest(damage=damage), self.assertRaises(ValueError):
                E.evaluate_predictions(sel, pred, expected_selection_sha256=sel.selection_sha256,
                                       load_reference=lambda *key: calls.append(key))
            self.assertEqual(calls, [])

    def test_frozen_selection_mismatch_precedes_reference_access(self):
        sel = selection()
        calls = []
        for bad in ('0' * 64, replace(sel, selected=tuple(reversed(sel.selected)))):
            with self.assertRaisesRegex(ValueError, 'binding mismatch'):
                E.evaluate_predictions(bad if isinstance(bad, E.Selection) else sel, candidate(sel),
                                       expected_selection_sha256=sel.selection_sha256 if isinstance(bad, E.Selection) else bad,
                                       load_reference=lambda *key: calls.append(key))
        self.assertEqual(calls, [])

    def test_no_undefined_electrode_omission(self):
        sel = selection()
        def bad_reference(*key):
            row = reference(*key)
            row['observations']['corrected_alpha'] = [3] * 75
            return row
        with self.assertRaisesRegex(ValueError, 'undefined metric'):
            E.evaluate_predictions(sel, candidate(sel), expected_selection_sha256=sel.selection_sha256,
                                   load_reference=bad_reference)

    def test_difference_of_medians_is_not_median_difference(self):
        c, a = [0, 1, 100], [0, 99, 100]
        self.assertEqual(E._median(c) - E._median(a), -98)
        self.assertEqual(E._median([x-y for x, y in zip(c, a)]), 0)


if __name__ == '__main__':
    unittest.main()
