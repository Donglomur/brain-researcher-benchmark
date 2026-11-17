#!/usr/bin/env python3
"""Prepare, inspect, freeze and measure continuous original-panel SMC outcomes.

This is a cooperative operator interface, not a sandbox. Source-method fidelity,
AI attribution and enforcement of one final submission require episode evidence.
The benchmark itself returns measurements without inventing a pass threshold.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import stat
import tempfile

HERE = Path(__file__).resolve().parent
TASK = HERE.parent.parent
RETAINED = HERE.parent / 'source-matched-nlb-v1'
TASK_ID = 'PAPER-SMC-RNN-2024'
CONDITIONS = ('paper_data', 'paper_data_author_code')
POLICY_SHA256 = '1e04f61dedded47ed5de763bb328d2aa15dc2c26e3869b76f68d9af51fea61d0'
CALIBRATION_REPORT = TASK.parents[2] / 'docs/science/smc-author-calibration-20261117.json'
CALIBRATION_SHA256 = 'e2b33c75d5aa834de6d16403ed9e63c397e6dac95eebe3b482b0dbb9eb925cd1'
MAX_FILE = 512 * 1024**2
MAX_FILES = 160
ATTRIBUTION = {
    'dataset': 'Mark Churchland and Matthew Kaufman (2022), MC_Maze delayed reaching recordings',
    'dataset_url': 'https://doi.org/10.48324/dandi.000128/0.220113.0400', 'dataset_license': 'CC-BY-4.0',
    'nlb_tools': 'neurallatents/nlb_tools 0.0.3, MIT; original tensors and evaluator retained',
    'data_transform': 'Original 20-ms panel; validation targets supplied, test targets excluded'}
SOURCE_PINS = {
    'delivery.py': 'bf63171f9737e6be6a0c6c7d575c727505f07208cfae6a460876746959a51cf8',
    'scorer.py': '48638a595755138b32ff9c228804fd8c19c9ff874cd254f135fc5245ee9a25f8',
    'reference_panel.json': '209a15e2189499a9e68264df5c9f81057dd919564d98a46fb64d75b3f39af2f3',
    'reference_validation_panel.json': '772123900caed9a8fdfc7799cb5496e70ff89620cbb01d271afb960ef86ed54a',
    'protocol.json': 'c8d437ece9c57b9066c5167ad499eada673d425ea17a06a9a20d62410ecbd644',
    'source_manifest.json': '07f763fea98dd95f8874939c1898c686b687008746265fe5eae4192c10699f34',
}


def _load(name, path, expected):
    # Bounded ordinary-file precheck before executing any retained Python source.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or Path(path).is_symlink() or not 0 < info.st_size <= 1024**2:
            raise ValueError('retained source is not a bounded ordinary file')
        body = handle.read(1024**2 + 1)
        final = os.fstat(handle.fileno())
        if len(body) != info.st_size or (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns, final.st_ctime_ns):
            raise ValueError('retained source changed during bounded read')
    if hashlib.sha256(body).hexdigest() != expected:
        raise ValueError('retained source hash changed: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


io = _load('_smc_continuous_io', HERE.parent / 'paired-reproduction-v1/reproduce.py',
           'e716bf5dc10723798b10a5f5650b6ed42342efe4693327c8e1188a637c59b222')
require, hash_file, read_json = io.require, io.hash_file, io.read_json
for _name, _expected in SOURCE_PINS.items():
    require(hash_file(RETAINED / _name) == _expected, 'retained dependency changed: ' + _name)
retained = _load('_smc_continuous_delivery', RETAINED / 'delivery.py', SOURCE_PINS['delivery.py'])
source = io.source


def load_policy():
    policy, _ = read_json(HERE / 'policy.json', POLICY_SHA256)
    require(hash_file(CALIBRATION_REPORT) == CALIBRATION_SHA256, 'retained calibration report changed')
    return policy


def positive_integer(value):
    return type(value) is int and value > 0


def validate_budget(value):
    require(isinstance(value, dict) and set(value) == {'reproduction', 'improvement'},
            'resource budget must specify both outcome profiles')
    for profile in value.values():
        require(isinstance(profile, dict) and set(profile) == {'cpu_seconds', 'wall_seconds', 'memory_bytes', 'threads'},
                'each resource profile needs exactly cpu_seconds, wall_seconds, memory_bytes and threads')
        require(all(positive_integer(x) for x in profile.values()), 'resource budgets must be finite positive integers')
    return value


def current_task(path, expected):
    document, _ = read_json(path, expected)
    require(document.get('id') == TASK_ID, 'wrong current task')
    require(document.get('continuous_outcomes_v1') == {
        'version': 1, 'policy_sha256': POLICY_SHA256,
        'entrypoint': 'implementations/continuous-outcomes-v1/benchmark.py'},
        'current task has not selected the adopted continuous outcome route')
    return document


def compare_metrics(outcome, results):
    policy = load_policy()
    require(outcome in policy['outcomes'], 'unknown outcome')
    require(isinstance(results, dict) and set(results) == set(policy['outcomes'][outcome]['submission_keys']),
            'outcome needs its complete submission set')
    for values in results.values():
        require(isinstance(values, dict) and set(values) == set(policy['metrics']), 'all four original metrics required')
        require(all(type(value) in (int, float) and math.isfinite(value) for value in values.values()),
                'metric values must be finite numbers')
    report = {'schema': 'smc_continuous_comparison_v1', 'outcome': outcome, 'metrics': results,
        'policy_sha256': POLICY_SHA256, 'binary_decision': 'not_applicable',
        'uncertainty': policy['uncertainty'], 'claim_limits': policy['claim_limits']}
    refs = {row['id']: row for row in policy['smc_references']}
    if outcome == 'reproduction':
        report['findings'] = []
        for arm, values in results.items():
            for metric in policy['metrics']:
                pub = refs['published_' + arm]['metrics'][metric]
                cur = refs['current_release_' + arm]['metrics'][metric]
                report['findings'].append({'arm': arm, 'metric': metric, 'observed': values[metric],
                    'published': pub, 'published_signed_difference': values[metric] - pub,
                    'published_absolute_difference': abs(values[metric] - pub),
                    'current_release_reference': cur, 'current_signed_difference': values[metric] - cur,
                    'current_absolute_difference': abs(values[metric] - cur)})
        report['aggregation'] = 'none'
    else:
        values = results['offline']
        comparisons = []
        for row in [*policy['smc_references'], *policy['source_paper_published_context']]:
            delta = {metric: values[metric] - row['metrics'][metric] for metric in policy['metrics']}
            comparisons.append({**row, 'signed_differences': delta,
                                'negative_companion_differences': {k: v for k, v in delta.items() if k != 'co-bps' and v < 0}})
        strongest = max(policy['smc_references'], key=lambda row: row['metrics']['co-bps'])
        require(strongest['id'] == policy['outcomes']['improvement']['selected_smc_reference_id'],
                'selected SMC reference is inconsistent with complete retained set')
        report.update(comparisons=comparisons, selected_smc_reference_id=strongest['id'],
            method_specific_smc_co_bps_difference=values['co-bps'] - strongest['metrics']['co-bps'],
            source_paper_NDT_co_bps_difference=values['co-bps'] - next(row['metrics']['co-bps']
                for row in policy['source_paper_published_context'] if row['id'] == 'NDT'),
            later_literature_context=policy['later_literature_context'])
    return report


def participant_instructions(panel, task_sha256, budget):
    policy = load_policy()
    return {'schema': 'smc_continuous_participant_task_v1', 'task_id': TASK_ID,
        'current_task_sha256': task_sha256, 'policy_sha256': POLICY_SHA256,
        'outcomes': policy['outcomes'], 'access': policy['access'], 'resource_budget': budget,
        'uncertainty': policy['uncertainty'], 'claim_limits': policy['claim_limits'],
        'reproduction_submission': 'Submit causal and noncausal together. Report all eight source-method measurements; no equivalence cutoff or averaging.',
        'improvement_submission': 'Submit one offline program result. All 35 same-trial held-in bins may be used. Report all four original metrics and retained reference deltas.',
        'execution_note': 'Budget and access are declared episode conditions; this package is not a sandbox. The operator must enforce them and one final joint submission per outcome.',
        'attribution_note': 'Method declarations do not prove execution, AI authorship, historical checkpoint identity or faithful reproduction. Construction controls are not AI results.',
        'author_protocol_scope': 'author_baseline_protocol.json records the retained operator calibration recipe, including its released checkpoint selection. Participant source-method reproduction retains the named method, particles/repeats and smooth setting, but does not require the identical author checkpoint; checkpoints are excluded from both current participant conditions.',
        'prediction_abi': {'format': 'HDF5', 'group': source.DATASET,
            'required_arrays': {key: panel['expected_shapes'][key] for key in sorted(source.REQUIRED_KEYS)},
            'optional_arrays': {key: panel['expected_shapes'][key] for key in sorted(source.OPTIONAL_KEYS)},
            'values': 'Finite nonnegative expected spike counts per 20-ms bin in complete original order.'},
        'target_exposure': policy['target_exposure']}


def payload_hash(path, limit):
    """Bound ordinary payload bytes, including authentic empty source modules."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as handle:
        initial = os.fstat(handle.fileno())
        require(stat.S_ISREG(initial.st_mode) and 0 <= initial.st_size <= limit, 'payload is not a bounded ordinary file')
        digest, total = hashlib.sha256(), 0
        for block in iter(lambda: handle.read(1024**2), b''):
            total += len(block)
            require(total <= limit, 'payload grew beyond byte bound')
            digest.update(block)
        require(total == initial.st_size and io._identity(initial) == io._identity(os.fstat(handle.fileno())),
                'payload changed during hashing')
    require(io._identity(initial) == io._identity(os.stat(path, follow_symlinks=False)), 'payload path changed during hashing')
    return digest.hexdigest()


def inventory(root, max_bytes):
    require(positive_integer(max_bytes), 'positive inventory byte bound required')
    rows, total, count = [], 0, 0
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(parent) / name
            count += 1
            require(count <= MAX_FILES * 2, 'too many delivery filesystem entries')
            mode = path.lstat().st_mode
            require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), 'delivery contains a symlink or special file')
            if stat.S_ISREG(mode):
                size = path.stat().st_size
                total += size
                require(total <= max_bytes and len(rows) < MAX_FILES, 'delivery exceeds file or byte bound')
                rows.append({'path': path.relative_to(root).as_posix(), 'bytes': size,
                             'sha256': payload_hash(path, min(MAX_FILE, max_bytes))})
    return sorted(rows, key=lambda row: row['path'])


def _public_panel(panel, phase):
    result = {key: panel[key] for key in source.PANEL_IDENTITY_FIELDS}
    result['inputs_sha256'] = panel['inputs_sha256']
    if phase == 'val':
        for key in ('validation_target_sha256', 'validation_target_shapes'):
            result[key] = panel[key]
    return result


def _plan(prepared_root, author_source, paper, task_path, task_sha256, budget, max_bytes):
    current_task(task_path, task_sha256)
    load_policy()
    require(hash_file(paper, 4 * 1024**2) == retained.PAPER_SHA256, 'wrong source publication')
    input_bytes = 0
    for phase in ('test', 'val'):
        root = Path(prepared_root) / 'mc_maze' / phase
        read_json(retained.regular_beneath(root, 'panel.json'))
        for name in ['train_input_20ms.h5', 'eval_input_20ms.h5'] + (['eval_target_20ms.h5'] if phase == 'val' else []):
            path = retained.regular_beneath(root, name)
            input_bytes += path.stat().st_size
            require(input_bytes <= max_bytes, 'prepared inputs exceed export byte bound')
            payload_hash(path, max_bytes)
    phases = {phase: retained.admitted_phase(prepared_root, phase) for phase in ('test', 'val')}
    code, metadata = retained.official_source_files(author_source, retained.SOURCE_MANIFEST)
    instructions = participant_instructions(phases['test'][0], task_sha256, budget)
    plans, manifests = {}, {}
    for condition in CONDITIONS:
        plan = plans[condition] = {}
        retained.plan_source(plan, 'paper.pdf', paper, retained.PAPER_SHA256)
        retained.plan_source(plan, 'registered_task.json', task_path, task_sha256)
        retained.plan_source(plan, 'measurement_policy.json', HERE / 'policy.json', POLICY_SHA256)
        retained.plan_source(plan, 'author_baseline_protocol.json', retained.PROTOCOL, SOURCE_PINS['protocol.json'])
        retained.plan_json(plan, 'resource_budget.json', budget)
        retained.plan_json(plan, 'task.json', instructions)
        retained.plan_json(plan, 'attribution.json', ATTRIBUTION)
        for phase, (panel, root) in phases.items():
            prefix = 'inputs/mc_maze/' + phase + '/'
            for name in ['train_input_20ms.h5', 'eval_input_20ms.h5'] + (['eval_target_20ms.h5'] if phase == 'val' else []):
                digest = panel['validation_target_sha256'] if name.startswith('eval_target') else panel['inputs_sha256'][name]
                retained.plan_source(plan, prefix + name, root / name, digest)
            retained.plan_json(plan, prefix + 'panel.json', _public_panel(panel, phase))
        if condition == CONDITIONS[1]:
            for path, relative, row in code:
                retained.plan_source(plan, 'official_source/' + str(relative), path, row['sha256'])
            retained.plan_json(plan, 'official_source_manifest.json', {**metadata, 'files': [row for _, _, row in code]})
        manifests[condition] = {'schema': 'smc_continuous_delivery_v1', 'condition': condition,
            'current_task_sha256': task_sha256, 'policy_sha256': POLICY_SHA256, 'files': retained.planned_inventory(plan)}
        retained.plan_json(plan, 'delivery_manifest.json', manifests[condition])
    shared = {row['path']: row['sha256'] for row in manifests[CONDITIONS[0]]['files']}
    additions = sorted(set(plans[CONDITIONS[1]]) - set(plans[CONDITIONS[0]]))
    pair = {'schema': 'smc_continuous_pair_v1', 'task_id': TASK_ID, 'conditions': list(CONDITIONS),
        'policy_sha256': POLICY_SHA256, 'current_task_sha256': task_sha256,
        'shared_files': shared, 'code_condition_additions': additions,
        'condition_manifest_sha256': {key: plans[key]['delivery_manifest.json']['sha256'] for key in CONDITIONS},
        'resource_budget': budget, 'execution_verified': False, 'AI_result': False}
    entire = {condition + '/' + path: row for condition in CONDITIONS for path, row in plans[condition].items()}
    retained.plan_json(entire, 'pair_manifest.json', pair)
    return pair, entire


def export_pair(prepared_root, author_source, paper, task_path, task_sha256, budget_path, output, *, max_bytes, reserve_bytes):
    require(positive_integer(max_bytes) and type(reserve_bytes) is int and reserve_bytes >= 0, 'invalid export capacity bounds')
    budget = validate_budget(read_json(budget_path)[0])
    output = Path(output).absolute()
    require(not output.exists() and not output.is_symlink(), 'export destination exists')
    output.parent.mkdir(parents=True, exist_ok=True)
    output = output.parent.resolve() / output.name
    require(not any((parent / '.git').exists() for parent in (output, *output.parents)), 'payload must remain outside public Git worktrees')
    pair, plan = _plan(prepared_root, author_source, paper, task_path, task_sha256, budget, max_bytes)
    size = sum(row['bytes'] for row in plan.values())
    require(size <= max_bytes and shutil.disk_usage(output.parent).free >= size + reserve_bytes,
            'complete export exceeds byte cap or free-space reserve')
    with tempfile.TemporaryDirectory(prefix='.smc-continuous-export-', dir=output.parent) as temporary:
        stage = Path(temporary) / 'pair'
        remaining = max_bytes
        for relative, row in plan.items():
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if 'source' in row:
                if row['bytes'] == 0:
                    require(payload_hash(row['source'], 0) == row['sha256'], 'empty source changed')
                    destination.touch(exist_ok=False)
                else:
                    remaining -= io._snapshot(row['source'], destination, row['sha256'], byte_budget=remaining)
            else:
                require(len(row['content']) <= remaining, 'export metadata exceeds remaining byte cap')
                destination.write_bytes(row['content'])
                remaining -= len(row['content'])
        require(inventory(stage, max_bytes) == retained.planned_inventory(plan), 'export changed from complete planned inventory')
        inspect_pair(stage / 'pair_manifest.json', hash_file(stage / 'pair_manifest.json'), task_path, task_sha256, max_bytes=max_bytes)
        require(not output.exists(), 'export destination appeared')
        stage.rename(output)
    return pair


def inspect_pair(pair_path, expected_sha256, task_path, task_sha256, *, max_bytes):
    current_task(task_path, task_sha256)
    policy = load_policy()
    pair_path = Path(pair_path)
    require(pair_path.name == 'pair_manifest.json', 'pair manifest must have its canonical name')
    root = pair_path.parent.resolve()
    pair, _ = read_json(pair_path, expected_sha256)
    require(set(pair) == {'schema', 'task_id', 'conditions', 'policy_sha256', 'current_task_sha256',
                         'shared_files', 'code_condition_additions', 'condition_manifest_sha256',
                         'resource_budget', 'execution_verified', 'AI_result'}, 'unexpected paired metadata fields')
    require(pair.get('schema') == 'smc_continuous_pair_v1' and pair.get('task_id') == TASK_ID,
            'obsolete or wrong paired materials; fresh export required')
    require(pair.get('conditions') == list(CONDITIONS) and pair.get('policy_sha256') == POLICY_SHA256
            and pair.get('current_task_sha256') == task_sha256, 'pair uses stale task or policy')
    require(pair['execution_verified'] is False and pair['AI_result'] is False
            and isinstance(pair['condition_manifest_sha256'], dict)
            and set(pair['condition_manifest_sha256']) == set(CONDITIONS), 'invalid pair provenance or condition identities')
    budget = validate_budget(pair['resource_budget'])
    actual = inventory(root, max_bytes)
    required = {'pair_manifest.json'}
    inventories, panels = {}, {}
    for condition in CONDITIONS:
        manifest_path = retained.regular_beneath(root, condition + '/delivery_manifest.json')
        manifest, _ = read_json(manifest_path, pair['condition_manifest_sha256'][condition])
        require(set(manifest) == {'schema', 'condition', 'current_task_sha256', 'policy_sha256', 'files'},
                'unexpected condition metadata fields')
        require(manifest.get('schema') == 'smc_continuous_delivery_v1' and manifest.get('condition') == condition
                and manifest.get('current_task_sha256') == task_sha256 and manifest.get('policy_sha256') == POLICY_SHA256,
                'condition manifest has wrong policy, identity or condition')
        rows = manifest['files']
        require(isinstance(rows, list) and len(rows) <= MAX_FILES, 'invalid condition inventory')
        mapping = {}
        for row in rows:
            require(set(row) == {'path', 'bytes', 'sha256'} and type(row['bytes']) is int and row['bytes'] >= 0 and io.digest(row['sha256']),
                    'invalid inventory row')
            relative = str(retained.safe_relative(row['path']))
            require(relative not in mapping, 'duplicate inventory path')
            mapping[relative] = row
            required.add(condition + '/' + relative)
        required.add(condition + '/delivery_manifest.json')
        observed = [dict(row, path=row['path'][len(condition) + 1:]) for row in actual
                    if row['path'].startswith(condition + '/') and row['path'] != condition + '/delivery_manifest.json']
        require(observed == sorted(rows, key=lambda row: row['path']), 'condition files differ from bound inventory')
        base = root / condition
        current_task(base / 'registered_task.json', task_sha256)
        require(hash_file(base / 'measurement_policy.json') == POLICY_SHA256 and read_json(base / 'resource_budget.json')[0] == budget,
                'participant policy or matched resource budget differs')
        require(hash_file(base / 'paper.pdf', 4 * 1024**2) == retained.PAPER_SHA256
                and hash_file(base / 'author_baseline_protocol.json') == SOURCE_PINS['protocol.json'], 'paper or source recipe differs')
        phases = {phase: retained.admitted_phase(base / 'inputs', phase)[0] for phase in ('test', 'val')}
        require(all(phases[phase] == _public_panel(phases[phase], phase) for phase in phases),
                'public panel contains undeclared metadata')
        require(read_json(base / 'attribution.json')[0] == ATTRIBUTION, 'attribution metadata differs')
        source.validate_panel(phases['test'])
        require(read_json(base / 'task.json')[0] == participant_instructions(phases['test'], task_sha256, budget),
                'participant instructions differ from adopted continuous policy')
        panels[condition] = phases['test']
        inventories[condition] = mapping
    left, right = (inventories[key] for key in CONDITIONS)
    require(all(right.get(path) == row for path, row in left.items()), 'shared materials differ across conditions')
    require(pair['shared_files'] == {path: row['sha256'] for path, row in left.items()}, 'shared identity map differs')
    additions = sorted(set(right) - set(left))
    require(pair['code_condition_additions'] == additions and additions
            and all(path.startswith('official_source/') or path == 'official_source_manifest.json' for path in additions),
            'conditions differ outside official source')
    code, metadata = retained.official_source_files(root / CONDITIONS[1] / 'official_source', retained.SOURCE_MANIFEST)
    expected_additions = sorted(['official_source_manifest.json'] + ['official_source/' + str(relative) for _, relative, _ in code])
    require(additions == expected_additions and read_json(root / CONDITIONS[1] / 'official_source_manifest.json')[0]
            == {**metadata, 'files': [row for _, _, row in code]}, 'official source metadata or allowlist changed')
    require({row['path'] for row in actual} == required, 'unexpected files in paired materials')
    # Exact shared allowlist excludes predictions, checkpoints and test targets even if rehashed together.
    allowed = {'paper.pdf', 'registered_task.json', 'measurement_policy.json', 'author_baseline_protocol.json',
               'resource_budget.json', 'task.json', 'attribution.json'}
    allowed.update('inputs/mc_maze/' + phase + '/' + name for phase in ('test', 'val')
                   for name in ('train_input_20ms.h5', 'eval_input_20ms.h5', 'panel.json'))
    allowed.add('inputs/mc_maze/val/eval_target_20ms.h5')
    require(set(left) == allowed, 'shared files exceed explicit participant allowlist')
    return {'schema': 'smc_continuous_readiness_v1', 'materials_valid': True,
        'episode_budget_declared': True, 'execution_verified': False, 'AI_result': False,
        'pair': pair, 'policy': policy, 'panels': panels, 'conditions': list(CONDITIONS),
        'qualification': 'Continuous interfaces and bound materials; sandbox enforcement and each result attribution are separate.'}


def validate_declaration(document, outcome, condition):
    require(set(document) == {'schema', 'role', 'method_id', 'outcome', 'condition', 'methods'}
            and document.get('schema') == 'smc_continuous_submission_declaration_v1'
            and document.get('role') in ('construction_control', 'participant')
            and document.get('outcome') == outcome and document.get('condition') == condition,
            'wrong submission declaration schema, role or outcome')
    require(isinstance(document['method_id'], str) and 0 < len(document['method_id']) <= 200, 'method id required')
    expected = load_policy()['outcomes'][outcome]['submission_keys']
    require(isinstance(document['methods'], dict) and set(document['methods']) == set(expected), 'incomplete method declarations')
    for row in document['methods'].values():
        require(isinstance(row, dict) and set(row) == {'source_sha256', 'seed', 'recipe', 'behavior_guided_fitting', 'behavior_guided_selection'}
                and io.digest(row['source_sha256']) and type(row['seed']) is int and row['seed'] >= 0,
                'method source identity and nonnegative seed declaration required')
        require(type(row['behavior_guided_fitting']) is bool and type(row['behavior_guided_selection']) is bool,
                'actual behavior-guided fitting and selection must be declared explicitly')
        recipe = {'particles': 192, 'repeats': 32, 'smooth': False} if outcome == 'reproduction' and document['role'] == 'participant' else None
        require(row['recipe'] == recipe and (recipe is None or all(type(row['recipe'][key]) is type(value) for key, value in recipe.items())),
                'participant reproduction must declare original source recipe; other roles do not assert it')
    return document


def _declaration(path, outcome, condition):
    document, sha = read_json(path)
    return validate_declaration(document, outcome, condition), sha


def body_digest(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def freeze(pair_path, pair_sha256, task_path, task_sha256, condition, outcome, submissions, declaration_path, output, *, max_bytes):
    require(not Path(output).parent.resolve(strict=True).is_relative_to(Path(pair_path).parent.resolve()),
            'operator output must be outside paired participant materials')
    require(not Path(output).exists() and not Path(output).is_symlink(), 'freeze output already exists')
    admission = inspect_pair(pair_path, pair_sha256, task_path, task_sha256, max_bytes=max_bytes)
    require(condition in CONDITIONS and outcome in admission['policy']['outcomes'], 'invalid condition or outcome')
    keys = admission['policy']['outcomes'][outcome]['submission_keys']
    require(isinstance(submissions, dict) and set(submissions) == set(keys), 'all outcome predictions must be frozen together')
    declaration, declaration_sha = _declaration(declaration_path, outcome, condition)
    records = {}
    for key in keys:
        path = Path(submissions[key]).absolute()
        digest = hash_file(path, MAX_FILE)
        source.validate_submission(path, admission['panels'][condition])
        require(hash_file(path, MAX_FILE) == digest, 'prediction changed during validation')
        records[key] = {'path': str(path), 'sha256': digest}
    record = {'schema': 'smc_continuous_prediction_freeze_v1', 'task_id': TASK_ID,
        'condition': condition, 'outcome': outcome, 'current_task_sha256': task_sha256,
        'pair_sha256': pair_sha256, 'policy_sha256': POLICY_SHA256,
        'declaration': declaration, 'declaration_sha256': declaration_sha,
        'declaration_body_sha256': body_digest(declaration), 'submissions': records,
        'target_accessed': False, 'execution_verified': False, 'AI_attribution_verified': False}
    io.write_new_json(output, record)
    return record


def score(frozen_path, frozen_sha256, pair_path, pair_sha256, task_path, task_sha256, condition_root,
          target, evaluator, output, *, scratch_bytes, max_bytes):
    require(positive_integer(scratch_bytes), 'explicit positive snapshot byte cap required')
    require(not Path(output).exists() and not Path(output).is_symlink(), 'result output already exists')
    require(not Path(output).parent.resolve(strict=True).is_relative_to(Path(pair_path).parent.resolve()),
            'operator output and scratch must be outside paired participant materials')
    admission = inspect_pair(pair_path, pair_sha256, task_path, task_sha256, max_bytes=max_bytes)
    record, _ = read_json(frozen_path, frozen_sha256)
    require(set(record) == {'schema', 'task_id', 'condition', 'outcome', 'current_task_sha256',
                           'pair_sha256', 'policy_sha256', 'declaration', 'declaration_sha256', 'declaration_body_sha256',
                           'submissions', 'target_accessed', 'execution_verified', 'AI_attribution_verified'},
            'unexpected frozen record fields')
    require(record.get('schema') == 'smc_continuous_prediction_freeze_v1' and record.get('task_id') == TASK_ID
            and record.get('pair_sha256') == pair_sha256 and record.get('current_task_sha256') == task_sha256
            and record.get('policy_sha256') == POLICY_SHA256, 'freeze uses wrong task, policy or pair')
    condition, outcome = record['condition'], record['outcome']
    require(condition in CONDITIONS and outcome in admission['policy']['outcomes'], 'invalid frozen condition or outcome')
    validate_declaration(record['declaration'], outcome, condition)
    require(record['declaration_body_sha256'] == body_digest(record['declaration']), 'embedded declaration differs from frozen body identity')
    require(io.digest(record['declaration_sha256']) and record.get('target_accessed') is False
            and record.get('execution_verified') is False and record.get('AI_attribution_verified') is False,
            'freeze contains unsupported provenance claims')
    condition_root = Path(condition_root).resolve(strict=True)
    require(condition_root == Path(pair_path).parent.resolve() / condition, 'wrong participant condition root')
    require(not Path(target).parent.resolve(strict=True).is_relative_to(Path(pair_path).parent.resolve()),
            'operator target must be outside paired participant materials')
    keys = admission['policy']['outcomes'][outcome]['submission_keys']
    require(set(record['submissions']) == set(keys), 'frozen outcome prediction set incomplete')
    evaluator = Path(evaluator)
    if evaluator.is_dir():
        evaluator = evaluator / 'nlb_tools/evaluation.py'
    require(hash_file(evaluator) == source.SCORER_SHA256, 'wrong original evaluator')
    original = source.load_original_scorer(evaluator)
    results = {}
    with tempfile.TemporaryDirectory(prefix='.smc-continuous-score-', dir=Path(output).parent) as temporary:
        snapshots, remaining = {}, scratch_bytes
        for key in keys:
            row = record['submissions'][key]
            require(set(row) == {'path', 'sha256'} and io.digest(row['sha256']), 'invalid frozen submission reference')
            require(Path(target).parent.resolve(strict=True) != Path(row['path']).parent.resolve(strict=True),
                    'operator target must be separate from participant predictions')
            snapshot = Path(temporary) / (key + '.h5')
            remaining -= io._snapshot(row['path'], snapshot, row['sha256'], byte_budget=remaining)
            source.validate_submission(snapshot, admission['panels'][condition])
            snapshots[key] = snapshot
        # Every complete prediction set has been snapshotted and validated before first target access.
        require(hash_file(target, io.MAX_TARGET_BYTES) == source.TARGET_SHA256, 'wrong original target identity')
        for key, snapshot in snapshots.items():
            require(not os.path.samefile(target, record['submissions'][key]['path']), 'target aliases prediction')
            raw = original.evaluate(str(target), str(snapshot))
            require(isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], dict)
                    and set(raw[0]) == {source.DATASET + '_split'}, 'original evaluator returned wrong panel')
            values = raw[0][source.DATASET + '_split']
            require(isinstance(values, dict) and set(values) == set(source.METRICS), 'incomplete original metrics')
            results[key] = {metric: float(values[metric]) for metric in source.METRICS}
        require(hash_file(target, io.MAX_TARGET_BYTES) == source.TARGET_SHA256, 'target changed while scoring')
        for key, snapshot in snapshots.items():
            require(hash_file(snapshot, MAX_FILE) == record['submissions'][key]['sha256'], 'snapshot changed while scoring')
    require(hash_file(frozen_path) == frozen_sha256 and hash_file(pair_path) == pair_sha256
            and hash_file(task_path) == task_sha256, 'operator-bound identities changed while scoring')
    report = compare_metrics(outcome, results)
    report.update(task_id=TASK_ID, condition=condition, role=record['declaration']['role'],
        method_id=record['declaration']['method_id'], prediction_freeze_sha256=frozen_sha256,
        current_task_sha256=task_sha256, pair_sha256=pair_sha256, target_sha256=source.TARGET_SHA256,
        evaluator_sha256=source.SCORER_SHA256, submissions=record['submissions'],
        declaration=record['declaration'], execution_verified=False, AI_attribution_verified=False,
        dependency_versions={name: importlib.metadata.version(name) for name in ('numpy', 'scipy', 'scikit-learn', 'h5py')},
        target_exposure=admission['policy']['target_exposure'])
    io.write_new_json(output, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'inspect', 'freeze', 'score'):
        cmd = commands.add_parser(name)
        cmd.add_argument('--task', type=Path, required=True)
        cmd.add_argument('--task-sha256', required=True)
        cmd.add_argument('--max-bytes', type=int, required=True, help='Maximum complete paired material bytes.')
        if name == 'prepare':
            for key in ('prepared-root', 'author-source', 'paper', 'budget', 'output'):
                cmd.add_argument('--' + key, type=Path, required=True)
            cmd.add_argument('--reserve-bytes', type=int, required=True)
        else:
            cmd.add_argument('--pair', type=Path, required=True)
            cmd.add_argument('--pair-sha256', required=True)
        if name == 'freeze':
            cmd.add_argument('--condition', choices=CONDITIONS, required=True)
            cmd.add_argument('--outcome', choices=('reproduction', 'improvement'), required=True)
            cmd.add_argument('--submission', action='append', required=True, help='KEY=PATH; both causal/noncausal or one offline.')
            cmd.add_argument('--declaration', type=Path, required=True)
            cmd.add_argument('--output', type=Path, required=True)
        if name == 'score':
            for key in ('frozen', 'condition-root', 'target', 'evaluator', 'output'):
                cmd.add_argument('--' + key, type=Path, required=True)
            cmd.add_argument('--frozen-sha256', required=True)
            cmd.add_argument('--scratch-bytes', type=int, required=True)
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        result = export_pair(args.prepared_root, args.author_source, args.paper, args.task, args.task_sha256,
            args.budget, args.output, max_bytes=args.max_bytes, reserve_bytes=args.reserve_bytes)
    elif args.command == 'inspect':
        result = inspect_pair(args.pair, args.pair_sha256, args.task, args.task_sha256, max_bytes=args.max_bytes)
    elif args.command == 'freeze':
        submissions = {}
        for value in args.submission:
            require('=' in value, 'submission must be KEY=PATH')
            key, path = value.split('=', 1)
            require(key not in submissions, 'duplicate submission key')
            submissions[key] = Path(path)
        result = freeze(args.pair, args.pair_sha256, args.task, args.task_sha256, args.condition, args.outcome,
            submissions, args.declaration, args.output, max_bytes=args.max_bytes)
    else:
        result = score(args.frozen, args.frozen_sha256, args.pair, args.pair_sha256, args.task, args.task_sha256,
            args.condition_root, args.target, args.evaluator, args.output, scratch_bytes=args.scratch_bytes, max_bytes=args.max_bytes)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
