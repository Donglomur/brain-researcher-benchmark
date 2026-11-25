"""Compare two complete NEURAL-021 visual sessions using one target capture.

Operator source and descriptive scoring only. A paired packet and replay do not
establish participant identity, no-tools enforcement, equal exposure or compute.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
GRADE_PIN = {'bytes': 13823,
             'sha256': '5b3a4f212a8b8d43bffb399fc7e83d4dc6ffe751baa174a0b459ec65f42109c2'}
MODES = ('direct_observation', 'typed_viewer')
MAX_TARGET = 1024**2
MAX_RESULT = 256 * 1024


def need(value, message):
    if not value:
        raise ValueError(message)


def load_grade(implementations_root=None):
    """Load exact existing grader bytes, then its unchanged source dependencies."""
    root = Path(implementations_root) if implementations_root is not None else HERE.parent
    path = (root / 'observation-grade-v1/grade.py').absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)),
         'ordinary original grader source required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
             and info.st_size == GRADE_PIN['bytes'], 'exact original grader extent required')
        body = stream.read(GRADE_PIN['bytes'] + 1)
    need(len(body) == GRADE_PIN['bytes']
         and hashlib.sha256(body).hexdigest() == GRADE_PIN['sha256'],
         'original grader source changed')
    grade = types.ModuleType('_neural021_paired_original_grade')
    grade.__file__ = str(path)
    exec(compile(body, str(path), 'exec'), grade.__dict__)
    return grade, grade.load_sources()


def _difference(viewer, direct):
    return None if viewer is None or direct is None else viewer - direct


def _exposure(grade, receipt_bytes):
    # Called only after complete original replay has authenticated every event.
    events = grade.json.loads(receipt_bytes)['events']
    training = [row['training_index'] for row in events if row['operation'] == 'training_view']
    query_views = [row for row in events if row['operation'] == 'query_view']
    return {
        'calibration_indices_in_view_order': training,
        'calibration_views': len(training),
        'distinct_calibration_trials_viewed': len(set(training)),
        'query_views': len(query_views),
        'cropped_query_views': sum(bool(row['viewport']) for row in query_views),
    }


def compare(grade, sources, packet, arms, load_private_targets):
    """Replay both arms before opening gold, then score the captured gold twice.

    The trusted caller supplies one original Packet and two {submission, receipt}
    byte records keyed by the exact modes. No participant-facing filesystem,
    target loader or callable is provided by this component.
    """
    need(type(arms) is dict and set(arms) == set(MODES), 'both exact visual arms required')
    need(callable(load_private_targets), 'operator target callback required')
    for mode in MODES:
        need(type(arms[mode]) is dict and set(arms[mode]) == {'submission', 'receipt'}
             and all(type(body) is bytes for body in arms[mode].values()),
             'exact immutable submission and receipt bytes required')
    # A target callback must not be able to replace the caller's arm mappings
    # between replay and scoring. Hold our own references to the four byte values.
    arms = {mode: dict(arms[mode]) for mode in MODES}
    replays = {
        mode: grade.replay(sources, packet, mode, arms[mode]['submission'], arms[mode]['receipt'])
        for mode in MODES
    }
    # Both complete public/observation replays have succeeded before this call.
    # Serialization snapshots the returned target generation once; each unchanged
    # scorer receives a fresh object parsed from those same captured bytes.
    target_bytes = grade.encode(load_private_targets())
    need(len(target_bytes) <= MAX_TARGET, 'bounded complete target generation required')
    scores = {
        mode: sources['scorer'].score(
            arms[mode]['submission'], packet.cases_bytes,
            lambda: sources['interface'].strict_json(target_bytes), sources['interface'])
        for mode in MODES
    }
    exposures = {mode: _exposure(grade, arms[mode]['receipt']) for mode in MODES}
    direct, viewer = (scores[mode] for mode in MODES)
    differences = {}
    for condition in ('active', 'passive'):
        a, b = direct['conditions'][condition], viewer['conditions'][condition]
        differences[condition] = {
            'trials': a['trials'], 'trajectory_rows': a['trajectory_rows'],
            'r2_variance_weighted': _difference(b['r2_variance_weighted'], a['r2_variance_weighted']),
            'axis_r2': [_difference(v, d) for v, d in zip(b['axis_r2'], a['axis_r2'])],
            'squared_euclidean_loss_m2_s2': _difference(
                b['squared_euclidean_loss_m2_s2'], a['squared_euclidean_loss_m2_s2']),
        }
    return {
        'schema': 'neural021_paired_observation_grade_v1', 'task_id': 'NEURAL-021',
        'status': 'complete_paired_source_replay_and_descriptive_grade',
        'queries_per_arm': 92, 'calibration_trials_available_per_arm': 272,
        'cases_sha256': packet.cases_sha256, 'observation_sha256': packet.observation_sha256,
        'replays': replays, 'scores': scores, 'exposures': exposures,
        'same_calibration_view_sequence':
            exposures[MODES[0]]['calibration_indices_in_view_order']
            == exposures[MODES[1]]['calibration_indices_in_view_order'],
        'viewer_minus_direct': {
            'conditions': differences,
            'mean_condition_r2': _difference(viewer['mean_condition_r2'], direct['mean_condition_r2']),
        },
        'difference_direction': 'typed_viewer minus direct_observation; positive R2 and negative loss favor viewer',
        'private_target_callbacks': 1, 'unchanged_original_scorer_calls': 2,
        'source': {'grader': GRADE_PIN, 'dependencies': grade.SOURCES},
        'runtime_qualified': False, 'scientific_qualified': False, 'submission_ready': False,
        'binary_success_threshold': None,
        'scope': 'Descriptive pairing on the same full one-session retrospective endpoint. '
                 'Calibration availability does not establish equal viewed exposure or compute; '
                 'matching calibration sequences does not match their timing relative to queries. '
                 'No independent-trial significance, causal tool benefit, participant identity, '
                 'no-tools isolation, native understanding, generalization or SOTA claim.',
    }


def operator_compare(public_root, arms, target_path, output_path, *, implementations_root=None):
    """Fixed original input generation; operator-selected frozen arm artifacts."""
    grade, sources = load_grade(implementations_root)
    public_root = grade.ordinary_path(public_root)
    target_path, output_path = grade.ordinary_path(target_path), grade.ordinary_path(output_path)
    need(public_root.is_dir() and output_path.parent.is_dir() and not os.path.lexists(output_path),
         'existing public directory and fresh operator output required')
    need(type(arms) is dict and set(arms) == set(MODES), 'both exact visual arms required')
    paths, normalized = [target_path, output_path], {}
    for mode in MODES:
        need(type(arms[mode]) is dict and set(arms[mode]) == {'submission', 'receipt'},
             'exact operator arm descriptors required')
        normalized[mode] = {}
        for role in ('submission', 'receipt'):
            descriptor = arms[mode][role]
            need(type(descriptor) is dict and set(descriptor) == {'path', 'pin'},
                 'exact operator artifact path and identity required')
            path = grade.ordinary_path(descriptor['path'])
            paths.append(path)
            normalized[mode][role] = (path, descriptor['pin'])
    need(len(set(paths)) == 6
         and all(not path.is_relative_to(public_root) for path in paths)
         and all(not path.is_relative_to(grade.IMPLEMENTATIONS) for path in paths),
         'separate arm artifacts, protected target and source/public trees required')
    # Authenticate all four public artifacts before loading observations or gold.
    captured = {mode: {role: grade.capture(path, expected, grade.MAX_JSON)
                       for role, (path, expected) in normalized[mode].items()} for mode in MODES}
    import numpy as np  # Existing original public-packet dependency only.
    packet = sources['delivery'].load_public(public_root, np)
    def targets():
        return sources['interface'].strict_json(grade.capture(target_path, grade.TARGET_PIN, MAX_TARGET))
    result = compare(grade, sources, packet, captured, targets)
    result['authenticated_input_generation'] = {'public': grade.PUBLIC_PINS, 'private_targets': grade.TARGET_PIN}
    body = grade.encode(result)
    need(len(body) <= MAX_RESULT, 'bounded complete paired result required')
    with output_path.open('xb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-root', required=True)
    parser.add_argument('--private-targets', required=True)
    parser.add_argument('--output', required=True)
    for prefix in ('direct', 'viewer'):
        for role in ('submission', 'receipt'):
            parser.add_argument(f'--{prefix}-{role}', required=True)
            parser.add_argument(f'--{prefix}-{role}-bytes', type=int, required=True)
            parser.add_argument(f'--{prefix}-{role}-sha256', required=True)
    args = parser.parse_args(argv)
    arms = {mode: {role: {'path': getattr(args, f'{prefix}_{role}'),
                         'pin': {'bytes': getattr(args, f'{prefix}_{role}_bytes'),
                                 'sha256': getattr(args, f'{prefix}_{role}_sha256')}}
                   for role in ('submission', 'receipt')}
            for mode, prefix in zip(MODES, ('direct', 'viewer'))}
    try:
        result = operator_compare(args.public_root, arms, args.private_targets, args.output)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'failed_paired_observation_grade',
                          'error_type': type(error).__name__, 'complete_grade': False,
                          'automatic_retry': False}), file=sys.stderr)
        return 2
    print(json.dumps({'status': result['status'], 'queries_per_arm': result['queries_per_arm']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
