"""Additive paired-participant bootstrap for an authenticated full32 result.

This sidecar reads completed evaluator summaries, never private labels, EEG or
participant code. It checks summary consistency; it does not independently prove
the upstream capture or evaluator execution. The caller must freeze the runtime
and the expected result/policy identities before execution. No significance,
pass/fail, readiness or representative-population inference is supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import stat


CONDITIONS = ('numeric_direct_four_demo', 'numeric_program_four_demo')
PEOPLE = ('sub-008', 'sub-009') + tuple(f'sub-{i:03d}' for i in range(11, 41))
METRICS = (
    'direct_minus_program_macro_balanced_accuracy',
    'direct_minus_program_macro_natural_log_loss',
    'numeric_direct_four_demo.participant_macro_balanced_accuracy',
    'numeric_program_four_demo.participant_macro_balanced_accuracy',
    'numeric_direct_four_demo.participant_macro_natural_log_loss',
    'numeric_program_four_demo.participant_macro_natural_log_loss',
)
POLICY = {
    'schema': 'erp-full32-paired-bootstrap-policy-v1',
    'original_condition_protocol_sha256': '170a32bfb9778f0f2d96affe166f78b2f1e8362bfdaebea36a23b91755c4aa02',
    'completion_scope': 'Prospective implementation conventions; original condition protocol and evaluator remain unchanged.',
    'participants': 32,
    'draw_size': 32,
    'resamples': 10000,
    'sampling_unit': 'participant_cluster',
    'sampling_with_replacement': True,
    'shared_draws_across_arms_and_metrics': True,
    'rng': 'NumPy.Generator(PCG64)',
    'seed': 20261119,
    'index_dtype': 'int64',
    'confidence_level': 0.95,
    'interval_family': 'percentile',
    'quantile_method': 'linear',
    'quantile_probabilities': [0.025, 0.975],
    'primary_interval': 'direct_minus_program_macro_balanced_accuracy',
    'secondary_unadjusted_intervals': [
        'direct_minus_program_macro_natural_log_loss',
        'numeric_direct_four_demo.participant_macro_balanced_accuracy',
        'numeric_program_four_demo.participant_macro_balanced_accuracy',
        'numeric_direct_four_demo.participant_macro_natural_log_loss',
        'numeric_program_four_demo.participant_macro_natural_log_loss',
    ],
    'missingness': 'Refuse incomplete, duplicate, foreign or reordered participant rows; no omission, imputation or subset.',
    'scope': 'Finite public cohort summary; not representative-population inference.',
    'significance_or_pass_threshold': None,
}
INPUT_CAP = 262144


VISUAL_PROFILE = 'erp-full32-visual-v1'
VISUAL_CONDITIONS = ('visual_direct_four_demo', 'visual_program_four_demo')


def conditions_for(profile='numeric'):
    need(profile in ('numeric', VISUAL_PROFILE), 'Explicit numeric or visual summary profile')
    return VISUAL_CONDITIONS if profile == VISUAL_PROFILE else CONDITIONS


def metrics_for(profile='numeric'):
    conditions = conditions_for(profile)
    return (METRICS[:2] + tuple(condition + '.participant_macro_' + metric
            for metric in ('balanced_accuracy','natural_log_loss') for condition in conditions))


def policy_for(profile='numeric'):
    conditions_for(profile)
    if profile == 'numeric':
        return dict(POLICY)
    # Only condition/schema plumbing changes. The sampling unit, draws, RNG,
    # seed, quantiles, orientations and missingness rule are identical.
    result = dict(POLICY)
    result.update(profile=VISUAL_PROFILE,
                  completion_scope='Explicit visual condition names; unchanged frozen full32 participant bootstrap algorithm.',
                  secondary_unadjusted_intervals=list(metrics_for(profile)[1:]))
    return result


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def decode(body):
    def unique(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def descriptor(value, cap=INPUT_CAP):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
         type(value['bytes']) is int and 0 < value['bytes'] <= cap and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'Exact bounded byte/hash descriptor required')


def finite_number(value, message):
    need(type(value) in (int, float) and math.isfinite(value), message)
    return float(value)


def validate_result(result, *, profile='numeric'):
    """Extract six paired vectors from an explicitly selected completed profile."""
    conditions = conditions_for(profile); metrics = metrics_for(profile)
    need(type(result) is dict and result.get('schema') == 'erp-full32-protected-pair-evaluation-v1' and
         result.get('status') == 'complete_finite_cohort_pair' and
         type(result.get('people')) is int and result['people'] == 32 and
         type(result.get('queries')) is int and result['queries'] == 6400 and
         result.get('both_public_arms_and_owned_closures_validated_before_private') is True and
         type(result.get('new_benchmarks')) is int and result['new_benchmarks'] == 0,
         'Complete previously validated full32 evaluator result required')
    if profile == VISUAL_PROFILE:
        need(result.get('profile') == VISUAL_PROFILE and result.get('conditions') == list(VISUAL_CONDITIONS)
             and result.get('operator_route') == 'full32_visual_provider_vs_frozen_image_programme_v1'
             and type(result.get('profile_commitment')) is str
             and re.fullmatch('[0-9a-f]{64}', result['profile_commitment']), 'Explicit visual upstream condition and display commitment')
    descriptor(result.get('contract'), 2*1024**2 if profile == VISUAL_PROFILE else 65536)
    arms = result.get('public_arm_receipts')
    need(type(arms) is list and len(arms) == 2, 'Both committed public arm receipts required')
    for arm in arms:
        descriptor(arm, 4 * 1024**2)
    scores = result.get('scores')
    need(type(scores) is dict and set(scores) == set(conditions), 'Exact paired selected conditions required')
    vectors = {}
    row_keys = {'participant_id', 'trials', 'targets', 'standards', 'target_true_positive',
                'standard_true_negative', 'balanced_accuracy', 'natural_log_loss'}
    for condition in conditions:
        score = scores[condition]
        need(type(score) is dict and set(score) == {'participants', 'participant_macro_balanced_accuracy',
                                                 'participant_macro_natural_log_loss'}, 'Exact evaluator score fields')
        rows = score['participants']
        need(type(rows) is list and len(rows) == 32, 'All32 participant rows required')
        ba, loss = [], []
        for person, row in zip(PEOPLE, rows, strict=True):
            need(type(row) is dict and set(row) == row_keys and row['participant_id'] == person,
                 'Exact ordered full32 participant pairing required')
            need(all(type(row[k]) is int for k in ('trials', 'targets', 'standards', 'target_true_positive', 'standard_true_negative')) and
                 row['trials'] == 200 and row['targets'] == 40 and row['standards'] == 160 and
                 0 <= row['target_true_positive'] <= 40 and 0 <= row['standard_true_negative'] <= 160,
                 'Fixed200/40/160 per-participant class support required')
            accuracy = finite_number(row['balanced_accuracy'], 'Finite nonboolean balanced accuracy')
            expected = .5 * (row['target_true_positive'] / 40 + row['standard_true_negative'] / 160)
            need(accuracy == expected, 'Balanced accuracy must match retained class-confusion counts')
            log_loss = finite_number(row['natural_log_loss'], 'Finite nonboolean natural log loss')
            need(log_loss >= 0, 'Natural log loss cannot be negative')
            ba.append(accuracy); loss.append(log_loss)
        for suffix, values in [('balanced_accuracy', ba), ('natural_log_loss', loss)]:
            observed = finite_number(score['participant_macro_' + suffix], 'Finite participant macro metric')
            need(observed == sum(values) / 32, 'Participant macro must weight each of32 people equally')
            vectors[condition + '.participant_macro_' + suffix] = values
    differences = result.get('paired_person_differences')
    need(type(differences) is list and len(differences) == 32, 'All32 paired person differences required')
    for metric in ('balanced_accuracy', 'natural_log_loss'):
        values = [a - b for a, b in zip(vectors[conditions[0] + '.participant_macro_' + metric],
                                        vectors[conditions[1] + '.participant_macro_' + metric], strict=True)]
        vectors['direct_minus_program_macro_' + metric] = values
    for index, (person, row) in enumerate(zip(PEOPLE, differences, strict=True)):
        need(type(row) is dict and set(row) == {'participant_id', 'direct_minus_program_balanced_accuracy',
                                               'direct_minus_program_natural_log_loss'} and row['participant_id'] == person,
             'Exact ordered paired-difference rows required')
        for metric in ('balanced_accuracy', 'natural_log_loss'):
            observed = finite_number(row['direct_minus_program_' + metric], 'Finite paired difference')
            need(observed == vectors['direct_minus_program_macro_' + metric][index],
                 'Paired difference must preserve direct-minus-program orientation')
    primary = finite_number(result.get('primary_direct_minus_program_macro_BA'), 'Finite primary contrast')
    need(primary == sum(vectors[metrics[0]]) / 32, 'Primary paired participant mean differs')
    return vectors


def paired_bootstrap(result, policy, *, expected_python_version, expected_numpy_version, profile='numeric'):
    """Pure numerical sidecar: fixed local RNG, no files, targets or candidates."""
    selected_policy = policy_for(profile); metrics = metrics_for(profile)
    need(type(policy) is dict and encode(policy) == encode(selected_policy), 'Exact versioned prospective bootstrap policy required')
    need(type(expected_python_version) is str and type(expected_numpy_version) is str and
         re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', expected_python_version) and
         re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', expected_numpy_version), 'Explicit frozen runtime versions required')
    need(platform.python_version() == expected_python_version, 'Python version differs from frozen runtime')
    vectors = validate_result(result, profile=profile)
    # Import the numerical runtime only after policy/input admission. The outer
    # operator authenticates its installation; this function checks versions.
    import numpy as np
    need(np.__version__ == expected_numpy_version, 'NumPy version differs from frozen runtime')
    matrix = np.asarray([vectors[name] for name in metrics], dtype=np.float64).T
    generator = np.random.Generator(np.random.PCG64(POLICY['seed']))
    indices = generator.integers(0, 32, size=(10000, 32), dtype=np.int64, endpoint=False)
    # One index array is reused for both arms, both metrics and both contrasts.
    means = matrix[indices].mean(axis=1, dtype=np.float64)
    limits = np.quantile(means, [0.025, 0.975], axis=0, method='linear')
    intervals = {}
    for column, name in enumerate(metrics):
        intervals[name] = {'point_estimate': sum(vectors[name]) / 32,
                           'lower': float(limits[0, column]), 'upper': float(limits[1, column]),
                           'role': 'primary' if column == 0 else 'secondary_unadjusted'}
    # Canonical draw fingerprint supports reproducibility without publishing a
    # large replicate array; it contains indices into fixed ordered PEOPLE only.
    draw_body = indices.astype('<i8', copy=False).tobytes(order='C')
    return {'schema': 'erp-full32-paired-participant-bootstrap-v1',
            'status': 'additive_finite_cohort_summary', 'policy': dict(selected_policy),
            'people': 32, 'queries': 6400,
            **({'profile': profile, 'conditions': list(VISUAL_CONDITIONS)} if profile == VISUAL_PROFILE else {}),
            'intervals': intervals,
            'draws': {'shape': [10000, 32], 'encoding': 'C-order signed little-endian int64', **pin(draw_body)},
            'runtime_versions': {'python': platform.python_version(), 'numpy': np.__version__},
            'runtime_installation_identity_is_outer_operator_responsibility': True,
            'upstream_contract': dict(result['contract']),
            'upstream_public_arm_receipts': [dict(row) for row in result['public_arm_receipts']],
            'private_targets_read': 0, 'trial_resampling': False, 'new_benchmarks': 0,
            'multiple_comparisons_adjusted': False,
            'interpretation': POLICY['scope'],
            'qualification': 'Summary of a separately authenticated completed evaluator result; no new capture, provider, waveform, model or population qualification.'}


def ordinary_path(path):
    path = Path(path).absolute()
    need(all(not item.is_symlink() for item in (path, *path.parents)), 'Symlink path refused')
    return path


def read_pinned(path, expected):
    descriptor(expected)
    path = ordinary_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected['bytes'],
             'Exact ordinary singly-linked input required')
        body = stream.read(INPUT_CAP + 1)
        after = os.fstat(stream.fileno())
    fields = lambda row: (row.st_dev, row.st_ino, row.st_size, row.st_mtime_ns, row.st_ctime_ns, row.st_nlink)
    need(fields(before) == fields(after) == fields(path.lstat()) and pin(body) == expected,
         'Input changed or byte/hash commitment differs')
    return body


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('numeric', VISUAL_PROFILE), default='numeric')
    for name in ('result', 'policy'):
        parser.add_argument('--' + name, type=Path, required=True)
        parser.add_argument('--' + name + '-bytes', type=int, required=True)
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--python-version', required=True)
    parser.add_argument('--numpy-version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    identities = {name: {'bytes': getattr(args, name + '_bytes'), 'sha256': getattr(args, name + '_sha256')}
                  for name in ('result', 'policy')}
    policy = decode(read_pinned(args.policy, identities['policy']))
    need(type(policy) is dict and encode(policy) == encode(policy_for(args.profile)), 'Exact versioned prospective bootstrap policy required')
    result = decode(read_pinned(args.result, identities['result']))
    output = paired_bootstrap(result, policy, expected_python_version=args.python_version,
                              expected_numpy_version=args.numpy_version, profile=args.profile)
    output['input_result'] = identities['result']
    output['input_policy'] = identities['policy']
    body = encode(output)
    need(len(body) <= INPUT_CAP, 'Bounded additive summary output')
    path = ordinary_path(args.output)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({'status': output['status'], 'people': 32, 'resamples': 10000,
                      'new_benchmarks': 0, 'output': pin(body)}, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
