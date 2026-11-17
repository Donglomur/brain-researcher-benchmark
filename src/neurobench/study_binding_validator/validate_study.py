#!/usr/bin/env python3
"""Validate a paired-study description without opening any referenced artifact."""
import argparse
from collections import Counter
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

FORMAT = 'neurobench.paired-study-binding.v1'
INPUT_LIMIT = 4 * 1024 * 1024
TEMPLATE_SHA256 = {
    'paper': 'fc999a0090875b8b0ce07d2f503b8e4cace7070bda2c614f4528323be586c575',
    'neural': 'ebc306ef4ecbf65d418c58c0ad2b1ab8d7582aa47fbe1a85a5ba4d618ddc3e6e',
}
FAILURES = ['infrastructure', 'invalid_submission', 'model_abstention',
            'resource_exhaustion', 'scientifically_invalid', 'successful_valid_submission']
PAPER_PHASES = ['reproduction', 'improvement_development', 'improvement_confirmation']
NEURAL_PHASES = ['development', 'assessment']
PLACEHOLDERS = {'tbd', 'todo', 'unbound', 'unknown', 'placeholder', 'null', 'none', 'n/a', 'fill_me'}


def obj(**properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def array(items, minimum=1, maximum=50000):
    return {'type': 'array', 'items': items, 'minItems': minimum, 'maxItems': maximum}


def enum(*values):
    return {'enum': list(values)}


def const(value):
    return {'const': value}


def nullable(schema):
    return {'anyOf': [{'type': 'null'}, schema]}


def mapping(values, minimum=1):
    return {'type': 'object', 'additionalProperties': values, 'minProperties': minimum, 'maxProperties': 512}


TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 8192, 'pattern': r'\S', 'x-bound-text': True}
ID = {**TEXT, 'maxLength': 128, 'pattern': r'^[A-Za-z0-9][A-Za-z0-9_.:-]*(?![\s\S])'}
SHA = {'type': 'string', 'minLength': 64, 'maxLength': 64, 'pattern': r'^(?!0{64}$)[0-9a-f]{64}$'}
UINT = {'type': 'integer', 'minimum': 0, 'maximum': 10**18}
POS = {**UINT, 'minimum': 1}
NUMBER = {'type': 'number', 'minimum': 0}
BOOL = {'type': 'boolean'}
PIN = obj(locator={**TEXT, 'pattern': r'^[A-Za-z][A-Za-z0-9+.-]*:[^\s]+(?![\s\S])'}, bytes=POS, sha256=SHA)
ARTIFACT = obj(role=TEXT, pin=PIN, privacy=enum('public_metadata', 'evaluator_metadata'),
               review=obj(author_id=ID, reviewer_id=ID, independence_declared=const(True), evidence=PIN))
ENDPOINT = obj(id=ID, metric=TEXT, direction=enum('higher_is_better', 'lower_is_better'), units=TEXT)
TASK = obj(id=ID, revision_artifact=ID, source_family_id=ID, endpoints=array(ENDPOINT, maximum=64))
CASE = obj(id=ID, independent_unit_id=ID, exposure_unit_id=ID, dependence_group_ids=array(ID, maximum=64))
CASES = obj(id=ID, task_id=ID, task_revision_sha256=SHA, phase=ID, artifact=ID, cases=array(CASE))
BUDGET = obj(id=ID, hardware_artifact=ID, measured_reference_artifact=ID,
             wall_seconds=POS, cpu_seconds=UINT, gpu_seconds=UINT, peak_memory_bytes=POS,
             model_calls=UINT, llm_input_tokens=UINT, llm_output_tokens=UINT,
             money_limit_minor_units=UINT, currency={'type': 'string', 'minLength': 3, 'maxLength': 3, 'pattern': r'^[A-Z]{3}$'},
             pricing_timestamp={'type': 'string', 'minLength': 20, 'maxLength': 20, 'pattern': r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$'})
ARM = obj(id=ID, mode=enum('reconstruct_then_improve', 'frozen_program', 'case_investigation'),
          common_information_artifact=ID, information_policy_artifact=ID,
          official_code_artifact=nullable(ID), numerical_tools_artifact=nullable(ID),
          specialist_tool_artifact=nullable(ID), adaptation_policy_artifact=nullable(ID),
          frozen_policy_artifact=nullable(ID), budget_ids=mapping(array(ID, maximum=4)))
ENDPOINT_APPLICABILITY = obj(task_id=ID, phase=ID, assigned_pair_ids=array(ID), assigned_pairs=POS,
                            denominator=const('all_assigned_pairs_for_endpoint_task_and_phase'))
ESTIMAND = obj(description=TEXT, effect_order=const('first_arm_minus_second_arm'),
               endpoint_ids=array(ID, maximum=512), denominator=const('all_assigned_pairs_in_contrast_phase'),
               assigned_pairs=POS, failures_in_denominator=const(True),
               missingness_policy_artifact=ID, minimum_effect_by_endpoint=mapping(NUMBER),
               endpoint_applicability=mapping(ENDPOINT_APPLICABILITY))
CONTRAST = obj(id=ID, arms=array(ID, minimum=2, maximum=2), phase=ID, primary=BOOL,
               declared_intervention=array(ID, maximum=16), estimand=ESTIMAND, analysis_artifact=ID)
ASSIGNMENT = obj(id=ID, pair_id=ID, arm_id=ID, task_id=ID, task_revision_sha256=SHA,
                 model_scaffold_id=ID, run_index=UINT, phase=ID, case_manifest_id=ID,
                 case_manifest_sha256=SHA, condition_order=UINT, budget_ids=array(ID, maximum=4))
DEPENDENCE = obj(id=ID, kind=enum('participant', 'animal', 'session', 'stimulus', 'source_family', 'other'),
                 case_keys=array(TEXT), evidence_artifact=ID)
ANALYSIS = obj(primary_contrast_ids=array(ID, maximum=64), exploratory_contrast_ids=array(ID, minimum=0, maximum=64),
               independent_units=array(obj(id=ID, kind=TEXT, definition_artifact=ID)),
               repeats_are_independent_units=const(False), dependence_groups=array(DEPENDENCE),
               aggregation_order=array(enum('case', 'independent_unit', 'task', 'source_family'), minimum=4, maximum=4),
               family_weighting_artifact=ID, endpoint_aggregation=const('separate_by_endpoint'),
               paired_uncertainty=obj(method=TEXT, level={'type': 'number', 'exclusiveMinimum': 0, 'exclusiveMaximum': 1},
                                      justification_artifact=ID),
               claim_scope=enum('finite_panel', 'specified_population'), population_basis_artifact=ID,
               multiplicity=obj(family=array(ID, maximum=64), rule=TEXT, policy_artifact=ID),
               analysis_code_artifact=ID, judgment_rubric_artifact=ID, expert_review_plan_artifact=ID)
EXPOSURE = obj(inventory_artifact=ID, split_and_overlap_audit_artifact=ID, training_history_artifact=ID,
               offline_information_policy_artifact=ID, across_suite_overlap_artifact=ID,
               rl_training_outer_separation_artifact=ID, rl_experiment_selected=const(False),
               final_labels_inaccessible=const(True), feedback_inaccessible_until_lock=const(True),
               new_context_is_unseen_guarantee=const(False), later_release_is_unseen_guarantee=const(False),
               confirmation_claim=enum('retrospective_development', 'protected_confirmation'),
               unit_status=mapping(enum('unexposed_declared', 'public_or_development_exposed', 'unresolved')))
FAILURE_POLICY = obj(ledger_artifact=ID, assigned_attempt_count=POS,
                     all_assigned_attempts_retained=const(True), primary_denominator=const('all_assigned_runs'),
                     failure_classes=array(ID, minimum=6, maximum=6), adjudication_artifact=ID,
                     complete_case_reporting=const('supplementary_only'),
                     continuous_missingness=obj(method=enum('predeclared_penalty', 'predeclared_model', 'bounds'), policy_artifact=ID),
                     retry_limit={**UINT, 'maximum': 100}, retryable_classes=array(ID, minimum=0, maximum=5),
                     retry_budget_id=nullable(ID), retry_aggregation_artifact=ID,
                     retry_adjudication=const('blinded_to_primary_outcome'), outcome_dependent_retry_or_drop=const(False))
SELECTION = obj(design=enum('fixed', 'sequential'), maximum_assigned_attempts=POS,
                 frozen_before_outcomes=const(True), selection_uses_development_only=const(True),
                 assessment_feedback_used=const(False), global_policy_frozen_before_assessment=const(True),
                 candidate_search_count=POS, search_budget_id=ID, precision_rationale_artifact=ID,
                 safety_stop_rule_artifact=ID, early_termination_reporting_artifact=ID,
                 material_change_refresh_policy_artifact=ID,
                 sequential=nullable(obj(rule_artifact=ID, validity_review_artifact=ID,
                                         look_after_pair_counts=array(POS, maximum=1000))))
TRACK_POLICY = obj(paper=nullable(obj(reproduction_locked_before_improvement=const(True),
                    carry_unused_reproduction_budget=const(False), candidate_and_analysis_locked_before_confirmation=const(True),
                    original_method_comparator_artifact=ID, same_case_resource_comparator=const(True),
                    improvement_decision_rule_artifact=ID, contemporary_comparator_policy_artifact=ID,
                    novelty_review_policy_artifact=ID, fidelity_improvement_frontier_claims_separate=const(True))),
                   neural=nullable(obj(live_llm_cost_is_additional=const(True), equal_total_expenditure_claim=const(False),
                    assessment_global_updates_allowed=const(False), case_reset_policy_artifact=ID,
                    policy_construction_protocol_artifact=ID, amortization_case_count=POS,
                    development_cost_included=const(True), inference_cost_included=const(True),
                    specialist_training_cost_policy_artifact=ID, cost_curve_policy_artifact=ID,
                    simple_reference_artifact=ID, specialist_reference_artifact=ID,
                    context_control_artifact=ID, disruption_validity_artifact=ID,
                    direct_signal_extension_selected=const(False))))
SCHEMA = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
          'title': 'Paired neuroscience study description binding',
          **obj(format=const(FORMAT), state=const('BOUND_DESCRIPTION_NOT_EXECUTABLE'), study_id=ID,
                record_kind=enum('study_description', 'generated_control'), track=enum('paper', 'neural'),
                template_sha256=SHA, registered_task_count_delta=const(0),
                authority=obj(execution_selected=const(False), scientific_qualification=const(False), submission_readiness=const(False)),
                artifacts=mapping(ARTIFACT), tasks=array(TASK, maximum=512), case_manifests=array(CASES, maximum=2048),
                budget_profiles=array(BUDGET, maximum=512), arms=array(ARM, minimum=2, maximum=4),
                contrasts=array(CONTRAST, maximum=64), assignments=array(ASSIGNMENT),
                repeats_per_task={**POS, 'maximum': 1000},
                pairing=obj(assignment_manifest_artifact=ID, order_randomization_artifact=ID,
                    context_workspace_cache_reset_artifact=ID, model_identity_policy_artifact=ID,
                    seed_support_and_limits=TEXT, repeat_count_rationale_artifact=ID,
                    identical_case_manifest_within_pair=const(True)),
                model_scaffolds=array(obj(id=ID, model_version=TEXT, scaffold_version=TEXT, identity_artifact=ID), maximum=256),
                corpus=obj(selection_artifact=ID, inclusion_exclusion_artifact=ID, exclusions_frozen_before_assignment=const(True),
                    intended_population=TEXT, limitations=TEXT, source_family_ids=array(ID, maximum=1024),
                    overlap_graph_artifact=ID, overlap_edges=array(obj(families=array(ID, minimum=2, maximum=2),
                        relation=TEXT, evidence_artifact=ID), minimum=0, maximum=4096)),
                analysis=ANALYSIS, exposure=EXPOSURE, failure_accounting=FAILURE_POLICY,
                selection_and_stopping=SELECTION, track_policy=TRACK_POLICY)}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def schema_check(value, schema, path='$'):
    """The fixed vocabulary used by SCHEMA; not an arbitrary JSON-Schema engine."""
    if 'anyOf' in schema:
        for branch in schema['anyOf']:
            try:
                schema_check(value, branch, path)
                return
            except ValueError:
                pass
        raise ValueError(path + ': no permitted shape')
    if 'const' in schema:
        need(type(value) is type(schema['const']) and value == schema['const'], path + ': fixed policy changed')
    if 'enum' in schema:
        need(any(type(value) is type(option) and value == option for option in schema['enum']), path + ': unknown option')
    kind = schema.get('type')
    types = {'object': dict, 'array': list, 'string': str, 'integer': int, 'boolean': bool, 'null': type(None)}
    if kind == 'number':
        need(type(value) in (int, float) and math.isfinite(value), path + ': finite number required')
    elif kind:
        need(type(value) is types[kind], path + ': wrong type')
    if kind == 'object':
        need(len(value) >= schema.get('minProperties', 0) and len(value) <= schema.get('maxProperties', 100000), path + ': object extent')
        need(set(schema.get('required', [])).issubset(value), path + ': missing required fields')
        properties = schema.get('properties', {})
        additional = schema.get('additionalProperties', True)
        for key, child in value.items():
            need(type(key) is str, path + ': string keys required')
            if key in properties:
                schema_check(child, properties[key], path + '.' + key)
            else:
                need(additional is not False, path + ': unexpected field ' + key)
                if isinstance(additional, dict):
                    schema_check(child, additional, path + '.' + key)
    elif kind == 'array':
        need(schema.get('minItems', 0) <= len(value) <= schema.get('maxItems', 100000), path + ': array extent')
        for index, child in enumerate(value):
            schema_check(child, schema['items'], f'{path}[{index}]')
    elif kind == 'string':
        need(schema.get('minLength', 0) <= len(value) <= schema.get('maxLength', 100000), path + ': text extent')
        need('pattern' not in schema or re.search(schema['pattern'], value) is not None, path + ': invalid text pattern')
        if schema.get('x-bound-text'):
            need(value.strip().lower() not in PLACEHOLDERS and '{{' not in value and '}}' not in value
                 and not (value.startswith('<') and value.endswith('>')), path + ': unresolved placeholder')
    if kind in ('integer', 'number'):
        for key, operation in [('minimum', lambda x, y: x >= y), ('maximum', lambda x, y: x <= y),
                               ('exclusiveMinimum', lambda x, y: x > y), ('exclusiveMaximum', lambda x, y: x < y)]:
            need(key not in schema or operation(value, schema[key]), path + ': numeric bound')


def unique(values, label):
    need(len(values) == len(set(values)), 'Duplicate ' + label)
    return set(values)


def indexed(rows, label):
    unique([row['id'] for row in rows], label)
    return {row['id']: row for row in rows}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def case_content(manifest):
    return {key: manifest[key] for key in ('task_id', 'task_revision_sha256', 'phase', 'cases')}


def validate(binding):
    schema_check(binding, SCHEMA)
    track = binding['track']
    need(binding['template_sha256'] == TEMPLATE_SHA256[track], 'Wrong source template revision')
    artifacts = binding['artifacts']
    for key, artifact in artifacts.items():
        schema_check(key, ID, 'artifact ID')
        review = artifact['review']
        need(review['author_id'] != review['reviewer_id'], 'Artifact review is declared self-review')
        need(review['evidence']['sha256'] != artifact['pin']['sha256'], 'Review evidence cannot be the reviewed artifact itself')
    def ref(identifier):
        need(identifier in artifacts, 'Unknown artifact ID: ' + str(identifier))
        return artifacts[identifier]
    tasks = indexed(binding['tasks'], 'task ID')
    budgets = indexed(binding['budget_profiles'], 'budget ID')
    arms = indexed(binding['arms'], 'arm ID')
    manifests = indexed(binding['case_manifests'], 'case-manifest ID')
    models = indexed(binding['model_scaffolds'], 'model/scaffold ID')
    contrasts = indexed(binding['contrasts'], 'contrast ID')
    units = indexed(binding['analysis']['independent_units'], 'independent-unit ID')
    groups = indexed(binding['analysis']['dependence_groups'], 'dependence-group ID')
    phases = PAPER_PHASES if track == 'paper' else NEURAL_PHASES
    endpoints, endpoint_tasks = {}, {}
    for task in tasks.values():
        ref(task['revision_artifact'])
        for endpoint in task['endpoints']:
            need(endpoint['id'] not in endpoints, 'Endpoint IDs must be unique across task contracts')
            endpoints[endpoint['id']] = endpoint
            endpoint_tasks[endpoint['id']] = task['id']
    families = unique(binding['corpus']['source_family_ids'], 'source family')
    need({task['source_family_id'] for task in tasks.values()}.issubset(families), 'Missing task source family')
    overlap_pairs = set()
    for edge in binding['corpus']['overlap_edges']:
        need(len(unique(edge['families'], 'overlap edge family')) == 2 and set(edge['families']).issubset(families), 'Invalid overlap edge')
        pair = tuple(sorted(edge['families']))
        need(pair not in overlap_pairs, 'Duplicate undirected source-family overlap edge')
        overlap_pairs.add(pair)
        ref(edge['evidence_artifact'])
    for key in ('selection_artifact', 'inclusion_exclusion_artifact', 'overlap_graph_artifact'):
        ref(binding['corpus'][key])
    for model in models.values():
        ref(model['identity_artifact'])
    unique([(m['model_version'], m['scaffold_version']) for m in models.values()], 'model/scaffold revision pair')
    for budget in budgets.values():
        ref(budget['hardware_artifact']); ref(budget['measured_reference_artifact'])
        datetime.datetime.strptime(budget['pricing_timestamp'], '%Y-%m-%dT%H:%M:%SZ')

    by_task_phase, case_keys, exposure_units, phase_exposure = {}, {}, set(), {p: set() for p in phases}
    for manifest in manifests.values():
        task = tasks.get(manifest['task_id'])
        need(task is not None and manifest['phase'] in phases, 'Unknown case task/phase')
        need(manifest['task_revision_sha256'] == ref(task['revision_artifact'])['pin']['sha256'], 'Case/task revision mismatch')
        key = (task['id'], manifest['phase'])
        need(key not in by_task_phase, 'More than one complete case manifest for task/phase')
        by_task_phase[key] = manifest
        pin = ref(manifest['artifact'])['pin']; raw = canonical(case_content(manifest))
        need(pin['bytes'] == len(raw) and pin['sha256'] == hashlib.sha256(raw).hexdigest(), 'Inline case roster does not match declared metadata pin')
        unique([case['id'] for case in manifest['cases']], 'case ID within manifest')
        for case in manifest['cases']:
            need(case['independent_unit_id'] in units, 'Unknown independent unit')
            need(unique(case['dependence_group_ids'], 'case dependence group').issubset(groups), 'Unknown dependence group')
            case_keys[manifest['id'] + '/' + case['id']] = case
            exposure_units.add(case['exposure_unit_id']); phase_exposure[manifest['phase']].add(case['exposure_unit_id'])
    need(set(by_task_phase) == {(task, phase) for task in tasks for phase in phases}, 'Incomplete task/phase case roster')
    need({case['independent_unit_id'] for case in case_keys.values()} == set(units), 'Unused or missing independent-unit declaration')
    for unit in units.values():
        ref(unit['definition_artifact'])
    for group in groups.values():
        ref(group['evidence_artifact']); declared = unique(group['case_keys'], 'dependence membership')
        observed = {key for key, case in case_keys.items() if group['id'] in case['dependence_group_ids']}
        need(declared == observed and observed, 'Dependence group/case membership mismatch')

    common = ('common_information_artifact', 'information_policy_artifact')
    for arm in arms.values():
        for key in common + ('official_code_artifact', 'numerical_tools_artifact', 'specialist_tool_artifact',
                             'adaptation_policy_artifact', 'frozen_policy_artifact'):
            if arm[key] is not None:
                ref(arm[key])
        need(set(arm['budget_ids']) == set(phases), 'Arm budgets must cover every phase')
        for values in arm['budget_ids'].values():
            need(unique(values, 'arm budget ID').issubset(budgets), 'Unknown arm budget')
    for key in common:
        need(len({arm[key] for arm in arms.values()}) == 1, 'Unmatched common information/access policy')
    if track == 'paper':
        need(set(arms) == {'paper_data', 'paper_data_code'}, 'Paper study requires both declared access arms')
        left, right = arms['paper_data_code'], arms['paper_data']
        need(left['official_code_artifact'] is not None and right['official_code_artifact'] is None, 'Official-code intervention is not bound')
        need(ref(left['official_code_artifact'])['pin']['sha256'] != ref(left['common_information_artifact'])['pin']['sha256'],
             'Official code cannot be the same artifact as common information')
        for arm in arms.values():
            need(arm['mode'] == 'reconstruct_then_improve' and all(arm[k] is None for k in
                 ('numerical_tools_artifact', 'specialist_tool_artifact', 'adaptation_policy_artifact', 'frozen_policy_artifact')), 'Incompatible paper arm fields')
            need(all(len(ids) == 1 for ids in arm['budget_ids'].values()), 'One explicit stage budget per paper arm required')
        need(left['budget_ids'] == right['budget_ids'], 'Paper phase resources must match')
        need(len({left['budget_ids'][p][0] for p in phases}) == 3, 'Paper stages need distinct nontransferable budget IDs')
        expected_contrasts = {
            'official_code_reproduction': (['paper_data_code', 'paper_data'], 'reproduction', ['official_code_artifact']),
            'official_code_end_to_end_improvement': (['paper_data_code', 'paper_data'], 'improvement_confirmation', ['official_code_artifact'])}
    else:
        need(set(arms) == {'program_numerical', 'investigator_numerical', 'program_specialist', 'investigator_specialist'}, 'Neural study requires the complete four-cell design')
        for key in ('numerical_tools_artifact', 'adaptation_policy_artifact'):
            need(None not in {a[key] for a in arms.values()} and len({a[key] for a in arms.values()}) == 1, 'Unmatched neural tools/adaptation')
        specialist = {arms[a]['specialist_tool_artifact'] for a in ('program_specialist', 'investigator_specialist')}
        need(len(specialist) == 1 and None not in specialist, 'Specialist checkpoint/interface must match')
        for name, arm in arms.items():
            live = name.startswith('investigator_')
            need(arm['mode'] == ('case_investigation' if live else 'frozen_program'), 'Neural mode mismatch')
            need(arm['official_code_artifact'] is None and arm['frozen_policy_artifact'] is not None, 'Neural policy lock missing or paper intervention mixed in')
            need((arm['specialist_tool_artifact'] is not None) == name.endswith('_specialist'), 'Specialist access mismatch')
            need(len(arm['budget_ids']['development']) == 1 and len(arm['budget_ids']['assessment']) == (2 if live else 1), 'Neural budget-role count mismatch')
        need(len({tuple(a['budget_ids']['development']) for a in arms.values()}) == 1, 'Development allowances differ')
        numerical = {a['budget_ids']['assessment'][0] for a in arms.values()}
        need(len(numerical) == 1, 'Numerical inference allowances differ')
        numeric_budget = budgets[next(iter(numerical))]
        need(all(numeric_budget[k] == 0 for k in ('model_calls', 'llm_input_tokens', 'llm_output_tokens')), 'Frozen assessment cannot permit new LLM calls/tokens')
        live_ids = {arms[a]['budget_ids']['assessment'][1] for a in ('investigator_numerical', 'investigator_specialist')}
        need(len(live_ids) == 1 and not live_ids & numerical, 'Additional live LLM budget must be explicit and matched')
        live_budget = budgets[next(iter(live_ids))]
        need(all(live_budget[k] > 0 for k in ('model_calls', 'llm_input_tokens', 'llm_output_tokens')), 'Live mode has no bound LLM allowance')
        expected_contrasts = {
            'live_given_numerical': (['investigator_numerical', 'program_numerical'], 'assessment', ['mode', 'live_llm_budget']),
            'live_given_specialist': (['investigator_specialist', 'program_specialist'], 'assessment', ['mode', 'live_llm_budget']),
            'specialist_given_program': (['program_specialist', 'program_numerical'], 'assessment', ['specialist_tool_artifact']),
            'specialist_given_investigator': (['investigator_specialist', 'investigator_numerical'], 'assessment', ['specialist_tool_artifact'])}

    need(set(contrasts) == set(expected_contrasts), 'Missing or incompatible intended contrasts')
    assignments = binding['assignments']; indexed(assignments, 'assignment ID')
    pairing = binding['pairing']
    for key, value in pairing.items():
        if key.endswith('_artifact'):
            ref(value)
    assignment_raw = canonical(assignments)
    assignment_pin = ref(pairing['assignment_manifest_artifact'])['pin']
    need(assignment_pin['bytes'] == len(assignment_raw)
         and assignment_pin['sha256'] == hashlib.sha256(assignment_raw).hexdigest(), 'Inline assignments do not match their declared metadata pin')
    expected_count = len(tasks) * len(phases) * len(models) * binding['repeats_per_task'] * len(arms)
    need(expected_count == len(assignments), 'Assignment roster is not the complete frozen matrix')
    semantic, pairs = set(), {}
    for row in assignments:
        need(row['task_id'] in tasks and row['phase'] in phases and row['arm_id'] in arms
             and row['model_scaffold_id'] in models and row['run_index'] < binding['repeats_per_task'], 'Unknown assignment dimension')
        manifest = by_task_phase[(row['task_id'], row['phase'])]
        need(row['task_revision_sha256'] == manifest['task_revision_sha256']
             and row['case_manifest_id'] == manifest['id']
             and row['case_manifest_sha256'] == ref(manifest['artifact'])['pin']['sha256'], 'Assignment task/case revision join mismatch')
        need(row['budget_ids'] == arms[row['arm_id']]['budget_ids'][row['phase']], 'Assignment overrides matched arm budget')
        key = (row['task_id'], row['phase'], row['model_scaffold_id'], row['run_index'])
        need((key, row['arm_id']) not in semantic, 'Duplicate assignment cell under another ID')
        semantic.add((key, row['arm_id'])); pairs.setdefault(row['pair_id'], []).append((key, row))
    for pair in pairs.values():
        need(len({key for key, _ in pair}) == 1 and {row['arm_id'] for _, row in pair} == set(arms)
             and len(pair) == len(arms), 'Incomplete or incompatible paired assignment')
        need({row['condition_order'] for _, row in pair} == set(range(len(arms))), 'Condition order must be a full permutation')
    primary = unique(binding['analysis']['primary_contrast_ids'], 'primary contrast')
    exploratory = unique(binding['analysis']['exploratory_contrast_ids'], 'exploratory contrast')
    need(not primary & exploratory and primary | exploratory == set(contrasts), 'Primary/exploratory partition incomplete')
    if track == 'neural':
        need(bool(primary & {'live_given_numerical', 'live_given_specialist'}), 'At least one intended mode effect must be primary')
    primary_pairs = set()
    for name, contrast in contrasts.items():
        expected_arms, phase, intervention = expected_contrasts[name]
        need(contrast['arms'] == expected_arms and contrast['phase'] == phase
             and contrast['declared_intervention'] == intervention, 'Contrast does not bind the declared comparison')
        need(contrast['primary'] == (name in primary), 'Primary flag/list mismatch')
        estimate = contrast['estimand']; endpoint_ids = unique(estimate['endpoint_ids'], 'contrast endpoint')
        need(endpoint_ids == set(endpoints), 'Contrast must retain every declared endpoint')
        need(set(estimate['minimum_effect_by_endpoint']) == endpoint_ids, 'Missing endpoint effect threshold declaration')
        selected_pairs = {pid for pid, pair in pairs.items() if pair[0][1]['phase'] == phase}
        need(estimate['assigned_pairs'] == len(selected_pairs), 'Contrast failure denominator differs from assignments')
        applicability = estimate['endpoint_applicability']
        need(set(applicability) == endpoint_ids, 'Endpoint applicability must cover exactly every declared endpoint')
        for endpoint_id, scope in applicability.items():
            task_id = endpoint_tasks[endpoint_id]
            need(scope['task_id'] == task_id and scope['phase'] == phase,
                 'Endpoint task/phase applicability join mismatch')
            applicable_pairs = {pid for pid in selected_pairs if pairs[pid][0][1]['task_id'] == task_id}
            declared_pairs = unique(scope['assigned_pair_ids'], 'endpoint assigned pair')
            need(declared_pairs == applicable_pairs, 'Endpoint applicable pairs differ from its task/phase assignments')
            need(scope['assigned_pairs'] == len(applicable_pairs), 'Endpoint failure denominator differs from applicable assignments')
        if name in primary:
            primary_pairs.update(selected_pairs)
        ref(estimate['missingness_policy_artifact']); ref(contrast['analysis_artifact'])
        need(estimate['missingness_policy_artifact'] == binding['failure_accounting']['continuous_missingness']['policy_artifact'],
             'Contrast/global missingness policies disagree')
        need(contrast['analysis_artifact'] == binding['analysis']['analysis_code_artifact'], 'Contrast/global analysis bindings disagree')

    analysis = binding['analysis']
    need(analysis['aggregation_order'] == ['case', 'independent_unit', 'task', 'source_family'], 'Aggregation must respect declared independence before family weighting')
    need(unique(analysis['multiplicity']['family'], 'multiplicity contrast') == primary, 'Multiplicity family must cover exactly all primary claims')
    for key in ('family_weighting_artifact', 'population_basis_artifact', 'analysis_code_artifact',
                'judgment_rubric_artifact', 'expert_review_plan_artifact'):
        ref(analysis[key])
    ref(analysis['paired_uncertainty']['justification_artifact']); ref(analysis['multiplicity']['policy_artifact'])
    exposure = binding['exposure']
    need(exposure['offline_information_policy_artifact'] == next(iter(arms.values()))['information_policy_artifact'],
         'Arm/exposure information policies disagree')
    need(set(exposure['unit_status']) == exposure_units, 'Exposure inventory does not cover exactly the declared units')
    for key, value in exposure.items():
        if key.endswith('_artifact'):
            ref(value)
    if exposure['confirmation_claim'] == 'protected_confirmation':
        assessment_phase = 'improvement_confirmation' if track == 'paper' else 'assessment'
        earlier = set().union(*(values for phase, values in phase_exposure.items() if phase != assessment_phase))
        final = phase_exposure[assessment_phase]
        need(not earlier & final and all(exposure['unit_status'][unit] == 'unexposed_declared' for unit in final), 'Exposure overlap/unresolved status blocks protected-confirmation description')
    failure = binding['failure_accounting']
    need(failure['assigned_attempt_count'] == len(assignments), 'Failure denominator drops assigned attempts')
    need(failure['failure_classes'] == FAILURES, 'Missing or changed failure classification denominator')
    retryable = unique(failure['retryable_classes'], 'retryable class')
    need(retryable.issubset(set(FAILURES[:-1])), 'Invalid retryable failure class')
    if failure['retry_limit'] == 0:
        need(not retryable and failure['retry_budget_id'] is None, 'Zero-retry design must not bind retry operations')
    else:
        need(retryable and failure['retry_budget_id'] in budgets, 'Positive retry design lacks classes/budget')
    for key in ('ledger_artifact', 'adjudication_artifact', 'retry_aggregation_artifact'):
        ref(failure[key])
    ref(failure['continuous_missingness']['policy_artifact'])
    selection = binding['selection_and_stopping']
    need(selection['maximum_assigned_attempts'] == len(assignments) and selection['search_budget_id'] in budgets, 'Selection/stopping assignment or budget mismatch')
    development_phase = 'improvement_development' if track == 'paper' else 'development'
    need(all(selection['search_budget_id'] in arm['budget_ids'][development_phase] for arm in arms.values()),
         'Candidate selection must bind the matched development budget')
    for key, value in selection.items():
        if key.endswith('_artifact'):
            ref(value)
    if selection['design'] == 'fixed':
        need(selection['sequential'] is None, 'Fixed design must explicitly leave sequential branch inapplicable')
    else:
        sequential = selection['sequential']; need(sequential is not None, 'Sequential design lacks prespecified rule')
        ref(sequential['rule_artifact']); ref(sequential['validity_review_artifact'])
        looks = sequential['look_after_pair_counts']
        need(looks == sorted(set(looks)) and looks[-1] == len(primary_pairs), 'Sequential looks must increase through the complete primary-pair denominator')
    policy = binding['track_policy']
    need(policy[track] is not None and policy['neural' if track == 'paper' else 'paper'] is None, 'Wrong or unbound track policy')
    for key, value in policy[track].items():
        if key.endswith('_artifact'):
            ref(value)
    return {'status': 'description_consistent_not_qualified', 'record_kind': binding['record_kind'],
            'study_id': binding['study_id'], 'track': track, 'tasks': len(tasks), 'arms': len(arms),
            'case_manifests': len(manifests), 'declared_cases': len(case_keys),
            'assigned_attempts': len(assignments), 'paired_blocks': len(pairs), 'primary_contrasts': sorted(primary),
            'referenced_artifacts_opened': 0, 'artifact_bytes_authenticated': False,
            'declared_review_independence_verified': False, 'budgets_enforced': False,
            'execution_authorized': False, 'scientific_qualification': False,
            'submission_readiness': False, 'registered_task_count_delta': 0}


def load_binding(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= INPUT_LIMIT, 'Binding must be an ordinary nonempty file of at most4MiB')
        raw = stream.read(INPUT_LIMIT + 1)
        need(len(raw) == info.st_size, 'Binding changed size during read')
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON field: ' + key)
            result[key] = value
        return result
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                       parse_constant=lambda constant: need(False, 'Nonfinite JSON constant'))
    return value, hashlib.sha256(raw).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binding', type=Path)
    args = parser.parse_args(argv)
    try:
        binding, digest = load_binding(args.binding)
        result = validate(binding)
        result['binding_sha256'] = digest
    except (ValueError, KeyError, TypeError, OSError, OverflowError, RecursionError) as error:
        print(json.dumps({'status': 'rejected_description', 'reason': str(error), 'execution_authorized': False}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
