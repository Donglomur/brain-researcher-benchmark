#!/usr/bin/env python3
"""Freeze both AI source-method predictions, then evaluate all eight findings.

The trusted operator supplies policy and execution pins. Hashes authenticate bytes,
not the scientific truth of their declarations. This is a cooperative evaluation
boundary, not an execution sandbox or a reproduction-success decision.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import tempfile

HERE = Path(__file__).resolve().parent
TASK = HERE.parent.parent
RETAINED = HERE.parent / 'source-matched-nlb-v1'
TASK_ID = 'PAPER-SMC-RNN-2024'
ARMS = ('causal', 'noncausal')
CONDITIONS = ('paper_data', 'paper_data_author_code')
EXPOSURE = 'public_original_test_targets_released_2026_01'
MAX_JSON_BYTES = 1024 * 1024
MAX_PREDICTION_BYTES = 512 * 1024 * 1024
MAX_TARGET_BYTES = 256 * 1024 * 1024
SOURCE_PINS = {
    'scorer.py': '48638a595755138b32ff9c228804fd8c19c9ff874cd254f135fc5245ee9a25f8',
    'reference_panel.json': '209a15e2189499a9e68264df5c9f81057dd919564d98a46fb64d75b3f39af2f3',
    'protocol.json': 'c8d437ece9c57b9066c5167ad499eada673d425ea17a06a9a20d62410ecbd644',
}
REPRODUCTION_SHA256 = 'd616c5c185d9affe390e9818a534d84071b4ae5f54e3cd407edcb777a1161856'
PRIMARY_SHA256 = '5f9aac50d4550908d0cca1ccc704d08e1d423f337ed4cf66a65963617171894d'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return isinstance(value, str) and len(value) == 64 and all(x in '0123456789abcdef' for x in value)


def _open_file(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        observed = os.fstat(fd)
        require(stat.S_ISREG(observed.st_mode), 'input must be an ordinary file')
        require(0 < observed.st_size <= limit, 'input exceeds its byte bound or is empty')
        return os.fdopen(fd, 'rb'), observed
    except BaseException:
        os.close(fd)
        raise


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def hash_file(path, limit=MAX_JSON_BYTES):
    handle, initial = _open_file(path, limit)
    result = hashlib.sha256()
    total = 0
    with handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            total += len(block)
            require(total <= limit, 'input grew beyond its byte bound')
            result.update(block)
        require(total == initial.st_size and _identity(initial) == _identity(os.fstat(handle.fileno())),
                'input changed during hashing')
    require(_identity(initial) == _identity(os.stat(path, follow_symlinks=False)),
            'input path changed during hashing')
    return result.hexdigest()


def read_json(path, expected=None):
    handle, initial = _open_file(path, MAX_JSON_BYTES)
    with handle:
        data = handle.read(MAX_JSON_BYTES + 1)
        require(len(data) <= MAX_JSON_BYTES and len(data) == initial.st_size
                and _identity(initial) == _identity(os.fstat(handle.fileno())), 'metadata changed or exceeded limit')
    require(_identity(initial) == _identity(os.stat(path, follow_symlinks=False)), 'metadata path changed')
    actual = hashlib.sha256(data).hexdigest()
    if expected is not None:
        require(digest(expected) and actual == expected, 'metadata differs from trusted frozen identity')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON number: ' + value)
    document = json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)
    require(isinstance(document, dict), 'metadata must be an object')
    return document, actual


def write_new_json(path, document):
    data = (json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    require(len(data) <= MAX_JSON_BYTES, 'output metadata exceeds byte bound')
    path = Path(path)
    # Complete bytes first, then atomically install without replacing a prior result.
    with tempfile.TemporaryDirectory(prefix='.smc-reproduction-result-', dir=path.parent) as temporary:
        staged = Path(temporary) / 'result.json'
        with staged.open('xb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(staged, path)


def verify_sources():
    for name, expected in SOURCE_PINS.items():
        require(hash_file(RETAINED / name) == expected, 'retained source changed: ' + name)
    require(hash_file(TASK / 'reproduction.v1.json') == REPRODUCTION_SHA256,
            'reproduction contract changed')


verify_sources()
_spec = importlib.util.spec_from_file_location('_smc_reproduction_retained_scorer', RETAINED / 'scorer.py')
source = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(source)


def validate_policy(document):
    fields = {'schema', 'task_id', 'outcome', 'current_task_sha256', 'reproduction_contract_sha256',
        'reference_panel_sha256', 'author_protocol_sha256', 'paired_delivery_sha256',
        'condition_manifest_sha256', 'materials_policy_sha256', 'selection_adaptation_policy_sha256',
        'resource_budget_policy_sha256', 'source_identity_review_sha256', 'agreement_policy_sha256',
        'uncertainty_policy_sha256', 'trusted_operator_review_sha256'}
    require(set(document) == fields, 'reproduction policy fields differ')
    require(document['schema'] == 'smc_paired_reproduction_policy_v1'
            and document['task_id'] == TASK_ID and document['outcome'] == 'reproduction',
            'wrong reproduction policy role or task')
    for field in fields - {'schema', 'task_id', 'outcome', 'condition_manifest_sha256'}:
        require(digest(document[field]), 'missing policy identity: ' + field)
    require(document['reproduction_contract_sha256'] == REPRODUCTION_SHA256
            and document['reference_panel_sha256'] == SOURCE_PINS['reference_panel.json']
            and document['author_protocol_sha256'] == SOURCE_PINS['protocol.json'],
            'wrong reproduction contract, complete panel or original recipe')
    manifests = document['condition_manifest_sha256']
    require(isinstance(manifests, dict) and set(manifests) == set(CONDITIONS)
            and all(digest(value) for value in manifests.values()), 'both access conditions must be frozen')


def validate_executions(document, episode_sha256, condition):
    fields = {'schema', 'task_id', 'outcome', 'condition', 'episode_policy_sha256', 'method_id', 'arms'}
    require(set(document) == fields and document.get('schema') == 'smc_ai_reproduction_execution_v1'
            and document.get('task_id') == TASK_ID and document.get('outcome') == 'reproduction',
            'not an AI reproduction execution record; calibration and improvement are separate')
    require(document['condition'] == condition and document['episode_policy_sha256'] == episode_sha256,
            'execution condition or policy differs')
    require(isinstance(document['method_id'], str) and 0 < len(document['method_id']) <= 200,
            'invalid participant method ID')
    require(isinstance(document['arms'], dict) and set(document['arms']) == set(ARMS),
            'both source-method executions required')
    fields = {'role', 'source_arm', 'submission_sha256', 'analysis_source_sha256', 'run_receipt_sha256',
        'source_method_review_sha256', 'granular_output_review_sha256', 'seed',
        'particles', 'repeats', 'smooth', 'behavior_guided_fitting', 'behavior_guided_selection'}
    for arm in ARMS:
        row = document['arms'][arm]
        require(isinstance(row, dict) and set(row) == fields and row['role'] == 'ai_reproduction'
                and row['source_arm'] == arm, 'wrong source-method execution fields or role')
        for key in fields:
            if key.endswith('_sha256'):
                require(digest(row[key]), 'missing execution evidence: ' + key)
        require(type(row['seed']) is int and row['seed'] >= 0, 'invalid execution seed')
        require(type(row['particles']) is int and row['particles'] == 192
                and type(row['repeats']) is int and row['repeats'] == 32 and row['smooth'] is False,
                'original source inference recipe must be preserved')
        require(type(row['behavior_guided_fitting']) is bool and type(row['behavior_guided_selection']) is bool,
                'behavioral guidance must be explicit')


def _context(panel, episode, episode_sha256, pair, delivery, executions, executions_sha256, condition):
    verify_sources()
    require(condition in CONDITIONS, 'invalid access condition')
    policy, _ = read_json(episode, episode_sha256)
    validate_policy(policy)
    require(hash_file(TASK / 'task.json') == policy['current_task_sha256'],
            'policy does not bind the current canonical task')
    pair_doc, _ = read_json(pair, policy['paired_delivery_sha256'])
    require(pair_doc.get('schema') == 'smc_offline_paired_delivery_v1'
            and pair_doc.get('task_id') == TASK_ID and pair_doc.get('conditions') == list(CONDITIONS)
            and pair_doc.get('current_task_sha256') == policy['current_task_sha256']
            and pair_doc.get('primary_contract_sha256') == PRIMARY_SHA256
            and pair_doc.get('condition_manifest_sha256') == policy['condition_manifest_sha256'],
            'paired delivery differs from admitted task/conditions')
    delivered, _ = read_json(delivery, policy['condition_manifest_sha256'][condition])
    require(delivered.get('schema') == 'smc_offline_participant_delivery_v1'
            and delivered.get('task_id') == TASK_ID and delivered.get('condition') == condition
            and delivered.get('current_task_sha256') == policy['current_task_sha256']
            and delivered.get('primary_contract_sha256') == PRIMARY_SHA256, 'condition delivery differs')
    rows = delivered.get('files')
    require(isinstance(rows, list) and all(isinstance(row, dict) and isinstance(row.get('path'), str)
            and digest(row.get('sha256')) for row in rows), 'missing delivery file inventory')
    inventory = {row['path']: row['sha256'] for row in rows}
    require(len(inventory) == len(rows), 'duplicate delivery paths')
    require(inventory.get('registered_task.json') == policy['current_task_sha256']
            and inventory.get('reproduction.v1.json') == REPRODUCTION_SHA256
            and inventory.get('author_baseline_protocol.json') == SOURCE_PINS['protocol.json'],
            'delivered source identities differ')
    execution_doc, _ = read_json(executions, executions_sha256)
    validate_executions(execution_doc, episode_sha256, condition)
    panel_doc, panel_hash = read_json(panel)
    source.validate_panel(panel_doc)
    require(inventory.get('inputs/mc_maze/test/panel.json') == panel_hash,
            'panel differs from the delivered input panel')
    return policy, execution_doc, panel_doc, panel_hash


def _prediction_hashes(submissions, panel):
    require(isinstance(submissions, dict) and set(submissions) == set(ARMS), 'both source-arm submissions required')
    result = {}
    for arm in ARMS:
        before = hash_file(submissions[arm], MAX_PREDICTION_BYTES)
        source.validate_submission(submissions[arm], panel, require_author_arrays=False)
        require(hash_file(submissions[arm], MAX_PREDICTION_BYTES) == before, 'prediction changed during validation')
        result[arm] = before
    return result


def freeze_predictions(submissions, panel, episode, episode_sha256, pair, delivery,
                       executions, executions_sha256, destination, *, condition):
    policy, execution_doc, panel_doc, panel_hash = _context(
        panel, episode, episode_sha256, pair, delivery, executions, executions_sha256, condition)
    predictions = _prediction_hashes(submissions, panel_doc)
    require(all(execution_doc['arms'][arm]['submission_sha256'] == predictions[arm] for arm in ARMS),
            'prediction differs from the trusted execution output')
    record = {'schema': 'smc_ai_paired_reproduction_freeze_v1', 'task_id': TASK_ID,
        'role': 'ai_reproduction', 'outcome': 'reproduction', 'condition': condition,
        'method_id': execution_doc['method_id'], 'created_utc': datetime.now(timezone.utc).isoformat(),
        'episode_policy_sha256': episode_sha256, 'execution_record_sha256': executions_sha256,
        'submission_sha256': predictions, 'panel_manifest_sha256': panel_hash,
        'reference_panel_sha256': SOURCE_PINS['reference_panel.json'],
        'reproduction_contract_sha256': REPRODUCTION_SHA256,
        'author_protocol_sha256': SOURCE_PINS['protocol.json'],
        'current_task_sha256': policy['current_task_sha256'],
        'paired_delivery_sha256': policy['paired_delivery_sha256'],
        'delivery_manifest_sha256': policy['condition_manifest_sha256'][condition],
        'target_exposure': EXPOSURE, 'scientific_outcome': 'unknown'}
    write_new_json(destination, record)
    return record


def validate_freeze(submissions, panel, episode, episode_sha256, pair, delivery,
                    executions, executions_sha256, freeze):
    record, freeze_hash = read_json(freeze)
    require(record.get('schema') == 'smc_ai_paired_reproduction_freeze_v1'
            and record.get('task_id') == TASK_ID and record.get('role') == 'ai_reproduction'
            and record.get('outcome') == 'reproduction', 'not a joint AI reproduction freeze')
    policy, execution_doc, panel_doc, panel_hash = _context(panel, episode, episode_sha256, pair,
        delivery, executions, executions_sha256, record.get('condition'))
    expected = {'schema': 'smc_ai_paired_reproduction_freeze_v1', 'task_id': TASK_ID,
        'role': 'ai_reproduction', 'outcome': 'reproduction', 'condition': execution_doc['condition'],
        'method_id': execution_doc['method_id'], 'episode_policy_sha256': episode_sha256,
        'execution_record_sha256': executions_sha256, 'submission_sha256': _prediction_hashes(submissions, panel_doc),
        'panel_manifest_sha256': panel_hash, 'reference_panel_sha256': SOURCE_PINS['reference_panel.json'],
        'reproduction_contract_sha256': REPRODUCTION_SHA256, 'author_protocol_sha256': SOURCE_PINS['protocol.json'],
        'current_task_sha256': policy['current_task_sha256'], 'paired_delivery_sha256': policy['paired_delivery_sha256'],
        'delivery_manifest_sha256': policy['condition_manifest_sha256'][execution_doc['condition']],
        'target_exposure': EXPOSURE, 'scientific_outcome': 'unknown'}
    require(all(execution_doc['arms'][arm]['submission_sha256'] == expected['submission_sha256'][arm]
                for arm in ARMS), 'prediction differs from the trusted execution output')
    require(set(record) == set(expected) | {'created_utc'}
            and all(record[key] == value for key, value in expected.items()), 'frozen reproduction content changed')
    require(isinstance(record['created_utc'], str) and len(record['created_utc']) <= 64, 'invalid freeze timestamp')
    stamp = datetime.fromisoformat(record['created_utc'])
    require(stamp.tzinfo is not None and stamp.utcoffset().total_seconds() == 0, 'freeze timestamp must be UTC')
    return record, policy, execution_doc, freeze_hash


def _snapshot(path, destination, expected, *, byte_budget):
    require(type(byte_budget) is int and byte_budget > 0, 'no remaining scratch budget')
    limit = min(MAX_PREDICTION_BYTES, byte_budget)
    handle, initial = _open_file(path, limit)
    result = hashlib.sha256()
    total = 0
    with handle, destination.open('xb') as output:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            total += len(block)
            require(total <= limit, 'prediction grew beyond remaining scratch budget')
            result.update(block)
            output.write(block)
        require(total == initial.st_size and _identity(initial) == _identity(os.fstat(handle.fileno())),
                'prediction changed during snapshot')
    require(result.hexdigest() == expected, 'snapshot differs from joint prediction freeze')
    return total


def score_predictions(submissions, panel, episode, episode_sha256, pair, delivery,
                      executions, executions_sha256, freeze, target, target_sha256,
                      scorer_source, destination, *, scratch_root, scratch_budget_bytes):
    require(target_sha256 == source.TARGET_SHA256, 'target must be original public test release')
    require(type(scratch_budget_bytes) is int and 0 < scratch_budget_bytes <= 2 * MAX_PREDICTION_BYTES,
            'scratch budget must be positive and at most 1 GiB')
    record, policy, execution_doc, freeze_hash = validate_freeze(submissions, panel, episode, episode_sha256,
        pair, delivery, executions, executions_sha256, freeze)
    require(not Path(destination).exists() and not Path(destination).is_symlink(), 'output already exists')
    require(sum(Path(submissions[arm]).stat().st_size for arm in ARMS) <= scratch_budget_bytes,
            'both complete snapshots exceed scratch budget')
    # Resolve directories only: opening or statting target waits for both snapshots.
    target_parent = Path(target).parent.resolve(strict=True)
    require(all(target_parent != Path(submissions[arm]).parent.resolve(strict=True) for arm in ARMS),
            'operator target must be separate from participant submissions')
    scorer_path = Path(scorer_source)
    if scorer_path.is_dir():
        scorer_path = scorer_path / 'nlb_tools' / 'evaluation.py'
    require(hash_file(scorer_path) == source.SCORER_SHA256, 'not the bounded original evaluator source')
    evaluator = source.load_original_scorer(scorer_source)
    metrics = {}
    with tempfile.TemporaryDirectory(prefix='smc-paired-reproduction-', dir=scratch_root) as temporary:
        snapshots = {arm: Path(temporary) / (arm + '.h5') for arm in ARMS}
        remaining = scratch_budget_bytes
        for arm in ARMS:
            remaining -= _snapshot(submissions[arm], snapshots[arm], record['submission_sha256'][arm],
                                   byte_budget=remaining)
        # No target access occurs until both complete committed submissions are snapshotted.
        require(hash_file(target, MAX_TARGET_BYTES) == target_sha256, 'target bytes differ')
        for arm in ARMS:
            require(not os.path.samefile(target, submissions[arm]), 'target aliases participant predictions')
        for arm in ARMS:
            result = evaluator.evaluate(str(target), str(snapshots[arm]))
            require(isinstance(result, list) and len(result) == 1
                    and isinstance(result[0], dict) and set(result[0]) == {source.DATASET + '_split'},
                    'evaluator did not return the complete original panel')
            values = result[0][source.DATASET + '_split']
            require(isinstance(values, dict) and set(values) == set(source.METRICS), 'missing source companion metric')
            metrics[arm] = {name: float(values[name]) for name in source.METRICS}
            require(all(math.isfinite(value) for value in metrics[arm].values()), 'nonfinite original metric')
        require(hash_file(target, MAX_TARGET_BYTES) == target_sha256, 'target changed during paired scoring')
        for arm in ARMS:
            require(hash_file(snapshots[arm], MAX_PREDICTION_BYTES) == record['submission_sha256'][arm],
                    'snapshot changed during paired scoring')
    require(hash_file(freeze) == freeze_hash and hash_file(episode) == episode_sha256
            and hash_file(executions) == executions_sha256, 'frozen policy or execution record changed during scoring')
    findings = []
    suffix = {'co-bps': 'co_bps', 'vel R2': 'velocity_r2', 'psth R2': 'psth_r2', 'fp-bps': 'forward_bps'}
    for arm in ARMS:
        for name in source.METRICS:
            expected = source.PUBLISHED[arm][name]
            findings.append({'id': arm + '_' + suffix[name], 'arm': arm, 'metric': name,
                'observed': metrics[arm][name], 'published': expected,
                'signed_difference': metrics[arm][name] - expected, 'scientific_outcome': 'unknown'})
    report = {'schema': 'smc_ai_paired_reproduction_score_v1', 'task_id': TASK_ID,
        'role': 'ai_reproduction', 'outcome': 'reproduction', 'condition': record['condition'],
        'method_id': record['method_id'], 'findings': findings, 'metrics': metrics,
        'prediction_freeze_sha256': freeze_hash, 'submission_sha256': record['submission_sha256'],
        'panel_manifest_sha256': record['panel_manifest_sha256'],
        'reference_panel_sha256': SOURCE_PINS['reference_panel.json'],
        'reproduction_contract_sha256': REPRODUCTION_SHA256,
        'episode_policy_sha256': episode_sha256, 'execution_record_sha256': executions_sha256,
        'paired_delivery_sha256': policy['paired_delivery_sha256'],
        'delivery_manifest_sha256': record['delivery_manifest_sha256'],
        'current_task_sha256': policy['current_task_sha256'],
        'author_protocol_sha256': SOURCE_PINS['protocol.json'],
        'agreement_policy_sha256': policy['agreement_policy_sha256'],
        'uncertainty_policy_sha256': policy['uncertainty_policy_sha256'],
        'execution_declarations': execution_doc['arms'],
        'scorer_sha256': source.SCORER_SHA256, 'target_sha256': target_sha256,
        'target_exposure': EXPOSURE, 'scientific_outcome': 'unknown',
        'dependency_versions': {name: importlib.metadata.version(name) for name in ('numpy', 'scipy', 'scikit-learn', 'h5py')},
        'interpretation': 'Complete original two-arm metric panel and declared provenance. '
            'Trusted execution, faithful source-method verification, justified agreement and uncertainty '
            'remain separate. No reproduction pass, improvement, independent generalization or SOTA is decided.'}
    write_new_json(destination, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('freeze', 'score'):
        command = commands.add_parser(name)
        for item in ('causal', 'noncausal', 'panel', 'episode-policy', 'pair-manifest',
                     'delivery-manifest', 'executions', 'output'):
            command.add_argument('--' + item, type=Path, required=True)
        command.add_argument('--episode-policy-sha256', required=True)
        command.add_argument('--executions-sha256', required=True)
        if name == 'freeze':
            command.add_argument('--condition', choices=CONDITIONS, required=True)
        else:
            for item in ('freeze', 'target', 'scorer-source', 'scratch-root'):
                command.add_argument('--' + item, type=Path, required=True)
            command.add_argument('--target-sha256', required=True)
            command.add_argument('--scratch-budget-bytes', type=int, required=True)
    args = parser.parse_args(argv)
    common = ({arm: getattr(args, arm) for arm in ARMS}, args.panel, args.episode_policy,
        args.episode_policy_sha256, args.pair_manifest, args.delivery_manifest,
        args.executions, args.executions_sha256)
    if args.command == 'freeze':
        result = freeze_predictions(*common, args.output, condition=args.condition)
    else:
        result = score_predictions(*common, args.freeze, args.target, args.target_sha256,
            args.scorer_source, args.output, scratch_root=args.scratch_root,
            scratch_budget_bytes=args.scratch_budget_bytes)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
