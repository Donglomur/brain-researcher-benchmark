"""Generated source-interface controls; no scientific or native backend run."""
import importlib.util
import itertools
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('isttc_endpoint_controls', HERE / 'endpoints.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def cohort():
    return {'schema': 'isttc_empirical_cohort_v1', 'source_sha256': 'a' * 64,
            'units': [{'unit_id': 'u' + str(i), 'mouse_id': 'm' + str(i % 26),
                       'session_id': 's' + str(i % 26), 'area': ("LGd", "VISp", "VISl", "VISrl", "LP", "VISal", "VISpm", "VISam")[i % 8],
                       'fr_hz': 10 + i % 5, 'lv': 1 + (i % 7) / 10} for i in range(5775)]}


def estimates(c):
    rows = []
    for unit in c['units']:
        for axis, levels, methods in [('duration_minutes', (1, 5, 10, 20, 30), e.METHODS[:2]),
                                      ('trial_count', (40, 60, 80, 100), e.METHODS[2:])]:
            for level in levels:
                for index, method in enumerate(methods):
                    reference = 10 * (index + 1)
                    tau = reference if axis == 'duration_minutes' and level == 30 else (
                        reference + (index + 1) * level if axis == 'duration_minutes' else reference + 400 * (index + 1) / level)
                    rows.append({'unit_id': unit['unit_id'], 'axis': axis, 'level': level,
                                 'method': method, 'tau_bins': tau, 'r_squared': 0.5, 'failure_reason': None})
    return {'schema': 'isttc_sensitivity_estimates_v1', 'rows': rows}


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cohort = cohort()
        cls.estimates = estimates(cls.cohort)

    def test_policy_is_exact_and_both_reference_outputs_are_mandatory(self):
        policy = e.policy()
        self.assertEqual(policy['prospective_windows']['seed'], 20261117004)
        self.assertEqual(policy['prospective_animal_uncertainty']['seed'], 20261117005)
        self.assertEqual(policy['prospective_animal_uncertainty']['repetitions'], 1000)
        report = e.sensitivity_report(self.cohort, self.estimates)
        self.assertEqual(list(report['reference_policy_reports']), list(e.REFERENCE_POLICIES))
        self.assertEqual(report['original_population_fit_support']['observed_coordinates'], 103950)
        self.assertEqual(report['original_population_fit_support']['failed_coordinates'], [])
        primary = report['reference_policy_reports']['method_specific_full']['panels']
        other = report['reference_policy_reports']['all_full_isttc']['panels']
        self.assertEqual(primary['duration_minutes']['complete_case_units'], 5775)
        self.assertEqual(primary['trial_count']['complete_case_units'], 5775)
        self.assertEqual(primary['duration_minutes']['unit_weighted_descriptive'][0]['median_pseudo_ree_percent'], 10)
        self.assertEqual(other['duration_minutes']['unit_weighted_descriptive'][0]['median_pseudo_ree_percent'], 45)
        self.assertEqual(primary['trial_count']['unit_weighted_descriptive'][0]['median_pseudo_ree_percent'], 100)
        self.assertEqual(other['trial_count']['unit_weighted_descriptive'][0]['median_pseudo_ree_percent'], 0)
        # 100-trial responses must use their own values, not the author's copied 40-trial log column.
        self.assertEqual(primary['trial_count']['records'][0]['errors'][-2]['pseudo_ree_percent'], 40)
        self.assertAlmostEqual(primary['trial_count']['records'][0]['errors'][-2]['log10_pseudo_ree_percent'], math.log10(40))
        self.assertEqual(len(primary['trial_count']['retention_by_mouse']), 26)
        self.assertEqual(len(primary['trial_count']['retention_by_area']), 8)
        self.assertFalse(report['scientifically_qualified'])

    def test_panel_masks_keep_partial_r2_and_reject_all_level_tau_gaps(self):
        rows = self.estimates['rows']
        saved = [dict(rows[i]) for i in (0, 1, 10, 19)]
        try:
            rows[0]['r_squared'] = -0.5
            rows[1].update(r_squared=None, failure_reason='undefined diagnostic R2')
            rows[10].update(tau_bins=None, failure_reason='trial fit failed')
            rows[19].update(tau_bins=None, failure_reason='duration fit failed')
            report = e.sensitivity_report(self.cohort, self.estimates)
            p = report['reference_policy_reports']['method_specific_full']['panels']
            self.assertEqual(p['duration_minutes']['complete_case_units'], 5774)
            self.assertEqual(p['trial_count']['complete_case_units'], 5774)
            self.assertEqual(p['duration_minutes']['records'][0]['status'], 'complete_case')
            self.assertEqual(len(p['duration_minutes']['records'][0]['negative_r2']), 1)
            self.assertEqual(len(p['duration_minutes']['records'][0]['missing_r2']), 1)
            self.assertEqual(p['duration_minutes']['records'][1]['status'], 'missing_tau')
            self.assertEqual(p['trial_count']['records'][0]['status'], 'missing_tau')
            self.assertEqual(len(report['original_population_fit_support']['failed_coordinates']), 3)
            q = report['reference_policy_reports']['all_full_isttc']['panels']
            for axis in p:
                self.assertEqual([r['unit_id'] for r in p[axis]['records'] if r['status'] != 'missing_tau'],
                                 [r['unit_id'] for r in q[axis]['records'] if r['status'] != 'missing_tau'])
        finally:
            for i, row in zip((0, 1, 10, 19), saved):
                rows[i] = row

    def test_nonpositive_reference_keeps_denominator_and_withholds_summaries(self):
        row = self.estimates['rows'][8]  # u0 ACF30
        saved = dict(row)
        try:
            row['tau_bins'] = 0
            report = e.sensitivity_report(self.cohort, self.estimates)
            p = report['reference_policy_reports']['method_specific_full']['panels']['duration_minutes']
            self.assertEqual(p['complete_case_units'], 5775)
            summary = p['unit_weighted_descriptive'][0]
            self.assertEqual(summary['defined_count'], 5774)
            self.assertFalse(summary['support_complete'])
            self.assertIsNone(summary['median_pseudo_ree_percent'])
            self.assertTrue(all(value is None for value in summary['within_percent'].values()))
            other = report['reference_policy_reports']['all_full_isttc']['panels']['duration_minutes']
            self.assertEqual(other['complete_case_units'], 5775)
            self.assertTrue(other['unit_weighted_descriptive'][0]['support_complete'])
        finally:
            row.clear(); row.update(saved)

    def test_missing_reference_keeps_policy_masks_identical(self):
        row = self.estimates['rows'][8]
        saved = dict(row)
        try:
            row.update(tau_bins=None, failure_reason='reference fit missing')
            report = e.sensitivity_report(self.cohort, self.estimates)
            for result in report['reference_policy_reports'].values():
                for panel in result['panels'].values():
                    self.assertEqual(panel['complete_case_units'], 5774)
                    self.assertEqual(panel['records'][0]['status'], 'missing_tau')
        finally:
            row.clear(); row.update(saved)

    def test_complete_population_and_coordinate_admission(self):
        with self.assertRaises(ValueError):
            e.sensitivity_report({**self.cohort, 'units': self.cohort['units'][:-1]}, self.estimates)
        with self.assertRaises(ValueError):
            e.estimate_rows({**self.estimates, 'rows': self.estimates['rows'][:-1]}, self.cohort['units'])
        replaced = self.estimates['rows'][-1]
        try:
            self.estimates['rows'][-1] = self.estimates['rows'][0]
            with self.assertRaises(ValueError):
                e.estimate_rows(self.estimates, self.cohort['units'])
        finally:
            self.estimates['rows'][-1] = replaced

    def test_figure7c_projection_preserves_exact_reference_and_trial_coordinates(self):
        selected = e.figure7c_estimates(self.cohort, self.estimates)
        self.assertEqual(len(selected['rows']), 23100)
        self.assertEqual([r['method'] for r in selected['rows'][:4]], list(e.METHODS))
        self.assertEqual([r['tau_bins'] for r in selected['rows'][:4]], [10, 20, 20, 40])
        self.assertEqual(selected['rows'][-1]['unit_id'], 'u5774')
        with self.assertRaises(ValueError):
            e.figure7c_estimates(self.cohort, {**self.estimates, 'rows': self.estimates['rows'][:-1]})

    def test_finite_relative_error_and_median_extremes(self):
        self.assertEqual(e._error(-1e308, 1e308), 200)
        self.assertEqual(e._median([1e308, 1e308]), 1e308)
        smallest = float.fromhex('0x0.0000000000001p-1022')
        self.assertEqual(e._median([smallest, 2 * smallest]), 2 * smallest)
        self.assertEqual(e._error(smallest, 2 * smallest), 50)
        self.assertIsNone(e._error(1e308, smallest))
        self.assertEqual(e._summary([25, 50, 75, 100], 4)['within_percent'],
                         {'100': 100, '75': 75, '50': 50, '25': 25})

    def test_window_clock_seed_count_order_and_non_nested_draws(self):
        rows = e.window_rows(self.cohort, e.WINDOW_SEED)
        first = next(rows)
        self.assertEqual([w[0] for w in first['conditions'][0]['windows_ticks'][:5]],
                         [39930256, 51255747, 27902207, 6982530, 41183338])
        self.assertEqual([row['trial_count'] for row in first['conditions']], [40, 60, 80, 100])
        self.assertNotEqual(first['conditions'][0]['windows_ticks'], first['conditions'][1]['windows_ticks'][:40])
        for item in first['conditions']:
            self.assertEqual(len(item['windows_ticks']), item['trial_count'])
            for start, end in item['windows_ticks']:
                self.assertEqual(end - start, 30000)
                self.assertTrue(0 <= start < end <= 54000000)
        self.assertEqual(next(rows)['unit_id'], 'u1')

    def test_complete_production_routes_prefixes_trials_and_explicit_failure(self):
        first_window = next(e.window_rows(self.cohort, e.WINDOW_SEED))['conditions'][0]['windows_ticks'][0]
        start, end = first_window
        special = sorted(set([0, start, start + 1, end - 1, end, 1800000 - 1, 1800000,
                              9000000 - 1, 9000000, 18000000 - 1, 18000000,
                              36000000 - 1, 36000000, 54000000 - 1]))
        def recordings():
            for i, unit in enumerate(self.cohort['units']):
                yield {'schema': 'isttc_empirical_spikes_v1', 'unit_id': unit['unit_id'],
                       'fs_hz': 30000, 'signal_ticks': 54000000, 'spike_ticks': special if i == 0 else []}
        class Backend:
            identity = {'kind': 'generated_transfer_control_only'}
            def __init__(self):
                self.calls = 0
                self.first = []
            def fit(self, axis, level, method, spikes, trials):
                if self.calls < 18:
                    self.first.append((axis, level, method, list(spikes), trials))
                self.calls += 1
                return (float('nan'), 0.0, 'invented failure') if self.calls == 1 else (2.0, -0.1, 'generated')
        backend = Backend()
        document, receipt = e.produce(self.cohort, recordings(), e.window_rows(self.cohort, e.WINDOW_SEED), backend)
        self.assertEqual(backend.calls, 103950)
        self.assertEqual(len(document['rows']), 103950)
        self.assertIsNone(document['rows'][0]['tau_bins'])
        self.assertEqual(document['rows'][0]['r_squared'], 0.0)
        self.assertTrue(document['rows'][0]['failure_reason'])
        for axis, level, method, selected, trials in backend.first[:10]:
            self.assertEqual(selected, [v for v in special if v < level * 60 * 30000])
            self.assertIsNone(trials)
        self.assertEqual(backend.first[10][4][0], [0, 1, 29999])
        for a, b in zip(backend.first[10::2], backend.first[11::2]):
            self.assertEqual(a[4], b[4])
            self.assertEqual(len(a[4]), a[1])
        self.assertEqual(receipt['fit_coordinates'], 103950)
        self.assertEqual(len(receipt['window_pins']), 5775)
        self.assertFalse(receipt['scientifically_qualified'])

    def test_backend_protocol_mismatch_aborts_without_failure_row(self):
        c = self.cohort
        recording = {'schema': 'isttc_empirical_spikes_v1', 'unit_id': 'u0',
                     'fs_hz': 30000, 'signal_ticks': 54000000, 'spike_ticks': []}
        class Backend:
            identity = {'kind': 'generated_control'}
            def fit(self, *args):
                raise e.producer().BackendProtocolError('invented interface mismatch')
        with self.assertRaises(e.producer().BackendProtocolError):
            e.produce(c, [recording], e.window_rows(c, e.WINDOW_SEED), Backend())

    def test_author_adapter_passes_paper_parameters_for_each_duration(self):
        calls = []
        def bin_signal(*args, **kwargs):
            calls.append(('bin', args, kwargs)); return ['invented_bins']
        def acf(*args, **kwargs):
            calls.append(('acf', args, kwargs)); return [1] * 21
        def sttc(*args, **kwargs):
            calls.append(('sttc', args, kwargs)); return [1] * 21
        exponential = object()
        def fit(*args, **kwargs):
            calls.append(('fit', args, kwargs)); return [0, 0, 3, 0, 0.25, 0, 'control']
        backend = object.__new__(e.AuthorSensitivityBackend)
        backend.original = types.SimpleNamespace(
            spikes=types.SimpleNamespace(bin_spike_train_fixed_len=bin_signal), acf=acf,
            np=types.SimpleNamespace(asarray=lambda value: value),
            curves=types.SimpleNamespace(acf_sttc=sttc),
            fitter=types.SimpleNamespace(fit_single_exp=fit, func_single_exp=exponential),
            fit=lambda method, spikes, trials: (method, len(trials), 'delegated'))
        for duration in (1, 5, 10, 20, 30):
            calls.clear()
            self.assertEqual(backend.fit('duration_minutes', duration, 'acf_full', [0, 30000], None), (3, 0.25, 'control'))
            self.assertEqual(calls[0][1], ([0, 30000], 50, 30000, duration * 60 * 30000))
            self.assertEqual(calls[1][2], {'nlags': 20})
            self.assertEqual(calls[2][2], {'start_idx_': 1, 'exp_fun_': exponential})
            calls.clear()
            backend.fit('duration_minutes', duration, 'isttc_full', [0, 30000], None)
            self.assertEqual(calls[0][1], ([0, 30000], 20))
            self.assertEqual(calls[0][2], {'lag_shift_': 1500, 'sttc_dt_': 750,
                                          'signal_length_': duration * 60 * 30000, 'verbose_': False})
        for count in (40, 60, 80, 100):
            self.assertEqual(backend.fit('trial_count', count, 'pearsonr_trial_avg', [], [[]] * count),
                             ('pearsonr_trial_avg', count, 'delegated'))
        backend.original.curves.acf_sttc = lambda *args, **kwargs: [1] * 20
        with self.assertRaises(e.producer().BackendProtocolError):
            backend.fit('duration_minutes', 1, 'isttc_full', [], None)

    def test_wrong_window_identity_or_seed_refuses_before_backend(self):
        recording = {'schema': 'isttc_empirical_spikes_v1', 'unit_id': 'u0',
                     'fs_hz': 30000, 'signal_ticks': 54000000, 'spike_ticks': []}
        class Never:
            identity = {}
            def fit(self, *args):
                raise AssertionError('backend must not be called')
        row = next(e.window_rows(self.cohort, e.WINDOW_SEED))
        row['conditions'][0]['windows_ticks'][0][0] += 1
        with self.assertRaises(ValueError):
            e.produce(self.cohort, [recording], [row], Never())
        row = next(e.window_rows(self.cohort, e.WINDOW_SEED + 1))
        with self.assertRaises(ValueError):
            e.produce(self.cohort, [recording], [row], Never())

    def test_strict_json_rejects_duplicates_and_nonfinite_literals(self):
        for body in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}']:
            with self.assertRaises(ValueError):
                e.strict_json(body)

    def test_cli_rejects_existing_output_and_invalid_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / 'cohort.json'
            source.write_text(json.dumps(self.cohort))
            output = home / 'output'
            output.mkdir()
            command = [sys.executable, '-I', '-S', '-B', str(HERE / 'endpoints.py'), 'windows',
                       '--cohort', str(source), '--output-directory', str(output)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(list(output.iterdir()), [])
            output.rmdir()
            run = subprocess.run(command + ['--seed', '1'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
