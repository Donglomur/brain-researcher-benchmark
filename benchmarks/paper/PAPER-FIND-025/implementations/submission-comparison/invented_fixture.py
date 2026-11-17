"""Tiny invented interface fixtures. No real mouse/session/trial/fold identities."""
from copy import deepcopy
import find025_contract as c


def fixture(mode='code_reconstruction'):
    plan = c.pending_plan(mode)
    plan['evidence_class'] = 'invented'
    plan['joins'] = {j: {'status': 'operator_resolved', 'evidence_id': 'INVENTED:' + j}
                     for j in c.JOINS}
    plan['resource_plan_id'] = 'INVENTED:equal_resource_ceilings'
    plan['protected_protocol'] = {k: 'INVENTED:' + k for k in c.PROTECTED_FIELDS}
    for name, (_, metrics, _) in c.OBLIGATIONS.items():
        selected = ((c.SIGNED, c.PAIRED_CORR) if mode == 'protected_improvement' else (c.CORR,)) if name.startswith('movement_') else (metrics[0],)
        for ordinal, metric in enumerate(selected):
            identity = {k: 'INVENTED:r' for k in c.IDENTITY_FIELDS}
            identity.update(metric_id=metric, metric_unit=c.UNITS[metric], bin_seconds=0.01,
                            rank_privilege='train_only', threshold_privilege='train_only',
                            split_id='INVENTED:split_id')
            case_id = name + ':' + str(ordinal)
            plan['cases'].append({'case_id': case_id, 'obligation': name,
                'cohort': 'randomized_delay' if name.startswith('randomized') else
                          ('two_context_dr_wc' if 'context' in name or 'dr_wc' in name else 'fixed_dr'),
                'animal': 'INVENTED_MOUSE', 'session': 'INVENTED_SESSION',
                'panel_id': 'INVENTED:' + name, 'identity': identity})
            plan['scope_matrix'][name].append(case_id)
    submissions = []
    for run in c.expected_runs(plan):
        execution = {k: 'INVENTED:' + k for k in c.EXECUTION_FIELDS}
        execution.update(resource_ceiling_id=plan['resource_plan_id'],
            target_visibility_id=plan['protected_protocol']['prediction_target_separation_id'],
            split_realization_id='INVENTED:split_id',
            baseline_rerun_id=plan['protected_protocol']['baseline_source_and_rerun_id'])
        submissions.append({'schema': 'find025_submission_v1', 'plan_sha256': c.digest(plan),
            'run_id': run, 'procedure_id': 'INVENTED:' + run.split('/')[1],
            'access_used': dict(plan['access'][run.split('/')[0]]),
            'predictor_intervention_id': 'INVENTED:declared_method',
            'execution_declaration': execution,
            'records': [{'case_id': row['case_id'], 'status': 'complete', 'reason': None,
                'identity': deepcopy(row['identity']), 'artifacts': [{
                    'kind': c.OBLIGATIONS[row['obligation']][2], 'logical_id': 'INVENTED:artifact',
                    'sha256': '0' * 64}]} for row in plan['cases']]})
    return plan, submissions, score_records(plan, submissions)


def score_records(plan, submissions):
    scores = []
    for s in submissions:
        for row in s['records']:
            metric = row['identity']['metric_id']
            if metric == c.ARTIFACT or row['status'] != 'complete':
                continue
            scores.append({'run_id': s['run_id'], 'case_id': row['case_id'],
                'submission_sha256': c.digest(s), 'identity': deepcopy(row['identity']),
                'status': 'valid', 'value': 0.4 if s['run_id'].endswith('/baseline') else 0.5,
                'evaluator_record_id': 'INVENTED:evaluator-record'})
    return scores


def rebind(plan, submissions):
    for s in submissions:
        s['plan_sha256'] = c.digest(plan)
    return score_records(plan, submissions)
