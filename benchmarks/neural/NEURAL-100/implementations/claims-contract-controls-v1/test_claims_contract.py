"""Maintained scientific-claim controls; generated structure, no neural arrays.

Exercise the actual pinned NEURAL-100 claim derivation and comparison against
complete 47-recording/41-mouse/eight-condition invented result dictionaries.
No onset estimator or bootstrap draw is run; these are contract counterexamples,
not synthetic neural measurements, execution admission or scientific evidence.
"""
import argparse
import copy
import hashlib
import importlib.abc
import math
from pathlib import Path
import socket
import subprocess
import sys
import types
import unittest
from unittest.mock import patch


SOURCE_ROOT = Path(__file__).resolve().parents[1] / 'investigation/investigation/package'
SOURCE_PINS = {
    'claims.py': (25881, 'd2c69e8e40b32b3809fef4f2faf213a92d325038086f753cc6b0f39ee6701424'),
    'upstream/report_contract.py': (3849, '23da789f65d2b7b590db6172bbc69db8a305984ea7a25cd60efb868849b87084'),
    'upstream/artifact_io.py': (2010, 'adf200892c5b850721d2ac479d506f7287bc325974c9d1ffcae8cedae4b6b817'),
}
CONDITIONS = (
    'primary', 'threshold_2_5', 'threshold_3_5', 'bins_2ms',
    'boundary_erosion_one_depth', 'baseline_pseudo_onset',
    'development_snr_bin_contact_matched', 'first_spike_median_descriptive',
)
FORBIDDEN = {'numpy', 'scipy', 'h5py', 'pandas', 'torch', 'jax', 'sklearn'}


class NoNumericalImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in FORBIDDEN:
            raise AssertionError('No numerical import in structural controls')


def prohibited(*args, **kwargs):
    raise AssertionError('No network, subprocess or native computation')


def load_sources():
    bodies = {}
    for name, (extent, digest) in SOURCE_PINS.items():
        path = SOURCE_ROOT / name
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
            raise AssertionError('Ordinary pinned source required')
        if path.stat().st_size != extent:
            raise AssertionError('Source extent changed; review required')
        body = path.read_bytes()
        if len(body) != extent or hashlib.sha256(body).hexdigest() != digest:
            raise AssertionError('Source identity changed; review required')
        bodies[name] = body

    def module(name, relative):
        value = types.ModuleType(name)
        value.__file__ = str(SOURCE_ROOT / relative)
        exec(compile(bodies[relative], value.__file__, 'exec'), value.__dict__)
        return value

    io = module('artifact_io', 'upstream/artifact_io.py')
    with patch.dict(sys.modules, {'artifact_io': io}):
        report = module('n100_contract_for_controls', 'upstream/report_contract.py')
    return module('n100_claims_for_controls', 'claims.py'), report


def fixture(deltas=None, absent_area_draws=0, missing_first_spike=False):
    """Invent all identities and result values, preserving full public geometry.

    A1 has 33 mice and 39 recordings (m00..m05 have two recordings each).
    A2 has eight different mice and eight recordings. Default L6-L4 is +2ms.
    This deliberately includes repeats so replacing mice by recordings fails.
    The formal bootstrap hash is invented: no actual draw identity is asserted.
    """
    deltas = {} if deltas is None else deltas
    roster, records = [], []
    for index in range(47):
        mouse = index if index < 33 else index - 33 if index < 39 else index - 6
        row = {'recording_id': f'invented-r{index:02d}',
               'participant_id': f'invented-m{mouse:02d}',
               'area': 'A1' if index < 39 else 'A2'}
        roster.append(row)
        conditions = {}
        for condition in CONDITIONS:
            delta = deltas.get((condition, index), 2.0)
            layers = {
                'L4': {'status': 'defined', 'latency_ms': 10.0},
                'L6': {'status': 'undefined' if delta is None else 'defined',
                       'latency_ms': None if delta is None else 10.0 + delta},
            }
            if condition == 'first_spike_median_descriptive':
                for layer, value in layers.items():
                    if missing_first_spike and index == 0 and layer == 'L6':
                        continue
                    spiking = 3 if value['status'] == 'defined' else 0
                    value.update(test_trials=5, spiking_trials=spiking, no_spike_trials=5-spiking)
            conditions[condition] = {'status': 'undefined' if delta is None else 'defined',
                'layers': layers, 'delta_l6_minus_l4_ms': delta}
        records.append({**row, 'conditions': conditions})

    areas = {}
    for condition in CONDITIONS:
        areas[condition] = {}
        for area in ('A1', 'A2'):
            selected = [r for r in records if r['area'] == area]
            participant_effects = []
            for mouse in sorted({r['participant_id'] for r in selected}):
                values = [r['conditions'][condition]['delta_l6_minus_l4_ms']
                          for r in selected if r['participant_id'] == mouse]
                missing = values.count(None)
                participant_effects.append({'participant_id': mouse, 'recordings': len(values),
                    'status': 'undefined' if missing else 'defined',
                    'delta_l6_minus_l4_ms': None if missing else sum(values) / len(values),
                    'undefined_recordings': missing})
            observed = [r['delta_l6_minus_l4_ms'] for r in participant_effects
                        if r['status'] == 'defined']
            complete = len(observed) == len(participant_effects)
            mean = math.fsum(observed) / len(observed) if observed else None
            no_area = absent_area_draws if area == 'A2' else 0
            undefined_selected = 0 if complete else 1000 - no_area
            defined = 1000 - no_area - undefined_selected
            ci = [mean, mean] if complete and defined == 1000 else None
            areas[condition][area] = {
                'participant_effects': participant_effects,
                'recorded_participants': len(participant_effects), 'recordings': len(selected),
                'defined_participants': len(observed),
                'undefined_participants': len(participant_effects) - len(observed),
                'full_area_mean_ms': mean if complete else None,
                'full_area_status': 'defined' if complete else 'undefined_incomplete_participant_effects',
                'observed_only_mean_ms': mean, 'observed_only_is_full_cohort': complete,
                'bootstrap': {
                    'draws': 1000, 'defined_draws': defined,
                    'undefined_draws': 1000-defined, 'no_area_participant_draws': no_area,
                    'undefined_participant_selected_draws': undefined_selected,
                    'redrawn_or_conditioned_on_defined_draws': False,
                    'percentile_95_interval_ms': ci,
                    'interval_status': 'defined' if ci is not None else
                                       'withheld_no_complete_unconditional_interval',
                },
            }
    full = {'policy': 'neural100_released_panel_draft_v1', 'recordings': 47, 'participants': 41,
        'source_area_recording_counts': {'A1': 39, 'A2': 8},
        'exact_paper_reproduction': False, 'timing_alignment_established_by_core': False,
        'paper_area_counts_used_to_select_or_relabel': False,
        'anatomical_shift_reconstruction': False, 'causal_pathway_claim': False,
        'scientific_success_threshold': None,
        'boundary_control': 'one_depth_exclusion_without_relabeling',
        'bootstrap_schedule': {'generator': 'PCG64', 'seed': 100043, 'draws': 1000,
            'draw_size': 41, 'participant_order': sorted({r['participant_id'] for r in roster}),
            'shared_across_areas_and_conditions': True, 'multiplicity_sha256': '0' * 64},
        'per_recording': records, 'conditions': areas}
    return full, roster


class ScientificClaimContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if FORBIDDEN.intersection(sys.modules):
            raise AssertionError('Use fresh standard-library interpreter')
        finder = NoNumericalImports()
        sys.meta_path.insert(0, finder)
        cls.addClassCleanup(sys.meta_path.remove, finder)
        for target, name in ((socket, 'socket'), (socket, 'create_connection'), (subprocess, 'Popen')):
            guard = patch.object(target, name, prohibited)
            guard.start()
            cls.addClassCleanup(guard.stop)
        cls.claims, cls.report = load_sources()

    def derive(self, full, roster):
        return self.claims.derive(full, self.report.project(full), roster)

    def test_complete_panel_and_all_eight_conditions(self):
        full, roster = fixture()
        expected = self.derive(full, roster)
        self.assertEqual(len(expected['recordings']), 47)
        self.assertEqual(set(expected['conditions']), set(CONDITIONS))
        self.assertEqual(expected['conditions']['primary']['areas']['A1']['participant_support'],
                         {'recorded': 33, 'defined': 33, 'undefined': 0})
        result = self.claims.compare(expected, expected)
        self.assertEqual(result['mismatches'], [])
        self.assertIsNone(result['scientific_reasoning_scalar'])
        self.assertFalse(result['scientific_success_or_SOTA_claim'])

    def test_contrast_sign_and_undefined_are_distinct(self):
        full, roster = fixture({('primary', 0): -2.0, ('primary', 1): 0.0,
                                ('primary', 2): 2.0, ('primary', 3): None})
        rows = self.derive(full, roster)['recordings']
        self.assertEqual([r['conditions']['primary']['direction'] for r in rows[:4]],
                         ['L6_earlier', 'equal', 'L6_later', 'undefined'])

    def test_one_undefined_repeat_withholds_full_mouse_and_area(self):
        full, roster = fixture({('primary', 33): None})
        area = self.derive(full, roster)['conditions']['primary']['areas']['A1']
        self.assertEqual(area['participant_support'], {'recorded': 33, 'defined': 32, 'undefined': 1})
        self.assertEqual(area['recording_support'], {'recorded': 39, 'defined': 38, 'undefined': 1})
        self.assertEqual(area['full_cohort_direction'], 'undefined')
        self.assertEqual(area['observed_only_direction'], 'L6_later')
        self.assertEqual(area['observed_only_scope'], 'defined_participants_only')
        self.assertEqual(area['direction_relation_to_primary'], 'unavailable')
        self.assertEqual(area['interval']['position'], 'withheld')

    def test_all_missing_is_not_zero_effect_or_observed_only_cohort(self):
        full, roster = fixture({('primary', i): None for i in range(39)})
        area = self.derive(full, roster)['conditions']['primary']['areas']['A1']
        self.assertEqual(area['observed_only_scope'], 'no_defined_participants')
        self.assertEqual(area['observed_only_direction'], 'undefined')
        self.assertEqual(area['participant_support']['defined'], 0)

    def test_reference_cannot_replace_mouse_mean_by_recording_weighted_mean(self):
        full, roster = fixture({('primary', 0): -4.0})
        self.assertAlmostEqual(full['conditions']['primary']['A1']['full_area_mean_ms'], 63 / 33)
        for field in ('full_area_mean_ms', 'observed_only_mean_ms'):
            full['conditions']['primary']['A1'][field] = 72 / 39
        with self.assertRaisesRegex(self.claims.InvalidReference, 'aggregate/support consistency'):
            self.derive(full, roster)

    def test_reference_cannot_fabricate_defined_repeat_hierarchy(self):
        full, roster = fixture({('primary', 33): None})
        row = full['conditions']['primary']['A1']['participant_effects'][0]
        row.update(status='defined', delta_l6_minus_l4_ms=2.0, undefined_recordings=0)
        with self.assertRaisesRegex(self.claims.InvalidReference, 'repeat/participant hierarchy'):
            self.derive(full, roster)

    def test_projection_must_come_from_same_full_reference(self):
        full, roster = fixture()
        projection = self.report.project(full)
        projection['areas']['primary']['A1']['full_mean_ms'] = -2.0
        with self.assertRaisesRegex(self.claims.InvalidReference, 'unchanged projection'):
            self.claims.derive(full, projection, roster)

    def test_area_count_relabeling_is_not_a_scientific_answer(self):
        full, roster = fixture()
        full['source_area_recording_counts'] = {'A1': 31, 'A2': 16}
        with self.assertRaises(self.claims.InvalidReference):
            self.derive(full, roster)

    def test_condition_dependent_no_area_draws_are_refused(self):
        full, roster = fixture(absent_area_draws=1)
        full['conditions']['threshold_2_5']['A2']['bootstrap']['no_area_participant_draws'] = 0
        with self.assertRaisesRegex(self.claims.InvalidReference, 'Shared participant draws'):
            self.derive(full, roster)

    def test_complete_mean_can_have_withheld_unconditional_interval(self):
        full, roster = fixture(absent_area_draws=1)
        area = self.derive(full, roster)['conditions']['primary']['areas']['A2']
        self.assertEqual(area['full_cohort_direction'], 'L6_later')
        self.assertEqual(area['interval'], {'position': 'withheld', 'defined_draws': 999,
            'undefined_draws': 1, 'complete_unconditional_interval': False})

    def test_zero_touching_intervals_are_not_strict_sign_evidence(self):
        for interval in ([-2.0, 0.0], [0.0, 0.0], [0.0, 3.0]):
            with self.subTest(interval=interval):
                full, roster = fixture()
                full['conditions']['primary']['A1']['bootstrap']['percentile_95_interval_ms'] = interval
                area = self.derive(full, roster)['conditions']['primary']['areas']['A1']
                self.assertEqual(area['interval']['position'], 'contains_zero')

    def test_pointwise_interval_is_not_simultaneous_significance(self):
        full, roster = fixture()
        expected = self.derive(full, roster)
        flag = 'intervals_are_simultaneous_significance_declarations'
        self.assertIs(expected['interpretation'][flag], False)
        candidate = copy.deepcopy(expected)
        candidate['interpretation'][flag] = True
        self.claims.admit(candidate, roster)
        self.assertEqual(self.claims.compare(candidate, expected)['mismatches'],
                         [{'path': '/interpretation/' + flag, 'kind': 'typed_claim_mismatch'}])

    def test_invalid_or_conditioned_intervals_cannot_be_reference_truth(self):
        mutations = (
            ('percentile_95_interval_ms', [3.0, 2.0]),
            ('percentile_95_interval_ms', None),
            ('redrawn_or_conditioned_on_defined_draws', True),
        )
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                full, roster = fixture()
                full['conditions']['primary']['A1']['bootstrap'][key] = value
                with self.assertRaises(self.claims.InvalidReference):
                    self.derive(full, roster)

    def test_missing_first_spike_evidence_is_ungradable_not_inferred(self):
        full, roster = fixture(missing_first_spike=True)
        expected = self.derive(full, roster)
        evidence = expected['recordings'][0]['first_spike_evidence']['L6']
        self.assertEqual([evidence[k] for k in ('test_trials', 'spiking_trials', 'no_spike_trials')],
                         [None, None, None])
        candidate = copy.deepcopy(expected)
        candidate['recordings'][0]['first_spike_evidence']['L6'].update(
            status='retained', test_trials=5, spiking_trials=3, no_spike_trials=2)
        result = self.claims.compare(candidate, expected)
        self.assertEqual(len(result['ungradable_evidence']), 3)
        self.assertEqual(result['mismatches'], [{'path':
            '/recordings/invented-r00/first_spike_evidence/L6/status', 'kind': 'typed_claim_mismatch'}])

    def test_wrong_well_formed_science_is_graded_not_schema_refused(self):
        full, roster = fixture()
        expected = self.derive(full, roster)
        candidate = copy.deepcopy(expected)
        candidate['interpretation']['causal_pathway_established'] = True
        candidate['recordings'][0]['conditions']['primary']['direction'] = 'L6_earlier'
        self.claims.admit(candidate, roster)
        mismatches = self.claims.compare(candidate, expected)['mismatches']
        self.assertEqual({r['path'] for r in mismatches}, {
            '/interpretation/causal_pathway_established',
            '/recordings/invented-r00/conditions/primary/direction'})
        self.assertTrue(all(set(row) == {'path', 'kind'} for row in mismatches))

    def test_missing_duplicate_or_incomplete_condition_is_malformed(self):
        full, roster = fixture()
        expected = self.derive(full, roster)
        for case in ('missing', 'duplicate', 'condition'):
            with self.subTest(case=case):
                candidate = copy.deepcopy(expected)
                if case == 'missing':
                    candidate['recordings'].pop()
                elif case == 'duplicate':
                    candidate['recordings'][-1] = copy.deepcopy(candidate['recordings'][0])
                else:
                    del candidate['conditions']['threshold_3_5']
                with self.assertRaises(self.claims.InvalidClaims):
                    self.claims.admit(candidate, roster)

    def test_boolean_support_and_broken_partitions_are_malformed(self):
        full, roster = fixture()
        expected = self.derive(full, roster)
        for replacement in (True, 0):
            with self.subTest(replacement=replacement):
                candidate = copy.deepcopy(expected)
                candidate['conditions']['primary']['areas']['A1']['participant_support']['defined'] = replacement
                with self.assertRaises(self.claims.InvalidClaims):
                    self.claims.admit(candidate, roster)

    def test_claim_order_does_not_change_recording_join(self):
        full, roster = fixture()
        expected = self.derive(full, roster)
        candidate = copy.deepcopy(expected)
        candidate['recordings'].reverse()
        self.assertEqual(self.claims.compare(candidate, expected)['mismatches'], [])

    def test_nonfinite_reference_and_false_scope_authority_are_refused(self):
        for field in ('nan', 'causal'):
            with self.subTest(field=field):
                full, roster = fixture()
                if field == 'nan':
                    full['per_recording'][0]['conditions']['primary']['layers']['L6']['latency_ms'] = float('nan')
                else:
                    full['causal_pathway_claim'] = True
                with self.assertRaises(self.claims.InvalidReference):
                    self.derive(full, roster)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument('--source-root', type=Path, default=SOURCE_ROOT)
    args, rest = parser.parse_known_args()
    SOURCE_ROOT = args.source_root
    unittest.main(argv=[sys.argv[0], *rest], verbosity=2)
