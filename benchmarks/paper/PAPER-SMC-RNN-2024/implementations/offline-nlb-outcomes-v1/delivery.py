#!/usr/bin/env python3
"""Prepare paired offline materials with unchanged authentic-source allowlists.

This exports no new data fields and executes no participant. A frozen trusted
episode policy, actual run and independent verification remain separate.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

spec = importlib.util.spec_from_file_location('_smc_offline_delivery_policy', Path(__file__).with_name('policy.py'))
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
retained = policy.load_source('delivery.py')
source = retained.contract
require = policy.require


def participant_task(panel, task_sha256):
    return {
        'schema': 'smc_offline_participant_task_v1', 'task_id': policy.TASK_ID,
        'current_task_sha256': task_sha256, 'primary_contract_sha256': policy.PRIMARY_SHA256,
        'reproduction_contract_sha256': policy.REPRODUCTION_SHA256,
        'outcomes': {
            'reproduction': 'Recompute both original source-method finding rows and all eight metrics with '
                'authentic inputs and trusted granular verification under independently justified agreement '
                'and uncertainty. Operator author calibration and copied printed values are not AI outcomes.',
            'improvement': 'Evaluate one complete-panel offline candidate against the strongest qualified '
                'relevant published/reproduced source comparator frozen before candidate results, with '
                'independently justified effect, uncertainty and all companion criteria.',
        },
        'allowed_observations': {
            'train_validation': 'Only the actual unchanged source-allowlisted training/validation files '
                'delivered here. Original NLB permits supplied behavior to guide learning or selection; '
                'report its actual use and freeze feedback, adaptation and budgets before execution.',
            'test': 'All 35 supplied same-trial held-in bins may inform observed-bin inference and '
                'prediction of ten unseen future bins. No test held-out spikes, future spikes or test behavior.',
            'further_access': 'No new data fields, trial, test-wide adaptation or candidate run is authorized '
                'by material preparation. The trusted episode policy must freeze actual access before execution.',
        },
        'temporal_access': {
            'scope': 'original_offline_mc_maze_20ms', 'observation_bins_zero_based': [0, 34],
            'future_bins_zero_based': [35, 44], 'full_observed_window_allowed': True,
            'source_method_note': 'Source max(t,13)/min(t+17,34) dependencies describe the two author '
                'recipes or optional explicitly matched studies. They are not a universal candidate mask.',
            'online_note': 'Strict-online claims require a separate qualified stream/state/latency policy; '
                'source reflect-padding startup is not strict online.',
        },
        'prediction_abi': {
            'format': 'HDF5', 'group': source.DATASET,
            'required_arrays': {key: panel['expected_shapes'][key] for key in sorted(source.REQUIRED_KEYS)},
            'optional_arrays': {key: panel['expected_shapes'][key] for key in sorted(source.OPTIONAL_KEYS)},
            'values': 'Finite nonnegative expected spike counts per 20-ms bin, original trial/neuron/bin '
                'order and complete source support; source scorer zero-rate clipping stays unchanged.',
            'primary_improvement_submission': 'offline/submission.h5',
            'source_reproduction': 'Both named source-method rows remain distinct. No two restricted '
                'candidate variants are required for the primary offline improvement outcome.',
        },
        'comparison_policy': 'The trusted pre-candidate policy retains both published and qualified '
            'reproduced anchors. A lower reproduced point cannot silently replace a higher published '
            'result for a paper-win claim. A source-5-ms NLB score is not the study 20-ms baseline.',
        'execution': 'Materials only; no sandbox, execution, target protection or trusted rerun is established. '
            'An explicit operator-pinned episode policy must identify comparator, actual learning access, '
            'behavior use, feedback/adaptation, equal budgets and independent scientific criteria.',
        'exposure': 'Original test targets were publicly released in January 2026; local exclusion does not '
            'make them untouched. No original test targets, checkpoints or operator predictions are exported.',
        'scientific_outcomes': {'reproduction': 'unknown', 'improvement': 'unknown'},
    }


def export_pair(prepared_root, author_source, paper, task_path, task_sha256, output, *, reserve_bytes=0):
    policy.contracts()
    require(policy.digest(task_sha256) and source.sha256(task_path) == task_sha256, 'current task differs from trusted operator pin')
    require(policy.read_json(task_path).get('id') == policy.TASK_ID, 'wrong current task')
    require(type(reserve_bytes) is int and reserve_bytes >= 0, 'invalid disk reserve')
    output = Path(output).resolve()
    require(not output.exists(), 'output already exists')
    require(not any((ancestor / '.git').exists() for ancestor in (output, *output.parents)),
            'authentic participant payloads must remain outside public Git worktrees')
    paper = Path(paper)
    require(paper.is_file() and not paper.is_symlink() and 0 < paper.stat().st_size <= 4 * 1024 * 1024,
            'original paper PDF required')
    require(source.sha256(paper) == retained.PAPER_SHA256, 'wrong source publication')
    test, test_root = retained.admitted_phase(prepared_root, 'test')
    val, val_root = retained.admitted_phase(prepared_root, 'val')
    code, code_metadata = retained.official_source_files(author_source, retained.SOURCE_MANIFEST)
    task = participant_task(test, task_sha256)
    plans, inventories = {}, {}
    for condition in policy.CONDITIONS:
        plan = plans[condition] = {}
        retained.plan_source(plan, 'paper.pdf', paper, retained.PAPER_SHA256)
        retained.plan_source(plan, 'registered_task.json', task_path, task_sha256)
        retained.plan_source(plan, 'improvement.temporal-scope.v1.json', policy.PRIMARY_CONTRACT, policy.PRIMARY_SHA256)
        retained.plan_source(plan, 'reproduction.v1.json', policy.REPRODUCTION_CONTRACT, policy.REPRODUCTION_SHA256)
        # Preserve the source recipe, explicitly labelled as author qualification.
        retained.plan_source(plan, 'author_baseline_protocol.json', retained.PROTOCOL, source.sha256(retained.PROTOCOL))
        retained.plan_json(plan, 'task.json', task)
        retained.plan_json(plan, 'attribution.json', {
            'dataset': 'Mark Churchland and Matthew Kaufman (2022), MC_Maze delayed reaching recordings',
            'dataset_url': 'https://doi.org/10.48324/dandi.000128/0.220113.0400', 'dataset_license': 'CC-BY-4.0',
            'nlb_tools': 'neurallatents/nlb_tools 0.0.3, MIT; original tensor recipe and evaluator preserved',
            'data_transform': 'Source 20-ms train/validation/test tensors; supplied validation targets retained, test targets excluded',
        })
        for phase, panel, root in (('val', val, val_root), ('test', test, test_root)):
            prefix = 'inputs/mc_maze/' + phase + '/'
            names = ['train_input_20ms.h5', 'eval_input_20ms.h5']
            if phase == 'val':
                names.append('eval_target_20ms.h5')
            for name in names:
                expected = panel['validation_target_sha256'] if name.startswith('eval_target_') else panel['inputs_sha256'][name]
                retained.plan_source(plan, prefix + name, root / name, expected)
            public_panel = {key: panel[key] for key in source.PANEL_IDENTITY_FIELDS}
            public_panel['inputs_sha256'] = panel['inputs_sha256']
            if phase == 'val':
                public_panel['validation_target_sha256'] = panel['validation_target_sha256']
                public_panel['validation_target_shapes'] = panel['validation_target_shapes']
            retained.plan_json(plan, prefix + 'panel.json', public_panel)
        if condition == 'paper_data_author_code':
            for path, relative, row in code:
                retained.plan_source(plan, 'official_source/' + str(relative), path, row['sha256'])
            retained.plan_json(plan, 'official_source_manifest.json', {**code_metadata, 'files': [row for _, _, row in code]})
        inventories[condition] = retained.planned_inventory(plan)
        retained.plan_json(plan, 'delivery_manifest.json', {
            'schema': 'smc_offline_participant_delivery_v1', 'task_id': policy.TASK_ID,
            'condition': condition, 'status': 'materials_prepared_only', 'files': inventories[condition],
            'current_task_sha256': task_sha256, 'primary_contract_sha256': policy.PRIMARY_SHA256,
            'execution_verified': False, 'scientific_outcome': 'unknown',
        })
    left = {row['path']: row['sha256'] for row in inventories[policy.CONDITIONS[0]]}
    right = {row['path']: row['sha256'] for row in inventories[policy.CONDITIONS[1]]}
    require(all(right.get(path) == value for path, value in left.items()), 'paired shared material bytes differ')
    additions = sorted(set(right) - set(left))
    require(all(path.startswith('official_source/') or path == 'official_source_manifest.json' for path in additions),
            'conditions differ outside official code')
    pair = {'schema': 'smc_offline_paired_delivery_v1', 'task_id': policy.TASK_ID,
        'conditions': list(policy.CONDITIONS), 'shared_files': left, 'code_condition_additions': additions,
        'condition_manifest_sha256': {condition: plans[condition]['delivery_manifest.json']['sha256'] for condition in policy.CONDITIONS},
        'primary_contract_sha256': policy.PRIMARY_SHA256, 'current_task_sha256': task_sha256,
        'operator_disk_reserve_bytes': reserve_bytes, 'execution_verified': False,
        'scientific_outcomes': {'reproduction': 'unknown', 'improvement': 'unknown'}}
    entire = {condition + '/' + path: row for condition in policy.CONDITIONS for path, row in plans[condition].items()}
    retained.plan_json(entire, 'pair_manifest.json', pair)
    output.parent.mkdir(parents=True, exist_ok=True)
    require(shutil.disk_usage(output.parent).free >= sum(row['bytes'] for row in entire.values()) + reserve_bytes,
            'insufficient capacity for complete paired payload and reserve')
    with tempfile.TemporaryDirectory(prefix='.smc-offline-pair-', dir=output.parent) as temporary:
        staging = Path(temporary) / 'pair'
        for relative, row in entire.items():
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if 'source' in row:
                retained.copy_verified(row['source'], destination, row['sha256'])
            else:
                destination.write_bytes(row['content'])
        require(retained.file_inventory(staging) == retained.planned_inventory(entire), 'written payload differs from complete byte plan')
        staging.rename(output)
    return pair


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('prepared-root', 'author-source', 'paper', 'task', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--task-sha256', required=True, help='Trusted current canonical task pin, not an old registration hash.')
    parser.add_argument('--reserve-bytes', type=int, required=True,
                        help='Explicit operator reserve. This wave requires 64424509440; export requires separate resource authorization.')
    args = parser.parse_args(argv)
    print(json.dumps(export_pair(args.prepared_root, args.author_source, args.paper, args.task,
        args.task_sha256, args.output, reserve_bytes=args.reserve_bytes), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
