"""FIND025 submission declarations and descriptive comparisons; no data execution.

Operator plans/scores are trusted assertions, not independently verified evidence.
No result of this module establishes paper reproduction, isolation, or readiness.
"""
from collections import Counter
from hashlib import sha256
import json
from math import isfinite

ASSIGNMENT = 'PAPER-FIND-025'
GIT = '0038351ee773c2aee8758b3d74b0c9bf2991f543'
ARCHIVE = '2cc5f81fd4e500cbb8481641d0ca0558416fe7ebb65093b2881073f42a71652c'
DOI = '10.1038/s41593-024-01859-1'
MODES = ('code_reconstruction', 'paper_reproduction', 'protected_improvement')
ARMS = ('paper_data', 'paper_data_code')
SIGNED = 'signed_variance_explained_v1'
CORR = 'pearson_squared_delay_trialmeans_git003835_v1'
PAIRED_CORR = 'pearson_squared_paired_vector_v1'
LATENCY = 'first_strict_90pct_latency_v1'
ACCURACY = 'binary_accuracy_v1'
VARIANCE = 'normalized_subspace_variance_v1'
ARTIFACT = 'artifact_only_v1'
# These are scientific obligations, not new benchmark IDs or guessed session joins.
OBLIGATIONS = {
    'subspaces_and_projectors': ('subspaces', (ARTIFACT,), 'bases_projectors'),
    'normalized_null_variance': ('subspaces', (VARIANCE,), 'covariance_variance_support'),
    'normalized_potent_variance': ('subspaces', (VARIANCE,), 'covariance_variance_support'),
    'population_reconstruction': ('subspaces', (ARTIFACT,), 'reconstructed_activity'),
    'dr_wc_choice_projections': ('subspaces', (ARTIFACT,), 'condition_projections'),
    'context_projections': ('subspaces', (ARTIFACT,), 'context_block_projections'),
    'choice_neural_decoding': ('decoding_delay', (ACCURACY,), 'label_predictions'),
    'choice_kinematic_decoding': ('decoding_delay', (ACCURACY,), 'label_predictions'),
    'context_neural_decoding': ('decoding_delay', (ACCURACY,), 'label_predictions'),
    'context_kinematic_decoding': ('decoding_delay', (ACCURACY,), 'label_predictions'),
    'movement_choice_prediction': ('decoding_delay', (SIGNED, CORR, PAIRED_CORR), 'activity_predictions'),
    'movement_ramp_prediction': ('decoding_delay', (SIGNED, CORR, PAIRED_CORR), 'activity_predictions'),
    'fixed_choice_onset': ('decoding_delay', (LATENCY,), 'oriented_smoothed_trace'),
    'randomized_choice_onset': ('decoding_delay', (LATENCY,), 'oriented_smoothed_trace'),
    'fixed_motion_onset': ('decoding_delay', (LATENCY,), 'oriented_smoothed_trace'),
    'randomized_motion_onset': ('decoding_delay', (LATENCY,), 'oriented_smoothed_trace'),
}
JOINS = (
    'cohort_animal_session_identity', 'condition_dictionary_and_trial_membership',
    'full_claim_to_case_matrix', 'dispatch_arguments_and_explicit_repairs',
    'time_metric_and_target_support', 'rank_threshold_and_preprocessing_origin',
    'dependency_and_data_rights', 'final_paper_output_mapping',
    'protected_folds_resources_and_baseline',
)
# IDs are opaque references to complete declarations held by the operator. None
# establishes the truth of its referenced document merely by being non-null.
IDENTITY_FIELDS = (
    'metric_id', 'metric_unit', 'paper_code_version_id', 'condition_dictionary_id',
    'condition_selection_id', 'outcome_definition_id', 'target_id', 'unit_selection_id',
    'time_grid_id', 'bin_seconds', 'score_window_id', 'trace_orientation_id',
    'smoothing_id', 'delay_onset_id', 'normalization_denominator_id',
    'fit_support_id', 'development_support_id', 'evaluation_support_id',
    'scoring_rows_id', 'target_preprocessing_id', 'dispatch_id', 'argument_binding_id',
    'repair_recipe_id', 'rank_policy_id', 'rank_fit_support_id', 'rank_privilege',
    'threshold_policy_id', 'threshold_fit_support_id', 'threshold_privilege',
    'split_id', 'missing_policy_id', 'aggregation_id',
)
SHARED_VECTOR_FIELDS = tuple(k for k in IDENTITY_FIELDS if k not in
                            ('metric_id', 'normalization_denominator_id', 'dispatch_id', 'argument_binding_id'))
PROTECTED_FIELDS = (
    'outer_animal_folds_id', 'inner_animal_folds_id', 'session_calibration_partition_id',
    'whole_trial_and_context_block_groups_id', 'all_eligible_animals_covered_id',
    'randomized_delay_fit_exclusion_id', 'train_only_transforms_id',
    'fixed_common_target_id', 'prediction_target_separation_id', 'trial_lag_reset_id',
    'prospective_freeze_id', 'baseline_source_and_rerun_id', 'paired_resource_ceiling_id',
    'minimum_support_failure_policy_id', 'inference_and_multiplicity_plan_id',
    'meaningful_effect_plan_id',
)
EXECUTION_FIELDS = ('resource_ceiling_id', 'target_visibility_id', 'split_realization_id',
                    'fit_transform_record_id', 'frozen_procedure_id', 'baseline_rerun_id')
PRIVILEGES = ('official_code', 'historical_rank_table', 'historical_motion_threshold',
              'saved_reference_outputs', 'evaluation_targets')
UNITS = {SIGNED: 'dimensionless', CORR: 'dimensionless', PAIRED_CORR: 'dimensionless', VARIANCE: 'dimensionless',
         ACCURACY: 'fraction', LATENCY: 'seconds', ARTIFACT: 'artifact'}


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def exact(obj, keys, where):
    require(type(obj) is dict and set(obj) == set(keys), where + ': exact fields required')


def text(value, where):
    require(type(value) is str and 0 < len(value) <= 512 and value.strip() == value,
            where + ': nonempty bounded text required')


def ref(value, where):
    if value is not None:
        text(value, where)
        require(value.lower() not in ('unknown', 'pending', 'unresolved', 'tbd', 'n/a',
                                     'not_applicable'), where + ': use null for unresolved')


def digest(value):
    """Content binding only; not an operator signature or custody proof."""
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             allow_nan=False).encode()).hexdigest()


def sha(value, where):
    require(type(value) is str and len(value) == 64 and
            all(c in '0123456789abcdef' for c in value), where + ': SHA256 required')


def identities(obj):
    exact(obj, IDENTITY_FIELDS, 'identity')
    for key, value in obj.items():
        if key == 'bin_seconds':
            require(value is None or (type(value) in (int, float) and
                    isfinite(value) and value > 0), 'bin_seconds: finite positive or null')
        elif key.endswith('_privilege'):
            require(value in (None, 'train_only', 'historical_full_session',
                              'historical_precomputed'), key + ': unknown privilege')
        else:
            ref(value, key)
    if obj['metric_id'] is not None:
        require(obj['metric_id'] in UNITS, 'unversioned/unknown metric')
        require(obj['metric_unit'] in (None, UNITS[obj['metric_id']]), 'metric unit differs')


def expected_runs(plan):
    roles = ('candidate', 'baseline') if plan['mode'] == 'protected_improvement' else ('candidate',)
    return tuple(arm + '/' + role for arm in ARMS for role in roles)


def required_joins(mode):
    common = JOINS[:7]
    if mode == 'paper_reproduction':
        return common + ('final_paper_output_mapping',)
    if mode == 'protected_improvement':
        return common + ('protected_folds_resources_and_baseline',)
    return common


def validate_plan(plan):
    exact(plan, ('schema', 'assignment', 'mode', 'evidence_class', 'source', 'joins',
                 'scope_matrix', 'cases', 'access', 'protected_protocol', 'resource_plan_id'), 'plan')
    require(plan['schema'] == 'find025_plan_v1' and plan['assignment'] == ASSIGNMENT,
            'wrong plan schema/assignment')
    require(plan['mode'] in MODES, 'unknown mode')
    require(plan['evidence_class'] in ('invented', 'operator_declared'), 'evidence class')
    require(plan['source'] == {'git_commit': GIT, 'archive_sha256': ARCHIVE, 'paper_doi': DOI},
            'source version changed; a new reviewed contract is required')
    exact(plan['joins'], JOINS, 'joins')
    for name, row in plan['joins'].items():
        exact(row, ('status', 'evidence_id'), name)
        require(row['status'] in ('unresolved', 'operator_resolved'), 'join status')
        ref(row['evidence_id'], name)
        require((row['status'] == 'unresolved') == (row['evidence_id'] is None),
                'join evidence/status mismatch')
    exact(plan['scope_matrix'], OBLIGATIONS, 'scope_matrix')
    require(type(plan['cases']) is list and len(plan['cases']) <= 10000, 'case list')
    cases = {}
    for row in plan['cases']:
        exact(row, ('case_id', 'obligation', 'cohort', 'animal', 'session', 'panel_id', 'identity'), 'case')
        for key in ('case_id', 'animal', 'session', 'panel_id'):
            text(row[key], key)
        require(row['cohort'] in ('fixed_dr', 'two_context_dr_wc', 'randomized_delay'), 'cohort')
        require(row['obligation'] in OBLIGATIONS, 'obligation')
        if row['obligation'] in ('fixed_choice_onset', 'fixed_motion_onset'):
            require(row['cohort'] == 'fixed_dr', 'fixed onset requires fixed_dr cohort')
        if row['obligation'] in ('randomized_choice_onset', 'randomized_motion_onset'):
            require(row['cohort'] == 'randomized_delay', 'randomized onset requires randomized_delay cohort')
        require(row['case_id'] not in cases, 'duplicate case')
        identities(row['identity'])
        require(row['identity']['metric_id'] is None or row['identity']['metric_id'] in
                OBLIGATIONS[row['obligation']][1], 'metric not applicable to obligation')
        if row['identity']['metric_id'] == PAIRED_CORR:
            require(plan['mode'] == 'protected_improvement', 'prospective paired corr is protected-only')
        if plan['mode'] == 'protected_improvement' and row['obligation'].startswith('movement_'):
            require(row['identity']['metric_id'] in (None, SIGNED, PAIRED_CORR),
                    'protected secondary must use prospective paired-vector identity')
        cases[row['case_id']] = row
    assigned = []
    for name, members in plan['scope_matrix'].items():
        require(type(members) is list and all(type(v) is str for v in members) and
                len(members) == len(set(members)), 'scope member list')
        for key in members:
            require(type(key) is str and key in cases and cases[key]['obligation'] == name,
                    'scope member missing or assigned to wrong obligation')
        assigned.extend(members)
    require(len(assigned) == len(set(assigned)) and set(assigned) == set(cases),
            'every case must occur exactly once in scope matrix')
    # Duplicate physical endpoint identities cannot pad declared denominators.
    endpoints = [digest({k: r[k] for k in ('obligation', 'cohort', 'animal', 'session',
                                         'panel_id', 'identity')}) for r in cases.values()]
    require(len(endpoints) == len(set(endpoints)), 'duplicate assigned endpoint')
    exact(plan['access'], ARMS, 'access')
    for arm, grants in plan['access'].items():
        exact(grants, PRIVILEGES, 'access grants')
        require(all(type(v) is bool for v in grants.values()), 'boolean access grants')
        require(grants['official_code'] == (arm == 'paper_data_code'), 'wrong code access condition')
        require(not grants['saved_reference_outputs'] and not grants['evaluation_targets'],
                'saved outputs/protected targets are not granted')
        if plan['mode'] == 'protected_improvement':
            require(not grants['historical_rank_table'] and not grants['historical_motion_threshold'],
                    'historical parameters cannot establish protected improvement')
    exact(plan['protected_protocol'], PROTECTED_FIELDS, 'protected_protocol')
    for key, value in plan['protected_protocol'].items():
        ref(value, key)
    ref(plan['resource_plan_id'], 'resource_plan_id')
    return cases


def plan_gaps(plan):
    """Unresolved declarations; declared resolutions remain unverified assertions."""
    gaps = ['join:' + j for j in required_joins(plan['mode'])
            if plan['joins'][j]['status'] == 'unresolved']
    gaps += ['scope:' + name for name, rows in plan['scope_matrix'].items() if not rows]
    if plan['resource_plan_id'] is None:
        gaps.append('resource_plan_id')
    if plan['mode'] == 'protected_improvement':
        gaps += ['protected:' + k for k, v in plan['protected_protocol'].items() if v is None]
        for name in ('movement_choice_prediction', 'movement_ramp_prediction'):
            groups = {}
            for row in plan['cases']:
                if row['obligation'] == name:
                    key = tuple(row[k] for k in ('cohort', 'animal', 'session', 'panel_id'))
                    groups.setdefault(key, []).append(row['identity'])
            if not groups or any(len(rows) != 2 or {r['metric_id'] for r in rows} != {SIGNED, PAIRED_CORR}
                                 for rows in groups.values()):
                gaps.append('protected_primary_and_secondary:' + name)
            if any(len({digest({k: r[k] for k in SHARED_VECTOR_FIELDS}) for r in rows}) != 1
                   for rows in groups.values()):
                gaps.append('protected_common_vector:' + name)
    return gaps


def validate_submission(plan, submission):
    cases = validate_plan(plan)
    exact(submission, ('schema', 'plan_sha256', 'run_id', 'procedure_id', 'access_used',
                       'predictor_intervention_id', 'execution_declaration', 'records'), 'submission')
    require(submission['schema'] == 'find025_submission_v1', 'submission schema')
    require(submission['plan_sha256'] == digest(plan), 'submission binds a different plan')
    require(submission['run_id'] in expected_runs(plan), 'unexpected run')
    text(submission['procedure_id'], 'procedure_id')
    ref(submission['predictor_intervention_id'], 'predictor_intervention_id')
    grants = dict(plan['access'][submission['run_id'].split('/')[0]])
    if submission['run_id'].endswith('/baseline'):
        grants['official_code'] = True  # evaluator baseline, never candidate access
    exact(submission['execution_declaration'], EXECUTION_FIELDS, 'execution_declaration')
    for key, value in submission['execution_declaration'].items():
        ref(value, key)
    exact(submission['access_used'], PRIVILEGES, 'access_used')
    require(all(type(v) is bool for v in submission['access_used'].values()), 'boolean used access')
    require(all(not v or grants[k] for k, v in submission['access_used'].items()), 'ungranted access')
    require(type(submission['records']) is list, 'records list')
    records = {}
    for row in submission['records']:
        exact(row, ('case_id', 'status', 'reason', 'identity', 'artifacts'), 'candidate record')
        require(type(row['case_id']) is str and row['case_id'] in cases and
                row['case_id'] not in records, 'unknown or duplicate submitted case')
        require(row['status'] in ('complete', 'failed', 'undefined', 'abstained'), 'candidate status')
        ref(row['reason'], 'reason')
        require(row['status'] == 'complete' or row['reason'] is not None, 'missing failure reason')
        identities(row['identity'])
        require(type(row['artifacts']) is list, 'artifacts list')
        for artifact in row['artifacts']:
            exact(artifact, ('kind', 'logical_id', 'sha256'), 'artifact descriptor')
            text(artifact['kind'], 'artifact kind')
            text(artifact['logical_id'], 'artifact logical_id')
            sha(artifact['sha256'], 'artifact hash')
        if row['status'] == 'complete':
            for field, access_key in (('rank_privilege', 'historical_rank_table'),
                                      ('threshold_privilege', 'historical_motion_threshold')):
                if row['identity'][field] == 'historical_precomputed':
                    require(submission['access_used'][access_key],
                            'historical precomputed privilege requires declared parameter intake')
            kind = OBLIGATIONS[cases[row['case_id']]['obligation']][2]
            require(any(a['kind'] == kind for a in row['artifacts']), 'required artifact missing')
            if plan['mode'] == 'protected_improvement' and kind == 'activity_predictions':
                require(sum(a['kind'] == kind for a in row['artifacts']) == 1,
                        'protected activity predictions must name exactly one primary artifact')
        records[row['case_id']] = row
    # Omitted records are preserved by report as missing, never silently removed.
    return records


def validate_scores(plan, submissions, scores):
    cases = validate_plan(plan)
    require(type(scores) is list, 'operator scores list')
    result = {}
    for row in scores:
        exact(row, ('run_id', 'case_id', 'submission_sha256', 'identity', 'status',
                    'value', 'evaluator_record_id'), 'operator score')
        text(row['run_id'], 'score run_id')
        text(row['case_id'], 'score case_id')
        key = (row['run_id'], row['case_id'])
        require(row['run_id'] in expected_runs(plan) and row['case_id'] in cases and key not in result,
                'unknown/duplicate operator score')
        require(row['run_id'] in submissions, 'orphan operator score')
        require(row['submission_sha256'] == digest(submissions[row['run_id']]), 'stale operator score')
        identities(row['identity'])
        text(row['evaluator_record_id'], 'evaluator_record_id')
        require(row['status'] in ('valid', 'undefined', 'failed'), 'operator status')
        if row['status'] == 'valid':
            value = row['value']
            require(type(value) in (int, float) and isfinite(value), 'finite scalar required')
            metric = row['identity']['metric_id']
            require(metric is not None and metric != ARTIFACT, 'numeric metric required')
            if metric in (ACCURACY, CORR, PAIRED_CORR):
                require(0 <= value <= 1, 'fraction/corr squared outside [0,1]')
            if metric == SIGNED:
                require(value <= 1, 'signed VE above 1')
            if metric == VARIANCE:
                # Cross-epoch denominator need not bound this ratio by 1.
                require(value >= 0, 'negative normalized variance')
        else:
            require(row['value'] is None, 'undefined/failed score must be null')
        result[key] = row
    return result


def prediction_pair_issues(plan, records):
    """Join declared prediction operands, without opening or trusting their bytes."""
    issues = {}
    if plan['mode'] != 'protected_improvement':
        return issues
    groups = {}
    for case in plan['cases']:
        if case['obligation'].startswith('movement_'):
            key = tuple(case[k] for k in ('obligation', 'cohort', 'animal', 'session', 'panel_id'))
            groups.setdefault(key, []).append(case['case_id'])
    for ids in groups.values():
        rows = [records.get(i) for i in ids]
        if len(ids) != 2 or any(r is None or r['status'] != 'complete' for r in rows):
            issues.update({i: 'protected_prediction_pair_incomplete' for i in ids})
        else:
            # validate_submission has required exactly one primary descriptor.
            artifacts = [next(a for a in r['artifacts'] if a['kind'] == 'activity_predictions')
                         for r in rows]
            if artifacts[0] != artifacts[1]:
                issues.update({i: 'protected_prediction_artifacts_differ' for i in ids})
    return issues


def report(plan, submissions, scores):
    """Compare declared matched endpoints. Never score candidate-supplied scalars."""
    cases = validate_plan(plan)
    require(type(submissions) is list, 'submissions list')
    by_run, records = {}, {}
    for submission in submissions:
        rows = validate_submission(plan, submission)
        run = submission['run_id']
        require(run not in by_run, 'duplicate run')
        by_run[run], records[run] = submission, rows
    scored = validate_scores(plan, by_run, scores)
    gaps = plan_gaps(plan)
    cells = {}
    for run in expected_runs(plan):
        prediction_issues = prediction_pair_issues(plan, records.get(run, {}))
        for case_id, case in cases.items():
            row = records.get(run, {}).get(case_id)
            cell = {'run_id': run, 'case_id': case_id, 'status': 'missing', 'value': None, 'reasons': [], 'candidate_reason': None}
            if row is not None:
                cell['status'] = row['status']
                cell['candidate_reason'] = row['reason']
                if row['status'] == 'complete':
                    why = ['identity:' + k for k, v in row['identity'].items()
                           if v is None or v != case['identity'][k]]
                    if plan['mode'] == 'protected_improvement':
                        why += [k for k in ('rank_privilege', 'threshold_privilege')
                                if row['identity'][k] != 'train_only']
                        if case_id in prediction_issues:
                            why.append(prediction_issues[case_id])
                        execution = by_run[run]['execution_declaration']
                        if run.endswith('/candidate') and by_run[run]['predictor_intervention_id'] is None:
                            why.append('execution:predictor_intervention_missing')
                        why += ['execution:' + k for k, v in execution.items()
                                if v is None and (k != 'baseline_rerun_id' or run.endswith('/baseline'))]
                        if execution['resource_ceiling_id'] != plan['resource_plan_id']:
                            why.append('execution:resource_ceiling_differs')
                        if execution['target_visibility_id'] != plan['protected_protocol']['prediction_target_separation_id']:
                            why.append('execution:target_visibility_differs')
                        if execution['split_realization_id'] != row['identity']['split_id']:
                            why.append('execution:split_differs')
                        if run.endswith('/baseline') and execution['baseline_rerun_id'] != plan['protected_protocol']['baseline_source_and_rerun_id']:
                            why.append('execution:baseline_rerun_differs')
                    score = scored.get((run, case_id))
                    if case['identity']['metric_id'] == ARTIFACT:
                        cell['status'] = 'artifact_declared'
                    elif score is None:
                        cell['status'] = 'missing_evaluator_record'
                    elif score['status'] != 'valid':
                        cell['status'] = 'evaluator_' + score['status']
                    else:
                        if score['identity'] != row['identity']:
                            why.append('evaluator_identity_differs')
                        cell['status'] = 'declared_numeric'
                        cell['value'] = score['value']
                    if why:
                        cell['status'], cell['value'] = 'noncomparable', None
                        cell['reasons'] = why
            cells[(run, case_id)] = cell
    pairs = ([(arm + '/candidate', arm + '/baseline') for arm in ARMS]
             if plan['mode'] == 'protected_improvement' else
             [('paper_data_code/candidate', 'paper_data/candidate')])
    comparisons = []
    for left, right in pairs:
        for case_id, case in cases.items():
            a, b = cells[(left, case_id)], cells[(right, case_id)]
            reasons = list(gaps)
            if plan['mode'] == 'protected_improvement':
                baselines = [by_run.get(arm + '/baseline') for arm in ARMS]
                if all(baselines) and baselines[0]['procedure_id'] != baselines[1]['procedure_id']:
                    reasons.append('baseline_procedure_differs_between_access_arms')
            if plan['mode'] == 'paper_reproduction':
                reasons.append('final_paper_adjudication_not_implemented')
            if a['status'] != 'declared_numeric' or b['status'] != 'declared_numeric':
                reasons.append('both_numeric_results_required')
            delta = None
            if not reasons:
                delta = a['value'] - b['value']
                if not isfinite(delta):
                    reasons.append('nonfinite_difference')
                    delta = None
            comparisons.append({'case_id': case_id, 'obligation': case['obligation'],
                'family': OBLIGATIONS[case['obligation']][0], 'animal': case['animal'],
                'session': case['session'], 'panel_id': case['panel_id'],
                'metric_id': case['identity']['metric_id'], 'left': left, 'right': right,
                'status': 'declared_comparable' if not reasons else 'incomplete_or_noncomparable',
                'left_minus_right': delta, 'reasons': reasons,
                'meaning': 'descriptive_difference_not_reproduction_or_superiority'})
    counts = {}
    for run in expected_runs(plan):
        counts[run] = {}
        for family in ('subspaces', 'decoding_delay'):
            family_cells = [v for (r, c), v in cells.items() if r == run and
                            OBLIGATIONS[cases[c]['obligation']][0] == family]
            counts[run][family] = {'assigned': len(family_cells),
                                  'statuses': dict(Counter(v['status'] for v in family_cells))}
    return {'schema': 'find025_comparison_v1', 'assignment': ASSIGNMENT,
            'plan_sha256': digest(plan), 'mode': plan['mode'], 'evidence_class': plan['evidence_class'],
            'evidence_authority': 'operator_declarations_not_independent_provenance_proof',
            'plan_gaps': gaps, 'denominators': counts, 'cells': list(cells.values()),
            'access_grants': {arm: dict(grants) for arm, grants in plan['access'].items()},
            'access_used_by_run': {run: dict(s['access_used']) for run, s in by_run.items()},
            'baseline_access_is_evaluator_only': True,
            'comparisons': comparisons, 'paper_pass': None, 'scientifically_qualified': False,
            'execution_ready': False, 'aggregate_score': None,
            'scope_limit': 'complete relative to declared assignment matrix only; authentic full scope unverified'}


def pending_plan(mode='code_reconstruction'):
    """Real pending template: no invented cohorts, folds, targets or tolerances."""
    return {'schema': 'find025_plan_v1', 'assignment': ASSIGNMENT, 'mode': mode,
        'evidence_class': 'operator_declared',
        'source': {'git_commit': GIT, 'archive_sha256': ARCHIVE, 'paper_doi': DOI},
        'joins': {j: {'status': 'unresolved', 'evidence_id': None} for j in JOINS},
        'scope_matrix': {o: [] for o in OBLIGATIONS}, 'cases': [],
        'access': {a: {k: k == 'official_code' and a == 'paper_data_code' for k in PRIVILEGES}
                   for a in ARMS},
        'protected_protocol': {k: None for k in PROTECTED_FIELDS}, 'resource_plan_id': None}
