"""Reduce all 93 MotorMINT author assessments to the selected Figure 5 profile.

This operator-side projection is not a scorer, authenticity gate, reproduction
decision or candidate win rule. It consumes existing independent assessments.
Missing/failed runs remain visible and cannot make a competing method disappear.
"""
from copy import deepcopy
import hashlib
import json
import math
import re


# Source-derived metadata, pinned in SOURCE.json. No result values occur here.
GROUPS = {
    'Area2_Bump': (('position', 2), ('velocity', 2), ('force_torque', 6),
                   ('joint_angles', 7), ('joint_velocities', 7),
                   ('muscle_lengths', 39), ('muscle_velocities', 39)),
    'MC_Cycle': (('phase', 1), ('angular_velocity', 1), ('position', 2),
                 ('velocity', 2), ('EMG', 7)),
    'MC_Maze': (('position', 2), ('velocity', 2)),
    'MC_RTT': (('velocity', 2),),
}
METHODS = (('MINT', 1), ('Wiener_filter', 1), ('Kalman_filter', 1),
           ('feedforward', 10), ('GRU', 10))
SHA = re.compile(r'[0-9a-f]{64}\Z')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=False, allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def sha(value):
    require(type(value) is str and SHA.fullmatch(value), 'SHA256 commitment')
    return value


def mean(values):
    # Dividing first avoids overflow in a sum of individually finite values.
    require(bool(values), 'nonempty mean')
    result = math.fsum(value / len(values) for value in values)
    require(math.isfinite(result), 'finite mean')
    return result


def roster():
    """Original 93 method/run bundles, not 93 tasks or independent animals."""
    answer = []
    for dataset in GROUPS:
        methods = METHODS + ((('Naive_Bayes_regression', 1),)
                             if dataset == 'MC_Maze' else ())
        for method, count in methods:
            eligible = [(name, width) for name, width in GROUPS[dataset]
                        if method != 'Kalman_filter' or name in ('position', 'velocity')]
            dimensions = [f'{name}:{j}' for name, width in eligible for j in range(width)]
            for repeat in range(count):
                answer.append({'slot': f'{dataset}:{method}:{repeat}',
                               'dataset': dataset, 'method': method, 'repeat': repeat,
                               'dimensions': dimensions.copy(),
                               'groups': [name for name, _ in eligible]})
    return answer


def _case_map(cases, *, candidate=False):
    slots = [row for row in roster() if not candidate or row['method'] == 'MINT']
    require(type(cases) is list and len(cases) == len(slots),
            'complete 4 candidate cases' if candidate else 'complete 93 original cases')
    expected = {row['slot']: row for row in slots}
    by_slot, ids = {}, set()
    for case in cases:
        require(type(case) is dict, 'case object')
        ident = case.get('id')
        require(type(ident) is str and ident and len(ident) <= 160 and ident not in ids,
                'unique bounded case ID')
        ids.add(ident)
        require(case.get('module') == 'primary_behavior' and
                case.get('mode') == 'behavior_causal' and
                case.get('purpose') == ('improve' if candidate else 'reproduce'),
                'original causal candidate cases' if candidate else 'original causal reproduction cases')
        outputs = case.get('outputs')
        require(type(outputs) is list and len(outputs) == 1 and
                type(outputs[0]) is str and outputs[0] in expected and
                outputs[0] not in by_slot, 'one unique original slot')
        target = expected[outputs[0]]
        require(type(case.get('repeat')) is int and
                all(case.get(key) == target[key] for key in ('dataset', 'method', 'repeat')),
                'original method/dataset/run identity')
        require(case.get('output_dimensions') == target['dimensions'],
                'complete original method-eligible dimensions')
        identities = case.get('output_identities')
        require(type(identities) is list and len(identities) == 1, 'one output identity')
        identity = identities[0]
        require(type(identity) is dict and identity.get('key') == target['slot'] and
                identity.get('estimand') == 'behavior_R2' and identity.get('kind') == 'behavior' and
                identity.get('selector') == [] and identity.get('dimensions') == target['dimensions'],
                'original full behavioral R2 identity')
        sha(identity.get('source_support_sha256'))
        for key in ('input_index_sha256', 'metric_recipe_sha256', 'source_recipe_sha256',
                    'reference_source_sha256', 'config_sha256'):
            sha(case.get(key))
        by_slot[target['slot']] = case
    require(set(by_slot) == set(expected), 'all original method/run slots')
    return by_slot


def _assessments(rows, case_ids):
    require(type(rows) is list and len(rows) <= 93, 'bounded assessment list')
    answer = {}
    for row in rows:
        require(type(row) is dict and row.get('case') in case_ids and
                row['case'] not in answer and row.get('module') == 'primary_behavior',
                'unique known primary assessment')
        answer[row['case']] = row
    return answer


def _run_value(case, slot, assessment, sample_support, *, value_role='reference'):
    result = {key: deepcopy(slot[key]) for key in ('slot', 'dataset', 'method', 'repeat', 'dimensions')}
    result.update(case_id=case['id'], sample_support_sha256=sample_support,
                  source_support_sha256=case['output_identities'][0]['source_support_sha256'],
                  commitments={key: case[key] for key in ('input_index_sha256',
                    'metric_recipe_sha256', 'source_recipe_sha256', 'reference_source_sha256',
                    'config_sha256')}, assessment_commitments=None,
                  per_dimension_r2=None, groups=None)
    if assessment is None:
        result.update(status='missing_assessment', reason='No assessment supplied for this required run.')
        return result
    outputs = assessment.get('outputs')
    require(type(outputs) is list and len(outputs) == 1 and type(outputs[0]) is dict and
            outputs[0].get('key') == slot['slot'], 'exact assessed output identity')
    out = outputs[0]
    result['assessment_commitments'] = deepcopy(out.get('commitments'))
    status = out.get('status')
    require(type(status) is str and 0 < len(status) <= 160, 'explicit assessment status')
    if status != 'numerically_assessed':
        reason = out.get('reason', 'Required run was not numerically assessed.')
        require(type(reason) is str and len(reason) <= 16384, 'bounded failure reason')
        result.update(status=status, reason=reason)
        return result
    require(out.get('kind') == 'behavior' and out.get('bank_agreement') is True,
            'existing independent behavioral assessment agreement')
    commitments = out.get('commitments')
    require(type(commitments) is dict and
            set(commitments) == {'input_index', 'recipe', 'source_recipe', 'artifacts'},
            'numeric assessment requires existing scorer commitments')
    for recorded, expected in (('input_index', 'input_index_sha256'),
                               ('recipe', 'metric_recipe_sha256'),
                               ('source_recipe', 'source_recipe_sha256')):
        sha(commitments[recorded])
        require(commitments[recorded] == case[expected],
                'numeric assessment commitment must match current case: ' + recorded)
    recorded = out.get(value_role)
    require(type(recorded) is dict and set(recorded) == {'per_dimension_r2', 'groups'},
            'original ' + value_role + ' assessment shape')
    values = recorded['per_dimension_r2']
    require(type(values) is list and len(values) == len(slot['dimensions']) and
            all(type(value) in (int, float) and math.isfinite(value) and value <= 1 for value in values),
            'complete finite per-dimension R2 values, not booleans')
    reduced = {name: mean([value for dimension, value in zip(slot['dimensions'], values)
                           if dimension.rsplit(':', 1)[0] == name]) for name in slot['groups']}
    supplied_groups = recorded['groups']
    require(type(supplied_groups) is dict and set(supplied_groups) == set(reduced),
            'complete original group names')
    for name, value in reduced.items():
        observed = supplied_groups[name]
        require(type(observed) in (int, float) and math.isfinite(observed) and
                math.isclose(observed, value, rel_tol=1e-12, abs_tol=1e-12),
                'reported group must agree with per-dimension arithmetic')
    result.update(status='numerically_assessed', reason=None,
                  per_dimension_r2=values.copy(), groups=reduced)
    return result


def build_reference_profile(cases, assessments, support_by_case):
    """Operator inputs: 93 original cases, saved assessments, frozen sample pins.

    support_by_case maps every case ID to the SHA256 of an operator-held ordered
    sample-manifest containing sample/trial IDs and 5-ms evaluation masks, WITHOUT
    behavior columns. All methods/runs of a dataset must name the same manifest.
    This function checks equality only: authentication, chronology and original
    support completeness remain outside this component.
    """
    case_map = _case_map(cases)
    case_ids = {case['id'] for case in case_map.values()}
    require(type(support_by_case) is dict and set(support_by_case) == case_ids,
            'frozen sample support for all 93 cases')
    by_id = _assessments(assessments, case_ids)
    dataset_support = {}
    for case in case_map.values():
        value = sha(support_by_case[case['id']])
        previous = dataset_support.setdefault(case['dataset'], value)
        require(previous == value, 'identical sample support across original method runs')
    runs = [_run_value(case_map[slot['slot']], slot,
                       by_id.get(case_map[slot['slot']]['id']),
                       support_by_case[case_map[slot['slot']]['id']]) for slot in roster()]
    profile, datasets = [], []
    for dataset, definitions in GROUPS.items():
        method_profiles = {}
        for method, _ in METHODS + ((('Naive_Bayes_regression', 1),) if dataset == 'MC_Maze' else ()):
            required = [run for run in runs if run['dataset'] == dataset and run['method'] == method]
            complete = all(run['status'] == 'numerically_assessed' for run in required)
            groups = [name for name, _ in definitions
                      if method != 'Kalman_filter' or name in ('position', 'velocity')]
            values = {name: mean([run['groups'][name] for run in required]) if complete else None
                      for name in groups}
            method_profiles[method] = {'required_run_slots': [run['slot'] for run in required],
                'incomplete_run_slots': [run['slot'] for run in required if run['status'] != 'numerically_assessed'],
                'complete': complete, 'group_r2': values,
                'dataset_r2': mean(list(values.values())) if complete else None,
                'dataset_group_support': groups}
        for name, width in definitions:
            eligible = {method: item['group_r2'][name] for method, item in method_profiles.items()
                        if name in item['group_r2']}
            complete = all(value is not None for value in eligible.values())
            strongest = max(eligible.values()) if complete else None
            profile.append({'dataset': dataset, 'group': name, 'dimension_count': width,
                'method_r2': eligible, 'all_eligible_methods_complete': complete,
                'strongest_original_reference_r2': strongest,
                'strongest_original_reference_methods': [method for method, value in eligible.items()
                    if complete and value == strongest],
                'difference_from_MINT': {method: (None if value is None or eligible['MINT'] is None
                    else value - eligible['MINT']) for method, value in eligible.items()}})
        datasets.append({'dataset': dataset, 'sample_manifest_sha256': dataset_support[dataset],
                         'methods': method_profiles})
    return {'schema': 'motormint-primary-reference-profile/v1', 'task_id': 'PAPER-paper-method-011',
            'input_commitments': {'cases_sha256': digest(cases), 'assessments_sha256': digest(assessments),
                                  'support_by_case_sha256': digest(support_by_case)},
            'required_run_count': 93, 'required_group_count': 15, 'runs': runs,
            'groups': profile, 'datasets': datasets,
            'numerical_profile_complete': all(row['status'] == 'numerically_assessed' for row in runs),
            'reference_role': 'operator_supplied_author_reference_assessments_not_authenticated_here',
            'reproduction': 'unknown', 'improvement': 'unknown', 'paper_win': None,
            'global_scalar': None, 'current_sota': 'not_assessed', 'scientific_qualification': False}


def compare_candidate_profile(reference_cases, reference_assessments, reference_support,
                              candidate_cases, candidate_assessments, candidate_support,
                              *, candidate_program_sha256, reference_metric_recipes,
                              candidate_metric_recipes):
    """Pair one declared candidate's four assessments with all 93 author runs.

    The four candidate cases use the runtime's existing MINT reference slots and
    purpose='improve'. Their candidate fields supply the proposed decoder values;
    their method tags identify the reference schedule, not the candidate model.
    All inputs are operator-side. A declared program pin and equal support hashes
    are consistency checks, not execution provenance or source authentication.
    """
    sha(candidate_program_sha256)
    reference = build_reference_profile(reference_cases, reference_assessments,
                                        reference_support)
    cases = _case_map(candidate_cases, candidate=True)
    case_ids = {case['id'] for case in cases.values()}
    require(type(candidate_support) is dict and set(candidate_support) == case_ids,
            'frozen sample support for all 4 candidate cases')
    assessments = _assessments(candidate_assessments, case_ids)
    reference_runs = {run['slot']: run for run in reference['runs']}
    original_cases = {case['outputs'][0]: case for case in reference_cases}
    mint_ids = {case['id'] for case in reference_cases if case['method'] == 'MINT'}
    require(type(reference_metric_recipes) is dict and set(reference_metric_recipes) == mint_ids,
            'four original MINT metric recipes')
    require(type(candidate_metric_recipes) is dict and set(candidate_metric_recipes) == case_ids,
            'four candidate metric recipes')
    candidate_runs = []
    for slot in (row for row in roster() if row['method'] == 'MINT'):
        case = cases[slot['slot']]
        anchor = reference_runs[slot['slot']]
        support = sha(candidate_support[case['id']])
        require(support == anchor['sample_support_sha256'],
                'candidate and reference must share ordered sample/mask support')
        require(case['output_identities'][0]['source_support_sha256'] ==
                anchor['source_support_sha256'], 'candidate and reference source support')
        # Case-specific decoder configurations may differ, but observed inputs,
        # targets, scoring semantics and original reference cannot be switched.
        for key in ('input_index_sha256', 'source_recipe_sha256', 'reference_source_sha256'):
            require(case[key] == anchor['commitments'][key],
                    'candidate and reference pairing commitment: ' + key)
        original_case = original_cases[slot['slot']]
        original_recipe = reference_metric_recipes[original_case['id']]
        candidate_recipe = candidate_metric_recipes[case['id']]
        scoring_semantics = []
        for bound_case, recipe in ((original_case, original_recipe), (case, candidate_recipe)):
            require(type(recipe) is dict and set(recipe) == {'module', 'outputs',
                    'policy_evidence_sha256', 'experiment_sha256', 'uncertainty_requirements'},
                    'existing complete metric recipe')
            require(digest(recipe) == bound_case['metric_recipe_sha256'],
                    'metric recipe must match its own frozen case')
            require(type(bound_case.get('factors')) is dict and
                    recipe['module'] == bound_case['module'] and
                    recipe['experiment_sha256'] == digest({key: bound_case[key] for key in
                        ('module', 'dataset', 'method', 'repeat', 'factors', 'output_dimensions')}),
                    'metric recipe must match the actual experiment')
            requirements = bound_case.get('uncertainty_requirements')
            require(type(requirements) is list and
                    recipe['uncertainty_requirements'] == requirements,
                    'uncertainty requirements must match their own case')
            for requirement in requirements:
                require(type(requirement) is dict and set(requirement) ==
                        {'id', 'target', 'kind', 'policy_sha256'} and
                        type(requirement['id']) is str and requirement['id'] and
                        requirement['target'] in bound_case['outputs'] and
                        requirement['kind'] in ('historical_absolute_trial_bootstrap',
                                                 'prospective_paired_gain'),
                        'existing uncertainty requirement identity')
                sha(requirement['policy_sha256'])
            scoring_semantics.append({key: value for key, value in recipe.items()
                                      if key != 'uncertainty_requirements'})
        require(any(item['kind'] == 'prospective_paired_gain' and
                    item['target'] == slot['slot'] for item in case['uncertainty_requirements']),
                'candidate requires its prospective paired uncertainty policy')
        require(digest(scoring_semantics[0]) == digest(scoring_semantics[1]),
                'candidate and reference must have identical scoring semantics')
        run = _run_value(case, slot, assessments.get(case['id']), support,
                         value_role='candidate')
        paired = _run_value(case, slot, assessments.get(case['id']), support)
        if run['status'] == 'numerically_assessed' and anchor['status'] == 'numerically_assessed':
            require(paired['per_dimension_r2'] == anchor['per_dimension_r2'],
                    'paired MINT values must match the original reference panel')
        run['paired_reference'] = {'status': paired['status'],
            'per_dimension_r2': paired['per_dimension_r2'], 'groups': paired['groups']}
        run['uncertainty_requirements'] = deepcopy(case['uncertainty_requirements'])
        run['reference_uncertainty_requirements'] = deepcopy(original_case['uncertainty_requirements'])
        run['scoring_semantics_sha256'] = digest(scoring_semantics[0])
        run['method_role'] = 'original_reference_slot_not_candidate_method'
        candidate_runs.append(run)
    by_dataset = {run['dataset']: run for run in candidate_runs}
    groups, datasets = [], []
    for original in reference['groups']:
        run = by_dataset[original['dataset']]
        name = original['group']
        value = run['groups'][name] if run['groups'] is not None else None
        mint = original['method_r2']['MINT']
        strongest = original['strongest_original_reference_r2']
        groups.append(dict(deepcopy(original), candidate_r2=value,
            candidate_status=run['status'],
            candidate_minus_MINT=(value - mint if value is not None and mint is not None else None),
            candidate_minus_strongest_original=(value - strongest
                if value is not None and strongest is not None else None),
            candidate_minus_method={method: (value - score
                if value is not None and score is not None else None)
                for method, score in original['method_r2'].items()}))
    for dataset, definitions in GROUPS.items():
        run = by_dataset[dataset]
        names = [name for name, _ in definitions]
        datasets.append({'dataset': dataset, 'groups': names,
            'sample_manifest_sha256': run['sample_support_sha256'],
            'candidate_r2': (mean([run['groups'][name] for name in names])
                             if run['groups'] is not None else None),
            'cross_method_winner': None})
    return {'schema': 'motormint-primary-candidate-comparison/v1',
        'task_id': 'PAPER-paper-method-011',
        'candidate_program_sha256': candidate_program_sha256,
        'candidate_identity_role': 'operator_declared_not_authenticated_here',
        'input_commitments': {'reference_profile_sha256': digest(reference),
            'candidate_cases_sha256': digest(candidate_cases),
            'candidate_assessments_sha256': digest(candidate_assessments),
            'candidate_support_sha256': digest(candidate_support),
            'reference_metric_recipes_sha256': digest(reference_metric_recipes),
            'candidate_metric_recipes_sha256': digest(candidate_metric_recipes)},
        'reference_profile': reference, 'candidate_runs': candidate_runs,
        'groups': groups, 'datasets': datasets,
        'numerical_comparison_complete': reference['numerical_profile_complete'] and
            all(run['status'] == 'numerically_assessed' for run in candidate_runs),
        'reproduction': 'unknown', 'improvement': 'unknown', 'paper_win': None,
        'global_scalar': None, 'current_sota': 'not_assessed',
        'scientific_qualification': False}
