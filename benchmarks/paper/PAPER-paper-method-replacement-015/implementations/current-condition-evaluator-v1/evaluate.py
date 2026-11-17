"""Operator evaluator for the adopted spinal current-source eligible condition.

Preserves the original producer/adapter. No model execution, adaptive alignment,
reference qualification, historical-paper comparison, or binary success rule.
"""
from dataclasses import dataclass
import argparse
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from artifact_io import SHA, digest, read_json, read_pinned, read_npz_bytes

ROSTER_SHA256 = 'bdc17caa464bce45efec0446da0e4c3bbe5ebdddf98a197a01d329ed109739cf'
METRICS_SHA256 = '7249e2d1d6ead3172fc9dc0f7910f36d2763806c6a308be064f8483095b94ed3'
INVENTORY_SHA256 = '718fd791559ebf03d68ac14c030a5b06ad9c2213b917cb52bc1b1fc55242779c'
CONDITION_ID = 'current_source_noise7_eligible_v1'
REFERENCE_METHODS = ('oasis', 'default_cascade', 'glutamatergic_cascade', 'gabaergic_cascade')
ALL_METHODS = ('raw_fluorescence',) + REFERENCE_METHODS
SOURCE_ARRAYS = {'fluorescence': 'float64', 'target_hz': 'float64', 'counts': 'int64',
                 'support': 'bool', 'bin_centers_seconds': 'float64'}
MAX_BUNDLE_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True)
class Bank:
    root: Path
    manifest_sha256: str
    metadata: dict
    roster: dict

    @property
    def eligible(self):
        return [row for row in self.metadata['recordings'] if row['status'] == 'prepared']

    @property
    def excluded(self):
        return [row for row in self.metadata['recordings'] if row['status'] != 'prepared']


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('finite real metadata number required')
    return value


def _open_bank(root, roster, inventory):
    """Internal reader permits generated fixture contracts; CLI uses frozen files."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('real operator bank directory required')
    metadata, sha = read_json(root / 'BANK.json', expected_sha=roster['bank_manifest_sha256'])
    if metadata['producer_sha256'] != roster['source_producer_sha256'] or metadata['inventory_sha256'] != INVENTORY_SHA256:
        raise ValueError('bank producer/inventory binding mismatch')
    condition = metadata['condition']
    if (condition['name'] != 'current_source_recipe_single_realization_v1'
            or _number(condition['nominal_rate_hz']) != 30
            or _number(condition['requested_noise_level']) != 7
            or _number(condition['target_sigma_seconds']) != .05
            or condition['context_window_bins'] != 64
            or condition['historical_paper_realization'] is not False
            or metadata['historical_paper_comparison_qualified'] is not False
            or metadata['bank_seed'] != roster['bank_seed']):
        raise ValueError('frozen current-source condition mismatch')
    expected = {row['neuron_id']: row['cohort'] for row in inventory['files']}
    if (len(expected) != 44 or list(expected.values()).count('glutamatergic') != 21
            or list(expected.values()).count('gabaergic') != 23
            or metadata['expected_neurons'] != expected or roster['expected_neurons'] != expected):
        raise ValueError('all44 original neurons and21/23 cohorts required')
    rows = metadata['recordings']
    if len(rows) != 132 or len(roster['records']) != 132 or metadata['source_recordings'] != 132:
        raise ValueError('all132 source census rows required')
    if metadata['native_samples'] != roster['native_samples'] or sum(r['native_samples'] for r in rows) != roster['native_samples']:
        raise ValueError('complete native sample census required')
    files = {r['path']: r for r in inventory['files']}
    seen = set()
    excluded = []
    ordinals = {k: [] for k in expected}
    payload_paths = set()
    payload_bytes = 0
    for row, frozen in zip(rows, roster['records']):
        # Exact frozen order includes every original recording, including excluded.
        if any(row.get(key, 0 if key in ('output_samples', 'scored_bins') else None) != value
               for key, value in frozen.items()):
            raise ValueError('source row, order or eligibility changed')
        identity = row['recording_id']
        if identity in seen:
            raise ValueError('repeated original recording')
        seen.add(identity)
        source = files.get(row['source_path'])
        if source is None or (row['source_sha256'], row['neuron_id'], row['cohort']) != (source['sha256'], source['neuron_id'], source['cohort']):
            raise ValueError('source inventory binding mismatch')
        ordinal = row['source_recording_index_zero_based']
        if type(ordinal) is not int or identity != f'{row["neuron_id"]}/recording-{ordinal:03d}':
            raise ValueError('canonical recording identity required')
        ordinals[row['neuron_id']].append(ordinal)
        noise = _number(row['native_standardized_noise'])
        if row['status'] == 'prepared':
            if noise > 7 or noise < 0 or row.get('reason') is not None:
                raise ValueError('prepared row violates frozen input-noise rule')
            n = row['output_samples']
            if type(n) is not int or not 64 < n <= 1_000_000 or row['scored_bins'] != n - 64:
                raise ValueError('fixed source context count mismatch')
            pin = row['operator_payload']
            if set(pin) != {'path', 'bytes', 'sha256'} or pin['path'] in payload_paths:
                raise ValueError('distinct exact operator payload pin required')
            payload_paths.add(pin['path'])
            if type(pin['bytes']) is not int or pin['bytes'] <= 0:
                raise ValueError('operator payload byte count required')
            payload_bytes += pin['bytes']
        else:
            if (row['status'] != 'unavailable' or row.get('reason') != 'native_noise_exceeds_requested_noise'
                    or noise <= 7 or 'operator_payload' in row):
                raise ValueError('unknown failure cannot become a source exclusion')
            excluded.append(identity)
    if len(excluded) != 16 or metadata['unavailable_recordings'] != excluded or len(payload_paths) != 116:
        raise ValueError('exact116eligible/16source-excluded roster required')
    if payload_bytes > MAX_BUNDLE_BYTES:
        raise ValueError('operator payload budget exceeded')
    if any(values != list(range(len(values))) for values in ordinals.values()):
        raise ValueError('all original neuron recording ordinals required')
    if {r['neuron_id'] for r in rows if r['status'] == 'prepared'} != set(expected):
        raise ValueError('every original neuron must retain eligible support')
    return Bank(root, sha, metadata, roster)


def load_bank(root):
    roster, _ = read_json(HERE / 'CASE_ROSTER.json', expected_sha=ROSTER_SHA256)
    inventory, _ = read_json(HERE.parent / 'source-condition-primitives-v1' / 'NATIVE_INVENTORY.json', expected_sha=INVENTORY_SHA256)
    return _open_bank(root, roster, inventory)


def _source_arrays(bank, row):
    payload = read_pinned(bank.root, row['operator_payload'])
    n = row['output_samples']
    arrays = read_npz_bytes(payload, {k: (policy, n) for k, policy in SOURCE_ARRAYS.items()})
    expected = np.zeros(n, dtype=bool); expected[32:-32] = True
    if not np.array_equal(arrays['support'], expected):
        raise ValueError('operator fixed support changed')
    for name in ('fluorescence', 'target_hz', 'bin_centers_seconds'):
        if not np.isfinite(arrays[name]).all():
            raise ValueError('source array is nonfinite')
    if (np.any(arrays['target_hz'] < 0) or np.any(arrays['counts'] < 0)
            or not np.all(np.diff(arrays['bin_centers_seconds']) > 0)):
        raise ValueError('invalid source rate/count/clock')
    return arrays


@dataclass(frozen=True)
class Predictions:
    root: Path
    manifest_sha256: str
    role: str
    metadata: dict
    by_id: dict


def load_predictions(root, bank, *, role, manifest_sha256):
    if not isinstance(manifest_sha256, str) or not SHA.fullmatch(manifest_sha256):
        raise ValueError('frozen lowercase SHA256 manifest binding required')
    if role not in ('operator_reference', 'candidate'):
        raise ValueError('fixed reference/candidate role required')
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('real prediction directory required')
    metadata, sha = read_json(root / 'PREDICTIONS.json', expected_sha=manifest_sha256)
    if set(metadata) != {'schema', 'role', 'condition_id', 'bank_manifest_sha256', 'methods', 'recordings', 'provenance_note'}:
        raise ValueError('exact prediction manifest fields required; targets/masks/alignment are forbidden')
    if (metadata['schema'] != 'spinal_current_prediction_bundle_v1' or metadata['role'] != role
            or metadata['condition_id'] != CONDITION_ID or metadata['bank_manifest_sha256'] != bank.manifest_sha256):
        raise ValueError('prediction role/bank/condition binding mismatch')
    methods = set(REFERENCE_METHODS) if role == 'operator_reference' else {'candidate'}
    if not isinstance(metadata['methods'], dict) or set(metadata['methods']) != methods:
        raise ValueError('references require exactlyfourcontrols; candidate cannot replace controls')
    for name, unit in metadata['methods'].items():
        if unit not in ({'arbitrary'} if name == 'oasis' else {'hz', 'expected_spikes_per_bin'}):
            raise ValueError('method unit mismatch')
    if not isinstance(metadata['provenance_note'], str) or len(metadata['provenance_note']) > 4000:
        raise ValueError('bounded unverified provenance note required')
    records = metadata['recordings']
    if not isinstance(records, list) or len(records) != 116:
        raise ValueError('every116 eligible recording required')
    rows, paths, total = {}, set(), 0
    for record in records:
        if not isinstance(record, dict) or set(record) != {'recording_id', 'payload'}:
            raise ValueError('exact recording/payload prediction row required')
        identity = record['recording_id']; pin = record['payload']
        if (not isinstance(identity, str) or identity in rows or not isinstance(pin, dict)
                or set(pin) != {'path', 'bytes', 'sha256'} or not isinstance(pin['path'], str)
                or pin['path'] in paths or type(pin['bytes']) is not int or pin['bytes'] <= 0):
            raise ValueError('distinct bounded prediction identities/payloads required')
        rows[identity] = pin; paths.add(pin['path']); total += pin['bytes']
    if set(rows) != {row['recording_id'] for row in bank.eligible}:
        raise ValueError('eligible prediction coverage mismatch; no added or omitted source rows')
    if total > MAX_BUNDLE_BYTES:
        raise ValueError('prediction bundle byte budget exceeded')
    return Predictions(root, sha, role, metadata, rows)


def _prediction_arrays(bundle, row):
    payload = read_pinned(bundle.root, bundle.by_id[row['recording_id']])
    return read_npz_bytes(payload, {method: ('numeric', row['output_samples']) for method in bundle.metadata['methods']})


def load_metrics():
    path = HERE.parent / 'original-endpoint-metrics-v1' / 'metrics.py'
    if digest(path.read_bytes()) != METRICS_SHA256:
        raise ValueError('unchanged scientific metric kernel required')
    spec = importlib.util.spec_from_file_location('spinal_eligible_metric_kernel', path)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _observations(bank, reference, candidate, metrics):
    """One neuron at a time; original recording order and source support persist."""
    for neuron in bank.metadata['expected_neurons']:
        target, support = [], []
        values = {k: [] for k in ALL_METHODS}
        if candidate is not None:
            values['candidate'] = []
        for row in bank.eligible:
            if row['neuron_id'] != neuron:
                continue
            source = _source_arrays(bank, row)
            controls = _prediction_arrays(reference, row)
            target.extend(map(float, source['target_hz']))
            support.extend(map(bool, source['support']))
            values['raw_fluorescence'].extend(map(float, source['fluorescence']))
            for method, vector in controls.items():
                values[method].extend(map(float, vector))
            if candidate is not None:
                values['candidate'].extend(map(float, _prediction_arrays(candidate, row)['candidate']))
        controls = {'raw_fluorescence': metrics.Prediction(tuple(values['raw_fluorescence']), 'arbitrary')}
        controls.update({method: metrics.Prediction(tuple(values[method]), reference.metadata['methods'][method])
                         for method in REFERENCE_METHODS})
        observation = {'neuron_id': neuron, 'target_hz': target, 'support': support, 'controls': controls}
        if candidate is not None:
            observation['candidate'] = metrics.Prediction(tuple(values['candidate']), candidate.metadata['methods']['candidate'])
        yield observation


def evaluate(bank, reference, candidate=None):
    if reference.role != 'operator_reference' or (candidate is not None and candidate.role != 'candidate'):
        raise ValueError('operator and candidate roles may not be swapped')
    for bundle in (reference, candidate):
        if bundle is not None and (bundle.metadata['bank_manifest_sha256'] != bank.manifest_sha256
                                  or set(bundle.by_id) != {r['recording_id'] for r in bank.eligible}):
            raise ValueError('same frozen bank and complete eligible support required')
    metrics = load_metrics()
    result = metrics.score_condition(expected_neurons=bank.metadata['expected_neurons'],
                                      observations=_observations(bank, reference, candidate, metrics), sampling_rate_hz=30.)
    return {'schema': 'spinal_current_condition_comparison_v1', 'condition_id': CONDITION_ID,
            'bank_manifest_sha256': bank.manifest_sha256,
            'operator_reference_manifest_sha256': reference.manifest_sha256,
            'candidate_manifest_sha256': candidate.manifest_sha256 if candidate else None,
            'aggregation': 'concatenate_eligible_supported_bins_within_neuron_then_equal_neuron_cohort_summaries',
            'coverage': {'source_neurons': 44, 'source_recording_rows': 132, 'eligible_recordings': 116,
                         'eligible_recording_ids': [r['recording_id'] for r in bank.eligible],
                         'source_exclusions': [{'recording_id': r['recording_id'], 'reason': r['reason']} for r in bank.excluded],
                         'scored_bins': sum(r['scored_bins'] for r in bank.eligible)},
            'metrics': result,
            'reference_qualification_established_by_this_evaluator': False,
            'provenance_notes_are_unverified': True,
            'historical_paper_reproduction_established': False,
            'paper_improvement_or_SOTA_established': False,
            'binary_success_threshold_defined': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank', type=Path, required=True)
    parser.add_argument('--references', type=Path, required=True)
    parser.add_argument('--reference-manifest-sha256', required=True, help='Frozen independently by operator; never supplied by candidate')
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--candidate-manifest-sha256')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if bool(args.candidate) != bool(args.candidate_manifest_sha256):
        parser.error('candidate directory and manifest SHA must occur together')
    if args.output.exists() or args.output.is_symlink():
        parser.error('output must not exist')
    bank = load_bank(args.bank)
    reference = load_predictions(args.references, bank, role='operator_reference', manifest_sha256=args.reference_manifest_sha256)
    candidate = load_predictions(args.candidate, bank, role='candidate', manifest_sha256=args.candidate_manifest_sha256) if args.candidate else None
    result = evaluate(bank, reference, candidate)
    # Output opened exclusively; no partial score report is written on load failure.
    payload = (json.dumps(result, indent=2, allow_nan=False) + '\n').encode()
    if len(payload) > 2 * 1024 * 1024:
        raise ValueError('comparison report byte budget exceeded')
    with args.output.open('xb') as stream:
        args.output.chmod(0o600); stream.write(payload)
    print(json.dumps({'condition_id': CONDITION_ID, 'neurons': 44, 'eligible_recordings': 116,
                      'source_exclusions': 16, 'scientific_success_claimed': False}))


if __name__ == '__main__':
    main()
