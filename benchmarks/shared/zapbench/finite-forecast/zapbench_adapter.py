"""ZAPBench finite-domain scoring and complete forecast geometry.

Independent standard-library implementation of source-derived formulas. This is
not a protected runner, data provenance admission, or bitwise JAX parity claim.
See SCIENTIFIC_CONTRACT.md for the official notebook/live nonfinite discrepancy.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Iterable

UPSTREAM_COMMIT = '7347b3b21a3f332e281b774c945f1505dd966abf'
OFFSETS = (0, 649, 2422, 3078, 3735, 5047, 5638, 6623, 7279, 7879)
NAMES = ('gain', 'dots', 'flash', 'taxis', 'turning', 'position',
         'open loop', 'rotation', 'dark')
TRAIN_CONDITIONS = (0, 1, 2, 4, 5, 6, 7, 8)
INFERENCE_ORDER = TRAIN_CONDITIONS + (3,)
NEURONS = 71721
HORIZON = 32
MAX_CONTEXT = 256
MAX_TILE_VALUES = 4096


class AdmissionError(ValueError):
    """A complete declared endpoint or finite numeric input was not supplied."""


def integer(value, name: str, lower: int, upper: int) -> int:
    if type(value) is not int or not lower <= value <= upper:
        raise AdmissionError(f'{name} must be integer in [{lower}, {upper}]')
    return value


def condition_bounds(condition: int) -> tuple[int, int]:
    integer(condition, 'condition', 0, 8)
    return OFFSETS[condition] + 1, OFFSETS[condition + 1] - 1


def target_interval(condition: int, split: str) -> tuple[int, int]:
    """Target interval; context may precede it within the padded condition."""
    lo, hi = condition_bounds(condition)
    length = hi - lo
    # Mirrors int(length * fraction) in the immutable official utility.
    test, val = int(length * .2), int(length * .1)
    train_end, val_end = hi - test - val, hi - test
    if condition == 3:
        if split != 'test_holdout':
            raise AdmissionError('taxis is excluded from training and validation')
        return lo + MAX_CONTEXT, hi
    if split == 'train':
        return lo, train_end
    if split == 'val':
        return train_end, val_end
    if split == 'test':
        return val_end, hi
    raise AdmissionError('condition/split combination is not official')


def window_geometry(condition: int, split: str, context: int) -> dict:
    integer(context, 'context', 1, MAX_CONTEXT)
    lo, hi = target_interval(condition, split)
    first_target = lo + context if split == 'train' else lo
    count = hi - first_target - HORIZON + 1
    if count <= 0:
        raise AdmissionError('empty prediction support')
    return {'condition': condition, 'split': split,
            'context_start': first_target - context,
            'first_target_start': first_target,
            'last_target_start': hi - HORIZON,
            'num_windows': count, 'shape': [count, HORIZON, NEURONS]}


def expected_manifest(context: int = MAX_CONTEXT) -> dict:
    integer(context, 'context', 1, MAX_CONTEXT)
    return {
        'schema': 'zapbench_complete_forecast_v1',
        'upstream_commit': UPSTREAM_COMMIT,
        'timeseries': '240930_traces', 'trace_shape': [7879, NEURONS],
        'context': context, 'horizon': HORIZON, 'output_offset': 0,
        'warmup_steps': 0, 'sequential': True,
        'neuron_axis': {'start': 0, 'stop': NEURONS, 'step': 1},
        'training_intervals': [
            {'condition': c, 'interval': list(target_interval(c, 'train'))}
            for c in TRAIN_CONDITIONS],
        'validation_target_intervals': [
            {'condition': c, 'interval': list(target_interval(c, 'val'))}
            for c in TRAIN_CONDITIONS],
        'endpoints': [window_geometry(c, 'test_holdout' if c == 3 else 'test', context)
                      for c in INFERENCE_ORDER],
    }


def _same(actual, expected) -> bool:
    # Python's bool/int equality and float/int equality must not admit metadata.
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return actual.keys() == expected.keys() and all(
            _same(actual[k], v) for k, v in expected.items())
    if type(expected) is list:
        return len(actual) == len(expected) and all(
            _same(a, b) for a, b in zip(actual, expected))
    return actual == expected


def validate_manifest(manifest: dict) -> dict:
    if type(manifest) is not dict:
        raise AdmissionError('manifest must be dictionary')
    expected = expected_manifest(manifest.get('context'))
    if not _same(manifest, expected):
        raise AdmissionError('manifest differs from complete frozen endpoint')
    return expected  # fresh copy; subsequent caller mutations cannot change it


def validate_window(condition: int, split: str, context: int,
                    context_start: int, target_start: int, target_end: int) -> None:
    """Validate one rolling window, including causal context and all 32 targets."""
    g = window_geometry(condition, split, context)
    for name, value in [('context_start', context_start),
                        ('target_start', target_start), ('target_end', target_end)]:
        integer(value, name, 0, OFFSETS[-1])
    if (target_start - context_start != context or target_end - target_start != HORIZON
            or not g['first_target_start'] <= target_start <= g['last_target_start']):
        raise AdmissionError('window violates causal context or split support')
    lo, hi = condition_bounds(condition)
    if context_start < lo or target_end > hi:
        raise AdmissionError('window crosses padded condition boundary')


def _finite(value) -> float:
    if type(value) not in (int, float):
        raise AdmissionError('numeric values must be Python int/float, not bool')
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise AdmissionError('nonrepresentable value') from error
    if not math.isfinite(result):
        raise AdmissionError('nonfinite prediction or target')
    return result


def tile_error_sums(predictions: list, targets: list) -> tuple[float, float, int]:
    """Finite-only kernel, independent of scientific cohort admission.

    No masking, NaN repair, target-variance denominator, or range clipping.
    Tiny invented tests can exercise this kernel without an authentic array.
    """
    if type(predictions) is not list or type(targets) is not list:
        raise AdmissionError('tile values must be lists')
    if not 1 <= len(predictions) <= MAX_TILE_VALUES or len(predictions) != len(targets):
        raise AdmissionError('empty, oversized, or unequal tile')
    absolute, squared = [], []
    for prediction, target in zip(predictions, targets):
        delta = _finite(target) - _finite(prediction)
        magnitude, square = abs(delta), delta * delta
        if not math.isfinite(magnitude) or not math.isfinite(square):
            raise AdmissionError('numeric overflow in error')
        absolute.append(magnitude)
        squared.append(square)
    try:
        return math.fsum(absolute), math.fsum(squared), len(absolute)
    except OverflowError as error:
        raise AdmissionError('numeric overflow in tile reduction') from error


@dataclass
class _Sum:
    total: float = 0.0
    correction: float = 0.0

    def add(self, value: float) -> None:
        result = self.total + value
        if abs(self.total) >= abs(value):
            self.correction += (self.total - result) + value
        else:
            self.correction += (value - result) + self.total
        self.total = result
        if not math.isfinite(self.total) or not math.isfinite(self.correction):
            raise AdmissionError('numeric overflow in full reduction')

    def value(self) -> float:
        result = self.total + self.correction
        if not math.isfinite(result):
            raise AdmissionError('numeric overflow in final reduction')
        return result


def _admit_tile(tile: dict, condition: int, window: int, horizon: int,
                first_neuron: int, target_time: int) -> int:
    keys = {'condition', 'window', 'horizon', 'first_neuron', 'target_time',
            'predictions', 'targets'}
    if type(tile) is not dict or tile.keys() != keys:
        raise AdmissionError('tile schema mismatch')
    expected = (condition, window, horizon, first_neuron, target_time)
    actual = tuple(tile[k] for k in ('condition', 'window', 'horizon',
                                    'first_neuron', 'target_time'))
    if any(type(x) is not int for x in actual) or actual != expected:
        raise AdmissionError('missing, duplicated, reordered, or misplaced tile')
    values = tile['predictions']
    if type(values) is not list or not 1 <= len(values) <= MAX_TILE_VALUES:
        raise AdmissionError('invalid prediction tile length')
    if first_neuron + len(values) > NEURONS:
        raise AdmissionError('neuron tile crosses official axis')
    return len(values)


def score_complete(manifest: dict, tiles: Iterable[dict]) -> dict:
    """Score every coordinate exactly once, or return no score.

    Tiles must traverse condition, window, horizon, neuron in canonical order.
    Targets are a trusted caller operand; this function cannot authenticate them
    or enforce candidate isolation. All errors invalidate the whole call.
    """
    plan = validate_manifest(manifest)
    stream = iter(tiles)
    per_condition = []
    for endpoint in plan['endpoints']:
        mae_sums = [_Sum() for _ in range(HORIZON)]
        mse_sums = [_Sum() for _ in range(HORIZON)]
        for window in range(endpoint['num_windows']):
            for h in range(HORIZON):
                neuron = 0
                while neuron < NEURONS:
                    try:
                        tile = next(stream)
                    except StopIteration as error:
                        raise AdmissionError('incomplete full endpoint') from error
                    length = _admit_tile(tile, endpoint['condition'], window, h + 1,
                                         neuron, endpoint['first_target_start'] + window + h)
                    absolute, squared, count = tile_error_sums(tile['predictions'], tile['targets'])
                    if count != length:
                        raise AdmissionError('tile length disagreement')
                    mae_sums[h].add(absolute)
                    mse_sums[h].add(squared)
                    neuron += length
        denominator = endpoint['num_windows'] * NEURONS
        mae = [s.value() / denominator for s in mae_sums]
        mse = [s.value() / denominator for s in mse_sums]
        per_condition.append({'condition': endpoint['condition'],
                              'num_windows': endpoint['num_windows'],
                              'mae_by_horizon': mae, 'mse_by_horizon': mse,
                              'mae': math.fsum(mae) / HORIZON,
                              'mse': math.fsum(mse) / HORIZON})
    try:
        next(stream)
    except StopIteration:
        pass
    else:
        raise AdmissionError('extra coordinates after full endpoint')
    # Official plot helper averages supplied condition rows equally. Keep heldout
    # separate and label the complete nine-condition macro rather than imply a
    # paper-specific condition filtering policy or extra benchmark endpoint.
    macro = {metric: [math.fsum(row[metric][h] for row in per_condition) / 9
                      for h in range(HORIZON)]
             for metric in ('mae_by_horizon', 'mse_by_horizon')}
    return {'schema': 'zapbench_finite_score_v1', 'official_runtime_parity': False,
            'scope': 'complete finite-domain formula adapter; no authentic qualification',
            'coordinates': sum(e['num_windows'] for e in plan['endpoints']) * HORIZON * NEURONS,
            'per_condition': per_condition, 'all_nine_condition_macro': macro}
