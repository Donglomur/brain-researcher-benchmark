"""Generated complete-roster controls, never authentic bank scoring."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate as e
from artifact_io import digest


def encode(value):
    return (json.dumps(value, allow_nan=False, sort_keys=True) + '\n').encode()


def pin(path):
    data = path.read_bytes()
    return {'path': path.name, 'bytes': len(data), 'sha256': digest(data)}


def fixture_bank(root):
    """Same132identities/44neurons but tiny generated arrays, distinct manifest."""
    root.mkdir()
    roster = json.loads((HERE / 'CASE_ROSTER.json').read_text())
    inventory = json.loads((HERE.parent / 'source-condition-primitives-v1' / 'NATIVE_INVENTORY.json').read_text())
    metadata = {'producer_sha256': roster['source_producer_sha256'], 'inventory_sha256': e.INVENTORY_SHA256,
                'bank_seed': roster['bank_seed'], 'expected_neurons': roster['expected_neurons'],
                'source_recordings': 132, 'native_samples': roster['native_samples'],
                'historical_paper_comparison_qualified': False,
                'condition': {'name': 'current_source_recipe_single_realization_v1', 'nominal_rate_hz': 30.,
                              'requested_noise_level': 7., 'target_sigma_seconds': .05,
                              'context_window_bins': 64, 'historical_paper_realization': False}, 'recordings': []}
    n = 80
    t = np.arange(n) / 30
    target = ((np.arange(n) % 17) + np.sin(np.arange(n) / 4.)).clip(min=0)
    mask = np.zeros(n, dtype=bool); mask[32:-32] = True
    for index, row in enumerate(roster['records']):
        if row['status'] == 'prepared':
            row['output_samples'] = n; row['scored_bins'] = int(mask.sum())
        item = deepcopy(row)
        item['native_standardized_noise'] = 1. if row['status'] == 'prepared' else 8.
        if row['status'] == 'prepared':
            path = root / f'recording-{index:03d}.npz'
            np.savez(path, fluorescence=np.sin(t), target_hz=target, counts=np.zeros(n, dtype=np.int64),
                     support=mask, bin_centers_seconds=t)
            item['operator_payload'] = pin(path)
        metadata['recordings'].append(item)
    metadata['unavailable_recordings'] = [r['recording_id'] for r in metadata['recordings'] if r['status'] != 'prepared']
    payload = encode(metadata); (root / 'BANK.json').write_bytes(payload)
    roster['bank_manifest_sha256'] = digest(payload)
    return e._open_bank(root, roster, inventory), roster, inventory


def fixture_predictions(root, bank, role):
    root.mkdir()
    methods = ({'oasis':'arbitrary', 'default_cascade':'expected_spikes_per_bin',
                'glutamatergic_cascade':'hz', 'gabaergic_cascade':'hz'} if role == 'operator_reference' else {'candidate':'hz'})
    meta = {'schema': 'spinal_current_prediction_bundle_v1', 'role': role, 'condition_id': e.CONDITION_ID,
            'bank_manifest_sha256': bank.manifest_sha256, 'methods': methods, 'recordings': [],
            'provenance_note': 'Generated control vectors only, not scientific model predictions'}
    for index, row in enumerate(bank.eligible):
        n = row['output_samples']
        target = ((np.arange(n) % 17) + np.sin(np.arange(n) / 4.)).clip(min=0)
        arr = {}
        for method, unit in methods.items():
            values = target if method == 'candidate' else np.roll(target, 1)
            arr[method] = (values / 30 if unit == 'expected_spikes_per_bin' else values).astype(np.float32)
        path = root / f'prediction-{index:03d}.npz'; np.savez(path, **arr)
        meta['recordings'].append({'recording_id':row['recording_id'], 'payload':pin(path)})
    payload = encode(meta); (root / 'PREDICTIONS.json').write_bytes(payload)
    return e.load_predictions(root, bank, role=role, manifest_sha256=digest(payload))


def reload_prediction_manifest(bundle, bank, mutate):
    metadata = deepcopy(bundle.metadata); mutate(metadata)
    path = bundle.root / 'PREDICTIONS.json'
    original = path.read_bytes()
    try:
        payload = encode(metadata); path.write_bytes(payload)
        return e.load_predictions(bundle.root, bank, role=bundle.role, manifest_sha256=digest(payload))
    finally:
        path.write_bytes(original)


class EligibleConditionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.bank, cls.roster, cls.inventory = fixture_bank(cls.root / 'bank')
        cls.references = fixture_predictions(cls.root / 'references', cls.bank, 'operator_reference')
        cls.candidate = fixture_predictions(cls.root / 'candidate', cls.bank, 'candidate')

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_generated_fixture_rejected_by_public_frozen_bank_loader(self):
        with self.assertRaisesRegex(ValueError, 'identity'):
            e.load_bank(self.bank.root)

    def test_complete_current_scope_and_explicit_denominators(self):
        result = e.evaluate(self.bank, self.references, self.candidate)
        self.assertEqual(len(result['metrics']['per_neuron']), 44)
        self.assertEqual(result['coverage']['source_recording_rows'], 132)
        self.assertEqual(len(result['coverage']['eligible_recording_ids']), 116)
        self.assertEqual(len(result['coverage']['source_exclusions']), 16)
        self.assertEqual(result['coverage']['scored_bins'], 116 * 16)
        self.assertEqual(result['metrics']['cohorts']['glutamatergic']['methods']['candidate']['correlation']['expected_neurons'], 21)
        self.assertEqual(result['metrics']['cohorts']['gabaergic']['methods']['candidate']['correlation']['expected_neurons'], 23)
        for group in ('glutamatergic', 'gabaergic'):
            self.assertGreater(result['metrics']['cohorts'][group]['paired_candidate_minus_reference']['correlation_delta']['mean'], 0)
        self.assertFalse(result['reference_qualification_established_by_this_evaluator'])
        self.assertFalse(result['paper_improvement_or_SOTA_established'])

    def test_reference_only_path_does_not_invent_candidate(self):
        result = e.evaluate(self.bank, self.references)
        self.assertIsNone(result['candidate_manifest_sha256'])
        self.assertNotIn('paired_candidate_minus_reference', result['metrics']['cohorts']['glutamatergic'])

    def test_existing_metric_kernel_parity_and_same_support(self):
        metrics = e.load_metrics()
        observations = list(e._observations(self.bank, self.references, self.candidate, metrics))
        direct = metrics.score_condition(expected_neurons=self.bank.metadata['expected_neurons'], observations=observations, sampling_rate_hz=30.)
        self.assertEqual(e.evaluate(self.bank, self.references, self.candidate)['metrics'], direct)
        row = next(r for r in observations if r['neuron_id'] == 'ds40_08')
        self.assertEqual(len(row['target_hz']), 2 * 80)
        self.assertEqual(sum(row['support']), 2 * 16)
        self.assertEqual(set(row['controls']), set(e.ALL_METHODS))

    def test_unknown_failure_cannot_be_reclassified_as_noise_exclusion(self):
        self.assert_bank_change_refused(lambda m: m['recordings'][next(i for i,r in enumerate(m['recordings']) if r['status']=='unavailable')].update(reason='model_failed'))

    def test_missing_original_source_row_refused(self):
        self.assert_bank_change_refused(lambda m: m['recordings'].pop())

    def test_reordered_original_records_refused(self):
        self.assert_bank_change_refused(lambda m: m['recordings'].reverse())

    def test_source_noise_eligibility_cannot_be_changed(self):
        self.assert_bank_change_refused(lambda m: m['recordings'][0].update(native_standardized_noise=8.))

    def test_source_neuron_cohort_cannot_be_changed(self):
        self.assert_bank_change_refused(lambda m: m['expected_neurons'].update(ds40_01='gabaergic'))

    def test_source_alignment_and_sigma_condition_bound(self):
        self.assert_bank_change_refused(lambda m: m['condition'].update(target_sigma_seconds=.4))

    def assert_bank_change_refused(self, mutate):
        metadata = deepcopy(self.bank.metadata); mutate(metadata)
        path = self.bank.root / 'BANK.json'; original = path.read_bytes()
        try:
            payload = encode(metadata); path.write_bytes(payload)
            roster = deepcopy(self.roster); roster['bank_manifest_sha256'] = digest(payload)
            with self.assertRaises((ValueError, KeyError)):
                e._open_bank(self.bank.root, roster, self.inventory)
        finally:
            path.write_bytes(original)

    def test_reference_manifest_must_be_frozen_by_operator(self):
        with self.assertRaisesRegex(ValueError, 'identity'):
            e.load_predictions(self.references.root, self.bank, role='operator_reference', manifest_sha256='0' * 64)

    def test_optional_or_malformed_prediction_manifest_pins_refused(self):
        for identity in (None, '', 'x' * 64, 'A' * 64):
            for role in ('operator_reference', 'candidate'):
                with self.subTest(identity=identity, role=role), self.assertRaisesRegex(ValueError, 'SHA256'):
                    e.load_predictions(self.references.root, self.bank, role=role, manifest_sha256=identity)

    def test_candidate_cannot_replace_raw_or_model_controls(self):
        with self.assertRaisesRegex(ValueError, 'candidate'):
            reload_prediction_manifest(self.candidate, self.bank, lambda m: m['methods'].update(raw_fluorescence='arbitrary'))
        with self.assertRaisesRegex(ValueError, 'roles'):
            e.evaluate(self.bank, self.candidate, self.references)

    def test_candidate_cannot_supply_target_mask_or_alignment(self):
        for key in ('targets', 'support', 'alignment', 'reference_manifest_sha256'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'forbidden'):
                reload_prediction_manifest(self.candidate, self.bank, lambda m: m.update({key:'override'}))

    def test_missing_eligible_or_extra_excluded_prediction_refused(self):
        with self.assertRaisesRegex(ValueError, 'every116'):
            reload_prediction_manifest(self.candidate, self.bank, lambda m: m['recordings'].pop())
        with self.assertRaisesRegex(ValueError, 'coverage'):
            reload_prediction_manifest(self.candidate, self.bank, lambda m: m['recordings'][0].update(recording_id=self.bank.excluded[0]['recording_id']))

    def test_prediction_bank_or_unit_mismatch_refused(self):
        with self.assertRaisesRegex(ValueError, 'binding'):
            reload_prediction_manifest(self.candidate, self.bank, lambda m: m.update(bank_manifest_sha256='0'*64))
        with self.assertRaisesRegex(ValueError, 'unit'):
            reload_prediction_manifest(self.references, self.bank, lambda m: m['methods'].update(oasis='hz'))

    def test_nonfinite_scored_prediction_refused_without_remasking(self):
        self.mutate_candidate(np.nan, 40, must_fail=True)

    def test_nonfinite_outside_fixed_support_does_not_expand_or_shrink_mask(self):
        result = self.mutate_candidate(np.nan, 0, must_fail=False)
        self.assertEqual(result['coverage']['scored_bins'], 116 * 16)

    def test_constant_prediction_retains_undefined_neuron_denominator(self):
        path = self.candidate.root / self.candidate.metadata['recordings'][0]['payload']['path']
        original = path.read_bytes()
        try:
            np.savez(path, candidate=np.zeros(80))
            candidate = self.candidate_with_new_first_pin(path)
            result = e.evaluate(self.bank, self.references, candidate)
            self.assertEqual(result['metrics']['per_neuron']['ds40_01']['methods']['candidate']['correlation']['status'], 'constant_prediction')
            summary = result['metrics']['cohorts']['glutamatergic']['methods']['candidate']['correlation']
            self.assertEqual((summary['expected_neurons'], summary['defined_neurons'], summary['undefined_neurons']), (21, 20, 1))
        finally:
            path.write_bytes(original)

    def candidate_with_new_first_pin(self, path):
        return reload_prediction_manifest(self.candidate, self.bank, lambda m: m['recordings'][0].update(payload=pin(path)))

    def mutate_candidate(self, value, index, must_fail):
        path = self.candidate.root / self.candidate.metadata['recordings'][0]['payload']['path']
        original = path.read_bytes()
        try:
            with np.load(path, allow_pickle=False) as npz:
                vector = npz['candidate'].copy()
            vector[index] = value; np.savez(path, candidate=vector)
            candidate = self.candidate_with_new_first_pin(path)
            if must_fail:
                with self.assertRaisesRegex(ValueError, 'finite'):
                    e.evaluate(self.bank, self.references, candidate)
            else:
                return e.evaluate(self.bank, self.references, candidate)
        finally:
            path.write_bytes(original)

    def test_prediction_vector_full_original_length_required(self):
        path = self.candidate.root / self.candidate.metadata['recordings'][0]['payload']['path']
        original = path.read_bytes()
        try:
            np.savez(path, candidate=np.zeros(79))
            with self.assertRaisesRegex(ValueError, 'dimensional'):
                e.evaluate(self.bank, self.references, self.candidate_with_new_first_pin(path))
        finally:
            path.write_bytes(original)

    def test_payload_changed_after_manifest_is_not_scored(self):
        path = self.candidate.root / self.candidate.metadata['recordings'][0]['payload']['path']
        original = path.read_bytes()
        try:
            content = bytearray(original); content[-1] ^= 1; path.write_bytes(content)
            with self.assertRaisesRegex(ValueError, 'identity'):
                e.evaluate(self.bank, self.references, self.candidate)
        finally:
            path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
