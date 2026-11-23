"""Validate a NEURAL-020 submission against its public query packet only.

This performs no scoring, fits, private-target reads or authenticity adjudication.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
EVALUATOR_SHA256 = '4a6263059ca21aadfeec97bf405ba4f8a454da6a1d92d7f205cb468a25916d23'
QUERY_FIELDS = ('trial_ids', 'heldin_unit_ids', 'heldout_unit_ids',
                'bin_left_edges_ms', 'prediction_units', 'packet_sha256',
                'visible_counts')
SUBMISSION_FIELDS = ('trial_ids', 'heldout_unit_ids', 'bin_left_edges_ms',
                     'packet_sha256', 'prediction_units', 'expected_counts')


def evaluator():
    """Reuse the unchanged source validator; never invoke its private scorer."""
    path = HERE / 'evaluator.py'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EVALUATOR_SHA256:
        raise ValueError('predecessor evaluator source changed')
    spec = importlib.util.spec_from_loader('neural020_preflight_evaluator', loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def validate_submission(query, submission):
    """Check complete public geometry and finite nonnegative expected counts.

    The packet digest is a declared identity, not proof that the supplied query
    came from the source recording. Hidden count coverage and condition labels
    can only be checked by the operator's separate private scoring route.
    """
    e = evaluator()
    e.exact_keys(query, QUERY_FIELDS, 'public query')
    e.exact_keys(submission, SUBMISSION_FIELDS, 'submission')
    trials = e.unique_ids(np.asarray(query['trial_ids']).tolist(), 'query trial IDs')
    heldin = e.unique_ids(np.asarray(query['heldin_unit_ids']).tolist(), 'heldin unit IDs')
    heldout = e.unique_ids(np.asarray(query['heldout_unit_ids']).tolist(), 'heldout unit IDs')
    e.require(2 <= len(trials) <= e.SOURCE_TRIALS, 'complete nonempty query trial axis required')
    e.require(heldin and heldout and len(heldin) + len(heldout) == e.SOURCE_UNITS
              and not set(heldin).intersection(heldout), 'complete disjoint 65-unit query axes required')
    bins = np.asarray(query['bin_left_edges_ms'])
    e.require(bins.ndim == 1 and bins.dtype.kind in 'iu' and
              any(np.array_equal(bins, np.arange(-100, 500, width)) for width in (5, 20)),
              'query bin grid differs from Area2 window')
    identity = np.asarray(query['packet_sha256'])
    e.require(identity.shape == () and isinstance(identity.item(), str) and
              len(identity.item()) == 64 and all(x in '0123456789abcdef' for x in identity.item()),
              'query packet fingerprint invalid')
    for name, packet in (('query', query), ('submission', submission)):
        units = np.asarray(packet['prediction_units'])
        e.require(units.shape == () and units.item() == 'spikes_per_bin',
                  name + ': explicit spikes_per_bin predictions required')
    visible = e.counts_array(query['visible_counts'], 'visible query counts')
    e.require(visible.shape == (len(trials), len(bins), len(heldin)),
              'visible query tensor geometry differs')
    for field in ('trial_ids', 'heldout_unit_ids', 'bin_left_edges_ms', 'packet_sha256'):
        e.require(np.array_equal(np.asarray(query[field]), np.asarray(submission[field])),
                  field + ': identity/order mismatch')
    prediction = e.real_array(submission['expected_counts'], 'expected counts')
    e.require(prediction.shape == (len(trials), len(bins), len(heldout)),
              'expected-count tensor geometry differs')
    e.require(np.isfinite(prediction).all() and np.all(prediction >= 0),
              'predictions must be finite and nonnegative, including unscored cells')
    return {
        'task_id': e.TASK_ID, 'status': 'public_submission_preflight_passed',
        'declared_packet_sha256': identity.item(),
        'evaluation_trials': len(trials), 'time_bins': len(bins),
        'heldin_units': len(heldin), 'heldout_units': len(heldout),
        'prediction_units': 'spikes_per_bin',
        'private_targets_read': False, 'score_computed': False,
        'source_authenticity_verified': False, 'private_coverage_verified': False,
        'research_qualified': False, 'submission_ready': False,
        'limits': 'Public shape, values and declared identities only; private condition/target coverage and source authenticity remain operator responsibilities.',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', required=True, help='public_query.npz only')
    parser.add_argument('--submission', required=True, help='predictions.npz')
    parser.add_argument('--output', required=True, help='new JSON preflight result')
    args = parser.parse_args(argv)
    e = evaluator()
    result = validate_submission(e.load_npz(args.query), e.load_npz(args.submission))
    with Path(args.output).open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
