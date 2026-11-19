#!/usr/bin/env python3
"""Explicit full-panel improvement condition on the original SMC 20-ms panel.

This is trusted operator source, not a sandbox. Its ordered view-release API
does not prove that an external author never saw publicly available test data.
The original strict condition and numerical evaluator remain unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import types

HERE = Path(__file__).resolve().parent
TASK_ID = 'PAPER-SMC-RNN-2024'
INFERENCE_CONDITION = 'full_panel_offline_transductive_v1'
CONDITIONS = ('paper_data', 'paper_data_author_code_and_weights')
POLICY_SHA256 = 'f383e252c52fab1681451cd9247acb324d8ac7588099476155ce03fd92d2e75e'
TASK_SHA256 = '5b3b1008cca8f9106a5031ee9f15dfd028bd11121912316bd1fe788a32580c88'
PARENT_TASK_SHA256 = 'e99cf60035a156fdb7a0a3b61b539db387ae53b31f1d4be59da31f18d9346fbd'
LEGACY_SHA256 = 'a9ca90b9a62e706d5522fc8e52be0b6d2ab6fc01fb6b700c9cd00f8fff777fd5'
BASE_RELATIVE = 'benchmarks/paper/PAPER-SMC-RNN-2024/implementations/continuous-outcomes-v2/benchmark.py'
TASK_RELATIVE = 'benchmarks/paper/PAPER-SMC-RNN-2024/task.json'
TEST_INPUT = 'inputs/mc_maze/test/eval_input_20ms.h5'
MAX_FILE = 512 * 1024**2
MAX_META = 1024**2
ACTION_FLAGS = {'load': 'loaded', 'adapt': 'adapted', 'fine_tune': 'fine_tuned',
                'retrain': 'retrained', 'replace': 'replaced'}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def _load_source(path, expected):
    """Execute the authenticated bytes, not a second pathname read."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as handle:
        initial = os.fstat(handle.fileno())
        need(stat.S_ISREG(initial.st_mode) and 0 < initial.st_size <= MAX_META,
             'dependency is not a bounded ordinary source file')
        raw = handle.read(MAX_META + 1)
        final = os.fstat(handle.fileno())
    identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    need(len(raw) == initial.st_size and identity(initial) == identity(final)
         and hashlib.sha256(raw).hexdigest() == expected, 'dependency identity changed')
    module = types.ModuleType('_smc_full_panel_verified_legacy')
    module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


class FullPanelAPI:
    """Immutable source bindings with an explicit repository location.

    Locations are configurable; expected source, task and policy identities are
    fixed by this implementation. No legacy module globals are reassigned.
    """
    task_sha256 = TASK_SHA256
    policy_sha256 = POLICY_SHA256
    CONDITIONS = CONDITIONS

    def __init__(self, repository_root=None, component_root=HERE):
        self.repository_root = Path(repository_root or HERE.parents[4]).resolve(strict=True)
        self.component_root = Path(component_root).resolve(strict=True)
        self.base = self.legacy = _load_source(self.repository_root / BASE_RELATIVE, LEGACY_SHA256)
        self.io, self.source, self.retained = self.base.io, self.base.source, self.base.retained
        self.hash_file, self.read_json = self.base.hash_file, self.base.read_json
        self.task_path, self.policy_path = self.component_root / 'task.json', self.component_root / 'policy.json'
        self.load_policy()
        self.current_task(self.task_path, TASK_SHA256)

    def load_policy(self):
        policy, _ = self.read_json(self.policy_path, POLICY_SHA256)
        need(policy.get('schema') == 'smc_full_panel_offline_improvement_policy_v1'
             and policy.get('task_id') == TASK_ID
             and policy.get('inference_condition_id') == INFERENCE_CONDITION
             and set(policy.get('outcomes', {})) == {'improvement'}, 'wrong full-panel policy')
        old = self.base.load_policy()
        for key in ('metrics', 'conditions', 'smc_references', 'source_paper_published_context',
                    'uncertainty', 'later_literature_context'):
            need(policy[key] == old[key], 'original numerical comparison changed: ' + key)
        need(policy['outcomes']['improvement'] == old['outcomes']['improvement'],
             'original improvement endpoints changed')
        need(policy['official_assets']['allowlist_sha256'] == self.base.ASSET_SHA256,
             'official asset identity changed')
        need(policy['access']['cross_test_trial_inference_allowed'] is True
             and policy['access']['test_wide_adaptation_allowed'] is True
             and policy['access']['test_feedback_allowed'] is False,
             'wrong full-panel information condition')
        return policy

    def current_task(self, path, expected):
        need(expected == TASK_SHA256, 'unselected successor task identity')
        task, _ = self.read_json(path, TASK_SHA256)
        need(task.get('schema') == 'smc_full_panel_offline_improvement_task_v1'
             and task.get('task_id') == TASK_ID
             and task.get('inference_condition_id') == INFERENCE_CONDITION,
             'wrong separately versioned condition task')
        return task

    def validate_budget(self, budget):
        need(isinstance(budget, dict) and set(budget) == {'improvement'},
             'only the improvement resource profile is selected')
        # The old validator checks finite typed profile fields. The duplicate is
        # internal compatibility, not a second selected outcome or extra budget.
        profile = budget['improvement']
        self.base.validate_budget({'reproduction': profile, 'improvement': profile})
        selected = self.load_policy()['resource_profile']
        need(profile == {key: selected[key] for key in ('cpu_seconds', 'wall_seconds', 'memory_bytes', 'threads')},
             'resource profile differs from the selected full-panel condition')
        return budget

    def participant_instructions(self, panel, task_sha256, budget):
        policy = self.load_policy()
        return {'schema': 'smc_full_panel_participant_task_v1', 'task_id': TASK_ID,
            'inference_condition_id': INFERENCE_CONDITION, 'current_task_sha256': task_sha256,
            'policy_sha256': POLICY_SHA256, 'outcome': 'improvement',
            'access': policy['access'], 'resource_budget': budget,
            'outcomes': policy['outcomes'], 'uncertainty': policy['uncertainty'],
            'claim_limits': policy['claim_limits'], 'official_assets': policy['official_assets'],
            'method_order': 'Author using the development view, freeze program/assets/seed/adaptation procedure, then release the permitted full test-input view. Declared parameters may adapt during that frozen program.',
            'submission': 'One complete offline prediction file and a post-execution actual-use declaration. No target or score feedback before final submission.',
            'scope': 'Fixed-panel full-panel/offline improvement; neither faithful SMC-method reproduction nor fresh-trial/inductive generalization nor the original 5-ms NLB competition.',
            'execution_note': 'These interfaces authenticate material contents and ordering. Separate process custody and isolation are required; declarations do not prove prior blindness, actual adaptation or AI attribution.',
            'prediction_abi': {'format': 'HDF5', 'group': self.source.DATASET,
                'required_arrays': {key: panel['expected_shapes'][key] for key in sorted(self.source.REQUIRED_KEYS)},
                'optional_arrays': {key: panel['expected_shapes'][key] for key in sorted(self.source.OPTIONAL_KEYS)},
                'values': 'Finite nonnegative expected spike counts per 20-ms bin in complete original order.'},
            'target_exposure': policy['target_exposure']}

    def _plan(self, prepared_root, author_source, paper, task_path, task_sha256, budget, max_bytes):
        self.current_task(task_path, task_sha256)
        self.validate_budget(budget)
        parent = self.repository_root / TASK_RELATIVE
        need(self.hash_file(parent) == PARENT_TASK_SHA256, 'strict predecessor task changed')
        profile = budget['improvement']
        _, admitted = self.base._plan(prepared_root, author_source, paper, parent,
            PARENT_TASK_SHA256, {'reproduction': profile, 'improvement': profile}, max_bytes)
        # Only freshly admitted original source/input payloads are reused. No
        # existing v2 pair is accepted, transformed or relabelled as this export.
        plans, manifests = {}, {}
        replaced = {'registered_task.json', 'measurement_policy.json', 'resource_budget.json',
                    'task.json', 'delivery_manifest.json'}
        test_panel = json.loads(admitted[CONDITIONS[0] + '/inputs/mc_maze/test/panel.json']['content'])
        for condition in CONDITIONS:
            prefix = condition + '/'
            plan = {name[len(prefix):]: row for name, row in admitted.items()
                    if name.startswith(prefix) and name[len(prefix):] not in replaced}
            self.retained.plan_source(plan, 'registered_task.json', task_path, task_sha256)
            self.retained.plan_source(plan, 'measurement_policy.json', self.policy_path, POLICY_SHA256)
            self.retained.plan_json(plan, 'resource_budget.json', budget)
            self.retained.plan_json(plan, 'task.json', self.participant_instructions(test_panel, task_sha256, budget))
            manifest = {'schema': 'smc_full_panel_delivery_v1', 'condition': condition,
                'inference_condition_id': INFERENCE_CONDITION, 'current_task_sha256': task_sha256,
                'policy_sha256': POLICY_SHA256, 'files': self.retained.planned_inventory(plan)}
            self.retained.plan_json(plan, 'delivery_manifest.json', manifest)
            plans[condition], manifests[condition] = plan, manifest
        left = {row['path']: row['sha256'] for row in manifests[CONDITIONS[0]]['files']}
        pair = {'schema': 'smc_full_panel_pair_v1', 'task_id': TASK_ID,
            'inference_condition_id': INFERENCE_CONDITION, 'conditions': list(CONDITIONS),
            'policy_sha256': POLICY_SHA256, 'current_task_sha256': task_sha256,
            'shared_files': left, 'code_condition_additions': sorted(set(plans[CONDITIONS[1]]) - set(plans[CONDITIONS[0]])),
            'condition_manifest_sha256': {key: plans[key]['delivery_manifest.json']['sha256'] for key in CONDITIONS},
            'resource_budget': budget, 'execution_verified': False, 'AI_result': False}
        entire = {condition + '/' + name: row for condition in CONDITIONS for name, row in plans[condition].items()}
        self.retained.plan_json(entire, 'pair_manifest.json', pair)
        return pair, entire

    def _outside(self, output, source_root):
        output = Path(output).absolute()
        output = output.parent.resolve(strict=True) / output.name
        need(not output.exists() and not output.is_symlink(), 'destination already exists')
        need(not output.is_relative_to(Path(source_root).resolve(strict=True)), 'operator output must be outside source materials')
        need(output.name != '.git' and not any((p / '.git').exists() for p in (output, *output.parents)),
             'material output must remain outside Git worktrees')
        return output

    def _publish_plan(self, plan, output, max_bytes, *, reserve_bytes=0, inspect=None):
        need(self.base.positive_integer(max_bytes) and type(reserve_bytes) is int and reserve_bytes >= 0, 'invalid capacity bounds')
        size = sum(row['bytes'] for row in plan.values())
        need(size <= max_bytes and shutil.disk_usage(output.parent).free >= size + reserve_bytes,
             'complete material plan exceeds byte cap or free-space reserve')
        with tempfile.TemporaryDirectory(prefix='.smc-full-panel-', dir=output.parent) as temporary:
            stage = Path(temporary) / 'materials'
            stage.mkdir()
            remaining = max_bytes
            for name, row in plan.items():
                destination = stage / self.retained.safe_relative(name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if 'source' in row and row['bytes']:
                    remaining -= self.io._snapshot(row['source'], destination, row['sha256'], byte_budget=remaining)
                elif 'source' in row:
                    need(self.base.payload_hash(row['source'], 0) == row['sha256'], 'empty source changed')
                    destination.touch(exist_ok=False)
                    destination.chmod(0o400)
                else:
                    need(len(row['content']) == row['bytes'] and row['bytes'] <= remaining, 'metadata exceeds remaining cap')
                    destination.write_bytes(row['content'])
                    destination.chmod(0o400)
                    remaining -= row['bytes']
            need(self.base.inventory(stage, max_bytes) == self.retained.planned_inventory(plan), 'staged material differs from plan')
            if inspect:
                inspect(stage)
            need(not output.exists(), 'destination appeared')
            stage.rename(output)

    def export_pair(self, prepared_root, author_source, paper, task_path, task_sha256, budget_path,
                    output, *, max_bytes, reserve_bytes):
        budget = self.validate_budget(self.read_json(budget_path)[0])
        output = self._outside(output, prepared_root)
        pair, plan = self._plan(prepared_root, author_source, paper, task_path, task_sha256, budget, max_bytes)
        self._publish_plan(plan, output, max_bytes, reserve_bytes=reserve_bytes,
            inspect=lambda stage: self.inspect_pair(stage / 'pair_manifest.json', self.hash_file(stage / 'pair_manifest.json'),
                                                    task_path, task_sha256, max_bytes=max_bytes))
        return pair

    def inspect_pair(self, pair_path, expected_sha256, task_path, task_sha256, *, max_bytes):
        self.current_task(task_path, task_sha256)
        pair_path = Path(pair_path)
        need(pair_path.name == 'pair_manifest.json', 'canonical pair manifest name required')
        pair, _ = self.read_json(pair_path, expected_sha256)
        need(pair.get('schema') == 'smc_full_panel_pair_v1'
             and pair.get('inference_condition_id') == INFERENCE_CONDITION
             and pair.get('policy_sha256') == POLICY_SHA256
             and pair.get('current_task_sha256') == task_sha256, 'stale or wrong full-panel material identity')
        budget = self.validate_budget(pair['resource_budget'])
        root = pair_path.parent.resolve(strict=True)
        expected, plan = self._plan(root / CONDITIONS[0] / 'inputs',
            root / CONDITIONS[1] / 'official_source', root / CONDITIONS[0] / 'paper.pdf',
            task_path, task_sha256, budget, max_bytes)
        need(pair == expected, 'full-panel pair metadata differs from fresh original-material plan')
        need(self.base.inventory(root, max_bytes) == self.retained.planned_inventory(plan),
             'full-panel physical inventory differs; targets, extra inputs and stale metadata are forbidden')
        panel = json.loads(plan[CONDITIONS[0] + '/inputs/mc_maze/test/panel.json']['content'])
        return {'schema': 'smc_full_panel_material_admission_v1', 'materials_valid': True,
            'pair': pair, 'policy': self.load_policy(), 'panels': {key: panel for key in CONDITIONS},
            'conditions': list(CONDITIONS), 'execution_verified': False, 'AI_result': False}

    def _condition_files(self, pair_path, pair, condition):
        need(condition in CONDITIONS, 'unknown access condition')
        root = Path(pair_path).parent.resolve() / condition
        manifest_path = self.retained.regular_beneath(root, 'delivery_manifest.json')
        manifest, _ = self.read_json(manifest_path, pair['condition_manifest_sha256'][condition])
        return root, manifest['files']

    def _view_plan(self, root, rows):
        plan = {}
        for row in rows:
            self.retained.plan_source(plan, row['path'], self.retained.regular_beneath(root, row['path']), row['sha256'])
        return plan

    def prepare_development_view(self, pair_path, pair_sha256, task_path, task_sha256, condition, output, *, max_bytes):
        admission = self.inspect_pair(pair_path, pair_sha256, task_path, task_sha256, max_bytes=max_bytes)
        root, rows = self._condition_files(pair_path, admission['pair'], condition)
        need(sum(row['path'] == TEST_INPUT for row in rows) == 1, 'exact held-out test-input entry required')
        plan = self._view_plan(root, [row for row in rows if row['path'] != TEST_INPUT])
        record = {'schema': 'smc_full_panel_development_view_v1', 'task_id': TASK_ID,
            'inference_condition_id': INFERENCE_CONDITION, 'condition': condition,
            'current_task_sha256': task_sha256, 'policy_sha256': POLICY_SHA256, 'pair_sha256': pair_sha256,
            'excluded_paths': [TEST_INPUT], 'files': self.retained.planned_inventory(plan),
            'test_input_delivered': False, 'earlier_authoring_blindness_verified': False}
        self.retained.plan_json(plan, 'development_manifest.json', record)
        destination = self._outside(output, Path(pair_path).parent)
        self._publish_plan(plan, destination, max_bytes)
        return record

    def inspect_development_view(self, manifest_path, expected, pair_path, pair_sha256,
                                 task_path, task_sha256, condition, *, max_bytes):
        admission = self.inspect_pair(pair_path, pair_sha256, task_path, task_sha256, max_bytes=max_bytes)
        need(Path(manifest_path).name == 'development_manifest.json', 'canonical development manifest name required')
        record, _ = self.read_json(manifest_path, expected)
        _, rows = self._condition_files(pair_path, admission['pair'], condition)
        wanted = sorted((row for row in rows if row['path'] != TEST_INPUT), key=lambda row: row['path'])
        exact = {'schema': 'smc_full_panel_development_view_v1', 'task_id': TASK_ID,
            'inference_condition_id': INFERENCE_CONDITION, 'condition': condition,
            'current_task_sha256': task_sha256, 'policy_sha256': POLICY_SHA256, 'pair_sha256': pair_sha256,
            'excluded_paths': [TEST_INPUT], 'files': wanted, 'test_input_delivered': False,
            'earlier_authoring_blindness_verified': False}
        need(record == exact, 'development manifest is not the exact TEST-input-excluding view')
        actual = self.base.inventory(Path(manifest_path).parent, max_bytes)
        self_row = {'path': 'development_manifest.json', 'bytes': Path(manifest_path).stat().st_size, 'sha256': expected}
        need(actual == sorted(wanted + [self_row], key=lambda row: row['path']), 'development view contains changed or extra files')
        return record

    def _identity(self, document, schema, condition):
        need(isinstance(document, dict) and document.get('schema') == schema
             and document.get('condition') == condition and condition in CONDITIONS
             and document.get('inference_condition_id') == INFERENCE_CONDITION
             and document.get('role') in ('participant', 'construction_control'), 'wrong method declaration identity')
        need(isinstance(document.get('method_id'), str) and 0 < len(document['method_id']) <= 200
             and self.io.digest(document.get('source_sha256')) and type(document.get('seed')) is int
             and document['seed'] >= 0, 'method id, program identity and seed required')

    @staticmethod
    def _text(value):
        return isinstance(value, str) and 0 < len(value) <= 8192 and value.strip() == value

    def validate_plan(self, document, condition):
        self._identity(document, 'smc_full_panel_method_plan_v1', condition)
        need(set(document) == {'schema', 'role', 'method_id', 'condition', 'inference_condition_id',
            'source_sha256', 'seed', 'adaptation_procedure', 'parameter_adaptation_planned',
            'behavior_guided_fitting_planned', 'behavior_guided_selection_planned', 'planned_asset_actions'},
            'unexpected planned-method fields')
        need(self._text(document['adaptation_procedure']), 'freeze the complete adaptation and cross-trial inference procedure')
        for flag in ('parameter_adaptation_planned', 'behavior_guided_fitting_planned', 'behavior_guided_selection_planned'):
            need(type(document[flag]) is bool, 'planned method flags must be booleans')
        usage = document['planned_asset_actions']
        need(isinstance(usage, list), 'asset plan must be a list')
        converted = []
        for row in usage:
            need(isinstance(row, dict) and set(row) == {'path', 'sha256'} | set(ACTION_FLAGS), 'wrong planned asset actions')
            converted.append({'path': row['path'], 'sha256': row['sha256'],
                              **{actual: row[planned] for planned, actual in ACTION_FLAGS.items()}})
        self.base.validate_asset_usage(converted, condition, document['role'])
        return document

    def validate_actual(self, document, condition, method, method_sha256):
        self._identity(document, 'smc_full_panel_actual_use_v1', condition)
        need(set(document) == {'schema', 'role', 'method_id', 'condition', 'inference_condition_id',
            'source_sha256', 'seed', 'method_freeze_sha256', 'parameter_adaptation_performed',
            'actual_adaptation_description', 'behavior_guided_fitting', 'behavior_guided_selection', 'asset_usage'},
            'unexpected actual-use fields')
        plan = self.validate_plan(method['plan'], condition)
        need(document['method_freeze_sha256'] == method_sha256
             and all(document[key] == plan[key] for key in ('role', 'method_id', 'source_sha256', 'seed')),
             'actual-use declaration is not the frozen method')
        need(self._text(document['actual_adaptation_description']), 'actual panel use/adaptation description required')
        for actual, planned in (('parameter_adaptation_performed', 'parameter_adaptation_planned'),
                                ('behavior_guided_fitting', 'behavior_guided_fitting_planned'),
                                ('behavior_guided_selection', 'behavior_guided_selection_planned')):
            need(type(document[actual]) is bool and (not document[actual] or plan[planned]),
                 'actual adaptation exceeds its frozen plan')
        self.base.validate_asset_usage(document['asset_usage'], condition, document['role'])
        planned = {row['path']: row for row in plan['planned_asset_actions']}
        for row in document['asset_usage']:
            need(all(not row[actual] or planned[row['path']][flag] for flag, actual in ACTION_FLAGS.items()),
                 'actual official-asset use exceeds its frozen plan')
        return document

    def freeze_method(self, dev_manifest_path, dev_sha256, pair_path, pair_sha256, task_path,
                      task_sha256, condition, program, plan_path, selected_artifacts, output, *, max_bytes):
        self.inspect_development_view(dev_manifest_path, dev_sha256, pair_path, pair_sha256,
            task_path, task_sha256, condition, max_bytes=max_bytes)
        declaration, declaration_sha = self.read_json(plan_path)
        self.validate_plan(declaration, condition)
        need(isinstance(selected_artifacts, dict) and len(selected_artifacts) <= 128, 'bounded candidate artifact map required')
        output = self._outside(output, Path(pair_path).parent)
        payload_root = output.parent / (output.name + '.materials')
        need(not payload_root.exists() and not payload_root.is_symlink(), 'method material destination exists')
        plan = {}
        self.retained.plan_source(plan, 'programme.py', program, declaration['source_sha256'])
        need(plan['programme.py']['bytes'] > 0, 'empty candidate program')
        provenance = {}
        official_hashes = {row['sha256'] for row in self.base.asset_allowlist()['files']}
        for name, selected in selected_artifacts.items():
            relative = str(self.retained.safe_relative(name))
            need(relative == name and relative != 'programme.py', 'invalid candidate artifact name')
            need(isinstance(selected, dict) and set(selected) == {'path', 'development_manifest_sha256', 'derivation'}
                 and selected['development_manifest_sha256'] == dev_sha256 and self._text(selected['derivation']),
                 'candidate artifacts require a declared derivation from this admitted development view')
            digest = self.base.payload_hash(selected['path'], MAX_FILE)
            need(digest not in official_hashes, 'released assets must use the declared assisted allowlist, not candidate provenance')
            self.retained.plan_source(plan, 'artifacts/' + relative, selected['path'], digest)
            provenance[name] = {'kind': 'candidate_derived', 'development_manifest_sha256': dev_sha256,
                'derivation': selected['derivation'], 'derivation_verified': False}
        self._publish_plan(plan, payload_root, max_bytes)
        def row(name):
            item = plan[name]
            return {'path': str(payload_root / name), 'bytes': item['bytes'], 'sha256': item['sha256']}
        record = {'schema': 'smc_full_panel_method_freeze_v1', 'task_id': TASK_ID,
            'inference_condition_id': INFERENCE_CONDITION, 'condition': condition, 'outcome': 'improvement',
            'current_task_sha256': task_sha256, 'pair_sha256': pair_sha256, 'policy_sha256': POLICY_SHA256,
            'development_manifest': {'path': str(Path(dev_manifest_path).resolve()), 'sha256': dev_sha256},
            'program': row('programme.py'), 'selected_artifacts': {name: row('artifacts/' + name) for name in selected_artifacts},
            'candidate_artifact_provenance': provenance,
            'plan': declaration, 'plan_sha256': declaration_sha, 'plan_body_sha256': self.base.body_digest(declaration),
            'test_inputs_released': False, 'pre_test_authoring_isolation_verified': False}
        self.io.write_new_json(output, record)
        return record

    def inspect_method(self, method_path, method_sha256, pair_path, pair_sha256, task_path,
                       task_sha256, condition, *, max_bytes):
        record, _ = self.read_json(method_path, method_sha256)
        need(set(record) == {'schema', 'task_id', 'inference_condition_id', 'condition', 'outcome',
            'current_task_sha256', 'pair_sha256', 'policy_sha256', 'development_manifest', 'program',
            'selected_artifacts', 'candidate_artifact_provenance', 'plan', 'plan_sha256', 'plan_body_sha256', 'test_inputs_released',
            'pre_test_authoring_isolation_verified'}, 'unexpected method-freeze fields')
        need(record['schema'] == 'smc_full_panel_method_freeze_v1' and record['task_id'] == TASK_ID
             and record['inference_condition_id'] == INFERENCE_CONDITION and record['outcome'] == 'improvement'
             and record['condition'] == condition and record['current_task_sha256'] == task_sha256
             and record['policy_sha256'] == POLICY_SHA256 and record['pair_sha256'] == pair_sha256
             and record['test_inputs_released'] is False and record['pre_test_authoring_isolation_verified'] is False,
             'wrong method-freeze identity or unsupported prior-isolation claim')
        dev = record['development_manifest']
        need(set(dev) == {'path', 'sha256'}, 'invalid development-view binding')
        self.inspect_development_view(dev['path'], dev['sha256'], pair_path, pair_sha256,
            task_path, task_sha256, condition, max_bytes=max_bytes)
        self.validate_plan(record['plan'], condition)
        need(record['plan_body_sha256'] == self.base.body_digest(record['plan']) and self.io.digest(record['plan_sha256']),
             'frozen planned method changed')
        artifacts = record['selected_artifacts']
        need(isinstance(artifacts, dict) and len(artifacts) <= 128, 'invalid frozen candidate artifact map')
        provenance = record['candidate_artifact_provenance']
        need(isinstance(provenance, dict) and set(provenance) == set(artifacts), 'incomplete candidate artifact provenance')
        official_hashes = {row['sha256'] for row in self.base.asset_allowlist()['files']}
        for name, declared in provenance.items():
            need(isinstance(declared, dict) and set(declared) == {'kind', 'development_manifest_sha256', 'derivation', 'derivation_verified'}
                 and declared['kind'] == 'candidate_derived' and declared['development_manifest_sha256'] == dev['sha256']
                 and self._text(declared['derivation']) and declared['derivation_verified'] is False
                 and artifacts[name]['sha256'] not in official_hashes,
                 'unbound, external or falsely verified candidate artifact provenance')
        root = Path(method_path).parent.resolve() / (Path(method_path).name + '.materials')
        wanted = []
        for name, row in [('programme.py', record['program'])] + [('artifacts/' + name, row) for name, row in artifacts.items()]:
            name = str(self.retained.safe_relative(name))
            need(set(row) == {'path', 'bytes', 'sha256'} and Path(row['path']) == root / name
                 and type(row['bytes']) is int and 0 <= row['bytes'] <= MAX_FILE and self.io.digest(row['sha256']),
                 'frozen method artifact is not an exact bounded snapshot')
            wanted.append({'path': name, 'bytes': row['bytes'], 'sha256': row['sha256']})
        need(record['program']['bytes'] > 0 and record['program']['sha256'] == record['plan']['source_sha256'],
             'frozen program differs from planned method')
        need(self.base.inventory(root, max_bytes) == sorted(wanted, key=lambda row: row['path']),
             'frozen program/artifacts changed or contain extras')
        return record

    def release_inference_view(self, method_path, method_sha256, pair_path, pair_sha256,
                               task_path, task_sha256, condition, output, *, max_bytes):
        self.inspect_method(method_path, method_sha256, pair_path, pair_sha256,
            task_path, task_sha256, condition, max_bytes=max_bytes)
        pair, _ = self.read_json(pair_path, pair_sha256)
        root, rows = self._condition_files(pair_path, pair, condition)
        plan = self._view_plan(root, rows)
        self.retained.plan_source(plan, 'delivery_manifest.json', root / 'delivery_manifest.json',
                                  pair['condition_manifest_sha256'][condition])
        record = self._release_record(self.retained.planned_inventory(plan), method_sha256,
                                      pair_sha256, task_sha256, condition)
        self.retained.plan_json(plan, 'inference_manifest.json', record)
        self._publish_plan(plan, self._outside(output, Path(pair_path).parent), max_bytes,
            inspect=lambda stage: self.inspect_method(method_path, method_sha256, pair_path, pair_sha256,
                task_path, task_sha256, condition, max_bytes=max_bytes))
        return record

    @staticmethod
    def _release_record(files, method_sha256, pair_sha256, task_sha256, condition):
        return {'schema': 'smc_full_panel_inference_view_v1', 'task_id': TASK_ID,
            'inference_condition_id': INFERENCE_CONDITION, 'condition': condition,
            'current_task_sha256': task_sha256, 'policy_sha256': POLICY_SHA256,
            'pair_sha256': pair_sha256, 'method_freeze_sha256': method_sha256, 'files': files,
            'release_after_method_freeze': True, 'earlier_authoring_blindness_verified': False}

    def inspect_release(self, release_manifest_path, release_sha256, method_path, method_sha256,
                        pair_path, pair_sha256, task_path, task_sha256, condition, *, max_bytes):
        method = self.inspect_method(method_path, method_sha256, pair_path, pair_sha256,
            task_path, task_sha256, condition, max_bytes=max_bytes)
        need(Path(release_manifest_path).name == 'inference_manifest.json', 'canonical inference manifest name required')
        record, _ = self.read_json(release_manifest_path, release_sha256)
        pair, _ = self.read_json(pair_path, pair_sha256)
        original_root, rows = self._condition_files(pair_path, pair, condition)
        manifest_path = original_root / 'delivery_manifest.json'
        rows = sorted(rows + [{'path': 'delivery_manifest.json', 'bytes': manifest_path.stat().st_size,
            'sha256': pair['condition_manifest_sha256'][condition]}], key=lambda row: row['path'])
        need(record == self._release_record(rows, method_sha256, pair_sha256, task_sha256, condition),
             'inference view is not bound to the exact frozen method and permitted full panel')
        root = Path(release_manifest_path).parent.resolve()
        own = {'path': 'inference_manifest.json', 'bytes': Path(release_manifest_path).stat().st_size, 'sha256': release_sha256}
        need(self.base.inventory(root, max_bytes) == sorted(rows + [own], key=lambda row: row['path']),
             'released inference view changed or contains extra observations')
        return {'manifest': record, 'root': str(root), 'method': method}

    def freeze(self, pair_path, pair_sha256, task_path, task_sha256, condition, outcome, submissions,
               declaration_path, output, *, max_bytes, method_path, method_sha256):
        need(outcome == 'improvement' and isinstance(submissions, dict) and set(submissions) == {'offline'},
             'this condition accepts exactly one complete offline improvement result')
        method = self.inspect_method(method_path, method_sha256, pair_path, pair_sha256,
            task_path, task_sha256, condition, max_bytes=max_bytes)
        admission = self.inspect_pair(pair_path, pair_sha256, task_path, task_sha256, max_bytes=max_bytes)
        actual, actual_sha = self.read_json(declaration_path)
        self.validate_actual(actual, condition, method, method_sha256)
        output = self._outside(output, Path(pair_path).parent)
        path = Path(submissions['offline']).absolute()
        digest = self.hash_file(path, MAX_FILE)
        self.source.validate_submission(path, admission['panels'][condition])
        need(self.hash_file(path, MAX_FILE) == digest, 'prediction changed during validation')
        record = {'schema': 'smc_full_panel_prediction_freeze_v1', 'task_id': TASK_ID,
            'inference_condition_id': INFERENCE_CONDITION, 'condition': condition, 'outcome': outcome,
            'current_task_sha256': task_sha256, 'pair_sha256': pair_sha256, 'policy_sha256': POLICY_SHA256,
            'method_freeze': {'path': str(Path(method_path).resolve()), 'sha256': method_sha256},
            'declaration': actual, 'declaration_sha256': actual_sha, 'declaration_body_sha256': self.base.body_digest(actual),
            'submissions': {'offline': {'path': str(path), 'sha256': digest}},
            'target_accessed': False, 'execution_verified': False, 'AI_attribution_verified': False}
        self.io.write_new_json(output, record)
        return record

    def compare_metrics(self, results):
        # Reuse the unchanged arithmetic and all retained source-paper vectors.
        original = self.base.compare_metrics('improvement', results)
        policy = self.load_policy()
        return {**original, 'schema': 'smc_full_panel_comparison_v1',
            'policy_sha256': POLICY_SHA256, 'inference_condition_id': INFERENCE_CONDITION,
            'numerical_reference_policy_sha256': self.base.POLICY_SHA256,
            'claim_limits': policy['claim_limits'], 'inference_scope': 'fixed_panel_full_panel_offline',
            'inductive_generalization_established': False}

    def score(self, frozen_path, frozen_sha256, pair_path, pair_sha256, task_path, task_sha256,
              condition_root, target, evaluator, output, *, scratch_bytes, max_bytes,
              method_path, method_sha256):
        need(self.base.positive_integer(scratch_bytes), 'positive prediction snapshot cap required')
        output = self._outside(output, Path(pair_path).parent)
        admission = self.inspect_pair(pair_path, pair_sha256, task_path, task_sha256, max_bytes=max_bytes)
        record, _ = self.read_json(frozen_path, frozen_sha256)
        need(set(record) == {'schema', 'task_id', 'inference_condition_id', 'condition', 'outcome',
            'current_task_sha256', 'pair_sha256', 'policy_sha256', 'method_freeze', 'declaration',
            'declaration_sha256', 'declaration_body_sha256', 'submissions', 'target_accessed',
            'execution_verified', 'AI_attribution_verified'}, 'unexpected prediction-freeze fields')
        need(record['schema'] == 'smc_full_panel_prediction_freeze_v1' and record['task_id'] == TASK_ID
             and record['inference_condition_id'] == INFERENCE_CONDITION and record['outcome'] == 'improvement'
             and record['current_task_sha256'] == task_sha256 and record['pair_sha256'] == pair_sha256
             and record['policy_sha256'] == POLICY_SHA256, 'stale or wrong frozen result identity')
        condition = record['condition']
        method = self.inspect_method(method_path, method_sha256, pair_path, pair_sha256,
            task_path, task_sha256, condition, max_bytes=max_bytes)
        need(record['method_freeze'] == {'path': str(Path(method_path).resolve()), 'sha256': method_sha256},
             'prediction freeze selects a different method')
        self.validate_actual(record['declaration'], condition, method, method_sha256)
        need(record['declaration_body_sha256'] == self.base.body_digest(record['declaration'])
             and self.io.digest(record['declaration_sha256']) and record['target_accessed'] is False
             and record['execution_verified'] is False and record['AI_attribution_verified'] is False,
             'actual-use identity changed or unsupported result provenance')
        need(Path(condition_root).resolve(strict=True) == Path(pair_path).parent.resolve() / condition,
             'wrong original participant condition root')
        need(not Path(target).parent.resolve(strict=True).is_relative_to(Path(pair_path).parent.resolve()),
             'protected target must remain outside paired materials')
        need(set(record['submissions']) == {'offline'}, 'complete offline prediction required')
        row = record['submissions']['offline']
        need(set(row) == {'path', 'sha256'} and self.io.digest(row['sha256']), 'invalid prediction reference')
        need(Path(target).parent.resolve(strict=True) != Path(row['path']).parent.resolve(strict=True),
             'protected target must remain separate from predictions')
        evaluator = Path(evaluator)
        evaluator = evaluator / 'nlb_tools/evaluation.py' if evaluator.is_dir() else evaluator
        need(self.hash_file(evaluator) == self.source.SCORER_SHA256, 'wrong original evaluator')
        original = self.source.load_original_scorer(evaluator)
        with tempfile.TemporaryDirectory(prefix='.smc-full-panel-score-', dir=output.parent) as temporary:
            snapshot = Path(temporary) / 'offline.h5'
            self.io._snapshot(row['path'], snapshot, row['sha256'], byte_budget=scratch_bytes)
            self.source.validate_submission(snapshot, admission['panels'][condition])
            # Full predictions are snapshotted and validated before first target access.
            need(self.hash_file(target, self.io.MAX_TARGET_BYTES) == self.source.TARGET_SHA256, 'wrong original test targets')
            need(not os.path.samefile(target, row['path']), 'target aliases candidate predictions')
            raw = original.evaluate(str(target), str(snapshot))
            need(isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], dict)
                 and set(raw[0]) == {self.source.DATASET + '_split'}, 'wrong original evaluation panel')
            values = raw[0][self.source.DATASET + '_split']
            need(isinstance(values, dict) and set(values) == set(self.source.METRICS), 'incomplete original metrics')
            results = {'offline': {metric: float(values[metric]) for metric in self.source.METRICS}}
            need(self.hash_file(target, self.io.MAX_TARGET_BYTES) == self.source.TARGET_SHA256
                 and self.hash_file(snapshot, MAX_FILE) == row['sha256'], 'evaluation inputs changed during scoring')
        # Reauthenticate all successor identities and frozen method after evaluation.
        self.inspect_method(method_path, method_sha256, pair_path, pair_sha256,
            task_path, task_sha256, condition, max_bytes=max_bytes)
        need(self.hash_file(frozen_path) == frozen_sha256, 'prediction-freeze identity changed during scoring')
        report = self.compare_metrics(results)
        report.update(task_id=TASK_ID, condition=condition, role=record['declaration']['role'],
            method_id=record['declaration']['method_id'], prediction_freeze_sha256=frozen_sha256,
            current_task_sha256=task_sha256, pair_sha256=pair_sha256, method_freeze_sha256=method_sha256,
            target_sha256=self.source.TARGET_SHA256, evaluator_sha256=self.source.SCORER_SHA256,
            declaration=record['declaration'], planned_method=method['plan'], submissions=record['submissions'],
            execution_verified=False, AI_attribution_verified=False, pre_test_authoring_isolation_verified=False,
            dependency_versions={name: importlib.metadata.version(name) for name in ('numpy', 'scipy', 'scikit-learn', 'h5py')},
            target_exposure=admission['policy']['target_exposure'])
        self.io.write_new_json(output, report)
        return report


def build(repository_root=None):
    return FullPanelAPI(repository_root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository-root', type=Path)
    parser.add_argument('operation', choices=('prepare', 'inspect', 'development', 'freeze-method', 'release', 'inspect-release', 'freeze', 'score'))
    parser.add_argument('--request', type=Path, required=True,
                        help='Trusted operator JSON mapping of the selected API arguments; not participant code.')
    args = parser.parse_args(argv)
    api = build(args.repository_root)
    request, _ = api.read_json(args.request)
    need(isinstance(request, dict), 'operator request must be a mapping')
    methods = {'prepare': api.export_pair, 'inspect': api.inspect_pair, 'development': api.prepare_development_view,
        'freeze-method': api.freeze_method, 'release': api.release_inference_view, 'inspect-release': api.inspect_release,
        'freeze': api.freeze, 'score': api.score}
    result = methods[args.operation](**request)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
