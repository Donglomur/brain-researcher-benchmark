"""Optional, unselected actor ABI example; not a result or qualification control.

This simple Laplace prior ignores features and uses calibration training labels.
It is not an improvement method and must not be silently selected for either arm.
F preserves this exact mounted source; I can use the same interface but its
investigation policy must be independently specified and frozen before exposure.
"""
import json
from pathlib import Path


def fit(calibration, tools):
    rows = calibration['train']
    if not rows or any(type(row.get('y')) is not int or row['y'] not in (0, 1)
                       for row in rows):
        raise ValueError('complete binary-labeled training calibration required')
    p = (1 + sum(row['y'] for row in rows)) / (2 + len(rows))
    # worker.__file__ is deliberately a captured-source sentinel. This is the
    # actual immutable source mount supplied by the owner during fit.
    source = Path('/input/policy.py').read_bytes()
    return {'source_body': source,
            'config_body': b'{"method":"unselected_Laplace_prior_ABI_example"}\n',
            'state_body': (json.dumps({'p': p}, allow_nan=False) + '\n').encode()}


def predict(view, config_body, state_body, tools):
    if 'y' in view:
        raise ValueError('query labels are not candidate inputs')
    return json.loads(state_body)['p']
