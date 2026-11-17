"""The released Figure 4 RNN loss; arithmetic, not benchmark admission.

The mathematical reduction follows modules_simpleRNN.loss_mse, with float64
accumulation for portability. PyTorch float32 reductions need not be bitwise
identical. No target construction, network inference or training occurs here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

SOURCE_SHAPE = (32, 1000, 500)  # sequence row, integration timestep, output unit


def _numeric_array(value, name):
    array = np.asarray(value)
    if array.dtype.kind not in 'fiu' or array.ndim != 3:
        raise ValueError(f'{name} must be a real numeric rank-3 array')
    if any(size == 0 for size in array.shape):
        raise ValueError(f'{name} has an empty axis')
    return array


def masked_trial_mse(output, target, mask, *, source_panel=False):
    """Return equal-trial masked MSE and each trial's contribution.

    This preserves the author's square *after* masking and the denominator
    from mask[:, :, 0]. A mask may have one channel or the full output shape.
    No implicit broadcasting is accepted for target, trial or time axes.
    Nonnegative finite masks with a positive first-channel sum are required;
    undefined author arithmetic fails explicitly instead of returning NaN.
    """
    output = _numeric_array(output, 'output')
    target = _numeric_array(target, 'target')
    mask = _numeric_array(mask, 'mask')
    if output.shape != target.shape:
        raise ValueError('output and target shapes differ')
    if mask.shape[:2] != output.shape[:2] or mask.shape[2] not in (1, output.shape[2]):
        raise ValueError('mask must align to trial/time and have one or all output channels')
    if source_panel and (output.shape != SOURCE_SHAPE or mask.shape != SOURCE_SHAPE):
        raise ValueError('released notebook panel requires shape (32, 1000, 500) for all arrays')

    trial_losses = []
    for trial in range(output.shape[0]):
        # Work per sequence, bounding temporary arrays independently of trial count.
        prediction = np.asarray(output[trial], dtype=np.float64)
        truth = np.asarray(target[trial], dtype=np.float64)
        weights = np.asarray(mask[trial], dtype=np.float64)
        if not all(np.isfinite(x).all() for x in (prediction, truth, weights)):
            raise ValueError('all output, target and mask values must be finite, including masked positions')
        if (weights < 0).any():
            raise ValueError('mask must be nonnegative')
        if source_panel and trial >= 14 and np.any(truth != 0):
            raise ValueError('released notebook target rows 14 through 31 are all zero')
        if source_panel and not (weights == 1).all():
            raise ValueError('released notebook uses an all-one full-output mask')
        denominator = weights[:, 0].sum(dtype=np.float64)
        if not np.isfinite(denominator) or denominator <= 0:
            raise ValueError('each trial needs a finite positive first-channel mask sum')
        with np.errstate(over='ignore', invalid='ignore'):
            squared = np.square(weights * (truth - prediction))
            value = squared.mean(axis=-1, dtype=np.float64).sum(dtype=np.float64) / denominator
        if not np.isfinite(value):
            raise ValueError('loss overflowed the finite arithmetic domain')
        trial_losses.append(float(value))
    with np.errstate(over='ignore', invalid='ignore'):
        mean = float(np.mean(np.asarray(trial_losses, dtype=np.float64)))
    if not np.isfinite(mean):
        raise ValueError('mean loss overflowed the finite arithmetic domain')
    return {'mean_trial_mse': mean, 'per_trial_mse': trial_losses}


def score_source_panel(output, target, mask):
    result = masked_trial_mse(output, target, mask, source_panel=True)
    values = result['per_trial_mse']
    result.update({
        'task_id': 'PAPER-FIND-NEW-002',
        'scope': 'released_notebook_full_training_panel_arithmetic',
        'shape': list(SOURCE_SHAPE),
        'direction': 'lower',
        'aggregation': 'equal weight to all 32 sequence rows; time and output units within rows',
        'diagnostics': {
            'natural_rows_0_to_13_mean': float(np.mean(values[:14])),
            'zero_input_control_rows_14_to_31_mean': float(np.mean(values[14:])),
        },
        'source_realization_authenticated': False,
        'author_baseline_comparison_performed': False,
        'paper_improvement_established': False,
        'precision': 'float64 mathematical reduction; not bitwise PyTorch float32 parity',
    })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-array', type=Path, required=True)
    parser.add_argument('--target-array', type=Path, required=True)
    parser.add_argument('--mask-array', type=Path, required=True)
    args = parser.parse_args()
    arrays = [np.load(p, mmap_mode='r', allow_pickle=False) for p in
              (args.output_array, args.target_array, args.mask_array)]
    if not all(isinstance(array, np.ndarray) for array in arrays):
        raise ValueError('inputs must be NPY arrays, not NPZ archives')
    print(json.dumps(score_source_panel(*arrays), allow_nan=False, sort_keys=True))


if __name__ == '__main__':
    main()
