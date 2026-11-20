"""Bounded-memory packaging of unchanged author particle means.

Upstream: mackelab/smc_rnns, Apache-2.0, c808c76ad940491b0a14d2671e3884140aa61258.
The original source remains intact and hash checked by author_predict.py.
"""
import inspect
import numpy as np


def patch_source(function_source):
    old = '.numpy()\n                    for '
    new = '.numpy().mean(axis=-1).transpose(0, 2, 1)\n                    for '
    if function_source.count(old) != 2:
        raise ValueError('Unexpected source inference structure')
    result = function_source.replace(old, new)
    for split, array in [('training', 'Xs_t'), ('eval', 'Xs_e')]:
        old = f'{split}_predictions_i = {array}.mean(axis=-1).transpose(0, 2, 1)'
        new = f'{split}_predictions_i = {array}'
        if result.count(old) != 1:
            raise ValueError('Unexpected source particle mean structure')
        result = result.replace(old, new)
    return result


def bounded_eval_nlb(original_function):
    namespace = original_function.__globals__.copy()
    exec(compile(patch_source(inspect.getsource(original_function)),
                 '<source-equivalent-particle-reduction>', 'exec'), namespace)
    return namespace[original_function.__name__]


def verify_reduction(chunks):
    """Exact array comparison, no RNG calls; use only during bounded controls."""
    original = np.concatenate(chunks).mean(axis=-1).transpose(0, 2, 1)
    bounded = np.concatenate([x.mean(axis=-1).transpose(0, 2, 1) for x in chunks])
    same = original.dtype == bounded.dtype and np.ascontiguousarray(original).tobytes() == np.ascontiguousarray(bounded).tobytes()
    difference = float(np.max(np.abs(original-bounded)))
    if not same:
        raise ValueError(f'Particle reduction differs: {difference}')
    return {'bitwise_equal': same, 'maximum_absolute_difference': difference,
            'dtype': str(original.dtype), 'output_shape': list(original.shape),
            'input_chunk_shapes': [list(x.shape) for x in chunks]}
