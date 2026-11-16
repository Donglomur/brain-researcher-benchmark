#!/usr/bin/env python3
"""Invented source-control bindings only: no real assignments or scientific data."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location('study_binding_validator', Path(__file__).with_name('validate_study.py'))
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def make(track):
    artifacts = {}
    def artifact(name, content=None):
        raw = validator.canonical({'generated_metadata': name}) if content is None else content
        review = validator.canonical({'generated_review_only': name})
        artifacts[name] = {'role': 'Generated control metadata for ' + name,
            'pin': {'locator': 'urn:generated-control:' + name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()},
            'privacy': 'evaluator_metadata',
            'review': {'author_id': 'GENERATED-AUTHOR', 'reviewer_id': 'GENERATED-REVIEWER', 'independence_declared': True,
                'evidence': {'locator': 'urn:generated-review:' + name, 'bytes': len(review), 'sha256': hashlib.sha256(review).hexdigest()}}}
        return name
    common = artifact('common-information')
    information = artifact('information-policy')
    analysis_code = artifact('analysis-code')
    missingness = artifact('missingness-policy')
    hardware = artifact('hardware-description')
    phases = validator.PAPER_PHASES if track == 'paper' else validator.NEURAL_PHASES
    budgets = []
    def budget(name, calls=0):
        budgets.append({'id': name, 'hardware_artifact': hardware, 'measured_reference_artifact': artifact(name + '-invented-reference'),
            'wall_seconds': 120, 'cpu_seconds': 60, 'gpu_seconds': 0, 'peak_memory_bytes': 1048576,
            'model_calls': calls, 'llm_input_tokens': calls * 100, 'llm_output_tokens': calls * 10,
            'money_limit_minor_units': 0, 'currency': 'USD', 'pricing_timestamp': '2000-01-01T00:00:00Z'})
        return name
    arms = []
    if track == 'paper':
        phase_budgets = {phase: [budget('budget-' + phase, 10)] for phase in phases}
        for name in ('paper_data', 'paper_data_code'):
            arms.append({'id': name, 'mode': 'reconstruct_then_improve', 'common_information_artifact': common,
                'information_policy_artifact': information,
                'official_code_artifact': artifact('sanitized-code') if name.endswith('_code') else None,
                'numerical_tools_artifact': None, 'specialist_tool_artifact': None,
                'adaptation_policy_artifact': None, 'frozen_policy_artifact': None,
                'budget_ids': {phase: list(ids) for phase, ids in phase_budgets.items()}})
        definitions = [('official_code_reproduction', ['paper_data_code', 'paper_data'], 'reproduction', ['official_code_artifact']),
                       ('official_code_end_to_end_improvement', ['paper_data_code', 'paper_data'], 'improvement_confirmation', ['official_code_artifact'])]
        primary = ['official_code_reproduction']
        search_budget = phase_budgets['improvement_development'][0]
        policy = {'paper': {'reproduction_locked_before_improvement': True, 'carry_unused_reproduction_budget': False,
            'candidate_and_analysis_locked_before_confirmation': True,
            'original_method_comparator_artifact': artifact('rerun-original-method'), 'same_case_resource_comparator': True,
            'improvement_decision_rule_artifact': artifact('improvement-decision'),
            'contemporary_comparator_policy_artifact': artifact('contemporary-comparator-policy'),
            'novelty_review_policy_artifact': artifact('novelty-review-policy'),
            'fidelity_improvement_frontier_claims_separate': True}, 'neural': None}
    else:
        development, numerical, live = budget('development-common', 10), budget('numerical-common'), budget('live-llm', 10)
        tools, specialist, adaptation = artifact('numerical-tools'), artifact('specialist-checkpoint-interface'), artifact('adaptation-and-reset')
        for name in ('program_numerical', 'investigator_numerical', 'program_specialist', 'investigator_specialist'):
            investigate = name.startswith('investigator_')
            arms.append({'id': name, 'mode': 'case_investigation' if investigate else 'frozen_program',
                'common_information_artifact': common, 'information_policy_artifact': information,
                'official_code_artifact': None, 'numerical_tools_artifact': tools,
                'specialist_tool_artifact': specialist if name.endswith('_specialist') else None,
                'adaptation_policy_artifact': adaptation, 'frozen_policy_artifact': artifact(name + '-policy-lock'),
                'budget_ids': {'development': [development], 'assessment': [numerical, live] if investigate else [numerical]}})
        definitions = [('live_given_numerical', ['investigator_numerical', 'program_numerical'], 'assessment', ['mode', 'live_llm_budget']),
                       ('live_given_specialist', ['investigator_specialist', 'program_specialist'], 'assessment', ['mode', 'live_llm_budget']),
                       ('specialist_given_program', ['program_specialist', 'program_numerical'], 'assessment', ['specialist_tool_artifact']),
                       ('specialist_given_investigator', ['investigator_specialist', 'investigator_numerical'], 'assessment', ['specialist_tool_artifact'])]
        primary = ['live_given_numerical']
        search_budget = development
        policy = {'paper': None, 'neural': {'live_llm_cost_is_additional': True, 'equal_total_expenditure_claim': False,
            'assessment_global_updates_allowed': False, 'case_reset_policy_artifact': artifact('case-reset-policy'),
            'policy_construction_protocol_artifact': artifact('common-policy-construction'),
            'amortization_case_count': 4, 'development_cost_included': True, 'inference_cost_included': True,
            'specialist_training_cost_policy_artifact': artifact('specialist-training-cost'),
            'cost_curve_policy_artifact': artifact('cost-curves'), 'simple_reference_artifact': artifact('simple-reference'),
            'specialist_reference_artifact': artifact('specialist-reference'), 'context_control_artifact': artifact('context-control'),
            'disruption_validity_artifact': artifact('disruption-validity'), 'direct_signal_extension_selected': False}}
    tasks, manifests, units, groups, exposure_status = [], [], [], {}, {}
    for task_index in range(2):
        task_id, family = 'GENERATED-TASK-' + str(task_index), 'GENERATED-FAMILY-' + str(task_index)
        revision = artifact(task_id + '-revision')
        tasks.append({'id': task_id, 'revision_artifact': revision, 'source_family_id': family,
            'endpoints': [{'id': task_id + '-endpoint', 'metric': 'Invented fraction for code tests',
                           'direction': 'higher_is_better', 'units': 'Generated dimensionless fraction'}]})
        for unit_index in range(2):
            unit = task_id + '-person-' + str(unit_index)
            units.append({'id': unit, 'kind': 'Generated participant', 'definition_artifact': artifact(unit + '-definition')})
        for phase in phases:
            manifest_id = task_id + '-' + phase
            cases = []
            for case_index in range(2):
                unit = task_id + '-person-' + str(case_index)
                case_id = 'GENERATED-CASE-' + str(case_index)
                exposure_id = manifest_id + '-exposure-' + str(case_index)
                group_names = [unit + '-group', family + '-group', 'GENERATED-STIMULUS-' + str(case_index)]
                cases.append({'id': case_id, 'independent_unit_id': unit, 'exposure_unit_id': exposure_id,
                              'dependence_group_ids': group_names})
                exposure_status[exposure_id] = 'unexposed_declared' if phase == phases[-1] else 'public_or_development_exposed'
                for group_name, kind in zip(group_names, ('participant', 'source_family', 'stimulus')):
                    group = groups.setdefault(group_name, {'id': group_name, 'kind': kind, 'case_keys': [],
                                                           'evidence_artifact': artifact(group_name + '-basis')})
                    group['case_keys'].append(manifest_id + '/' + case_id)
            manifest = {'id': manifest_id, 'task_id': task_id, 'task_revision_sha256': artifacts[revision]['pin']['sha256'],
                        'phase': phase, 'artifact': manifest_id + '-metadata', 'cases': cases}
            artifact(manifest['artifact'], validator.canonical(validator.case_content(manifest)))
            manifests.append(manifest)
    assignments = []
    for manifest in manifests:
        for repeat in range(2):
            pair_id = manifest['id'] + '-pair-' + str(repeat)
            for index, arm in enumerate(arms):
                assignments.append({'id': pair_id + '-' + arm['id'], 'pair_id': pair_id, 'arm_id': arm['id'],
                    'task_id': manifest['task_id'], 'task_revision_sha256': manifest['task_revision_sha256'],
                    'model_scaffold_id': 'GENERATED-MODEL-SCAFFOLD', 'run_index': repeat, 'phase': manifest['phase'],
                    'case_manifest_id': manifest['id'], 'case_manifest_sha256': artifacts[manifest['artifact']]['pin']['sha256'],
                    'condition_order': (index + repeat) % len(arms), 'budget_ids': list(arm['budget_ids'][manifest['phase']])})
    endpoints = [task['endpoints'][0]['id'] for task in tasks]
    contrasts = [{'id': name, 'arms': pair, 'phase': phase, 'primary': name in primary,
        'declared_intervention': intervention, 'analysis_artifact': analysis_code,
        'estimand': {'description': 'Generated difference for validator controls, never a proposed scientific estimand',
            'effect_order': 'first_arm_minus_second_arm', 'endpoint_ids': list(endpoints),
            'denominator': 'all_assigned_pairs_in_contrast_phase', 'assigned_pairs': 4,
            'failures_in_denominator': True, 'missingness_policy_artifact': missingness,
            'minimum_effect_by_endpoint': {endpoint: 0.1 for endpoint in endpoints},
            'endpoint_applicability': {task['endpoints'][0]['id']: {
                'task_id': task['id'], 'phase': phase,
                'assigned_pair_ids': sorted({row['pair_id'] for row in assignments if row['task_id'] == task['id'] and row['phase'] == phase}),
                'assigned_pairs': 2, 'denominator': 'all_assigned_pairs_for_endpoint_task_and_phase'} for task in tasks}}}
        for name, pair, phase, intervention in definitions]
    binding = {'format': validator.FORMAT, 'state': 'BOUND_DESCRIPTION_NOT_EXECUTABLE',
        'study_id': 'GENERATED-' + track.upper(), 'record_kind': 'generated_control', 'track': track,
        'template_sha256': validator.TEMPLATE_SHA256[track], 'registered_task_count_delta': 0,
        'authority': {'execution_selected': False, 'scientific_qualification': False, 'submission_readiness': False},
        'artifacts': artifacts, 'tasks': tasks, 'case_manifests': manifests, 'budget_profiles': budgets,
        'arms': arms, 'contrasts': contrasts, 'assignments': assignments, 'repeats_per_task': 2,
        'pairing': {'assignment_manifest_artifact': artifact('assignment-metadata', validator.canonical(assignments)),
            'order_randomization_artifact': artifact('order-randomization-policy'),
            'context_workspace_cache_reset_artifact': artifact('context-reset-policy'),
            'model_identity_policy_artifact': artifact('model-identity-policy'),
            'seed_support_and_limits': 'Generated controls make no platform seed reproducibility claim',
            'repeat_count_rationale_artifact': artifact('repeat-count-rationale'), 'identical_case_manifest_within_pair': True},
        'model_scaffolds': [{'id': 'GENERATED-MODEL-SCAFFOLD', 'model_version': 'GENERATED-MODEL-REVISION',
            'scaffold_version': 'GENERATED-SCAFFOLD-REVISION', 'identity_artifact': artifact('served-model-identity')}],
        'corpus': {'selection_artifact': artifact('corpus-selection'), 'inclusion_exclusion_artifact': artifact('eligibility'),
            'exclusions_frozen_before_assignment': True, 'intended_population': 'Invented finite control panel only',
            'limitations': 'No empirical population, subjects, assignments or results are represented',
            'source_family_ids': [task['source_family_id'] for task in tasks], 'overlap_graph_artifact': artifact('family-overlap-graph'),
            'overlap_edges': [{'families': [task['source_family_id'] for task in tasks], 'relation': 'Shared invented stimulus IDs',
                               'evidence_artifact': artifact('generated-stimulus-overlap')}]},
        'analysis': {'primary_contrast_ids': primary, 'exploratory_contrast_ids': [row['id'] for row in contrasts if row['id'] not in primary],
            'independent_units': units, 'repeats_are_independent_units': False, 'dependence_groups': list(groups.values()),
            'aggregation_order': ['case', 'independent_unit', 'task', 'source_family'],
            'family_weighting_artifact': artifact('family-weighting'), 'endpoint_aggregation': 'separate_by_endpoint',
            'paired_uncertainty': {'method': 'Invented paired-unit control policy', 'level': 0.95,
                                   'justification_artifact': artifact('uncertainty-justification')},
            'claim_scope': 'finite_panel', 'population_basis_artifact': artifact('finite-panel-basis'),
            'multiplicity': {'family': list(primary), 'rule': 'Invented family rule for code controls', 'policy_artifact': artifact('multiplicity-policy')},
            'analysis_code_artifact': analysis_code, 'judgment_rubric_artifact': artifact('judgment-rubric'),
            'expert_review_plan_artifact': artifact('expert-review-plan')},
        'exposure': {'inventory_artifact': artifact('exposure-inventory'), 'split_and_overlap_audit_artifact': artifact('exposure-overlap-audit'),
            'training_history_artifact': artifact('training-history'), 'offline_information_policy_artifact': information,
            'across_suite_overlap_artifact': artifact('across-suite-overlap'),
            'rl_training_outer_separation_artifact': artifact('rl-outer-separation'), 'rl_experiment_selected': False,
            'final_labels_inaccessible': True, 'feedback_inaccessible_until_lock': True,
            'new_context_is_unseen_guarantee': False, 'later_release_is_unseen_guarantee': False,
            'confirmation_claim': 'protected_confirmation', 'unit_status': exposure_status},
        'failure_accounting': {'ledger_artifact': artifact('attempt-ledger'), 'assigned_attempt_count': len(assignments),
            'all_assigned_attempts_retained': True, 'primary_denominator': 'all_assigned_runs', 'failure_classes': list(validator.FAILURES),
            'adjudication_artifact': artifact('failure-adjudication'), 'complete_case_reporting': 'supplementary_only',
            'continuous_missingness': {'method': 'bounds', 'policy_artifact': missingness},
            'retry_limit': 0, 'retryable_classes': [], 'retry_budget_id': None, 'retry_aggregation_artifact': artifact('no-retries-policy'),
            'retry_adjudication': 'blinded_to_primary_outcome', 'outcome_dependent_retry_or_drop': False},
        'selection_and_stopping': {'design': 'fixed', 'maximum_assigned_attempts': len(assignments),
            'frozen_before_outcomes': True, 'selection_uses_development_only': True, 'assessment_feedback_used': False,
            'global_policy_frozen_before_assessment': True, 'candidate_search_count': 1, 'search_budget_id': search_budget,
            'precision_rationale_artifact': artifact('precision-rationale'), 'safety_stop_rule_artifact': artifact('safety-stop'),
            'early_termination_reporting_artifact': artifact('early-stop-reporting'),
            'material_change_refresh_policy_artifact': artifact('material-change-refresh'), 'sequential': None},
        'track_policy': policy}
    return binding


def write_generated(directory):
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    for track in ('paper', 'neural'):
        binding = make(track)
        validator.validate(binding)
        with (directory / (track + '.generated.json')).open('xb') as stream:
            stream.write(validator.canonical(binding))
    return directory


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps({'generated_only': True, 'directory': str(write_generated(args.output)), 'real_study_bound': False}))
