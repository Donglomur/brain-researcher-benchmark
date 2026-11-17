#!/usr/bin/env python3
"""Freeze one offline candidate, then score it with the original NLB evaluator.

Only trusted operators may supply episode-policy pins or access target files.
These receipts report metrics and declared identities, never scientific success.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import tempfile

spec = importlib.util.spec_from_file_location('_smc_offline_policy', Path(__file__).with_name('policy.py'))
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
source = policy.load_source('scorer.py')
require = policy.require
TARGET_EXPOSURE = 'public_original_test_targets_released_2026_01'


def _episode(path, expected):
    policy.contracts()
    return policy.load_episode(path, expected, source.sha256(source.REFERENCE_PANEL))


def _delivery(manifest, episode, condition):
    require(manifest.get('schema') == 'smc_offline_participant_delivery_v1'
            and manifest.get('condition') == condition, 'wrong delivery schema/condition')
    require(manifest.get('task_id') == policy.TASK_ID, 'delivery task identity differs')
    require(manifest.get('primary_contract_sha256') == policy.PRIMARY_SHA256,
            'delivery primary contract differs')
    require(manifest.get('current_task_sha256') == episode['current_task_sha256'],
            'delivery current task identity differs')


def freeze_predictions(submission, panel, episode_path, episode_sha256,
                       delivery_manifest, destination, *, condition, method_id,
                       run_receipt_sha256, seed, behavior_guided_fitting,
                       behavior_guided_selection):
    """No target argument or target read is present in this interface."""
    episode = _episode(episode_path, episode_sha256)
    require(condition in policy.CONDITIONS, 'invalid delivery condition')
    require(isinstance(method_id, str) and 0 < len(method_id) <= 200, 'invalid method ID')
    require(type(seed) is int and seed >= 0, 'seed must be a nonnegative integer')
    require(type(behavior_guided_fitting) is bool and type(behavior_guided_selection) is bool,
            'behavior use must be explicitly declared')
    require(policy.digest(run_receipt_sha256), 'independent run receipt identity required')
    require(source.sha256(delivery_manifest) == episode['condition_manifest_sha256'][condition],
            'delivery does not match frozen condition')
    manifest = policy.read_json(delivery_manifest)
    _delivery(manifest, episode, condition)
    source.validate_submission(submission, policy.read_json(panel), require_author_arrays=False)
    record = {
        'schema': 'smc_nlb_offline_prediction_freeze_v1', 'task_id': policy.TASK_ID,
        'dataset': source.DATASET, 'role': 'ai_candidate', 'comparison_scope': 'original_offline_mc_maze_20ms',
        'created_utc': datetime.now(timezone.utc).isoformat(), 'condition': condition,
        'method_id': method_id, 'seed': seed, 'run_receipt_sha256': run_receipt_sha256,
        'behavior_guided_fitting': behavior_guided_fitting,
        'behavior_guided_selection': behavior_guided_selection,
        'submission_sha256': source.sha256(submission), 'panel_manifest_sha256': source.sha256(panel),
        'reference_panel_sha256': source.sha256(source.REFERENCE_PANEL),
        'primary_contract_sha256': policy.PRIMARY_SHA256,
        'current_task_sha256': episode['current_task_sha256'],
        'episode_policy_sha256': episode_sha256,
        'paired_delivery_sha256': episode['paired_delivery_sha256'],
        'delivery_manifest_sha256': source.sha256(delivery_manifest),
        'selected_reference_id': episode['selected_reference_id'],
        'target_exposure': TARGET_EXPOSURE,
        'scientific_outcome': 'unknown',
    }
    source.write_new_json(destination, record)
    return record


def validate_freeze(submission, panel, episode_path, episode_sha256, delivery_manifest, freeze_path):
    episode = _episode(episode_path, episode_sha256)
    freeze_bytes = Path(freeze_path).read_bytes()
    freeze_sha256 = hashlib.sha256(freeze_bytes).hexdigest()
    record = policy.loads_json(freeze_bytes)
    require(record.get('schema') == 'smc_nlb_offline_prediction_freeze_v1'
            and record.get('task_id') == policy.TASK_ID and record.get('dataset') == source.DATASET
            and record.get('role') == 'ai_candidate'
            and record.get('comparison_scope') == 'original_offline_mc_maze_20ms',
            'not a primary offline AI freeze; old source-arm/author receipts are distinct')
    require(record.get('scientific_outcome') == 'unknown' and 'arm' not in record,
            'an offline freeze cannot assert science or a source-arm claim')
    require(record.get('target_exposure') == TARGET_EXPOSURE,
            'frozen target exposure must retain the original public release')
    created = record.get('created_utc')
    require(isinstance(created, str) and 0 < len(created) <= 64, 'invalid freeze UTC timestamp')
    try:
        parsed = datetime.fromisoformat(created)
    except ValueError as error:
        raise ValueError('invalid freeze UTC timestamp') from error
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0,
            'freeze timestamp must explicitly use UTC')
    condition = record.get('condition')
    require(condition in policy.CONDITIONS, 'invalid frozen condition')
    require(type(record.get('seed')) is int and record['seed'] >= 0
            and isinstance(record.get('method_id'), str) and 0 < len(record['method_id']) <= 200,
            'invalid frozen candidate identity')
    require(policy.digest(record.get('run_receipt_sha256'))
            and type(record.get('behavior_guided_fitting')) is bool
            and type(record.get('behavior_guided_selection')) is bool, 'missing execution or behavior declaration')
    for key, path in (('submission_sha256', submission), ('panel_manifest_sha256', panel),
                      ('reference_panel_sha256', source.REFERENCE_PANEL), ('episode_policy_sha256', episode_path),
                      ('delivery_manifest_sha256', delivery_manifest)):
        require(record.get(key) == source.sha256(path), 'frozen content changed: ' + key)
    require(record['episode_policy_sha256'] == episode_sha256
            and record['primary_contract_sha256'] == policy.PRIMARY_SHA256
            and record.get('current_task_sha256') == episode['current_task_sha256']
            and record['paired_delivery_sha256'] == episode['paired_delivery_sha256']
            and record['selected_reference_id'] == episode['selected_reference_id']
            and record['delivery_manifest_sha256'] == episode['condition_manifest_sha256'][condition],
            'frozen policy/comparator/delivery binding changed')
    manifest = policy.read_json(delivery_manifest)
    _delivery(manifest, episode, condition)
    source.validate_submission(submission, policy.read_json(panel), require_author_arrays=False)
    return record, episode, freeze_sha256


def score_predictions(submission, panel, episode_path, episode_sha256, delivery_manifest,
                      freeze_path, target, target_sha256, scorer_source, destination):
    require(target_sha256 == source.TARGET_SHA256, 'target must be the pinned original exposed test release')
    record, episode, freeze_sha256 = validate_freeze(submission, panel, episode_path, episode_sha256, delivery_manifest, freeze_path)
    require(Path(target).resolve() != Path(submission).resolve()
            and Path(target).resolve().parent != Path(submission).resolve().parent,
            'operator targets must be separate from participant predictions')
    evaluator = source.load_original_scorer(scorer_source)
    with tempfile.TemporaryDirectory(prefix='smc-offline-operator-') as temporary:
        snapshot = Path(temporary) / 'submission.h5'
        shutil.copyfile(submission, snapshot)
        require(source.sha256(snapshot) == record['submission_sha256'], 'submission changed during snapshot')
        # No access to the target occurs above this line.
        require(source.sha256(target) == target_sha256, 'target bytes differ from the original exposed release')
        result = evaluator.evaluate(str(target), str(snapshot))
    require(source.sha256(freeze_path) == freeze_sha256, 'freeze receipt changed during scoring')
    require(isinstance(result, list) and len(result) == 1 and set(result[0]) == {source.DATASET + '_split'},
            'evaluator did not return the complete original panel')
    metrics = result[0][source.DATASET + '_split']
    require(set(metrics) == set(source.METRICS), 'original companion metric missing')
    metrics = {key: float(metrics[key]) for key in source.METRICS}
    require(all(math.isfinite(value) for value in metrics.values()), 'nonfinite source metric')
    selected = next(ref for ref in episode['references'] if ref['id'] == episode['selected_reference_id'])
    report = {
        'schema': 'smc_nlb_offline_operator_score_v1', 'task_id': policy.TASK_ID,
        'dataset': source.DATASET, 'role': 'ai_candidate', 'condition': record['condition'],
        'comparison_scope': record['comparison_scope'], 'metrics': metrics,
        'source_references': episode['references'], 'selected_reference': selected,
        'co_bps_difference_from_selected': metrics['co-bps'] - selected['co_bps'],
        'prediction_freeze_sha256': freeze_sha256,
        'submission_sha256': record['submission_sha256'],
        'panel_manifest_sha256': record['panel_manifest_sha256'],
        'reference_panel_sha256': record['reference_panel_sha256'],
        'primary_contract_sha256': policy.PRIMARY_SHA256, 'episode_policy_sha256': episode_sha256,
        'current_task_sha256': episode['current_task_sha256'],
        'scorer_sha256': source.SCORER_SHA256, 'target_sha256': target_sha256,
        'behavior_guided_fitting': record['behavior_guided_fitting'],
        'behavior_guided_selection': record['behavior_guided_selection'],
        'target_exposure': record['target_exposure'], 'scientific_outcome': 'unknown',
        'interpretation': 'Original offline metrics and declared provenance only. Trusted execution and source '
            'qualification require independent evidence. No reproduction, superiority, matched neural-only, '
            'causal/online or current-SOTA result is decided here.',
    }
    source.write_new_json(destination, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('freeze', 'score'):
        command = commands.add_parser(name)
        for argument in ('submission', 'panel', 'episode-policy', 'delivery-manifest', 'output'):
            command.add_argument('--' + argument, type=Path, required=True)
        command.add_argument('--episode-policy-sha256', required=True,
                             help='Trusted operator pin frozen before the candidate; never candidate-selected.')
        if name == 'freeze':
            command.add_argument('--condition', choices=policy.CONDITIONS, required=True)
            command.add_argument('--method-id', required=True)
            command.add_argument('--run-receipt-sha256', required=True)
            command.add_argument('--seed', type=int, required=True)
            command.add_argument('--behavior-guided-fitting', choices=('yes', 'no'), required=True)
            command.add_argument('--behavior-guided-selection', choices=('yes', 'no'), required=True)
        else:
            for argument in ('freeze', 'target', 'scorer-source'):
                command.add_argument('--' + argument, type=Path, required=True)
            command.add_argument('--target-sha256', required=True)
    args = parser.parse_args(argv)
    common = (args.submission, args.panel, args.episode_policy, args.episode_policy_sha256, args.delivery_manifest)
    if args.command == 'freeze':
        result = freeze_predictions(*common, args.output, condition=args.condition, method_id=args.method_id,
            run_receipt_sha256=args.run_receipt_sha256, seed=args.seed,
            behavior_guided_fitting=args.behavior_guided_fitting == 'yes',
            behavior_guided_selection=args.behavior_guided_selection == 'yes')
    else:
        result = score_predictions(*common, args.freeze, args.target, args.target_sha256, args.scorer_source, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
