"""Spinal CASCADE current-source single-realization bank, not historical replay.

Numerical recipe adapted from Cascade utils.py at 1f9f98b (GPL-3.0).
See LICENSE, README.md and upstream/utils.py. Native MAT extraction reuses the
previous authenticated parser, without its prospective native-400ms projection.
No model, learned calibration, assessment shift search, or success threshold.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path, PurePosixPath
import sys

import numpy as np
from scipy import __version__ as scipy_version
from scipy.interpolate import interp1d
from scipy.io import loadmat
from scipy.ndimage import gaussian_filter1d
from scipy.signal import resample

HERE = Path(__file__).resolve().parent
INVENTORY_SHA256 = '718fd791559ebf03d68ac14c030a5b06ad9c2213b917cb52bc1b1fc55242779c'
METRICS_SHA256 = '7249e2d1d6ead3172fc9dc0f7910f36d2763806c6a308be064f8483095b94ed3'
SOURCE_SIGMA_SECONDS = {2.5: .4, 5.: .2, 10.: .1, 15.: .1, 20.: .1, 25.: .05, 30.: .05}
METHODS = ('raw_fluorescence', 'oasis', 'default_cascade', 'glutamatergic_cascade', 'gabaergic_cascade')
MAX_NATIVE_BYTES = 8 * 1024 * 1024
MAX_NATIVE_SAMPLES = 500_000
MAX_OUTPUT_SAMPLES = 1_000_000
MAX_OUTPUT_BYTES = 32 * 1024 * 1024


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, allow_nan=False, sort_keys=True) + '\n').encode()


@dataclass(frozen=True)
class Condition:
    rate_hz: float = 30.
    noise_level: float = 7.

    def __post_init__(self):
        if type(self.rate_hz) not in (int, float) or self.rate_hz not in SOURCE_SIGMA_SECONDS:
            raise ValueError('rate must be one of the seven paper rates')
        if type(self.noise_level) not in (int, float) or not math.isfinite(self.noise_level) or not 0 <= self.noise_level <= 59:
            raise ValueError('noise must be finite in [0,59]; source calibration may have narrower support')

    @property
    def sigma_seconds(self):
        return SOURCE_SIGMA_SECONDS[self.rate_hz]

    @property
    def window(self):
        return 32 if self.rate_hz < 15 else 64

    def metadata(self):
        return {'name': 'current_source_recipe_single_realization_v1',
                'nominal_rate_hz': float(self.rate_hz), 'requested_noise_level': float(self.noise_level),
                'target_sigma_seconds': self.sigma_seconds, 'context_window_bins': self.window,
                'original_figure4_anchor_parameters': self.rate_hz == 30 and self.noise_level == 7,
                'historical_paper_realization': False,
                'complete_paper_noise_grid_or_matched_precision_panel': False}


@dataclass(frozen=True)
class NativeRecord:
    neuron_id: str
    cohort: str
    source_path: str
    source_sha256: str
    ordinal: int
    recordings_in_neuron: int
    times: np.ndarray
    fluorescence: np.ndarray
    event_seconds: np.ndarray
    dropped_nan_events: int = 0

    @property
    def identity(self):
        return f'{self.neuron_id}/recording-{self.ordinal:03d}'


def parse_trial(trial):
    """Reuse the native fields/clock checks; do not use any prepared targets."""
    if not isinstance(trial, dict) or not {'fluo_time', 'fluo_mean', 'events_AP'} <= set(trial):
        raise ValueError('native CAttached fields required')
    def vector(field):
        raw = np.asarray(trial[field])
        if raw.dtype.kind not in 'fiu' or raw.ndim > 2 or sum(n > 1 for n in raw.shape) > 1:
            raise ValueError('native fields must be real numeric vectors')
        return raw.astype(np.float64).reshape(-1)
    times = vector('fluo_time')
    values = vector('fluo_mean')
    events = vector('events_AP')
    if len(times) != len(values) or not 3 <= len(times) <= MAX_NATIVE_SAMPLES:
        raise ValueError('complete equal native time/fluorescence arrays required')
    if not np.isfinite(times).all() or not np.isfinite(values).all():
        raise ValueError('native times/fluorescence must be finite; no silent truncation')
    with np.errstate(over='ignore', divide='ignore', invalid='ignore'):
        dt = np.diff(times)
        mean_dt = np.mean(dt)
        rate = 1 / mean_dt
        finite_differences = np.isfinite(np.diff(values)).all()
    if (not np.isfinite(dt).all() or not np.isfinite(mean_dt) or not np.isfinite(rate)
            or rate <= 0 or not finite_differences or not (dt > 0).all()
            or not np.allclose(dt, mean_dt, rtol=1e-6, atol=1e-10)):
        raise ValueError('strictly increasing uniform native timestamps required')
    if np.isinf(events).any():
        raise ValueError('infinite electrical event time')
    dropped = int(np.isnan(events).sum())
    return times, values, np.sort(events[~np.isnan(events)] / 10_000.), dropped


def _read_native(original, inventory):
    """Internal reader also used with generated fixture inventories in controls."""
    original = Path(original)
    if original.is_symlink() or not original.is_dir():
        raise ValueError('original must be a real directory')
    original = original.resolve()
    rows = inventory['files']
    if len(rows) != inventory['expected_neurons'] or sum(r['bytes'] for r in rows) != inventory['expected_file_bytes']:
        raise ValueError('inconsistent frozen inventory')
    if inventory['expected_file_bytes'] > MAX_NATIVE_BYTES:
        raise ValueError('native source byte budget exceeded')
    if len({r['path'] for r in rows}) != len(rows) or len({r['neuron_id'] for r in rows}) != len(rows):
        raise ValueError('duplicate native source or neuron')
    records = []
    total_samples = 0
    for row in rows:
        relative = PurePosixPath(row['path'])
        if relative.is_absolute() or '..' in relative.parts or '\\' in row['path']:
            raise ValueError('unsafe source path')
        path = original
        for part in relative.parts:
            path = path / part
            if path.is_symlink():
                raise ValueError('source symlink refused')
        if not path.is_file() or path.stat().st_size != row['bytes']:
            raise ValueError(f'missing or wrong-size source: {row["path"]}')
        with path.open('rb') as stream:
            payload = stream.read(row['bytes'] + 1)
        blob = hashlib.sha1(b'blob ' + str(len(payload)).encode() + b'\0' + payload).hexdigest()
        if len(payload) != row['bytes'] or sha256(payload) != row['sha256'] or blob != row['git_blob_sha1']:
            raise ValueError('native byte identity mismatch')
        data = loadmat(io.BytesIO(payload), simplify_cells=True, verify_compressed_data_integrity=True)['CAttached']
        trials = [data] if isinstance(data, dict) else list(data)
        if not trials:
            raise ValueError('source neuron has no recordings')
        for ordinal, trial in enumerate(trials):
            times, values, events, dropped = parse_trial(trial)
            total_samples += len(times)
            if total_samples > MAX_NATIVE_SAMPLES:
                raise ValueError('native sample budget exceeded')
            records.append(NativeRecord(row['neuron_id'], row['cohort'], row['path'], row['sha256'],
                                        ordinal, len(trials), times, values, events, dropped))
    if len(records) != inventory['expected_recordings'] or total_samples != inventory['expected_native_samples']:
        raise ValueError('complete native recording/sample census mismatch')
    return records


def read_native(original):
    payload = (HERE / 'NATIVE_INVENTORY.json').read_bytes()
    if sha256(payload) != INVENTORY_SHA256:
        raise ValueError('native inventory pin mismatch')
    return _read_native(original, json.loads(payload))


def keyed_rng(record, condition, bank_seed):
    if not isinstance(bank_seed, str) or not 1 <= len(bank_seed) <= 128:
        raise ValueError('prospectively frozen bank seed must contain 1..128 characters')
    key = json.dumps(['spinal-current-source-v1', bank_seed, record.source_path, record.source_sha256,
                      record.ordinal, float(condition.rate_hz), float(condition.noise_level),
                      'single-assessment-realization'], separators=(',', ':'), ensure_ascii=True).encode()
    digest = hashlib.sha256(key).digest()
    return np.random.RandomState(np.frombuffer(digest, dtype='<u4')), digest.hex()


def prepare_record(record, condition, bank_seed):
    """Exact recovered one-replica recipe with explicit failures and fixed support.

    Per-record RNG reset is new benchmark policy; source used process-global RNG.
    Source silently catches failures. Here every original recording remains named.
    """
    times, trace, events = record.times, record.fluorescence, record.event_seconds
    frame_rate = 1 / np.nanmean(np.diff(times))
    rng, seed_digest = keyed_rng(record, condition, bank_seed)
    meta = {'recording_id': record.identity, 'neuron_id': record.neuron_id, 'cohort': record.cohort,
            'source_path': record.source_path, 'source_sha256': record.source_sha256,
            'source_recording_index_zero_based': record.ordinal, 'native_samples': len(trace),
            'native_rate_hz': float(frame_rate), 'rng_key_sha256': seed_digest,
            'electrical_events': len(events), 'dropped_nan_event_entries': record.dropped_nan_events,
            'status': 'unavailable'}
    result = {'metadata': meta, 'arrays': {}}
    base_noise = np.nanmedian(np.abs(np.diff(trace))) * 100 / np.sqrt(frame_rate)
    meta['native_standardized_noise'] = float(base_noise)
    test_noise = np.zeros(60)
    # Preserve source random calls, including the zero-scale first draw.
    for i in range(60):
        noise = rng.normal(0, i / 100 * np.sqrt(frame_rate), trace.shape)
        test_noise[i] = np.nanmedian(np.abs(np.diff(noise + trace))) * 100 / np.sqrt(frame_rate)
    meta['calibration_noise_range'] = [float(np.min(test_noise)), float(np.max(test_noise))]
    if condition.noise_level < test_noise[0]:
        meta['reason'] = 'native_noise_exceeds_requested_noise'
        return result
    # interp1d sorts by x exactly as in source. Nonmonotonic probe levels are not
    # "repaired". Duplicate calibration coordinates are explicitly unavailable.
    if not np.isfinite(test_noise).all() or len(np.unique(test_noise)) != 60:
        meta['reason'] = 'degenerate_source_noise_calibration'
        return result
    try:
        noise_std = float(interp1d(test_noise, np.arange(60), kind='linear')(condition.noise_level)) / 100 * np.sqrt(frame_rate)
    except ValueError:
        meta['reason'] = 'requested_noise_outside_source_probe_range'
        return result
    changed_rate = abs(condition.rate_hz - frame_rate) / frame_rate > .05
    if changed_rate:
        n = int(round(len(trace) * condition.rate_hz / frame_rate))
        if not 2 <= n <= MAX_OUTPUT_SAMPLES:
            meta['reason'] = 'resampling_length_outside_bounds'
            return result
        trace, _discarded_source_times = resample(trace, n, times, axis=0)
        noise_std *= np.sqrt(condition.rate_hz / frame_rate)
    # Source truncates to integer replica count after its 800k sample heuristic.
    replica_count = int(int(min(8e5, record.recordings_in_neuron * len(trace)) / len(trace)) / record.recordings_in_neuron)
    if replica_count != 1:
        meta['reason'] = 'source_single_replica_cap_excludes_recording'
        return result
    centers = np.linspace(times[0], times[-1], len(trace))
    edges = np.append(centers, centers[-1] + 1 / condition.rate_hz) - 1 / condition.rate_hz / 2
    counts, _ = np.histogram(events, bins=edges)
    level = np.sqrt(np.abs(trace + 1))
    median_level = np.median(level)
    if median_level <= 0 or not np.isfinite(level).all():
        meta['reason'] = 'invalid_source_heteroscedastic_scale'
        return result
    level /= median_level
    observation = trace + rng.normal(0, noise_std * level, trace.shape)
    target_hz = gaussian_filter1d(counts.astype(float), condition.sigma_seconds * condition.rate_hz,
                                 mode='reflect', truncate=4.) * condition.rate_hz
    half = condition.window // 2
    support = np.zeros(len(trace), dtype=bool)
    if len(trace) > condition.window:
        support[half:len(trace) - half] = True
    if not np.isfinite(observation).all() or not np.isfinite(target_hz).all():
        raise ValueError('nonfinite source recipe output')
    meta.update(status='prepared', resampled=bool(changed_rate), output_samples=len(trace),
                source_bin_center_rate_hz=float((len(trace) - 1) / (times[-1] - times[0])),
                nominal_rate_hz=float(condition.rate_hz), added_noise_std=float(noise_std),
                realized_standardized_noise=float(np.median(np.abs(np.diff(observation))) * 100 / np.sqrt(condition.rate_hz)),
                scored_bins=int(support.sum()), events_in_source_bins=int(counts.sum()),
                events_outside_source_bins=int(len(events) - counts.sum()),
                alignment='hardware_event_clock_zero_extra_shift',
                support_policy='source_symmetric_context_per_original_recording',
                short_recording=bool(not support.any()))
    result['arrays'] = {'fluorescence': observation, 'target_hz': target_hz, 'counts': counts,
                        'support': support, 'bin_centers_seconds': centers}
    return result


def build_bank(records, condition, bank_seed):
    if not records or len({r.identity for r in records}) != len(records):
        raise ValueError('complete distinct native recordings required')
    # Admit the complete condition's allocation before any Fourier arrays exist.
    projected_samples = 0
    for record in records:
        native_rate = 1 / np.mean(np.diff(record.times))
        n = (int(round(len(record.times) * condition.rate_hz / native_rate))
             if abs(condition.rate_hz - native_rate) / native_rate > .05 else len(record.times))
        if n > MAX_OUTPUT_SAMPLES:
            raise ValueError('condition sample budget exceeded before resampling')
        projected_samples += max(0, n)
    if projected_samples > MAX_OUTPUT_SAMPLES:
        raise ValueError('condition sample budget exceeded before resampling')
    rows = [prepare_record(r, condition, bank_seed) for r in records]
    if sum(r['metadata'].get('output_samples', 0) for r in rows) > MAX_OUTPUT_SAMPLES:
        raise ValueError('condition sample budget exceeded')
    return {'condition': condition.metadata(), 'bank_seed': bank_seed,
            'scope': 'spinal_only_current_source_recipe_not_full_paper_comparison',
            'numpy_version': np.__version__, 'scipy_version': scipy_version,
            'recordings': rows,
            'expected_neurons': {r.neuron_id: r.cohort for r in records},
            'source_recordings': len(records), 'native_samples': sum(len(r.times) for r in records),
            'unavailable_recordings': [r['metadata']['recording_id'] for r in rows if r['metadata']['status'] != 'prepared'],
            'historical_paper_comparison_qualified': False}


def training_records(bank, held_neuron):
    """Exclude every recording of held neuron; no filename/class guess exclusions."""
    if held_neuron not in bank['expected_neurons']:
        raise ValueError('unknown held neuron')
    return [r for r in bank['recordings'] if r['metadata']['neuron_id'] != held_neuron]


def load_metrics():
    path = HERE.parent / 'original-endpoint-metrics-v1' / 'metrics.py'
    if sha256(path.read_bytes()) != METRICS_SHA256:
        raise ValueError('existing metric pin mismatch')
    spec = importlib.util.spec_from_file_location('spinal_original_metric_kernel', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def metric_operands(bank, predictions):
    """Connect complete prepared records to existing five-method neuron metrics.

    Predictions keyed by recording ID, then method, each {values,unit}. Values
    must already use declared hardware alignment and condition smoothing; this
    function never selects shifts/smoothing using assessment events. Raw control
    is always the bank observation; supplied raw replacements are refused.
    """
    if bank['unavailable_recordings']:
        raise ValueError('unavailable original recordings forbid complete-condition scoring')
    rows = bank['recordings']
    ids = {r['metadata']['recording_id'] for r in rows}
    if set(predictions) != ids:
        raise ValueError('predictions must cover every original recording exactly')
    metrics = load_metrics()
    observations = []
    candidate_flags = set()
    for identity in bank['expected_neurons']:
        pieces = [r for r in rows if r['metadata']['neuron_id'] == identity]
        target, support = [], []
        method_values = {k: [] for k in METHODS}
        units = {k: set() for k in METHODS}
        candidate_values, candidate_units = [], set()
        for row in pieces:
            arr = row['arrays']
            supplied = predictions[row['metadata']['recording_id']]
            if set(supplied) not in (set(METHODS[1:]), set(METHODS[1:]) | {'candidate'}):
                raise ValueError('four model controls required; raw fluorescence fixed by bank')
            candidate_flags.add('candidate' in supplied)
            n = len(arr['target_hz'])
            target.extend(map(float, arr['target_hz']))
            support.extend(map(bool, arr['support']))
            method_values['raw_fluorescence'].extend(map(float, arr['fluorescence']))
            units['raw_fluorescence'].add('arbitrary')
            for method, prediction in supplied.items():
                if set(prediction) != {'values', 'unit'} or len(prediction['values']) != n:
                    raise ValueError('complete original recording bin count and prediction unit required')
                values = np.asarray(prediction['values'])
                if values.ndim != 1 or values.dtype.kind not in 'fiu':
                    raise ValueError('prediction must be a real numeric vector')
                values = list(map(float, values))
                if method == 'candidate':
                    candidate_values.extend(values); candidate_units.add(prediction['unit'])
                else:
                    method_values[method].extend(values); units[method].add(prediction['unit'])
        if sum(support) < 2:
            raise ValueError('a required neuron has insufficient fixed source context support')
        if any(len(values) != 1 for values in units.values()) or len(candidate_units) > 1:
            raise ValueError('units must be constant across a neuron recordings')
        observation = {'neuron_id': identity, 'target_hz': target, 'support': support,
                       'controls': {m: metrics.Prediction(tuple(method_values[m]), next(iter(units[m]))) for m in METHODS}}
        if candidate_units:
            observation['candidate'] = metrics.Prediction(tuple(candidate_values), next(iter(candidate_units)))
        observations.append(observation)
    if len(candidate_flags) != 1:
        raise ValueError('candidate must cover all original recordings or none')
    return metrics, observations


def score_bank(bank, predictions):
    metrics, observations = metric_operands(bank, predictions)
    result = metrics.score_condition(expected_neurons=bank['expected_neurons'], observations=observations,
                                     sampling_rate_hz=bank['condition']['nominal_rate_hz'])
    return {'condition': bank['condition'], 'historical_paper_comparison_qualified': False,
            'scope': bank['scope'], 'metrics': result}


def write_bank(bank, output):
    """Operator-only bundle. It contains targets; never distribute it to solvers."""
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('output must not exist')
    # Conservative ZIP/NPY/JSON allowance, checked before creating the directory.
    estimate = 1024 * 1024 + sum(4096 + sum(a.nbytes for a in row['arrays'].values())
                               for row in bank['recordings'])
    if estimate > MAX_OUTPUT_BYTES:
        raise ValueError('operator artifact byte budget exceeded before writing')
    output.mkdir(parents=True, mode=0o700)
    output.chmod(0o700)
    receipt = {k: v for k, v in bank.items() if k != 'recordings'}
    receipt['operator_only_contains_targets'] = True
    receipt['inventory_sha256'] = INVENTORY_SHA256
    receipt['producer_sha256'] = sha256(Path(__file__).read_bytes())
    receipt['recordings'] = []
    written_bytes = 0
    for index, row in enumerate(bank['recordings']):
        metadata = dict(row['metadata'])
        if row['arrays']:
            filename = f'recording-{index:03d}.npz'
            np.savez(output / filename, **row['arrays'])
            (output / filename).chmod(0o600)
            data = (output / filename).read_bytes()
            written_bytes += len(data)
            if written_bytes > MAX_OUTPUT_BYTES - 1024 * 1024:
                raise ValueError('operator artifact byte budget exceeded')
            metadata['operator_payload'] = {'path': filename, 'bytes': len(data), 'sha256': sha256(data)}
        receipt['recordings'].append(metadata)
    metadata_bytes = json_bytes(receipt)
    if written_bytes + len(metadata_bytes) > MAX_OUTPUT_BYTES:
        raise ValueError('operator artifact byte budget exceeded')
    (output / 'BANK.json').write_bytes(metadata_bytes)
    (output / 'BANK.json').chmod(0o600)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bank-seed', required=True)
    parser.add_argument('--rate-hz', type=float, choices=sorted(SOURCE_SIGMA_SECONDS), default=30.)
    parser.add_argument('--noise-level', type=float, default=7.)
    args = parser.parse_args()
    condition = Condition(args.rate_hz, args.noise_level)
    if args.output.exists():
        parser.error('output already exists')
    bank = build_bank(read_native(args.original), condition, args.bank_seed)
    receipt = write_bank(bank, args.output)
    print(json.dumps({'source_neurons': len(receipt['expected_neurons']), 'source_recordings': receipt['source_recordings'],
                      'unavailable_recordings': len(receipt['unavailable_recordings']),
                      'historical_paper_comparison_qualified': False}))


if __name__ == '__main__':
    main()
